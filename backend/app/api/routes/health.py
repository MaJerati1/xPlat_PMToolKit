"""Health check and diagnostics endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.config import settings
from app.core.database import get_db

router = APIRouter()


@router.get("/health")
async def health_check():
    """Application health check."""
    return {"status": "healthy", "service": "meeting-toolkit-api", "version": "0.1.0"}


@router.get("/health/diagnostics")
async def diagnostics(db: AsyncSession = Depends(get_db)):
    """Full system diagnostics — checks API keys, database, Redis, and LLM providers.

    Use this to verify your .env configuration is working correctly.
    API key values are never exposed — only validation status is shown.
    """
    results = {
        "status": "ok",
        "database": await _check_database(db),
        "redis": await _check_redis(),
        "llm_providers": _check_llm_keys(),
        "google_oauth": _check_google_oauth(),
        "configuration": {
            "app_env": settings.APP_ENV,
            "llm_default_tier": settings.LLM_DEFAULT_TIER,
            "llm_primary_model": settings.LLM_PRIMARY_MODEL,
            "llm_budget_model": settings.LLM_BUDGET_MODEL,
            "llm_selfhosted_model": settings.LLM_SELFHOSTED_MODEL,
            "frontend_url": settings.FRONTEND_URL,
        },
    }

    issues = []
    if results["database"]["status"] != "connected":
        issues.append("database")
    if not results["llm_providers"]["any_provider_available"]:
        issues.append("no LLM provider")

    if issues:
        results["status"] = f"degraded ({', '.join(issues)})"

    return results


@router.get("/health/check-keys")
async def check_api_keys():
    """Test LLM API keys by making a minimal call to each provider.

    Actually calls each configured API to verify the key works.
    Uses the smallest possible request to minimize cost.
    """
    results = {}

    # Check Anthropic
    anthropic_key = settings.ANTHROPIC_API_KEY
    has_real_anthropic = (
        anthropic_key
        and anthropic_key.startswith("sk-ant-")
        and "your-key" not in anthropic_key
        and len(anthropic_key) > 20
    )

    if has_real_anthropic:
        results["anthropic"] = await _test_anthropic_key(anthropic_key)
    else:
        results["anthropic"] = {
            "status": "not_configured",
            "reason": _describe_key_issue(anthropic_key, "sk-ant-"),
        }

    # Check OpenAI
    openai_key = settings.OPENAI_API_KEY
    has_real_openai = (
        openai_key
        and openai_key.startswith("sk-")
        and "your-key" not in openai_key
        and len(openai_key) > 20
    )

    if has_real_openai:
        results["openai"] = await _test_openai_key(openai_key)
    else:
        results["openai"] = {
            "status": "not_configured",
            "reason": _describe_key_issue(openai_key, "sk-"),
        }

    # Check Ollama
    results["ollama"] = await _test_ollama()

    # Summary
    active = [k for k, v in results.items() if v.get("status") == "valid"]
    results["summary"] = {
        "active_providers": active,
        "fallback": "MockProvider (heuristic analysis)" if not active else None,
    }

    return results


# ============================================
# INTERNAL CHECK FUNCTIONS
# ============================================

async def _check_database(db: AsyncSession) -> dict:
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        return {"status": "connected", "url": _mask_url(settings.DATABASE_URL)}
    except Exception as e:
        return {"status": "error", "error": str(e), "url": _mask_url(settings.DATABASE_URL)}


async def _check_redis() -> dict:
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.ping()
        await r.aclose()
        return {"status": "connected", "url": settings.REDIS_URL}
    except ImportError:
        return {"status": "skipped", "reason": "redis package not installed"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _check_llm_keys() -> dict:
    anthropic_key = settings.ANTHROPIC_API_KEY
    openai_key = settings.OPENAI_API_KEY

    has_real_anthropic = (
        anthropic_key
        and anthropic_key.startswith("sk-ant-")
        and "your-key" not in anthropic_key
        and len(anthropic_key) > 20
    )
    has_real_openai = (
        openai_key
        and openai_key.startswith("sk-")
        and "your-key" not in openai_key
        and len(openai_key) > 20
    )

    return {
        "anthropic": {
            "configured": has_real_anthropic,
            "key_preview": f"{anthropic_key[:12]}...{anthropic_key[-4:]}" if has_real_anthropic else None,
            "model": settings.LLM_PRIMARY_MODEL,
            "issue": None if has_real_anthropic else _describe_key_issue(anthropic_key, "sk-ant-"),
        },
        "openai": {
            "configured": has_real_openai,
            "key_preview": f"{openai_key[:8]}...{openai_key[-4:]}" if has_real_openai else None,
            "model": settings.LLM_BUDGET_MODEL,
            "issue": None if has_real_openai else _describe_key_issue(openai_key, "sk-"),
        },
        "ollama": {
            "configured": True,
            "base_url": settings.OLLAMA_BASE_URL,
            "model": settings.LLM_SELFHOSTED_MODEL,
        },
        "any_provider_available": has_real_anthropic or has_real_openai,
        "active_tier1": "anthropic" if has_real_anthropic else ("openai" if has_real_openai else "mock"),
    }


def _check_google_oauth() -> dict:
    has_client_id = bool(settings.GOOGLE_CLIENT_ID) and "your-google" not in settings.GOOGLE_CLIENT_ID
    has_client_secret = bool(settings.GOOGLE_CLIENT_SECRET) and "your-google" not in settings.GOOGLE_CLIENT_SECRET
    return {
        "configured": has_client_id and has_client_secret,
        "client_id_set": has_client_id,
        "client_secret_set": has_client_secret,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
    }


async def _test_anthropic_key(api_key: str) -> dict:
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "content-type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": settings.LLM_PRIMARY_MODEL,
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "Say OK"}],
                },
                timeout=15.0,
            )
        data = response.json()
        if response.status_code == 200:
            return {"status": "valid", "model": settings.LLM_PRIMARY_MODEL}
        else:
            error = data.get("error", {})
            return {
                "status": "invalid",
                "http_code": response.status_code,
                "error_type": error.get("type", "unknown"),
                "error_message": error.get("message", str(data)),
            }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _test_openai_key(api_key: str) -> dict:
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.LLM_BUDGET_MODEL,
                    "max_completion_tokens": 10,
                    "messages": [{"role": "user", "content": "Say OK"}],
                },
                timeout=15.0,
            )
        data = response.json()
        if response.status_code == 200:
            return {"status": "valid", "model": settings.LLM_BUDGET_MODEL}
        else:
            error = data.get("error", {})
            return {
                "status": "invalid",
                "http_code": response.status_code,
                "error_type": error.get("type", "unknown"),
                "error_message": error.get("message", str(data)),
            }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _test_ollama() -> dict:
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.OLLAMA_BASE_URL}/api/tags",
                timeout=5.0,
            )
        if response.status_code == 200:
            models = [m["name"] for m in response.json().get("models", [])]
            return {"status": "connected", "available_models": models}
        else:
            return {"status": "error", "http_code": response.status_code}
    except Exception as e:
        return {"status": "unreachable", "error": str(e)}


def _describe_key_issue(key: str, expected_prefix: str) -> str:
    if not key:
        return "No key set (empty)"
    if "your-key" in key or "your-" in key.lower():
        return f"Placeholder value detected: '{key[:20]}...'"
    if not key.startswith(expected_prefix):
        return f"Invalid prefix: expected '{expected_prefix}', got '{key[:10]}...'"
    if len(key) <= 20:
        return f"Key too short ({len(key)} chars)"
    return "Unknown issue"


def _mask_url(url: str) -> str:
    import re
    return re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', url)


@router.get("/health/ollama-models")
async def list_ollama_models():
    """Detect installed models on the connected Ollama server.

    Calls the Ollama /api/tags endpoint to list all available models.
    Returns model names and sizes for the frontend model selector.
    """
    import httpx

    base_url = settings.OLLAMA_BASE_URL
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{base_url}/api/tags", timeout=10.0)

        if resp.status_code != 200:
            return {"connected": False, "models": [], "error": f"HTTP {resp.status_code}"}

        data = resp.json()
        models = []
        for m in data.get("models", []):
            models.append({
                "name": m.get("name", ""),
                "model": m.get("model", m.get("name", "")),
                "size": m.get("size", 0),
                "size_gb": round(m.get("size", 0) / 1e9, 1) if m.get("size") else None,
                "modified_at": m.get("modified_at", ""),
                "family": m.get("details", {}).get("family", ""),
                "parameter_size": m.get("details", {}).get("parameter_size", ""),
            })

        return {
            "connected": True,
            "base_url": base_url,
            "models": models,
            "total": len(models),
        }
    except Exception as e:
        return {
            "connected": False,
            "base_url": base_url,
            "models": [],
            "error": str(e),
        }
