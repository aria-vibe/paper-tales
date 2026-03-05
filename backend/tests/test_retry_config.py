"""Tests for retry configuration on Gemini model objects and embedding retries."""

from unittest.mock import MagicMock, patch

import pytest
from google.adk.models import Gemini
from google.api_core.exceptions import ServiceUnavailable
from google.genai import types

from papertales.config import (
    MODEL_GEMINI_FLASH,
    MODEL_GEMINI_FLASH_IMAGE,
    MODEL_GEMINI_FLASH_LITE,
    RETRY_OPTIONS,
)
from papertales.tools.factcheck_tools import _embed_content


class TestRetryConfig:
    """Verify retry options are properly configured on model objects."""

    def test_retry_options_values(self):
        assert RETRY_OPTIONS.attempts == 5
        assert RETRY_OPTIONS.initial_delay == 2.0
        assert RETRY_OPTIONS.max_delay == 60.0
        assert RETRY_OPTIONS.exp_base == 2.0
        assert set(RETRY_OPTIONS.http_status_codes) == {408, 429, 500, 502, 503, 504}

    def test_flash_model_is_gemini_with_retry(self):
        assert isinstance(MODEL_GEMINI_FLASH, Gemini)
        assert MODEL_GEMINI_FLASH.model == "gemini-2.5-flash"
        assert MODEL_GEMINI_FLASH.retry_options is RETRY_OPTIONS

    def test_flash_lite_model_is_gemini_with_retry(self):
        assert isinstance(MODEL_GEMINI_FLASH_LITE, Gemini)
        assert MODEL_GEMINI_FLASH_LITE.model == "gemini-2.5-flash-lite"
        assert MODEL_GEMINI_FLASH_LITE.retry_options is RETRY_OPTIONS

    def test_flash_image_model_is_gemini_with_retry(self):
        assert isinstance(MODEL_GEMINI_FLASH_IMAGE, Gemini)
        assert MODEL_GEMINI_FLASH_IMAGE.model == "gemini-2.5-flash-image"
        assert MODEL_GEMINI_FLASH_IMAGE.retry_options is RETRY_OPTIONS


class TestEmbedContentRetry:
    """Verify the _embed_content helper retries on transient errors."""

    def test_succeeds_on_first_try(self):
        client = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.values = [0.1, 0.2, 0.3]
        mock_result = MagicMock()
        mock_result.embeddings = [mock_embedding]
        client.models.embed_content.return_value = mock_result

        result = _embed_content(client, "test text")

        assert result == [0.1, 0.2, 0.3]
        assert client.models.embed_content.call_count == 1

    def test_retries_on_service_unavailable(self):
        client = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.values = [0.5, 0.5]
        mock_result = MagicMock()
        mock_result.embeddings = [mock_embedding]

        # Fail twice with 503, then succeed
        client.models.embed_content.side_effect = [
            ServiceUnavailable("503 Service Unavailable"),
            ServiceUnavailable("503 Service Unavailable"),
            mock_result,
        ]

        # Patch tenacity's wait to avoid real delays in tests
        with patch("papertales.tools.factcheck_tools._embed_content.retry.wait", return_value=0):
            result = _embed_content(client, "test text")

        assert result == [0.5, 0.5]
        assert client.models.embed_content.call_count == 3

    def test_raises_after_max_retries(self):
        client = MagicMock()
        client.models.embed_content.side_effect = ServiceUnavailable("503")

        # Patch tenacity's wait to avoid real delays in tests
        with patch("papertales.tools.factcheck_tools._embed_content.retry.wait", return_value=0):
            with pytest.raises(ServiceUnavailable):
                _embed_content(client, "test text")

        assert client.models.embed_content.call_count == 5

    def test_does_not_retry_on_value_error(self):
        """Non-retryable exceptions should propagate immediately."""
        client = MagicMock()
        client.models.embed_content.side_effect = ValueError("bad input")

        with pytest.raises(ValueError, match="bad input"):
            _embed_content(client, "test text")

        assert client.models.embed_content.call_count == 1
