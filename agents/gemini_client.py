"""Gemini LLM Client and Retry Utility for StocX AI Agents.

Provides centralized model instantiation, API key validation, secret sanitization,
and exponential backoff retry handling for Gemini API invocations.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Callable

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

import config

logger = logging.getLogger(__name__)

# Known placeholder key patterns to guard against
_PLACEHOLDER_PATTERNS = {
    "your_google_api_key_here",
    "your_tavily_api_key_here",
    "placeholder",
    "todo",
    "dummy",
    "none",
    "null",
}


def sanitize_secret(text: str) -> str:
    """Mask known API keys and sensitive query parameter patterns from text.

    Args:
        text: Input string (e.g. exception message or log output).

    Returns:
        Sanitized string safe for logging.
    """
    if not text:
        return ""

    sanitized = str(text)

    # 1. Mask actual environment keys if present
    for env_var in ("GOOGLE_API_KEY", "TAVILY_API_KEY"):
        val = os.getenv(env_var)
        if val and len(val) > 4:
            sanitized = sanitized.replace(val, "[REDACTED_API_KEY]")

    # 2. Mask Google API key patterns (AIzaSy...)
    sanitized = re.sub(r"AIzaSy[A-Za-z0-9_-]{33}", "[REDACTED_GOOGLE_API_KEY]", sanitized)

    # 3. Mask key= query parameter patterns
    sanitized = re.sub(r"(key|api_key|token)=([^\s&\"']+)", r"\1=[REDACTED]", sanitized, flags=re.IGNORECASE)

    return sanitized


def is_valid_api_key(key: str | None) -> bool:
    """Validate whether an API key is present and not a known placeholder."""
    if not key or not isinstance(key, str):
        return False
    stripped = key.strip()
    if len(stripped) < 8:
        return False
    lowered = stripped.lower()
    if lowered in _PLACEHOLDER_PATTERNS:
        return False
    if "your_" in lowered or "placeholder" in lowered:
        return False
    return True


def get_api_key() -> str:
    """Retrieve and validate the Google API key from environment / config.

    Raises:
        ValueError: If GOOGLE_API_KEY is not set or set to a placeholder.
    """
    if "GOOGLE_API_KEY" in os.environ:
        key = os.environ.get("GOOGLE_API_KEY")
    else:
        key = getattr(config, "GOOGLE_API_KEY", None)

    if not is_valid_api_key(key):
        raise ValueError(
            "GOOGLE_API_KEY is missing or set to a placeholder in .env. "
            "Please provide a valid Gemini API key to enable live LLM agents."
        )
    return str(key).strip()


def is_retryable_error(exc: Exception) -> bool:
    """Determine whether an exception is transient and safe to retry.

    Permanent errors (400 Invalid Argument, 401 Unauthorized, 403 Forbidden,
    API_KEY_INVALID) return False so the system fails fast.
    """
    if isinstance(exc, ValueError):
        # Configuration or validation errors are permanent
        return False

    err_str = str(exc).lower()

    # Permanent failures - do NOT retry
    permanent_indicators = [
        "400",
        "401",
        "403",
        "404",
        "not_found",
        "not found",
        "no longer available",
        "api_key_invalid",
        "invalid_argument",
        "permission_denied",
        "unauthenticated",
        "unauthorized",
        "forbidden",
        "api key not valid",
        "limit: 0",
        "free tier",
        "free_tier",
        "per day limit",
        "quota exceeded",
        "exceeded your current quota",
        "limit exceeded",
    ]
    for term in permanent_indicators:
        if term in err_str:
            return False

    # Retryable transient conditions
    retryable_indicators = [
        "429",
        "resourceexhausted",
        "resource_exhausted",
        "rate limit",
        "quota",
        "too many requests",
        "500",
        "502",
        "503",
        "504",
        "service_unavailable",
        "serviceunavailable",
        "internal_server_error",
        "bad gateway",
        "gateway timeout",
        "timed out",
        "timeout",
        "connection reset",
        "connection error",
        "connectionerror",
    ]
    for term in retryable_indicators:
        if term in err_str:
            return True

    # Default to non-retryable for unexpected unclassified exceptions
    return False


def invoke_with_retry(
    llm_or_callable: Any,
    messages: Any,
    max_attempts: int | None = None,
    backoff_factor: float | None = None,
    base_delay: float = 1.0,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Any:
    """Invoke an LLM or structured callable with exponential backoff on transient errors.

    Args:
        llm_or_callable: An object with ``.invoke(messages)`` or a callable.
        messages: The input messages or payload.
        max_attempts: Total attempts before failure (defaults to config.LLM_MAX_RETRIES).
        backoff_factor: Multiplier for exponential backoff (defaults to config.LLM_RETRY_BACKOFF).
        base_delay: Initial sleep duration in seconds.
        sleep_fn: Sleeper function (injected for testing).

    Returns:
        The invocation result.

    Raises:
        The underlying exception (sanitized) once max attempts are exhausted
        or immediately upon encountering a permanent error.
    """
    attempts_limit = max_attempts or getattr(config, "LLM_MAX_RETRIES", 3)
    backoff = backoff_factor or getattr(config, "LLM_RETRY_BACKOFF", 2.0)

    last_exception: Exception | None = None

    for attempt in range(1, attempts_limit + 1):
        try:
            if hasattr(llm_or_callable, "invoke"):
                return llm_or_callable.invoke(messages)
            return llm_or_callable(messages)
        except Exception as exc:
            last_exception = exc
            sanitized_msg = sanitize_secret(str(exc))

            if not is_retryable_error(exc) or attempt >= attempts_limit:
                logger.error(
                    "LLM invocation failed permanently or exhausted retries (attempt %d/%d): %s",
                    attempt,
                    attempts_limit,
                    sanitized_msg,
                )
                raise RuntimeError(sanitized_msg) from None

            delay = base_delay * (backoff ** (attempt - 1))
            logger.warning(
                "Transient error in LLM invocation (attempt %d/%d): %s. Retrying in %.2fs...",
                attempt,
                attempts_limit,
                sanitized_msg,
                delay,
            )
            sleep_fn(delay)

    raise RuntimeError(sanitize_secret(str(last_exception))) from None


def extract_message_text(response: Any) -> str:
    """Extract clean text string from LangChain AIMessage response."""
    if hasattr(response, "content"):
        content = response.content
    else:
        content = response

    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict) and "text" in p:
                parts.append(str(p["text"]))
            elif isinstance(p, str):
                parts.append(p)
            else:
                parts.append(str(p))
        return "".join(parts).strip()
    return str(content).strip()


def get_gemini_client(
    model_type: str = "fast",
    temperature: float = 0.0,
    structured_schema: type[BaseModel] | None = None,
) -> Any:
    """Create a configured Gemini LLM instance.

    Args:
        model_type: ``"fast"`` for Gemini Flash, ``"reasoning"`` for Gemini Pro,
            or an explicit model name.
        temperature: Sampling temperature (0.0 for deterministic output).
        structured_schema: Optional Pydantic model for structured output.

    Returns:
        ChatGoogleGenerativeAI instance or structured runnable.
    """
    api_key = get_api_key()

    if model_type == "fast":
        model_name = getattr(config, "GEMINI_FAST_MODEL", getattr(config, "FAST_LLM_MODEL", "gemini-3.8-flash"))
    elif model_type == "reasoning":
        model_name = getattr(config, "GEMINI_PRO_MODEL", getattr(config, "REASONING_LLM_MODEL", "gemini-3.1-pro-preview"))
    else:
        model_name = model_type

    llm = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        google_api_key=api_key,
        timeout=10.0,
        max_retries=1,
    )

    if structured_schema is not None:
        return llm.with_structured_output(structured_schema)

    return llm
