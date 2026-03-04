"""Tools for audio narration using Google Cloud Text-to-Speech."""

import base64

from google.cloud import texttospeech


def get_voice_for_age_group(age_group: str) -> dict:
    """Get recommended TTS voice settings for a given age group.

    Args:
        age_group: Target age group — "6-9", "10-13", or "14-17".

    Returns:
        A dict with 'voice_name', 'speaking_rate', and 'description'.
    """
    voices = {
        "6-9": {
            "voice_name": "en-US-Journey-D",
            "speaking_rate": 0.9,
            "description": "Warm, friendly voice at a slower pace for young listeners",
        },
        "10-13": {
            "voice_name": "en-US-Journey-D",
            "speaking_rate": 1.0,
            "description": "Clear, engaging voice at a normal pace for middle readers",
        },
        "14-17": {
            "voice_name": "en-US-Journey-D",
            "speaking_rate": 1.05,
            "description": "Natural, mature voice at a slightly faster pace for teens",
        },
    }
    return voices.get(age_group, voices["10-13"])


def synthesize_speech(
    text: str,
    voice_name: str = "en-US-Journey-D",
    speaking_rate: float = 1.0,
) -> dict:
    """Convert text to speech using Google Cloud TTS.

    Args:
        text: The text to convert to speech.
        voice_name: Google Cloud TTS voice name.
        speaking_rate: Speech speed multiplier (0.25 to 4.0).

    Returns:
        A dict with 'audio_base64', 'mime_type', and 'size_bytes' on success,
        or 'error' on failure.
    """
    if not text or not text.strip():
        return {"error": "Text is empty — nothing to synthesize"}

    try:
        client = texttospeech.TextToSpeechClient()

        synthesis_input = texttospeech.SynthesisInput(text=text)

        voice_params = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name=voice_name,
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=speaking_rate,
        )

        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config,
        )

        audio_base64 = base64.b64encode(response.audio_content).decode("utf-8")

        return {
            "audio_base64": audio_base64,
            "mime_type": "audio/mpeg",
            "size_bytes": len(response.audio_content),
        }

    except Exception as exc:
        return {"error": f"TTS synthesis failed: {exc}"}
