"""Agent 4: Narrative Designer — creates story structure and plot outline."""

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from ..config import MODEL_GEMINI_FLASH, STATE_NARRATIVE
from ..tools.story_tools import get_story_template

narrative_designer = LlmAgent(
    name="narrative_designer",
    model=MODEL_GEMINI_FLASH,
    description="Designs the narrative structure and plot for the illustrated story.",
    instruction="""You are a narrative designer who creates engaging story outlines
from simplified scientific content.

Simplified content:
{simplified_content}

Story style: {story_style}
Age group: {age_group}

Your task:
1. Use the story template tool to get the structure for the requested style
2. Create compelling characters that embody or interact with the scientific concepts
3. Design a plot arc that naturally teaches the concepts through the story
4. Plan 4-6 story scenes, each with:
   - Scene description
   - Key dialogue
   - Scientific concept being taught
   - Illustration prompt (what the image should show)

Return a detailed story outline with scene-by-scene breakdown.
""",
    tools=[FunctionTool(get_story_template)],
    output_key=STATE_NARRATIVE,
)
