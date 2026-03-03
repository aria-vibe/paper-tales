"""Agent 3: Language Simplifier — adapts content for target age group."""

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from ..config import MODEL_GEMINI_FLASH, STATE_SIMPLIFIED
from ..tools.readability_tools import score_readability

language_simplifier = LlmAgent(
    name="language_simplifier",
    model=MODEL_GEMINI_FLASH,
    description="Simplifies scientific language for the target age group.",
    instruction="""You are a language simplifier specializing in making scientific content
accessible to young readers.

Extracted concepts:
{extracted_concepts}

Target age group: {age_group}

Your task:
1. Rewrite all concepts using age-appropriate vocabulary
2. Replace jargon with simple, everyday words
3. Use the readability scoring tool to verify your output matches the target level
4. Create simple analogies for complex ideas

Age group guidelines:
- **6-9**: Very simple sentences, familiar comparisons (like animals, toys, food)
- **10-13**: Moderate vocabulary, can handle some scientific terms with definitions
- **14-17**: Near-adult vocabulary, can handle nuance and complexity

Return the simplified content in a structured format.
""",
    tools=[FunctionTool(score_readability)],
    output_key=STATE_SIMPLIFIED,
)
