"""Agent 8: Story Assembler — combines all outputs into the final story package."""

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from ..config import MODEL_GEMINI_FLASH, STATE_FINAL
from ..tools.storage_tools import save_to_firestore, upload_to_gcs

story_assembler = LlmAgent(
    name="story_assembler",
    model=MODEL_GEMINI_FLASH,
    description="Assembles the final story package from all generated components.",
    instruction="""You are a story assembler. Your job is to combine all generated
components into a polished, final story package.

Generated story (text + images):
{generated_story}

Audio narration URLs:
{audio_urls}

Fact-check results:
{fact_check_result}

Your task:
1. If the fact-check flagged issues, note them as disclaimers
2. Organize the story into a final structured format with:
   - Title and metadata
   - Story scenes (text + image references + audio references)
   - Glossary of scientific terms
   - "Learn More" section linking back to the original paper
3. Save the final story to storage using the available tools

Return the complete, assembled story in a structured format ready for display.
""",
    tools=[
        FunctionTool(save_to_firestore),
        FunctionTool(upload_to_gcs),
    ],
    output_key=STATE_FINAL,
)
