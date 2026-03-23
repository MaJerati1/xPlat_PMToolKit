"""LLM Abstraction Layer - Provider-agnostic interface with tiered data isolation.

This is the central integration point for all AI-powered operations.
Routes requests to the appropriate LLM provider based on the configured
data isolation tier without requiring changes to the calling code.

Tiers:
    1: Cloud API with zero data retention (Claude/GPT-4o) - DEFAULT
    2: Redaction middleware → Cloud API (sensitive identifiers masked)
    3: Self-hosted LLM via Ollama (air-gapped, no external data transfer)
"""

import json
from typing import Any, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import IntEnum


class IsolationTier(IntEnum):
    """LLM data isolation tiers."""
    CLOUD_ZDR = 1       # Cloud API with zero data retention
    REDACTED = 2        # Redaction layer → Cloud API
    SELF_HOSTED = 3     # On-premises / private LLM


@dataclass
class LLMRequest:
    """Standardized request format for all LLM operations."""
    prompt: str
    transcript_data: str
    output_schema: Optional[dict] = None   # Expected JSON structure for structured outputs
    temperature: float = 0.3               # Lower for factual extraction
    max_tokens: int = 4000
    tier_override: Optional[IsolationTier] = None


@dataclass
class LLMResponse:
    """Standardized response format from all LLM providers."""
    content: str
    structured_data: Optional[dict] = None  # Parsed JSON if output_schema was provided
    provider: str = ""
    model: str = ""
    tier: int = 1
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def process(self, request: LLMRequest) -> LLMResponse:
        """Process an LLM request and return a standardized response."""
        pass


class ClaudeProvider(LLMProvider):
    """Anthropic Claude API provider (Tier 1)."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.model = model

    async def process(self, request: LLMRequest) -> LLMResponse:
        """Send request to Claude API with tool_use for structured output."""
        import httpx
        import time

        start = time.monotonic()

        messages = [{"role": "user", "content": f"{request.prompt}\n\n--- TRANSCRIPT ---\n{request.transcript_data}\n--- END TRANSCRIPT ---"}]

        payload = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "messages": messages,
            "temperature": request.temperature,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "content-type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                json=payload,
                timeout=120.0,
            )

        elapsed = (time.monotonic() - start) * 1000
        data = response.json()

        # Raise on API errors so the fallback chain catches it
        if response.status_code != 200 or "error" in data:
            error_msg = data.get("error", {}).get("message", f"HTTP {response.status_code}")
            raise RuntimeError(f"Claude API error: {error_msg}")

        content = ""
        if "content" in data and data["content"]:
            content = data["content"][0].get("text", "")

        if not content:
            raise RuntimeError("Claude returned empty content")

        # Parse structured output if schema was provided
        structured = None
        if request.output_schema and content:
            try:
                cleaned = content.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.removeprefix("```json").removeprefix("```")
                    if cleaned.endswith("```"):
                        cleaned = cleaned[:-3]
                    cleaned = cleaned.strip()
                structured = json.loads(cleaned)
            except json.JSONDecodeError:
                pass  # Return raw content; caller can handle

        return LLMResponse(
            content=content,
            structured_data=structured,
            provider="anthropic",
            model=self.model,
            tier=1,
            input_tokens=data.get("usage", {}).get("input_tokens", 0),
            output_tokens=data.get("usage", {}).get("output_tokens", 0),
            latency_ms=elapsed,
        )


class OpenAIProvider(LLMProvider):
    """OpenAI GPT API provider (Tier 1 budget / fallback)."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    async def process(self, request: LLMRequest) -> LLMResponse:
        """Send request to OpenAI API."""
        import httpx
        import time

        start = time.monotonic()

        messages = [{"role": "user", "content": f"{request.prompt}\n\n--- TRANSCRIPT ---\n{request.transcript_data}\n--- END TRANSCRIPT ---"}]

        # Detect model family for parameter compatibility
        is_reasoning = any(x in self.model for x in ["o1", "o3", "o4"])
        is_modern = is_reasoning or "gpt-4o" in self.model

        payload = {
            "model": self.model,
            "messages": messages,
        }

        # o-series reasoning models don't support temperature
        if not is_reasoning:
            payload["temperature"] = request.temperature

        # Modern models use max_completion_tokens
        if is_modern:
            payload["max_completion_tokens"] = request.max_tokens
        else:
            payload["max_tokens"] = request.max_tokens

        # Longer timeout for large transcripts
        timeout = 180.0 if len(request.transcript_data) > 10000 else 120.0

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout,
            )

        elapsed = (time.monotonic() - start) * 1000
        data = response.json()

        # Raise on API errors so the fallback chain catches it
        if response.status_code != 200 or "error" in data:
            error_msg = data.get("error", {}).get("message", f"HTTP {response.status_code}")
            raise RuntimeError(f"OpenAI API error: {error_msg}")

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not content:
            raise RuntimeError("OpenAI returned empty content")

        structured = None
        if request.output_schema and content:
            try:
                cleaned = content.strip()
                # Remove markdown code fences if present
                if cleaned.startswith("```"):
                    cleaned = cleaned.removeprefix("```json").removeprefix("```")
                    if cleaned.endswith("```"):
                        cleaned = cleaned[:-3]
                    cleaned = cleaned.strip()
                structured = json.loads(cleaned)
            except json.JSONDecodeError:
                pass

        usage = data.get("usage", {})
        return LLMResponse(
            content=content,
            structured_data=structured,
            provider="openai",
            model=self.model,
            tier=1,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            latency_ms=elapsed,
        )


