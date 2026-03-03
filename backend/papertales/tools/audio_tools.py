"""Tools for audio narration."""


def synthesize_speech(text: str, voice_name: str = "en-US-Journey-D") -> dict:
    """Convert text to speech using Google Cloud TTS.

    Args:
        text: The text to convert to speech.
        voice_name: Google Cloud TTS voice name.

    Returns:
        A dict with 'audio_url' and 'duration_seconds'.
    """
    # TODO: Implement with google-cloud-texttospeech
    return {
        "audio_url": "[stub] gs://bucket/audio.mp3",
        "duration_seconds": 0.0,
    }
