"""Unit tests for the LLM adapter using mocked clients and offline mock provider.

All tests run 100% offline without live API credentials or network access.
"""

import json
from unittest.mock import MagicMock

import pytest

from llm.adapter import (
    LLMAdapter,
    LLMConfigurationError,
    LLMRateLimitError,
    LLMSchemaValidationError,
    LLMTimeoutError,
)
from llm.schemas import SmokeTestResult


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Provide an isolated temporary cache directory for each test."""
    cache_path = tmp_path / "llm_cache"
    cache_path.mkdir()
    return cache_path


def test_mock_provider_deterministic_generation(temp_cache_dir):
    """Test that mock provider returns a valid typed Pydantic instance."""
    adapter = LLMAdapter(
        provider="mock",
        cache_dir=temp_cache_dir,
        cache_enabled=False,
    )
    result = adapter.generate_structured("test prompt", SmokeTestResult)

    assert isinstance(result, SmokeTestResult)
    assert result.status == "mock_status"
    assert result.message == "mock_message"


def test_mock_provider_canned_response(temp_cache_dir):
    """Test registering and retrieving custom canned responses in mock provider."""
    adapter = LLMAdapter(
        provider="mock",
        cache_dir=temp_cache_dir,
        cache_enabled=False,
    )
    canned = {"status": "verified", "message": "Mock UPI Scam Detected", "timestamp": "2026-11-15T00:00:00Z"}
    adapter.register_mock_response("SmokeTestResult", canned)

    result = adapter.generate_structured("any prompt", SmokeTestResult)
    assert result.status == "verified"
    assert result.message == "Mock UPI Scam Detected"
    assert result.timestamp == "2026-11-15T00:00:00Z"


def test_gemini_provider_with_mocked_client(temp_cache_dir):
    """Test Gemini provider parsing structured JSON with an injected mock SDK client."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({"status": "ok", "message": "System operational"})
    mock_client.models.generate_content.return_value = mock_response

    adapter = LLMAdapter(
        provider="gemini",
        model="gemini-test-flash",
        api_key="test-key",
        client=mock_client,
        cache_dir=temp_cache_dir,
        cache_enabled=False,
    )

    result = adapter.generate_structured("Ping system", SmokeTestResult)
    assert isinstance(result, SmokeTestResult)
    assert result.status == "ok"
    assert result.message == "System operational"
    assert mock_client.models.generate_content.call_count == 1


def test_markdown_code_fence_cleaning(temp_cache_dir):
    """Test that responses wrapped in markdown ```json ... ``` are cleanly parsed."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "```json\n{\"status\": \"ok\", \"message\": \"Fenced payload\"}\n```"
    mock_client.models.generate_content.return_value = mock_response

    adapter = LLMAdapter(
        provider="gemini",
        model="gemini-test-flash",
        api_key="test-key",
        client=mock_client,
        cache_dir=temp_cache_dir,
        cache_enabled=False,
    )

    result = adapter.generate_structured("Ping", SmokeTestResult)
    assert result.status == "ok"
    assert result.message == "Fenced payload"


def test_disk_caching_behavior(temp_cache_dir):
    """Test that identical requests hit the disk cache and avoid duplicate API calls."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({"status": "cached", "message": "From API"})
    mock_client.models.generate_content.return_value = mock_response

    adapter = LLMAdapter(
        provider="gemini",
        model="gemini-test-flash",
        api_key="test-key",
        client=mock_client,
        cache_dir=temp_cache_dir,
        cache_enabled=True,
    )

    # First call: hits client and saves to cache
    result1 = adapter.generate_structured("Cache test prompt", SmokeTestResult)
    assert result1.message == "From API"
    assert mock_client.models.generate_content.call_count == 1

    # Second call: hits cache, client call count stays 1
    result2 = adapter.generate_structured("Cache test prompt", SmokeTestResult)
    assert result2.message == "From API"
    assert mock_client.models.generate_content.call_count == 1

    # Different prompt: misses cache, client is called again
    adapter.generate_structured("Different prompt", SmokeTestResult)
    assert mock_client.models.generate_content.call_count == 2


def test_retry_on_transient_error(temp_cache_dir):
    """Test that transient errors trigger exponential backoff retry and succeed."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({"status": "ok", "message": "Recovered after failure"})

    # First attempt fails with transient error, second succeeds
    mock_client.models.generate_content.side_effect = [
        Exception("503 Service Unavailable"),
        mock_response,
    ]

    adapter = LLMAdapter(
        provider="gemini",
        model="gemini-test-flash",
        api_key="test-key",
        client=mock_client,
        cache_dir=temp_cache_dir,
        cache_enabled=False,
        max_retries=2,
    )

    result = adapter.generate_structured("Retry test", SmokeTestResult)
    assert result.status == "ok"
    assert result.message == "Recovered after failure"
    assert mock_client.models.generate_content.call_count == 2


def test_rate_limit_exhaustion_raises_rate_limit_error(temp_cache_dir):
    """Test that repeated 429 errors exhaust retries and raise LLMRateLimitError."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("429 Resource Exhausted")

    adapter = LLMAdapter(
        provider="gemini",
        model="gemini-test-flash",
        api_key="test-key",
        client=mock_client,
        cache_dir=temp_cache_dir,
        cache_enabled=False,
        max_retries=1,
    )

    with pytest.raises(LLMRateLimitError):
        adapter.generate_structured("Rate limit test", SmokeTestResult)

    assert mock_client.models.generate_content.call_count == 2  # initial + 1 retry


def test_timeout_error_handling(temp_cache_dir):
    """Test that timeout errors raise LLMTimeoutError."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("Connection timed out")

    adapter = LLMAdapter(
        provider="gemini",
        model="gemini-test-flash",
        api_key="test-key",
        client=mock_client,
        cache_dir=temp_cache_dir,
        cache_enabled=False,
        max_retries=1,
    )

    with pytest.raises(LLMTimeoutError):
        adapter.generate_structured("Timeout test", SmokeTestResult)


def test_missing_model_raises_configuration_error(monkeypatch):
    """Test that missing LLM_MODEL raises LLMConfigurationError with helpful message."""
    monkeypatch.delenv("LLM_MODEL", raising=False)

    with pytest.raises(LLMConfigurationError) as exc_info:
        LLMAdapter(provider="gemini", model="", api_key="dummy")

    assert "LLM_MODEL environment variable must be set" in str(exc_info.value)


def test_invalid_json_raises_schema_validation_error(temp_cache_dir):
    """Test that malformed JSON from provider raises LLMSchemaValidationError."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "This is not valid json {"
    mock_client.models.generate_content.return_value = mock_response

    adapter = LLMAdapter(
        provider="gemini",
        model="gemini-test-flash",
        api_key="test-key",
        client=mock_client,
        cache_dir=temp_cache_dir,
        cache_enabled=False,
    )

    with pytest.raises(LLMSchemaValidationError):
        adapter.generate_structured("Invalid JSON test", SmokeTestResult)
