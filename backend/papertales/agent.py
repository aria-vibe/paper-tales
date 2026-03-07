"""PaperTales — Root agent orchestrating the full paper-to-story pipeline."""

from google.adk.agents import ParallelAgent, SequentialAgent

from .agents.paper_parser import paper_parser
from .agents.concept_extractor import concept_extractor
from .agents.language_simplifier import language_simplifier
from .agents.narrative_designer import narrative_designer
from .agents.narrative_gate import narrative_gate
from .agents.story_illustrator import story_illustrator
from .agents.audio_narrator import audio_narrator
from .agents.fact_checker import fact_checker
from .agents.story_assembler import story_assembler

# audio_narrator and fact_checker are independent — both read from
# generated_story but neither reads the other's output.  Running them
# in parallel saves the duration of whichever finishes first (~3-5 s).
post_story_parallel = ParallelAgent(
    name="post_story_processing",
    description="Runs audio narration and fact-checking in parallel.",
    sub_agents=[audio_narrator, fact_checker],
)

root_agent = SequentialAgent(
    name="papertales",
    description=(
        "Transforms research papers into illustrated, age-appropriate stories. "
        "Runs an 8-agent pipeline: parse → extract concepts → simplify → "
        "design narrative → write & illustrate → narrate + fact-check → assemble."
    ),
    sub_agents=[
        paper_parser,
        concept_extractor,
        language_simplifier,
        narrative_designer,
        narrative_gate,
        story_illustrator,
        post_story_parallel,
        story_assembler,
    ],
)