class OllamaProvider(LLMProvider):
    """Self-hosted LLM via Ollama (Tier 3 - air-gapped)."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.3:70b"):
        self.base_url = base_url
        self.model = model

    async def process(self, request: LLMRequest) -> LLMResponse:
        """Send request to local Ollama instance (OpenAI-compatible API)."""
        import httpx
        import time

        start = time.monotonic()

        messages = [{"role": "user", "content": f"{request.prompt}\n\n--- TRANSCRIPT ---\n{request.transcript_data}\n--- END TRANSCRIPT ---"}]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": request.temperature,
            "stream": False,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=300.0,  # Longer timeout for self-hosted models
            )

        elapsed = (time.monotonic() - start) * 1000
        data = response.json()

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        structured = None
        if request.output_schema and content:
            try:
                cleaned = content.strip().removeprefix("```json").removesuffix("```").strip()
                structured = json.loads(cleaned)
            except json.JSONDecodeError:
                pass

        return LLMResponse(
            content=content,
            structured_data=structured,
            provider="ollama",
            model=self.model,
            tier=3,
            latency_ms=elapsed,
        )


class RedactionMiddleware:
    """Tier 2 redaction layer - masks sensitive identifiers before LLM processing.

    Detects and replaces sensitive patterns (project names, client names,
    financial figures, etc.) with placeholders. After LLM processing,
    re-inserts original values into the output.
    """

    def __init__(self):
        self._replacements: dict[str, str] = {}
        self._counter = 0

    def redact(self, text: str, patterns: list[str]) -> str:
        """Replace sensitive patterns with placeholders.

        Args:
            text: Original transcript text
            patterns: List of sensitive strings to redact (e.g., project names, client names)

        Returns:
            Redacted text with placeholders
        """
        self._replacements = {}
        self._counter = 0
        redacted = text
        for pattern in patterns:
            if pattern in redacted:
                placeholder = f"[REDACTED_{self._counter:03d}]"
                self._replacements[placeholder] = pattern
                redacted = redacted.replace(pattern, placeholder)
                self._counter += 1
        return redacted

    def restore(self, text: str) -> str:
        """Re-insert original values into LLM output.

        Args:
            text: LLM output containing placeholders

        Returns:
            Text with original sensitive values restored
        """
        restored = text
        for placeholder, original in self._replacements.items():
            restored = restored.replace(placeholder, original)
        return restored


class LLMService:
    """Main LLM service - routes requests through the appropriate tier.

    Usage:
        service = LLMService(settings)
        response = await service.process(
            LLMRequest(prompt="Summarize this meeting", transcript_data="..."),
            tier=IsolationTier.CLOUD_ZDR
        )
    """

    def __init__(self, settings: Any):
        self.settings = settings
        self._providers: dict[int, LLMProvider] = {}
        self._redaction = RedactionMiddleware()
        self._initialize_providers()

    def _initialize_providers(self):
        """Set up available LLM providers based on configuration.

        Validates API keys to filter out placeholders before creating providers.
        Uses LLM_PREFERRED_PROVIDER to determine which provider is primary.
        The other configured provider becomes the fallback.
        """
        has_real_anthropic = (
            self.settings.ANTHROPIC_API_KEY
            and self.settings.ANTHROPIC_API_KEY.startswith("sk-ant-")
            and "your-key" not in self.settings.ANTHROPIC_API_KEY
            and len(self.settings.ANTHROPIC_API_KEY) > 20
        )
        has_real_openai = (
            self.settings.OPENAI_API_KEY
            and self.settings.OPENAI_API_KEY.startswith("sk-")
            and "your-key" not in self.settings.OPENAI_API_KEY
            and len(self.settings.OPENAI_API_KEY) > 20
        )

        anthropic_provider = None
        openai_provider = None

        if has_real_anthropic:
            anthropic_provider = ClaudeProvider(
                api_key=self.settings.ANTHROPIC_API_KEY,
                model=self.settings.LLM_PRIMARY_MODEL,
            )

        if has_real_openai:
            openai_provider = OpenAIProvider(
                api_key=self.settings.OPENAI_API_KEY,
                model=self.settings.LLM_BUDGET_MODEL,
            )

        # Determine primary and fallback based on preference
        preferred = getattr(self.settings, 'LLM_PREFERRED_PROVIDER', 'anthropic').lower()

        if preferred == "openai" and openai_provider:
            self._providers[1] = openai_provider
            self._fallback_provider = anthropic_provider
        elif preferred == "ollama":
            # Ollama as primary, cloud providers as fallback
            self._fallback_provider = anthropic_provider or openai_provider
        elif anthropic_provider:
            # Default: Anthropic primary
            self._providers[1] = anthropic_provider
            self._fallback_provider = openai_provider
        elif openai_provider:
            # Only OpenAI available
            self._providers[1] = openai_provider
            self._fallback_provider = None
        else:
            self._fallback_provider = None

        self._providers[3] = OllamaProvider(
            base_url=self.settings.OLLAMA_BASE_URL,
            model=self.settings.LLM_SELFHOSTED_MODEL,
        )

    async def process(
        self,
        request: LLMRequest,
        tier: Optional[IsolationTier] = None,
        redaction_patterns: Optional[list[str]] = None,
    ) -> LLMResponse:
        """Process an LLM request through the configured isolation tier.

        Args:
            request: Standardized LLM request
            tier: Override isolation tier (defaults to settings.LLM_DEFAULT_TIER)
            redaction_patterns: Sensitive strings to redact (Tier 2 only)

        Returns:
            Standardized LLM response
        """
        effective_tier = request.tier_override or tier or IsolationTier(self.settings.LLM_DEFAULT_TIER)

        # Tier 2: Apply redaction before sending to cloud API
        if effective_tier == IsolationTier.REDACTED:
            if not redaction_patterns:
                raise ValueError("Tier 2 requires redaction_patterns to be provided")
            request.transcript_data = self._redaction.redact(request.transcript_data, redaction_patterns)
            effective_tier = IsolationTier.CLOUD_ZDR  # Route to cloud after redaction

        # Get the appropriate provider
        provider = self._providers.get(effective_tier)
        if not provider:
            raise RuntimeError(f"No LLM provider configured for tier {effective_tier}")

        # Process the request
        try:
            response = await provider.process(request)
        except Exception as e:
            # Fallback to secondary provider on primary failure
            if hasattr(self, "_fallback_provider") and self._fallback_provider:
                response = await self._fallback_provider.process(request)
            else:
                raise

        # Tier 2: Restore redacted content in output
        if tier == IsolationTier.REDACTED:
            response.content = self._redaction.restore(response.content)
            if response.structured_data:
                # Restore in JSON values too
                restored_json = json.dumps(response.structured_data)
                restored_json = self._redaction.restore(restored_json)
                response.structured_data = json.loads(restored_json)
            response.tier = 2

        return response
