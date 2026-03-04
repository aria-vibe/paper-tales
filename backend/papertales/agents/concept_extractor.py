"""Agent 2: Concept Extractor — identifies key scientific concepts."""

from google.adk.agents import LlmAgent

from ..config import MODEL_GEMINI_FLASH, STATE_CONCEPTS

CONCEPT_EXTRACTOR_INSTRUCTION = """\
You are a scientific concept extractor. Analyze the parsed research paper below
and identify the most important concepts that need to be communicated in a story
for the target age group.

## Input

Parsed paper content:
{parsed_paper}

Target age group: {age_group}

## Age-Specific Guidance
- **6–9 years**: Use concrete, familiar references (animals, food, playground).
  Limit to 3 core concepts. Analogies should be tangible and visual.
- **10–13 years**: Can handle moderate abstraction. Use relatable technology
  and nature analogies. 4-5 concepts are fine.
- **14–17 years**: Preserve scientific complexity. Use precise terminology
  with clear definitions. Up to 5 concepts with deeper chains.

## Output Format

### PAPER SUMMARY
Write ONE paragraph summarizing what this paper is about, what problem it
solves, and why it matters — in plain language appropriate for the age group.

### CORE CONCEPTS
For each concept (3–5, ranked by importance):

**Concept N: <Name>**
- **Scientific explanation**: What it actually means in the paper
- **Why it matters**: Its role in the paper's contribution
- **Difficulty level**: Easy / Medium / Hard (relative to age group)

### KEY TERMS

| Term | Simple Definition | Analogy |
|------|-------------------|---------|
| ... | ... | ... |

Include 5–10 essential terms from the paper.

### CAUSE-EFFECT CHAINS
Show how concepts connect using linked chains:
- <Cause A> → <leads to B> → <which enables C> → <resulting in D>

Provide 2–3 chains that capture the paper's core logic.

### REAL-WORLD ANALOGIES
For each core concept, provide a real-world analogy calibrated to {age_group}:
- **<Concept>**: "<Analogy>"

### FIELD OF STUDY
Classify this paper into exactly ONE field from this list:
Biology, Chemistry, Computer Science, Earth Science, Economics,
Engineering, Environmental Science, Mathematics, Medicine,
Neuroscience, Physics, Psychology, Social Science, Other

**Field**: [one field from the list above]

### VISUAL OPPORTUNITIES
List 3–5 scenes that the downstream illustration agent could draw to
explain these concepts visually. Each should be:
- **Scene N**: <Short description of what to illustrate>
  - Key concept shown: <which concept this visualizes>
  - Suggested style elements: <colors, characters, setting>
"""

concept_extractor = LlmAgent(
    name="concept_extractor",
    model=MODEL_GEMINI_FLASH,
    description="Identifies and extracts key scientific concepts from parsed paper text.",
    instruction=CONCEPT_EXTRACTOR_INSTRUCTION,
    output_key=STATE_CONCEPTS,
)
