"""Agent 2: Concept Extractor — identifies key scientific concepts."""

from google.adk.agents import LlmAgent

from ..config import MODEL_GEMINI_FLASH, STATE_CONCEPTS

concept_extractor = LlmAgent(
    name="concept_extractor",
    model=MODEL_GEMINI_FLASH,
    description="Identifies and extracts key scientific concepts from parsed paper text.",
    instruction="""You are a scientific concept extractor. Analyze the parsed research paper
and identify the most important concepts that need to be communicated in a story.

Parsed paper content:
{parsed_paper}

Target age group: {age_group}

Extract and return:
1. **Core Concepts** (3-5): The main scientific ideas, ranked by importance
2. **Key Terms**: Important vocabulary with simple definitions
3. **Cause-Effect Relationships**: How the concepts connect to each other
4. **Real-World Analogies**: Everyday comparisons that could explain each concept
5. **Visual Elements**: Concepts that could be illustrated effectively

Format your output as a structured list.
""",
    output_key=STATE_CONCEPTS,
)
