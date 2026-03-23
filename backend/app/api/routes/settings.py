"""Settings API — secure configuration management from the UI.

Allows users to configure API keys and service URLs through the
Getting Started page instead of manually editing .env files.

Secured with a SETUP_TOKEN that must be provided in the request.
The token defaults to the APP_SECRET_KEY if not explicitly set.
"""

import os
import re
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Default placeholder values that indicate unconfigured state
DEFAULT_PLACEHOLDERS = {"change-me", "ma-je-ra-ti", ""}
ENV_FILE_PATH = os.environ.get("ENV_FILE_PATH", ".env")

# Keys that can be configured through this API
ALLOWED_KEYS = {
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "OLLAMA_BASE_URL",
    "SETUP_TOKEN",
    "APP_SECRET_KEY",
    "LLM_PRIMARY_MODEL",
    "LLM_BUDGET_MODEL",
}


def _is_first_run() -> bool:
    """Detect if this is a first-run (no real token configured yet)."""
    setup_token = settings.SETUP_TOKEN
    secret_key = settings.APP_SECRET_KEY
    # First run if both are empty/placeholder values
    return (not setup_token or setup_token in DEFAULT_PLACEHOLDERS) and \
           (not secret_key or secret_key in DEFAULT_PLACEHOLDERS)


def _get_effective_token() -> str:
    """Get the token that should be used for auth."""
    if settings.SETUP_TOKEN and settings.SETUP_TOKEN not in DEFAULT_PLACEHOLDERS:
        return settings.SETUP_TOKEN
    if settings.APP_SECRET_KEY and settings.APP_SECRET_KEY not in DEFAULT_PLACEHOLDERS:
        return settings.APP_SECRET_KEY
    return ""


# ============================================
# SCHEMAS
# ============================================

class SetupStatus(BaseModel):
    """Whether the app needs first-time setup."""
    first_run: bool
    token_configured: bool
    message: str


class SettingsStatus(BaseModel):
    """Current configuration status (no secrets exposed)."""
    anthropic: dict = {}
    openai: dict = {}
    google_oauth: dict = {}
    ollama: dict = {}
    setup_required: bool = True


class SettingsUpdate(BaseModel):
    """Key-value pairs to update in the .env file."""
    ANTHROPIC_API_KEY: Optional[str] = Field(None, description="Anthropic API key (starts with sk-ant-)")
    OPENAI_API_KEY: Optional[str] = Field(None, description="OpenAI API key (starts with sk-)")
    GOOGLE_CLIENT_ID: Optional[str] = Field(None, description="Google OAuth Client ID")
    GOOGLE_CLIENT_SECRET: Optional[str] = Field(None, description="Google OAuth Client Secret")
    OLLAMA_BASE_URL: Optional[str] = Field(None, description="Ollama server URL (e.g. http://localhost:11434)")
    SETUP_TOKEN: Optional[str] = Field(None, description="Setup token for securing the settings API")
    APP_SECRET_KEY: Optional[str] = Field(None, description="Application secret key")
    LLM_PRIMARY_MODEL: Optional[str] = Field(None, description="Primary LLM model (Anthropic)")
    LLM_BUDGET_MODEL: Optional[str] = Field(None, description="Budget LLM model (OpenAI)")


class SettingsUpdateResponse(BaseModel):
    """Result of a settings update."""
    updated: list[str] = []
    warnings: list[str] = []
    message: str = ""
    generated_token: Optional[str] = Field(None, description="Auto-generated setup token (only shown once on first run)")


class KeyTestResult(BaseModel):
    """Result of testing a single key."""
    key: str
    status: str
    detail: Optional[str] = None


# ============================================
# AUTH HELPER
# ============================================

