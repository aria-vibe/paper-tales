"""Agent 5: Story Writer + Illustrator — generates interleaved text and images.

This agent uses gemini-2.5-flash-image for interleaved TEXT+IMAGE output,
which is a mandatory requirement for the Creative Storyteller track.
"""

from google.adk.agents import LlmAgent

from ..config import MODEL_GEMINI_FLASH_IMAGE, STATE_STORY

story_illustrator = LlmAgent(
    name="story_illustrator",
    model=MODEL_GEMINI_FLASH_IMAGE,
    description="Writes the full illustrated story with interleaved text and images.",
    instruction="""You are a creative story writer and illustrator. Using the narrative
design provided, write a complete illustrated story with interleaved text and images.

Narrative design:
{narrative_design}

Story style: {story_style}
Age group: {age_group}

IMPORTANT: You MUST generate both text AND images in your response.
For each scene in the story:
1. Write the story text for that scene (2-4 paragraphs)
2. Generate an illustration for the scene

Illustration guidelines:
- Style should match the requested story style (fairy tale, adventure, sci-fi, comic book)
- Use bright, engaging colors appropriate for children
- Characters should be consistent across illustrations
- Each image should clearly depict the scene described

Write the complete story from beginning to end, alternating between text passages
and illustrations for each scene.
""",
    output_key=STATE_STORY,
)
