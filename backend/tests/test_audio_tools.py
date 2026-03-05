"""Tests for papertales.tools.audio_tools."""

import base64
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
        assert "description" in result
        assert result["voice_name"] == "Leda"

    def test_age_10_13_returns_valid_config(self):
        result = get_voice_for_age_group("10-13")
        assert "voice_name" in result
        assert "description" in result
        assert result["voice_name"] == "Achird"

    def test_age_14_17_returns_valid_config(self):
        result = get_voice_for_age_group("14-17")
        assert "voice_name" in result
        assert "description" in result
        assert result["voice_name"] == "Orus"

    def test_unknown_age_group_returns_default(self):
        result = get_voice_for_age_group("99-99")
        default = get_voice_for_age_group("10-13")
        assert result == default

    def test_each_group_has_unique_voice(self):
        voices = {get_voice_for_age_group(ag)["voice_name"] for ag in ("6-9", "10-13", "14-17")}
        assert len(voices) == 3


# ===========================================================================
# TestSynthesizeSpeech (mocked Gemini TTS client)
# ===========================================================================


class TestSynthesizeSpeech:
    @patch("papertales.tools.audio_tools.genai.Client")
    def test_valid_text_returns_audio(self, mock_client_cls):
        pcm_bytes = b"\x00\x01" * 200  # fake PCM data
        mock_part = MagicMock()
        mock_part.inline_data.data = pcm_bytes
        mock_response = MagicMock()
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [mock_part]
        mock_client_cls.return_value.models.generate_content.return_value = mock_response

        result = synthesize_speech("Hello, this is a test.")

        assert "error" not in result
        assert "audio_base64" in result
        assert result["mime_type"] == "audio/wav"
        assert result["size_bytes"] > len(pcm_bytes)  # WAV header adds bytes
        mock_client_cls.return_value.models.generate_content.assert_called_once()

    @patch("papertales.tools.audio_tools.genai.Client")
    def test_custom_voice(self, mock_client_cls):
        pcm_bytes = b"\x00" * 50
        mock_part = MagicMock()
        mock_part.inline_data.data = pcm_bytes
        mock_response = MagicMock()
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [mock_part]
        mock_client_cls.return_value.models.generate_content.return_value = mock_response

        result = synthesize_speech("Test text", voice_name="Leda")

        assert "error" not in result
        assert result["size_bytes"] > 0

    def test_empty_text_returns_error(self):
        result = synthesize_speech("")
        assert "error" in result
        assert "empty" in result["error"].lower()

    def test_whitespace_only_returns_error(self):
        result = synthesize_speech("   \n\t  ")
        assert "error" in result

    @patch("papertales.tools.audio_tools.genai.Client")
    def test_tts_exception_returns_error(self, mock_client_cls):
        mock_client_cls.return_value.models.generate_content.side_effect = Exception(
            "API quota exceeded"
        )

        result = synthesize_speech("Some text to narrate.")

        assert "error" in result
        assert "API quota exceeded" in result["error"]

    @patch("papertales.tools.audio_tools.genai.Client")
    def test_audio_base64_is_decodable_wav(self, mock_client_cls):
        raw_pcm = b"\x01\x02\x03\x04" * 100
        mock_part = MagicMock()
        mock_part.inline_data.data = raw_pcm
        mock_response = MagicMock()
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [mock_part]
        mock_client_cls.return_value.models.generate_content.return_value = mock_response

        result = synthesize_speech("Decode test.")

        decoded = base64.b64decode(result["audio_base64"])
        # WAV files start with RIFF header
        assert decoded[:4] == b"RIFF"
        assert decoded[8:12] == b"WAVE"