def _verify_token(authorization: Optional[str]) -> None:
    """Verify the setup token from the Authorization header.

    On first run (no token configured), access is allowed without auth
    so the user can complete initial setup.
    """
    if _is_first_run():
        # First run — allow access without token
        return

    effective_token = _get_effective_token()
    if not effective_token:
        raise HTTPException(status_code=500, detail="No setup token configured. Set SETUP_TOKEN or APP_SECRET_KEY in .env")

    if not authorization:
        raise HTTPException(status_code=401, detail="Setup token required. Send as: Authorization: Bearer <token>")

    token = authorization.replace("Bearer ", "").strip()
    if token != effective_token:
        raise HTTPException(status_code=403, detail="Invalid setup token")


# ============================================
# ENDPOINTS
# ============================================

@router.get("/settings/setup-status", response_model=SetupStatus)
async def get_setup_status():
    """Check if the application needs first-time setup.

    This endpoint is PUBLIC (no token required) so the Getting Started
    page can determine whether to show the token gate or the welcome flow.
    """
    first_run = _is_first_run()
    token_configured = not first_run

    if first_run:
        message = "Welcome! No setup token is configured. You can proceed with initial setup without a token."
    else:
        message = "Setup token is configured. Enter your token to access settings."

    return SetupStatus(
        first_run=first_run,
        token_configured=token_configured,
        message=message,
    )


@router.get("/settings/debug-env")
async def debug_env_path():
    """Debug endpoint to check .env file accessibility. No auth required."""
    path = ENV_FILE_PATH
    exists = os.path.exists(path)
    is_file = os.path.isfile(path) if exists else False
    is_dir = os.path.isdir(path) if exists else False
    readable = os.access(path, os.R_OK) if exists else False
    writable = os.access(path, os.W_OK) if exists else False

    # Try a test write
    test_write = None
    if exists and is_file:
        try:
            content = open(path, 'r').read()
            test_write = f"readable ({len(content)} bytes)"
        except Exception as e:
            test_write = f"read error: {e}"
    elif not exists:
        try:
            with open(path, 'w') as f:
                f.write("# Meeting Toolkit .env\n")
            test_write = "created successfully"
        except Exception as e:
            test_write = f"create error: {e}"

    return {
        "env_file_path": path,
        "exists": exists,
        "is_file": is_file,
        "is_dir": is_dir,
        "readable": readable,
        "writable": writable,
        "test_result": test_write,
        "cwd": os.getcwd(),
        "parent_contents": os.listdir(os.path.dirname(path) or '.') if os.path.exists(os.path.dirname(path) or '.') else "parent not found",
    }


@router.get("/settings/status", response_model=SettingsStatus)
async def get_settings_status(authorization: Optional[str] = Header(None)):
    """Get current configuration status.

    Shows which services are configured (without exposing secrets).
    Requires setup token for access (skipped on first run).
    """
    _verify_token(authorization)

    anthropic_key = settings.ANTHROPIC_API_KEY
    openai_key = settings.OPENAI_API_KEY

    has_real_anthropic = (
        anthropic_key and anthropic_key.startswith("sk-ant-")
        and "your-key" not in anthropic_key and len(anthropic_key) > 20
    )
    has_real_openai = (
        openai_key and openai_key.startswith("sk-")
        and "your-key" not in openai_key and len(openai_key) > 20
    )
    has_google_id = bool(settings.GOOGLE_CLIENT_ID) and "your-google" not in settings.GOOGLE_CLIENT_ID
    has_google_secret = bool(settings.GOOGLE_CLIENT_SECRET) and "your-google" not in settings.GOOGLE_CLIENT_SECRET

    return SettingsStatus(
        anthropic={
            "configured": has_real_anthropic,
            "preview": f"{anthropic_key[:12]}...{anthropic_key[-4:]}" if has_real_anthropic else None,
            "model": settings.LLM_PRIMARY_MODEL,
        },
        openai={
            "configured": has_real_openai,
            "preview": f"{openai_key[:8]}...{openai_key[-4:]}" if has_real_openai else None,
            "model": settings.LLM_BUDGET_MODEL,
        },
        google_oauth={
            "configured": has_google_id and has_google_secret,
            "client_id_set": has_google_id,
            "client_secret_set": has_google_secret,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        },
        ollama={
            "configured": True,
            "base_url": settings.OLLAMA_BASE_URL,
            "model": settings.LLM_SELFHOSTED_MODEL,
        },
        setup_required=not (has_real_anthropic or has_real_openai),
    )


