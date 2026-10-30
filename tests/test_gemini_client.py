"""Unit tests for agents/gemini_client.py."""

from unittest.mock import MagicMock, patch
import pytest

from agents.gemini_client import (
    get_api_key,
    get_gemini_client,
    invoke_with_retry,
    is_retryable_error,
    is_valid_api_key,
    sanitize_secret,
)


class TestGeminiClientValidationAndSanitization:
    """Tests for API key validation and secret redaction."""

    def test_sanitize_secret_masks_keys(self, monkeypatch):
        test_key = "AIzaSyFakeKeyForTesting123456789012"
        monkeypatch.setenv("GOOGLE_API_KEY", test_key)
        monkeypatch.setenv("TAVILY_API_KEY", "tvly-testkey-123456")

        raw_log = f"Error communicating with Gemini at https://generativelanguage.googleapis.com/v1beta/models?key={test_key} and tavily tvly-testkey-123456"
        sanitized = sanitize_secret(raw_log)

        assert test_key not in sanitized
        assert "tvly-testkey-123456" not in sanitized
        assert "[REDACTED" in sanitized

    def test_is_valid_api_key(self):
        assert is_valid_api_key(None) is False
        assert is_valid_api_key("") is False
        assert is_valid_api_key("   ") is False
        assert is_valid_api_key("short") is False
        assert is_valid_api_key("your_google_api_key_here") is False
        assert is_valid_api_key("placeholder") is False
        assert is_valid_api_key("AIzaSyValidLengthKeyForTesting1234") is True

    def test_get_api_key_raises_on_placeholder(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "your_google_api_key_here")
        with pytest.raises(ValueError, match="GOOGLE_API_KEY is missing or set to a placeholder"):
            get_api_key()

    def test_get_api_key_raises_on_empty(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "")
        with pytest.raises(ValueError, match="GOOGLE_API_KEY is missing or set to a placeholder"):
            get_api_key()

    def test_get_api_key_success(self, monkeypatch):
        valid_key = "AIzaSyValidLengthKeyForTesting1234"
        monkeypatch.setenv("GOOGLE_API_KEY", valid_key)
        assert get_api_key() == valid_key


class TestErrorClassification:
    """Tests for error retry classification."""

    def test_retryable_errors(self):
        assert is_retryable_error(Exception("429 ResourceExhausted: Quota exceeded")) is True
        assert is_retryable_error(Exception("503 Service Unavailable")) is True
        assert is_retryable_error(Exception("500 Internal Server Error")) is True
        assert is_retryable_error(Exception("Request timed out")) is True
        assert is_retryable_error(Exception("Connection reset by peer")) is True

    def test_permanent_errors(self):
        assert is_retryable_error(ValueError("Invalid config")) is False
        assert is_retryable_error(Exception("400 API_KEY_INVALID: API key not valid")) is False
        assert is_retryable_error(Exception("403 PermissionDenied")) is False
        assert is_retryable_error(Exception("401 Unauthorized")) is False


class TestInvokeWithRetry:
    """Tests for retry behavior and backoff logic."""

    def test_successful_invocation(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = "Mock output"

        res = invoke_with_retry(mock_llm, ["hello"])
        assert res == "Mock output"
        assert mock_llm.invoke.call_count == 1

    def test_transient_failure_then_success(self):
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            Exception("429 Rate limit exceeded"),
            "Recovered output",
        ]
        sleep_mock = MagicMock()

        res = invoke_with_retry(
            mock_llm,
            ["hello"],
            max_attempts=3,
            backoff_factor=2.0,
            base_delay=1.0,
            sleep_fn=sleep_mock,
        )

        assert res == "Recovered output"
        assert mock_llm.invoke.call_count == 2
        sleep_mock.assert_called_once_with(1.0)

    def test_permanent_error_fails_immediately_without_retrying(self):
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("400 API_KEY_INVALID")
        sleep_mock = MagicMock()

        with pytest.raises(RuntimeError, match="400 API_KEY_INVALID"):
            invoke_with_retry(mock_llm, ["hello"], max_attempts=3, sleep_fn=sleep_mock)

        assert mock_llm.invoke.call_count == 1
        sleep_mock.assert_not_called()

    def test_retry_exhaustion(self):
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("503 Service Unavailable")
        sleep_mock = MagicMock()

        with pytest.raises(RuntimeError, match="503 Service Unavailable"):
            invoke_with_retry(
                mock_llm,
                ["hello"],
                max_attempts=3,
                backoff_factor=2.0,
                base_delay=1.0,
                sleep_fn=sleep_mock,
            )

        assert mock_llm.invoke.call_count == 3
        assert sleep_mock.call_count == 2
        sleep_mock.assert_any_call(1.0)
        sleep_mock.assert_any_call(2.0)


class TestGetGeminiClient:
    """Tests for get_gemini_client factory."""

    def test_get_gemini_client_fails_if_placeholder_key(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "your_google_api_key_here")
        with pytest.raises(ValueError, match="GOOGLE_API_KEY is missing or set to a placeholder"):
            get_gemini_client("fast")

    def test_get_gemini_client_instantiates_with_valid_key(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "AIzaSyValidTestKey123456789012345")
        with patch("agents.gemini_client.ChatGoogleGenerativeAI") as mock_chat:
            mock_instance = MagicMock()
            mock_chat.return_value = mock_instance

            client = get_gemini_client("fast", temperature=0.1)
            mock_chat.assert_called_once()
            assert client == mock_instance
