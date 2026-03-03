"""PaperTales — Root agent orchestrating the full paper-to-story pipeline."""

from google.adk.agents import SequentialAgent

from .agents.paper_parser import paper_parser
from .agents.concept_extractor import concept_extractor
from .agents.language_simplifier import language_simplifier
from .agents.narrative_designer import narrative_designer
from .agents.story_illustrator import story_illustrator
from .agents.audio_narrator import audio_narrator
from .agents.fact_checker import fact_checker
from .agents.story_assembler import story_assembler

root_agent = SequentialAgent(
    name="papertales",
    description=(
        "Transforms research papers into illustrated, age-appropriate stories. "
        "Runs an 8-agent pipeline: parse → extract concepts → simplify → "
        "design narrative → write & illustrate → narrate → fact-check → assemble."
    ),
    sub_agents=[
        paper_parser,
        concept_extractor,
        language_simplifier,
        narrative_designer,
        story_illustrator,
        audio_narrator,
        fact_checker,
        story_assembler,
    ],
)