@router.put("/settings/update", response_model=SettingsUpdateResponse)
async def update_settings(
    data: SettingsUpdate,
    authorization: Optional[str] = Header(None),
):
    """Update configuration values in the .env file.

    Accepts any combination of supported keys. Only provided (non-null)
    values are written. Existing values are updated in-place; new keys
    are appended.

    Requires setup token for access.

    After updating, the application will use the new values on the next
    request (settings are reloaded from .env on each service init).
    """
    _verify_token(authorization)

    updates = {}
    warnings = []

    # Collect non-null values
    for key in ALLOWED_KEYS:
        value = getattr(data, key, None)
        if value is not None:
            value = value.strip()
            if not value:
                continue

            # Validate formats
            if key == "ANTHROPIC_API_KEY" and not value.startswith("sk-ant-"):
                warnings.append(f"{key}: expected prefix 'sk-ant-', got '{value[:10]}...'")
            elif key == "OPENAI_API_KEY" and not value.startswith("sk-"):
                warnings.append(f"{key}: expected prefix 'sk-', got '{value[:10]}...'")
            elif key == "OLLAMA_BASE_URL" and not value.startswith("http"):
                warnings.append(f"{key}: expected URL starting with 'http', got '{value[:20]}...'")

            updates[key] = value

    # On first run, auto-generate a SETUP_TOKEN if the user didn't provide one
    generated_token = None
    if _is_first_run() and "SETUP_TOKEN" not in updates:
        import secrets
        generated_token = secrets.token_urlsafe(32)
        updates["SETUP_TOKEN"] = generated_token

    # Also generate a proper APP_SECRET_KEY if it's still a placeholder
    if settings.APP_SECRET_KEY in DEFAULT_PLACEHOLDERS and "APP_SECRET_KEY" not in updates:
        import secrets
        updates["APP_SECRET_KEY"] = secrets.token_urlsafe(32)

    if not updates:
        return SettingsUpdateResponse(message="No values to update")

    # Read existing .env file
    logger.info(f"Settings update: ENV_FILE_PATH={ENV_FILE_PATH}, exists={os.path.exists(ENV_FILE_PATH)}, is_file={os.path.isfile(ENV_FILE_PATH) if os.path.exists(ENV_FILE_PATH) else 'N/A'}")
    try:
        env_content = _read_env_file()
        logger.info(f"Read .env file: {len(env_content)} bytes")
    except FileNotFoundError:
        logger.warning(f".env file not found at {ENV_FILE_PATH}, creating new one")
        env_content = ""
    except PermissionError:
        logger.error(f"Permission denied reading {ENV_FILE_PATH}")
        raise HTTPException(status_code=500, detail=f"Cannot read .env file at {ENV_FILE_PATH} — permission denied")
    except Exception as e:
        logger.error(f"Error reading .env: {e}")
        raise HTTPException(status_code=500, detail=f"Cannot read .env file: {str(e)}")

    # Update or append each key
    for key, value in updates.items():
        env_content = _set_env_value(env_content, key, value)

    # Write back
    try:
        _write_env_file(env_content)
        logger.info(f"Wrote .env file: {len(env_content)} bytes to {ENV_FILE_PATH}")
    except PermissionError:
        logger.error(f"Permission denied writing {ENV_FILE_PATH}")
        raise HTTPException(status_code=500, detail=f"Cannot write to .env file at {ENV_FILE_PATH} — permission denied")
    except Exception as e:
        logger.error(f"Error writing .env: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to write .env file at {ENV_FILE_PATH}: {str(e)}")

    # Reload settings in-memory so subsequent requests use new values
    for key, value in updates.items():
        if hasattr(settings, key):
            setattr(settings, key, value)

    message = f"Updated {len(updates)} setting(s). Changes take effect immediately."
    if generated_token:
        message += " A setup token was auto-generated. Save it now — it will only be shown once."

    return SettingsUpdateResponse(
        updated=list(updates.keys()),
        warnings=warnings,
        message=message,
        generated_token=generated_token,
    )


