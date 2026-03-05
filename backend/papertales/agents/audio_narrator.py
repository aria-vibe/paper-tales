"""Agent 6: Audio Narrator — generates speech from story text using Gemini TTS.

This is a non-LLM agent: it extracts scene text via simple parsing and calls
the TTS tools directly, avoiding Gemini API calls and rate-limit issues.
"""

import logging
import re
from collections.abc import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.genai import types

from ..config import STATE_AUDIO, STATE_STORY, STATE_USER_AGE_GROUP
from ..tools.audio_tools import get_voice_for_age_group, synthesize_speech

logger = logging.getLogger(__name__)


def _extract_scene_texts(story_text: str) -> list[dict]:
    """Extract labelled narration texts from the story markdown.

    Returns a list of ``{"label": str, "text": str}`` dicts where label is
    one of ``"title"``, ``"scene_0"`` … ``"scene_N"``, or ``"conclusion"``.
    """
    if not story_text or not story_text.strip():
        return []

    # Split on scene headers (## Scene 1: Title, ## Scene 2: Title, etc.)
    scene_pattern = re.compile(r"^## Scene \d+:", re.MULTILINE)
    parts = scene_pattern.split(story_text)

    items: list[dict] = []

    # First part is the title/intro before Scene 1
    intro = parts[0].strip() if parts else ""
    if intro:
        lines = [
            ln.strip()
            for ln in intro.split("\n")
            if ln.strip()
            and not ln.strip().startswith("|")
            and not ln.strip().startswith("###")
        ]
        intro_text = " ".join(lines)
        intro_text = re.sub(r"[#*_`]", "", intro_text).strip()
        if intro_text:
            items.append({"label": "title", "text": intro_text})

    # Each subsequent part is a scene body (after the header was split off)
    scene_index = 0
    for part in parts[1:]:
        # Stop at glossary or "The End" section
        end_markers = ["### GLOSSARY", "## The End"]
        text = part
        for marker in end_markers:
            idx = text.find(marker)
            if idx != -1:
                text = text[:idx]

        # Clean up: remove image markers, empty lines, markdown formatting
        lines = []
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("|"):  # table rows
                continue
            if line.startswith("[Generate") or line.startswith("[Image"):
                continue
            lines.append(line)

        scene_text = " ".join(lines)
        scene_text = re.sub(r"[#*_`]", "", scene_text).strip()
        if scene_text:
            items.append({"label": f"scene_{scene_index}", "text": scene_text})
            scene_index += 1

    # Capture "The End" / "What We Learned" conclusion section
    end_match = re.search(r"## The End\s*\n(.*?)(?:### GLOSSARY|$)", story_text, re.DOTALL)
    if end_match:
        end_text = end_match.group(1).strip()
        lines = [
            ln.strip()
            for ln in end_text.split("\n")
            if ln.strip() and not ln.strip().startswith("|")
        ]
        end_text = " ".join(lines)
        end_text = re.sub(r"[#*_`]", "", end_text).strip()
        if end_text:
            items.append({"label": "conclusion", "text": end_text})

    return items


class AudioNarratorAgent(BaseAgent):
    """Non-LLM agent that narrates story scenes using TTS tools directly."""

    model_config = {"arbitrary_types_allowed": True}

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        story_text = str(state.get(STATE_STORY, ""))
        age_group = str(state.get(STATE_USER_AGE_GROUP, "10-13"))

        # Get voice for age group
        voice_info = get_voice_for_age_group(age_group)
        voice_name = voice_info["voice_name"]
        logger.info(
            "Audio narrator: voice=%s for age_group=%s", voice_name, age_group
        )

        # Extract labelled narration texts
        narration_items = _extract_scene_texts(story_text)
        logger.info("Audio narrator: extracted %d narration items", len(narration_items))

        if not narration_items:
            summary = "Audio narration skipped: no scene text found."
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=summary)],
                ),
                actions=EventActions(state_delta={STATE_AUDIO: summary}),
            )
            return

        # Synthesize each narration item
        successful = 0
        failed = 0
        rate_limited = False
        for item in narration_items:
            label = item["label"]
            result = synthesize_speech(item["text"], voice_name)

            if result.get("rate_limited"):
                logger.warning(
                    "TTS daily limit reached at %s, skipping remaining audio",
                    label,
                )
                rate_limited = True
                break

            # Tag the result with its label so main.py can route it
            result["label"] = label

            if result.get("error"):
                logger.warning("TTS failed for %s: %s", label, result["error"])
                failed += 1
            else:
                logger.info(
                    "TTS success for %s: %d bytes",
                    label,
                    result.get("size_bytes", 0),
                )
                successful += 1

            # Emit function_response event so main.py can capture audio_base64
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                name="synthesize_speech",
                                response=result,
                            ),
                        )
                    ],
                ),
            )

        if rate_limited:
            summary = (
                "Audio narration skipped: Gemini TTS daily limit reached. "
                "Story generated without audio."
            )
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=summary)],
                ),
                actions=EventActions(state_delta={STATE_AUDIO: summary}),
            )
            return

        # Final summary event with state update
        summary = (
            f"## AUDIO NARRATION\n\n"
            f"- Voice: {voice_name}\n"
            f"- Total items: {len(narration_items)}\n"
            f"- Successful: {successful}\n"
            f"- Failed: {failed}\n"
            f"- Age group: {age_group}\n"
        )

        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=types.Content(
                role="model",
                parts=[types.Part(text=summary)],
            ),
            actions=EventActions(state_delta={STATE_AUDIO: summary}),
        )


audio_narrator = AudioNarratorAgent(
    name="audio_narrator",
    description="Converts story text into audio narration using text-to-speech.",
)
