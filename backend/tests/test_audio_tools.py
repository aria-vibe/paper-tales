"""Tests for papertales.tools.audio_tools."""

from unittest.mock import MagicMock, patch

import pytest

from papertales.tools.audio_tools import get_voice_for_age_group, synthesize_speech


# ===========================================================================
# TestGetVoiceForAgeGroup
# ===========================================================================


class TestGetVoiceForAgeGroup:
    def test_age_6_9_returns_valid_config(self):
        result = get_voice_for_age_group("6-9")
        assert "voice_name" in result
        assert "speaking_rate" in result
        assert "description" in result

    def test_age_10_13_returns_valid_config(self):
        result = get_voice_for_age_group("10-13")
        assert "voice_name" in result
        assert "speaking_rate" in result
        assert "description" in result

    def test_age_14_17_returns_valid_config(self):
        result = get_voice_for_age_group("14-17")
        assert "voice_name" in result
        assert "speaking_rate" in result
        assert "description" in result

    def test_unknown_age_group_returns_default(self):
        result = get_voice_for_age_group("99-99")
        default = get_voice_for_age_group("10-13")
        assert result == default

    def test_younger_has_slower_rate(self):
        young = get_voice_for_age_group("6-9")
        mid = get_voice_for_age_group("10-13")
        teen = get_voice_for_age_group("14-17")
        assert young["speaking_rate"] < mid["speaking_rate"]
        assert mid["speaking_rate"] < teen["speaking_rate"]

    def test_all_groups_have_voice_name(self):
        for age in ("6-9", "10-13", "14-17"):
            result = get_voice_for_age_group(age)
            assert result["voice_name"].startswith("en-US-")


# ===========================================================================
# TestSynthesizeSpeech (mocked TTS client)
# ===========================================================================


class TestSynthesizeSpeech:
    @patch("papertales.tools.audio_tools.texttospeech.TextToSpeechClient")
    def test_valid_text_returns_audio(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.audio_content = b"\xff\xfb\x90\x00" * 100  # fake MP3 bytes
        mock_client_cls.return_value.synthesize_speech.return_value = mock_response

        result = synthesize_speech("Hello, this is a test.")

        assert "error" not in result
        assert "audio_base64" in result
        assert result["mime_type"] == "audio/mpeg"
        assert result["size_bytes"] == 400
        mock_client_cls.return_value.synthesize_speech.assert_called_once()

    @patch("papertales.tools.audio_tools.texttospeech.TextToSpeechClient")
    def test_custom_voice_and_rate(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.audio_content = b"\x00" * 50
        mock_client_cls.return_value.synthesize_speech.return_value = mock_response

        result = synthesize_speech(
            "Test text",
            voice_name="en-US-Journey-F",
            speaking_rate=0.9,
        )

        assert "error" not in result
        assert result["size_bytes"] == 50

    def test_empty_text_returns_error(self):
        result = synthesize_speech("")
        assert "error" in result
        assert "empty" in result["error"].lower()

    def test_whitespace_only_returns_error(self):
        result = synthesize_speech("   \n\t  ")
        assert "error" in result

    @patch("papertales.tools.audio_tools.texttospeech.TextToSpeechClient")
    def test_tts_exception_returns_error(self, mock_client_cls):
        mock_client_cls.return_value.synthesize_speech.side_effect = Exception(
            "API quota exceeded"
        )

        result = synthesize_speech("Some text to narrate.")

        assert "error" in result
        assert "API quota exceeded" in result["error"]

    @patch("papertales.tools.audio_tools.texttospeech.TextToSpeechClient")
    def test_audio_base64_is_decodable(self, mock_client_cls):
        import base64

        raw_bytes = b"fake audio content for testing"
        mock_response = MagicMock()
        mock_response.audio_content = raw_bytes
        mock_client_cls.return_value.synthesize_speech.return_value = mock_response

        result = synthesize_speech("Decode test.")

        decoded = base64.b64decode(result["audio_base64"])
        assert decoded == raw_bytes
