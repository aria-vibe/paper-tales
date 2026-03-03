"""Agent 6: Audio Narrator — generates speech from story text."""

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from ..config import MODEL_GEMINI_FLASH, STATE_AUDIO
from ..tools.audio_tools import synthesize_speech

audio_narrator = LlmAgent(
    name="audio_narrator",
    model=MODEL_GEMINI_FLASH,
    description="Converts story text into audio narration using text-to-speech.",
    instruction="""You are an audio narrator. Your job is to prepare the story text
for narration and generate audio.

Generated story:
{generated_story}

Age group: {age_group}

Your task:
1. Extract the text portions of the story (skip image descriptions)
2. Break the text into narration segments (one per scene)
3. Add appropriate pauses and emphasis markers
4. Use the synthesize_speech tool for each segment
5. Return a list of audio URLs mapped to their story scenes

Choose a voice appropriate for the target age group.
""",
    tools=[FunctionTool(synthesize_speech)],
    output_key=STATE_AUDIO,
)
