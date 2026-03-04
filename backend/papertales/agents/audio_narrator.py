"""Agent 6: Audio Narrator — generates speech from story text using Google Cloud TTS."""

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from ..config import MODEL_GEMINI_FLASH, STATE_AUDIO
from ..tools.audio_tools import get_voice_for_age_group, synthesize_speech

audio_narrator = LlmAgent(
    name="audio_narrator",
    model=MODEL_GEMINI_FLASH,
    description="Converts story text into audio narration using text-to-speech.",
    instruction="""You are a professional audio narrator. Your job is to extract the
text portions of an illustrated story and produce audio narration for each scene
using text-to-speech.

## INPUT

Generated story (with interleaved text and images from the previous agent):
{generated_story}

Age group: {age_group}

## YOUR TASK

1. **Get voice settings**: Call the `get_voice_for_age_group` tool with the age group
   to determine the right voice and speaking rate.

2. **Extract narration text**: Go through the story and extract ONLY the text portions.
   Skip any image descriptions, image markers, or illustration references. Include:
   - Story title and tagline
   - All story prose (scene text, dialogue, narration)
   - The closing "What We Learned" section
   - Do NOT include the glossary table

3. **Narrate scene by scene**: For each scene, prepare the narration text and call
   the `synthesize_speech` tool with:
   - The scene's text content
   - The voice_name from step 1
   - The speaking_rate from step 1
   Add a brief pause marker ("...") between scenes for natural pacing.

4. **Compile results**: Report the narration results in the structured format below.

## NARRATION TIPS

- For scene transitions, add a short pause by including "..." between scenes
- For dialogue, the TTS will naturally handle quotation marks
- Keep each synthesis call to one scene at a time (not the entire story at once)
- If a synthesis call fails, note the error and continue with the next scene

## OUTPUT FORMAT

```
## AUDIO NARRATION

### Title
- Text: [title and tagline text]
- Voice: [voice_name]
- Speaking rate: [rate]
- Audio: [base64 reference or error message]
- Size: [size_bytes] bytes

### Scene 1: [Scene Title]
- Text: [first 50 chars of scene text...]
- Voice: [voice_name]
- Speaking rate: [rate]
- Audio: [base64 reference or error message]
- Size: [size_bytes] bytes

### Scene 2: [Scene Title]
...

### Ending
- Text: [closing text...]
- Voice: [voice_name]
- Speaking rate: [rate]
- Audio: [base64 reference or error message]
- Size: [size_bytes] bytes

### NARRATION SUMMARY
- Total scenes narrated: [N]
- Successful: [N]
- Failed: [N]
- Voice profile: [description from get_voice_for_age_group]
- Age group: [age_group]
```""",
    tools=[
        FunctionTool(get_voice_for_age_group),
        FunctionTool(synthesize_speech),
    ],
    output_key=STATE_AUDIO,
)
