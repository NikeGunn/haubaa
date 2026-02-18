"""LLM Router — unified interface for all LLM providers via litellm."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator

import litellm
import structlog

from hauba.core.config import ConfigManager
from hauba.core.types import LLMMessage, LLMResponse
from hauba.exceptions import HaubaError

logger = structlog.get_logger()

# Suppress litellm's verbose logging
litellm.suppress_debug_info = True

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds
RETRY_BACKOFF_FACTOR = 2.0
# Exceptions that are worth retrying (transient failures)
_RETRYABLE_KEYWORDS = ["rate_limit", "timeout", "503", "429", "overloaded", "capacity"]


class LLMRouter:
    """Routes LLM calls through litellm with fallback and cost tracking."""

    def __init__(self, config: ConfigManager) -> None:
        self._config = config
        self._total_tokens: int = 0
        self._total_cost: float = 0.0
        self._call_count: int = 0
        self._setup_provider()

    def _setup_provider(self) -> None:
        """Configure litellm based on settings."""
        settings = self._config.settings.llm
        if settings.api_key and settings.provider != "ollama":
            # Set the API key for the provider
            if settings.provider == "anthropic":
                litellm.api_key = settings.api_key
                import os
                os.environ["ANTHROPIC_API_KEY"] = settings.api_key
            elif settings.provider == "openai":
                import os
                os.environ["OPENAI_API_KEY"] = settings.api_key
            elif settings.provider == "deepseek":
                import os
                os.environ["DEEPSEEK_API_KEY"] = settings.api_key

    def _get_model_string(self) -> str:
        """Get the litellm model string."""
        settings = self._config.settings.llm
        provider = settings.provider
        model = settings.model

        if provider == "ollama":
            return f"ollama/{model}"
        if provider == "deepseek":
            return f"deepseek/{model}"
        # anthropic and openai models are passed directly
        return model

    async def complete(
        self,
        messages: list[LLMMessage],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """Send a completion request to the LLM."""
        settings = self._config.settings.llm
        model = self._get_model_string()
        msg_dicts = [{"role": m.role, "content": m.content} for m in messages]

        kwargs: dict = {
            "model": model,
            "messages": msg_dicts,
            "max_tokens": max_tokens or settings.max_tokens,
            "temperature": temperature if temperature is not None else settings.temperature,
        }
        if settings.api_key and settings.provider != "ollama":
            kwargs["api_key"] = settings.api_key
        if settings.base_url:
            kwargs["api_base"] = settings.base_url

        start = time.monotonic()
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await litellm.acompletion(**kwargs)
                break
            except Exception as exc:
                last_exc = exc
                safe_msg = self._sanitize_error(str(exc))
                if attempt < MAX_RETRIES and self._is_retryable(str(exc)):
                    delay = RETRY_BASE_DELAY * (RETRY_BACKOFF_FACTOR ** attempt)
                    logger.warning(
                        "llm.retry",
                        model=model,
                        attempt=attempt + 1,
                        delay=f"{delay:.1f}s",
                        error=safe_msg,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.error("llm.error", model=model, error=safe_msg)
                raise HaubaError(f"LLM call failed: {safe_msg}") from exc
        else:
            safe_msg = self._sanitize_error(str(last_exc))
            raise HaubaError(f"LLM call failed after {MAX_RETRIES} retries: {safe_msg}") from last_exc

        elapsed = time.monotonic() - start
        content = response.choices[0].message.content or ""
        usage = response.usage
        tokens = (usage.total_tokens if usage else 0) or 0
        cost = litellm.completion_cost(completion_response=response) if usage else 0.0

        self._total_tokens += tokens
        self._total_cost += cost
        self._call_count += 1

        logger.info(
            "llm.response",
            model=model,
            tokens=tokens,
            cost=f"${cost:.4f}",
            elapsed=f"{elapsed:.2f}s",
        )

        return LLMResponse(
            content=content,
            model=model,
            tokens_used=tokens,
            cost=cost,
            finish_reason=response.choices[0].finish_reason or "",
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a completion response chunk by chunk."""
        settings = self._config.settings.llm
        model = self._get_model_string()
        msg_dicts = [{"role": m.role, "content": m.content} for m in messages]

        kwargs: dict = {
            "model": model,
            "messages": msg_dicts,
            "max_tokens": max_tokens or settings.max_tokens,
            "temperature": temperature if temperature is not None else settings.temperature,
            "stream": True,
        }
        if settings.api_key and settings.provider != "ollama":
            kwargs["api_key"] = settings.api_key
        if settings.base_url:
            kwargs["api_base"] = settings.base_url

        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await litellm.acompletion(**kwargs)
                async for chunk in response:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content
                return  # Success — exit retry loop
            except Exception as exc:
                last_exc = exc
                safe_msg = self._sanitize_error(str(exc))
                if attempt < MAX_RETRIES and self._is_retryable(str(exc)):
                    delay = RETRY_BASE_DELAY * (RETRY_BACKOFF_FACTOR ** attempt)
                    logger.warning("llm.stream_retry", attempt=attempt + 1, delay=f"{delay:.1f}s")
                    await asyncio.sleep(delay)
                    continue
                logger.error("llm.stream_error", model=model, error=safe_msg)
                raise HaubaError(f"LLM stream failed: {safe_msg}") from exc
        safe_msg = self._sanitize_error(str(last_exc))
        raise HaubaError(f"LLM stream failed after {MAX_RETRIES} retries: {safe_msg}") from last_exc

    @staticmethod
    def _is_retryable(error_msg: str) -> bool:
        """Check if an error is transient and worth retrying."""
        lower = error_msg.lower()
        return any(kw in lower for kw in _RETRYABLE_KEYWORDS)

    def _sanitize_error(self, msg: str) -> str:
        """Remove API keys from error messages."""
        import re
        # Mask any sk-proj-... or sk-... tokens
        sanitized = re.sub(r'sk-[A-Za-z0-9_-]{10,}', 'sk-***REDACTED***', msg)
        return sanitized

    @property
    def stats(self) -> dict:
        """Return usage statistics."""
        return {
            "total_tokens": self._total_tokens,
            "total_cost": self._total_cost,
            "call_count": self._call_count,
        }
