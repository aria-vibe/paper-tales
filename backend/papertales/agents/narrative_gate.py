"""Thin gateway agent between narrative_designer and story_illustrator.

Truncates the narrative_design state value if it would cause
gemini-2.5-flash-image to exceed its 32,768 input-token limit.
"""

import logging
from collections.abc import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.genai import types

from ..config import STATE_NARRATIVE

logger = logging.getLogger(__name__)

# gemini-2.5-flash-image has a 32,768-token input limit.
# The story_illustrator instruction is ~1,800 tokens.  Leave headroom.
_MAX_NARRATIVE_CHARS = 100_000  # ~25K tokens


class NarrativeGateAgent(BaseAgent):
    """Caps narrative_design length to stay within model input limits."""

    model_config = {"arbitrary_types_allowed": True}

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        narrative = str(ctx.session.state.get(STATE_NARRATIVE, ""))
        if len(narrative) > _MAX_NARRATIVE_CHARS:
            logger.warning(
                "Truncating narrative_design from %d to %d chars to stay within "
                "gemini-2.5-flash-image input limit",
                len(narrative),
                _MAX_NARRATIVE_CHARS,
            )
            truncated = narrative[:_MAX_NARRATIVE_CHARS] + "\n\n[Truncated for length]"
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="Narrative design trimmed for model input limits.")],
                ),
                actions=EventActions(state_delta={STATE_NARRATIVE: truncated}),
            )
        else:
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="Narrative design validated.")],
                ),
            )


narrative_gate = NarrativeGateAgent(
    name="narrative_gate",
    description="Validates and truncates narrative design for model input limits.",
)
