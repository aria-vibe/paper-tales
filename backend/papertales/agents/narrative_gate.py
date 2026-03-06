"""Thin gateway agent between narrative_designer and story_illustrator.

Truncates the narrative_design state value if it would cause
gemini-2.5-flash-image to exceed its 32,768 input-token limit.

Also checks that science anchors from the concept extractor are present
in the narrative design. If anchors are missing, appends an ACCURACY WARNING
section so the story illustrator can see them.
"""

import logging
import re
from collections.abc import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.genai import types

from ..config import STATE_CONCEPTS, STATE_NARRATIVE

logger = logging.getLogger(__name__)

# gemini-2.5-flash-image has a 32,768-token input limit.
# The story_illustrator instruction is ~1,800 tokens.  Leave headroom.
_MAX_NARRATIVE_CHARS = 100_000  # ~25K tokens


def _extract_anchors(concepts_text: str) -> list[str]:
    """Extract science anchor statements from concept extractor output.

    Looks for lines like '**Anchor N**: <text>' in the SCIENCE ANCHORS section.
    """
    anchors: list[str] = []
    in_section = False
    for line in concepts_text.splitlines():
        stripped = line.strip()
        if "SCIENCE ANCHORS" in stripped.upper():
            in_section = True
            continue
        if in_section:
            # Stop at next section header
            if stripped.startswith("### ") or stripped.startswith("## "):
                break
            match = re.match(r"\*\*Anchor\s+\d+\*\*:\s*(.+)", stripped)
            if match:
                anchors.append(match.group(1).strip())
    return anchors


def _check_anchor_coverage(narrative: str, anchors: list[str]) -> list[str]:
    """Return anchors that are missing from the narrative (keyword overlap check).

    For each anchor, extracts significant words (4+ chars) and checks if at least
    40% of them appear in the narrative. Returns list of missing anchor texts.
    """
    narrative_lower = narrative.lower()
    missing: list[str] = []
    for anchor in anchors:
        words = [w.lower() for w in re.findall(r"[a-zA-Z]{4,}", anchor)]
        if not words:
            continue
        found = sum(1 for w in words if w in narrative_lower)
        coverage = found / len(words)
        if coverage < 0.4:
            missing.append(anchor)
    return missing


class NarrativeGateAgent(BaseAgent):
    """Caps narrative_design length and checks science anchor coverage."""

    model_config = {"arbitrary_types_allowed": True}

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        narrative = str(ctx.session.state.get(STATE_NARRATIVE, ""))
        concepts = str(ctx.session.state.get(STATE_CONCEPTS, ""))
        modified = False
        messages: list[str] = []

        # --- Anchor coverage check ---
        anchors = _extract_anchors(concepts)
        if anchors:
            missing = _check_anchor_coverage(narrative, anchors)
            if missing:
                logger.warning(
                    "Narrative missing %d/%d science anchors: %s",
                    len(missing),
                    len(anchors),
                    missing,
                )
                warning_section = "\n\n## ACCURACY WARNING\nThe following science anchors from the paper are not adequately covered in the narrative. The story illustrator MUST include these facts:\n"
                for i, anchor in enumerate(missing, 1):
                    warning_section += f"\n{i}. {anchor}"
                narrative = narrative + warning_section
                modified = True
                messages.append(f"Appended accuracy warning for {len(missing)} missing anchor(s).")

        # --- Truncation check ---
        if len(narrative) > _MAX_NARRATIVE_CHARS:
            logger.warning(
                "Truncating narrative_design from %d to %d chars to stay within "
                "gemini-2.5-flash-image input limit",
                len(narrative),
                _MAX_NARRATIVE_CHARS,
            )
            narrative = narrative[:_MAX_NARRATIVE_CHARS] + "\n\n[Truncated for length]"
            modified = True
            messages.append("Narrative design trimmed for model input limits.")

        if not messages:
            messages.append("Narrative design validated.")

        summary = " ".join(messages)

        if modified:
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=summary)],
                ),
                actions=EventActions(state_delta={STATE_NARRATIVE: narrative}),
            )
        else:
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=summary)],
                ),
            )


narrative_gate = NarrativeGateAgent(
    name="narrative_gate",
    description="Validates and truncates narrative design for model input limits.",
)
