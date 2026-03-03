"""Agent 7: Fact Checker — verifies story accuracy against source paper."""

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from ..config import MODEL_GEMINI_FLASH, STATE_FACTCHECK
from ..tools.factcheck_tools import compare_semantic_similarity

fact_checker = LlmAgent(
    name="fact_checker",
    model=MODEL_GEMINI_FLASH,
    description="Verifies that the generated story accurately represents the source paper.",
    instruction="""You are a scientific fact checker. Your job is to verify that the
generated story accurately represents the research paper's findings.

Original paper content:
{parsed_paper}

Generated story:
{generated_story}

Your task:
1. Use the semantic similarity tool to compare the paper and story
2. Identify any scientific inaccuracies or misrepresentations
3. Check that simplifications haven't distorted the core findings
4. Flag any claims in the story that aren't supported by the paper
5. Rate overall accuracy on a scale: excellent / good / needs_revision

Return a structured fact-check report with:
- Overall accuracy rating
- List of verified facts
- List of flagged inaccuracies (if any)
- Suggested corrections (if needed)
""",
    tools=[FunctionTool(compare_semantic_similarity)],
    output_key=STATE_FACTCHECK,
)
