"""LLM Adapter module for Artha Kavach.

Provides a unified, resilient interface to LLMs with:
- Configurable provider selection via environment variables ('gemini' or 'mock').
- Strict structured JSON output with Pydantic validation.
- Exponential backoff retries with jitter.
- Configurable request timeouts.
- File-based disk caching to avoid redundant API spend and stay within rate limits.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional, Type, TypeVar, Union

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

# Load environment variables once at module load
load_dotenv()

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class LLMAdapterError(Exception):
    """Base exception for all LLM adapter failures."""
    pass


class LLMConfigurationError(LLMAdapterError):
    """Raised when environment variables or settings are missing or invalid."""
    pass


class LLMTimeoutError(LLMAdapterError):
    """Raised when an LLM request exceeds configured timeout limits."""
    pass


class LLMRateLimitError(LLMAdapterError):
    """Raised when rate limit quotas are exceeded after retries."""
    pass


class LLMSchemaValidationError(LLMAdapterError):
    """Raised when LLM output cannot be parsed or validated against the schema."""
    pass


# ---------------------------------------------------------------------------
# Helper: JSON text extraction
# ---------------------------------------------------------------------------

def _clean_json_text(text: str) -> str:
    """Extract clean JSON text by stripping markdown code blocks if present."""
    trimmed = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", trimmed, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return trimmed


# ---------------------------------------------------------------------------
# Helper: Deterministic Mock Data Generator
# ---------------------------------------------------------------------------

def _generate_mock_instance(model_cls: Type[T]) -> T:
    """Deterministically construct a valid mock instance for a given Pydantic model."""
    data: Dict[str, Any] = {}
    for field_name, field_info in model_cls.model_fields.items():
        # Use default if available
        if field_info.default is not None and not repr(field_info.default).startswith("PydanticUndefined"):
            data[field_name] = field_info.default
            continue

        annotation = field_info.annotation
        # Resolve Optional / Union
        origin = getattr(annotation, "__origin__", None)
        args = getattr(annotation, "__args__", ())

        if origin is Union and type(None) in args:
            # For Optional[X], find non-none type
            non_none = [a for a in args if a is not type(None)]
            if non_none:
                annotation = non_none[0]
                origin = getattr(annotation, "__origin__", None)
                args = getattr(annotation, "__args__", ())

        if annotation is str:
            data[field_name] = f"mock_{field_name}"
        elif annotation is int:
            data[field_name] = 1
        elif annotation is float:
            data[field_name] = 1.0
        elif annotation is bool:
            data[field_name] = True
        elif origin is list or annotation is list:
            data[field_name] = []
        elif origin is dict or annotation is dict:
            data[field_name] = {}
        elif isinstance(annotation, type) and issubclass(annotation, BaseModel):
            data[field_name] = _generate_mock_instance(annotation)
        else:
            data[field_name] = f"mock_{field_name}"

    return model_cls.model_validate(data)


# ---------------------------------------------------------------------------
# LLM Adapter Implementation
# ---------------------------------------------------------------------------

class LLMAdapter:
    """Unified adapter for Gemini and offline Mock provider.

    Attributes:
        provider: 'gemini' or 'mock' (read from LLM_PROVIDER).
        model: Model identifier (read strictly from LLM_MODEL).
        temperature: Sampling temperature (default: 0.1).
        timeout_seconds: Timeout per request in seconds (default: 30.0).
        max_retries: Number of retry attempts on transient errors (default: 3).
        cache_enabled: Whether disk caching is enabled (default: True).
        cache_dir: Directory where cached responses are stored.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        cache_enabled: Optional[bool] = None,
        cache_dir: Optional[Union[str, Path]] = None,
        client: Optional[Any] = None,
    ) -> None:
        self.provider = (provider or os.getenv("LLM_PROVIDER", "gemini")).strip().lower()
        if self.provider not in ("gemini", "mock"):
            raise LLMConfigurationError(
                f"Unsupported LLM_PROVIDER '{self.provider}'. Supported providers are: 'gemini', 'mock'."
            )

        self.api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY")

        # LLM_MODEL must come from environment/args and never be hardcoded.
        # model=None means "not provided by caller, check env".
        # model="" means "caller explicitly passed empty string, treat as missing".
        if model is not None:
            raw_model = model  # caller explicitly set it (even if empty)
        else:
            raw_model = os.getenv("LLM_MODEL", "")
        if self.provider == "gemini":
            if not raw_model or not raw_model.strip():
                raise LLMConfigurationError(
                    "LLM_MODEL environment variable must be set. "
                    "Please specify a current Gemini Flash model from Google AI Studio in your .env file."
                )
            self.model = raw_model.strip()
        else:
            self.model = raw_model.strip() if raw_model else "mock-model"

        # Operational parameters
        temp_env = os.getenv("LLM_TEMPERATURE")
        self.temperature = float(temperature if temperature is not None else (temp_env if temp_env else 0.1))

        timeout_env = os.getenv("LLM_TIMEOUT_SECONDS")
        self.timeout_seconds = float(
            timeout_seconds if timeout_seconds is not None else (timeout_env if timeout_env else 30.0)
        )

        retries_env = os.getenv("LLM_MAX_RETRIES")
        self.max_retries = int(
            max_retries if max_retries is not None else (retries_env if retries_env else 3)
        )

        cache_env = os.getenv("LLM_CACHE_ENABLED", "true").lower()
        self.cache_enabled = (
            cache_enabled if cache_enabled is not None else (cache_env in ("1", "true", "yes"))
        )

        dir_env = os.getenv("LLM_CACHE_DIR", ".cache/llm")
        self.cache_dir = Path(cache_dir or dir_env)
        if self.cache_enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Mock canned responses registry
        self._canned_mock_responses: Dict[str, Any] = {}

        # Gemini client (injectable or lazily initialized)
        self._client = client

    @property
    def client(self) -> Any:
        """Lazily initialize and return the Google Gen AI SDK client."""
        if self._client is not None:
            return self._client

        if self.provider == "gemini":
            from google import genai

            if not self.api_key:
                raise LLMConfigurationError(
                    "LLM_API_KEY environment variable is required when using the 'gemini' provider."
                )
            self._client = genai.Client(api_key=self.api_key)
            return self._client

        return None

    def register_mock_response(self, schema_name: str, response_data: Union[Dict[str, Any], BaseModel]) -> None:
        """Register a specific canned response for the mock provider."""
        if isinstance(response_data, BaseModel):
            self._canned_mock_responses[schema_name] = response_data.model_dump()
        else:
            self._canned_mock_responses[schema_name] = response_data

    # -----------------------------------------------------------------------
    # Caching
    # -----------------------------------------------------------------------

    def _compute_cache_key(self, prompt: str, schema_cls: Type[BaseModel]) -> str:
        """Compute a deterministic SHA-256 cache key based on prompt and schema."""
        raw_key = (
            f"provider={self.provider}|"
            f"model={self.model}|"
            f"temp={self.temperature:.2f}|"
            f"schema={schema_cls.__name__}|"
            f"schema_json={json.dumps(schema_cls.model_json_schema(), sort_keys=True)}|"
            f"prompt={prompt}"
        )
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def _get_from_cache(self, cache_key: str, schema_cls: Type[T]) -> Optional[T]:
        """Retrieve and validate a cached response from disk if present."""
        if not self.cache_enabled:
            return None

        cache_file = self.cache_dir / f"{cache_key}.json"
        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
            data = payload.get("data")
            if data is not None:
                return schema_cls.model_validate(data)
        except Exception as e:
            logger.warning("Failed to read cache file %s: %s", cache_file, e)

        return None

    def _save_to_cache(self, cache_key: str, instance: BaseModel) -> None:
        """Persist a validated response model instance to disk cache."""
        if not self.cache_enabled:
            return

        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            payload = {
                "provider": self.provider,
                "model": self.model,
                "created_at": time.time(),
                "data": instance.model_dump(),
            }
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            logger.warning("Failed to write to cache file %s: %s", cache_file, e)

    def clear_cache(self) -> int:
        """Remove all cache files from the cache directory and return count removed."""
        if not self.cache_dir.exists():
            return 0
        count = 0
        for f in self.cache_dir.glob("*.json"):
            try:
                f.unlink()
                count += 1
            except Exception:
                pass
        return count

    # -----------------------------------------------------------------------
    # Main Generation Method
    # -----------------------------------------------------------------------

    def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        temperature: Optional[float] = None,
    ) -> T:
        """Generate structured output adhering to a Pydantic schema.

        Args:
            prompt: Text prompt to submit.
            response_model: Pydantic model class defining the desired schema.
            temperature: Optional override for sampling temperature.

        Returns:
            Validated instance of response_model.

        Raises:
            LLMTimeoutError: If request times out.
            LLMRateLimitError: If rate limit is hit and retries are exhausted.
            LLMSchemaValidationError: If output cannot be parsed to response_model.
            LLMAdapterError: For other execution failures.
        """
        temp = temperature if temperature is not None else self.temperature

        # Check disk cache
        cache_key = self._compute_cache_key(prompt, response_model)
        cached_result = self._get_from_cache(cache_key, response_model)
        if cached_result is not None:
            return cached_result

        # Execute provider call with retry logic
        if self.provider == "mock":
            result = self._call_mock(response_model)
        elif self.provider == "gemini":
            result = self._call_gemini_with_retries(prompt, response_model, temp)
        else:
            raise LLMConfigurationError(f"Unsupported provider: {self.provider}")

        # Save to disk cache
        self._save_to_cache(cache_key, result)
        return result

    def generate(
        self,
        prompt: str,
        response_schema: Type[T],
        temperature: Optional[float] = None,
    ) -> T:
        """Alias used by core/ and scam/ callers: generate(prompt, response_schema=...).

        Delegates to generate_structured. (Without this alias every LLM path in the
        app raised AttributeError, was swallowed by its try/except, and silently fell
        back to rules-only.)
        """
        return self.generate_structured(prompt, response_schema, temperature)

    # -----------------------------------------------------------------------
    # Mock Provider
    # -----------------------------------------------------------------------

    def _call_mock(self, response_model: Type[T]) -> T:
        """Generate deterministic mock output matching response_model."""
        schema_name = response_model.__name__
        if schema_name in self._canned_mock_responses:
            return response_model.model_validate(self._canned_mock_responses[schema_name])
        return _generate_mock_instance(response_model)

    # -----------------------------------------------------------------------
    # Gemini Provider with Retries
    # -----------------------------------------------------------------------

    def _call_gemini_with_retries(
        self,
        prompt: str,
        response_model: Type[T],
        temperature: float,
    ) -> T:
        """Call Gemini API via Google Gen AI SDK with backoff retries and timeouts."""
        from google.genai import types

        last_exception: Optional[Exception] = None

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_model,
            temperature=temperature,
            http_options=types.HttpOptions(timeout=int(self.timeout_seconds * 1000)),
        )

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )

                if not response or not response.text:
                    raise LLMSchemaValidationError("Gemini returned an empty response.")

                clean_text = _clean_json_text(response.text)
                try:
                    data = json.loads(clean_text)
                    return response_model.model_validate(data)
                except (json.JSONDecodeError, ValidationError) as parse_err:
                    raise LLMSchemaValidationError(
                        f"Failed to validate response against schema {response_model.__name__}: {parse_err}. "
                        f"Raw text: {response.text[:200]}"
                    ) from parse_err

            except LLMSchemaValidationError:
                # Do not retry on schema validation failures unless retries permit
                raise

            except Exception as e:
                last_exception = e
                err_msg = str(e).lower()

                # Detect timeout
                if "timeout" in err_msg or "timed out" in err_msg:
                    if attempt >= self.max_retries:
                        raise LLMTimeoutError(
                            f"Gemini call timed out after {self.timeout_seconds}s (attempt {attempt + 1}/{self.max_retries + 1}): {e}"
                        ) from e

                # Detect rate limit (429 / resource exhausted)
                is_rate_limit = (
                    "429" in err_msg
                    or "resource_exhausted" in err_msg
                    or "quota" in err_msg
                    or "rate limit" in err_msg
                )

                if attempt >= self.max_retries:
                    if is_rate_limit:
                        raise LLMRateLimitError(
                            f"Rate limit exceeded after {self.max_retries} retries: {e}"
                        ) from e
                    raise LLMAdapterError(
                        f"Gemini request failed after {self.max_retries} retries: {e}"
                    ) from e

                # Exponential backoff with jitter: 2^attempt * 1.0s + jitter
                backoff = (2 ** attempt) * 1.0 + random.uniform(0.1, 0.5)
                logger.warning(
                    "Gemini request attempt %d failed (%s). Retrying in %.2fs...",
                    attempt + 1,
                    e,
                    backoff,
                )
                time.sleep(backoff)

        raise LLMAdapterError(f"Request failed: {last_exception}") from last_exception
