"""Tools for audio narration using Gemini TTS."""

import base64
import io
import wave

from google import genai
from google.genai import types


def get_voice_for_age_group(age_group: str) -> dict:
    """Get recommended TTS voice settings for a given age group.

    Args:
        age_group: Target age group — "6-9", "10-13", or "14-17".

    Returns:
        A dict with 'voice_name' and 'description'.
    """
    voices = {
        "6-9": {
            "voice_name": "Leda",
            "description": "Warm, youthful voice for young listeners",
        },
        "10-13": {
            "voice_name": "Achird",
            "description": "Clear, friendly voice for middle readers",
        },
        "14-17": {
            "voice_name": "Orus",
            "description": "Natural, firm voice for teens",
        },
    }
    return voices.get(age_group, voices["10-13"])


def synthesize_speech(
    text: str,
    voice_name: str = "Achird",
) -> dict:
    """Convert text to speech using Gemini TTS.

    Args:
        text: The text to convert to speech.
        voice_name: Gemini TTS voice name (e.g. Leda, Achird, Orus).

    Returns:
        A dict with 'audio_base64', 'mime_type', and 'size_bytes' on success,
        or 'error' on failure.
    """
    if not text or not text.strip():
        return {"error": "Text is empty — nothing to synthesize"}

    try:
        client = genai.Client()

        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_name,
                        ),
                    ),
                ),
            ),
        )

        pcm_data = response.candidates[0].content.parts[0].inline_data.data

        # Convert raw PCM (24kHz, 16-bit, mono) to WAV
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(24000)
            wf.writeframes(pcm_data)

        wav_bytes = wav_buffer.getvalue()
        audio_base64 = base64.b64encode(wav_bytes).decode("utf-8")

        return {
            "audio_base64": audio_base64,
            "mime_type": "audio/wav",
            "size_bytes": len(wav_bytes),
        }

    except Exception as exc:
        return {"error": f"TTS synthesis failed: {exc}"}
