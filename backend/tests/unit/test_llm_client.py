"""Tests for app.services.llm_client — mocked, no real API calls."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.llm_client import (
    LLMError,
    LLMNoKeyError,
    LLMRateLimitError,
    LLMSchemaError,
    LLMTimeoutError,
    cheap_complete,
    extract_content,
    extract_tool_calls,
    smart_complete,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class FakeAISettings:
    provider = "google"
    api_key_encrypted = "FAKE_ENCRYPTED"
    cheap_model = "gemini-2.5-flash"
    smart_model = "gemini-2.5-pro"


@pytest.fixture()
def db_session():
    """Minimal mock Session."""
    return MagicMock()


@pytest.fixture()
def _patch_settings(db_session):
    """Patch _get_user_settings and decrypt_api_key."""
    with (
        patch("app.services.llm_client._get_user_settings", return_value=FakeAISettings()),
        patch("app.services.llm_client.decrypt_api_key", return_value="sk-test-key-12345"),
    ):
        yield


# ---------------------------------------------------------------------------
# cheap_complete
# ---------------------------------------------------------------------------

class TestCheapComplete:
    @pytest.mark.usefixtures("_patch_settings")
    def test_passes_correct_args_to_litellm(self, db_session):
        mock_response = MagicMock()
        mock_response.model_dump.return_value = {
            "choices": [{"message": {"content": "OK"}}],
        }
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 2
        mock_response.usage = mock_usage

        with patch("litellm.completion", return_value=mock_response) as mock_comp:
            result = cheap_complete(
                "user-1",
                db_session,
                [{"role": "user", "content": "Hello"}],
            )

        mock_comp.assert_called_once()
        call_kwargs = mock_comp.call_args.kwargs
        assert call_kwargs["model"] == "gemini/gemini-2.5-flash"
        assert call_kwargs["api_key"] == "sk-test-key-12345"
        assert call_kwargs["temperature"] == 0.0
        assert call_kwargs["timeout"] == 30.0
        assert result["choices"][0]["message"]["content"] == "OK"

    @pytest.mark.usefixtures("_patch_settings")
    def test_propagates_rate_limit_error(self, db_session):
        import litellm as _litellm

        with patch(
            "litellm.completion",
            side_effect=_litellm.RateLimitError(
                message="rate limited",
                model="gemini/gemini-2.5-flash",
                llm_provider="gemini",
            ),
        ):
            with pytest.raises(LLMRateLimitError):
                cheap_complete("user-1", db_session, [{"role": "user", "content": "Hi"}])

    @pytest.mark.usefixtures("_patch_settings")
    def test_propagates_timeout_error(self, db_session):
        import litellm as _litellm

        with patch(
            "litellm.completion",
            side_effect=_litellm.Timeout(
                message="timed out",
                model="gemini/gemini-2.5-flash",
                llm_provider="gemini",
            ),
        ):
            with pytest.raises(LLMTimeoutError):
                cheap_complete("user-1", db_session, [{"role": "user", "content": "Hi"}])

    def test_raises_no_key_error_when_settings_missing(self, db_session):
        db_session.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(LLMNoKeyError):
            cheap_complete("user-1", db_session, [{"role": "user", "content": "Hi"}])


# ---------------------------------------------------------------------------
# smart_complete
# ---------------------------------------------------------------------------

class TestSmartComplete:
    @pytest.mark.usefixtures("_patch_settings")
    def test_uses_smart_model(self, db_session):
        mock_response = MagicMock()
        mock_response.model_dump.return_value = {
            "choices": [{"message": {"content": "OK"}}],
        }
        mock_response.usage = MagicMock(prompt_tokens=50, completion_tokens=10)

        with patch("litellm.completion", return_value=mock_response) as mock_comp:
            smart_complete("user-1", db_session, [{"role": "user", "content": "Hello"}])

        call_kwargs = mock_comp.call_args.kwargs
        assert call_kwargs["model"] == "gemini/gemini-2.5-pro"
        assert call_kwargs["timeout"] == 90.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_extract_content(self):
        resp = {"choices": [{"message": {"content": "Hello world"}}]}
        assert extract_content(resp) == "Hello world"

    def test_extract_content_empty_raises(self):
        with pytest.raises(LLMSchemaError, match="No choices"):
            extract_content({"choices": []})

    def test_extract_tool_calls(self):
        resp = {
            "choices": [{
                "message": {
                    "tool_calls": [
                        {"function": {"name": "map_line_items", "arguments": "{}"}}
                    ]
                }
            }]
        }
        calls = extract_tool_calls(resp)
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "map_line_items"

    def test_extract_tool_calls_missing_raises(self):
        resp = {"choices": [{"message": {"content": "No tools"}}]}
        with pytest.raises(LLMSchemaError, match="did not use"):
            extract_tool_calls(resp)


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

class TestErrorTypes:
    def test_no_key_error_status(self):
        err = LLMNoKeyError()
        assert err.http_status == 400

    def test_rate_limit_error_status(self):
        err = LLMRateLimitError(retry_after=30)
        assert err.http_status == 429
        assert "30s" in str(err)

    def test_timeout_error_status(self):
        err = LLMTimeoutError(30)
        assert err.http_status == 504

    def test_schema_error_status(self):
        err = LLMSchemaError("bad json")
        assert err.http_status == 502
        assert "bad json" in str(err)

    def test_base_error_status(self):
        err = LLMError("generic")
        assert err.http_status == 500