@router.post("/settings/test-keys", response_model=list[KeyTestResult])
async def test_configured_keys(authorization: Optional[str] = Header(None)):
    """Test all configured API keys by making minimal API calls."""
    _verify_token(authorization)

    results = []

    try:
        import httpx

        # Test Anthropic
        key = settings.ANTHROPIC_API_KEY
        if key and key.startswith("sk-ant-") and "your-key" not in key and len(key) > 20:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={"x-api-key": key, "content-type": "application/json", "anthropic-version": "2023-06-01"},
                        json={"model": settings.LLM_PRIMARY_MODEL, "max_tokens": 10, "messages": [{"role": "user", "content": "Say OK"}]},
                        timeout=15.0,
                    )
                if resp.status_code == 200:
                    results.append(KeyTestResult(key="ANTHROPIC_API_KEY", status="valid"))
                else:
                    err = resp.json().get("error", {}).get("message", f"HTTP {resp.status_code}")
                    results.append(KeyTestResult(key="ANTHROPIC_API_KEY", status="invalid", detail=str(err)))
            except Exception as e:
                results.append(KeyTestResult(key="ANTHROPIC_API_KEY", status="error", detail=str(e)))
        else:
            results.append(KeyTestResult(key="ANTHROPIC_API_KEY", status="not_configured"))

        # Test OpenAI
        key = settings.OPENAI_API_KEY
        if key and key.startswith("sk-") and "your-key" not in key and len(key) > 20:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                        json={"model": settings.LLM_BUDGET_MODEL, "max_completion_tokens": 10, "messages": [{"role": "user", "content": "Say OK"}]},
                        timeout=15.0,
                    )
                if resp.status_code == 200:
                    results.append(KeyTestResult(key="OPENAI_API_KEY", status="valid"))
                else:
                    err = resp.json().get("error", {}).get("message", f"HTTP {resp.status_code}")
                    results.append(KeyTestResult(key="OPENAI_API_KEY", status="invalid", detail=str(err)))
            except Exception as e:
                results.append(KeyTestResult(key="OPENAI_API_KEY", status="error", detail=str(e)))
        else:
            results.append(KeyTestResult(key="OPENAI_API_KEY", status="not_configured"))

        # Test Ollama
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=5.0)
            if resp.status_code == 200:
                results.append(KeyTestResult(key="OLLAMA_BASE_URL", status="valid", detail=f"Connected at {settings.OLLAMA_BASE_URL}"))
            else:
                results.append(KeyTestResult(key="OLLAMA_BASE_URL", status="error", detail=f"HTTP {resp.status_code}"))
        except Exception as e:
            results.append(KeyTestResult(key="OLLAMA_BASE_URL", status="unreachable", detail=str(e)))

    except Exception as e:
        # Catch-all to prevent 500s
        results.append(KeyTestResult(key="GENERAL", status="error", detail=f"Test failed: {str(e)}"))

    return results


# ============================================
# .ENV FILE HELPERS
# ============================================

def _read_env_file() -> str:
    """Read the .env file content."""
    with open(ENV_FILE_PATH, "r") as f:
        return f.read()


def _write_env_file(content: str) -> None:
    """Write content to the .env file."""
    with open(ENV_FILE_PATH, "w") as f:
        f.write(content)


def _set_env_value(content: str, key: str, value: str) -> str:
    """Set a key=value in the .env content string.

    If the key exists (even commented out with a value), update it in place.
    Otherwise, append it to the end.
    """
    # Match: KEY=value or KEY="value" (with optional leading #)
    pattern = rf'^(#?\s*)?{re.escape(key)}\s*=\s*.*$'

    if re.search(pattern, content, re.MULTILINE):
        # Replace existing line (uncomment if commented)
        return re.sub(pattern, f"{key}={value}", content, flags=re.MULTILINE)
    else:
        # Append to end
        if not content.endswith("\n"):
            content += "\n"
        return content + f"{key}={value}\n"
