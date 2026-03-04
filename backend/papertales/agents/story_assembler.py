"""Agent 8: Story Assembler — combines all outputs into the final story package."""

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from ..config import MODEL_GEMINI_FLASH, STATE_FINAL
from ..tools.storage_tools import save_to_firestore, upload_to_gcs

story_assembler = LlmAgent(
    name="story_assembler",
    model=MODEL_GEMINI_FLASH,
    description="Assembles the final story package from all generated components.",
    instruction="""You are a story assembler. Your job is to compile all generated components into a polished, structured final story package.

## INPUT

Generated story (text + images):
{generated_story}

Audio narration URLs:
{audio_urls}

Fact-check results:
{fact_check_result}

Source paper metadata:
{parsed_paper}

## YOUR TASK

1. Parse the generated story to extract individual scenes (text, image references).
2. Match audio URLs to their corresponding scenes.
3. Review the fact-check results:
   - If accuracy rating is "needs_revision", include flagged issues as disclaimers.
   - If "excellent" or "good", proceed normally.
4. Extract paper metadata (title, authors, abstract snippet) from the parsed paper for the "Learn More" section.
5. Build a glossary of scientific terms used in the story with child-friendly definitions.
6. Compile everything into the JSON structure below.
7. Optionally save the final package to Firestore and/or GCS using the available tools.

## OUTPUT FORMAT

Return ONLY valid JSON matching this structure:

```json
{
  "title": "Story title",
  "age_group": "6-9 or 10-13 or 14-17",
  "story_style": "fairy_tale / adventure / sci_fi / comic_book",
  "source_paper": {
    "title": "Original paper title",
    "authors": ["Author 1", "Author 2"],
    "abstract_snippet": "First 1-2 sentences of the abstract"
  },
  "scenes": [
    {
      "scene_number": 1,
      "title": "Scene title",
      "text": "Scene narrative text",
      "has_illustration": true,
      "has_audio": true
    }
  ],
  "glossary": [
    {
      "term": "Scientific term",
      "meaning": "Child-friendly explanation"
    }
  ],
  "fact_check": {
    "accuracy_rating": "excellent / good / needs_revision",
    "summary": "Brief accuracy summary"
  },
  "what_we_learned": "A short paragraph summarizing the key scientific takeaway in age-appropriate language"
}
```

Important:
- Every scene must have scene_number, title, and text.
- Set has_illustration and has_audio to true/false based on available content.
- The glossary should contain 3-8 terms from the story.
- what_we_learned should be 2-3 sentences that a child can understand.
""",
    tools=[
        FunctionTool(save_to_firestore),
        FunctionTool(upload_to_gcs),
    ],
    output_key=STATE_FINAL,
)
