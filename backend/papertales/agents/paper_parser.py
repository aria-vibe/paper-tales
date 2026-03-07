"""Agent 1: Paper Parser — extracts text and metadata from research papers.

When the paper content is already cached (STATE_PAPER_CACHED == "true"),
skips the LLM call entirely and emits the cached text directly.
"""

import logging
from collections.abc import AsyncGenerator

from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.adk.tools import FunctionTool
from google.genai import types

from ..config import (
    MODEL_GEMINI_FLASH,
    STATE_PAPER_CACHED,
    STATE_PAPER_TEXT,
    STATE_USER_PAPER_URL,
)
from ..tools.pdf_tools import fetch_paper_from_url

logger = logging.getLogger(__name__)

PAPER_PARSER_INSTRUCTION = """\
You are a research paper parser. Your job is to provide structured paper content.

## CRITICAL INSTRUCTIONS

You MUST call `fetch_paper_from_url` with the paper URL below. This is mandatory.
- Do NOT generate paper content from your own knowledge.
- Do NOT skip the tool call for any reason.

Paper URL: {user_paper_url}

## Steps
1. Call `fetch_paper_from_url` with the exact paper URL shown above.
2. If the tool returns an error, report it clearly — do NOT fabricate content.
3. Organize the extracted text into the structured format below using ONLY \
the text returned by the tool.

## Output Format
Return the paper content organized EXACTLY with these section headers:

**TITLE**: <paper title>

**AUTHORS**: <comma-separated list>

**ABSTRACT**: <the paper abstract>

**INTRODUCTION**: <introduction section content>

**METHODS**: <methodology / approach section content>

**RESULTS**: <results / experiments section content>

**DISCUSSION**: <discussion section content, or "Not found" if absent>

**CONCLUSION**: <conclusion section content>

Preserve the original technical content faithfully. If a section is not \
clearly present in the paper, write "Section not clearly delineated in source" \
rather than guessing.
"""

_llm_parser = LlmAgent(
    name="paper_parser_llm",
    model=MODEL_GEMINI_FLASH,
    description="LLM sub-agent that fetches and structures paper text.",
    instruction=PAPER_PARSER_INSTRUCTION,
    tools=[
        FunctionTool(fetch_paper_from_url),
    ],
    generate_content_config=types.GenerateContentConfig(
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True,
        ),
    ),
    output_key=STATE_PAPER_TEXT,
)


class PaperParserAgent(BaseAgent):
    """Skips the LLM call when paper content is cached; delegates otherwise."""

    model_config = {"arbitrary_types_allowed": True}

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        cached = str(state.get(STATE_PAPER_CACHED, ""))
        cached_text = str(state.get(STATE_PAPER_TEXT, ""))

        if cached == "true" and len(cached_text) >= 500:
            logger.info(
                "Paper parser: cache HIT (%d chars), skipping LLM call",
                len(cached_text),
            )
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=cached_text)],
                ),
                actions=EventActions(
                    state_delta={STATE_PAPER_TEXT: cached_text}
                ),
            )
            return

        # Not cached — delegate to the LLM sub-agent
        logger.info("Paper parser: cache MISS, delegating to LLM parser")
        async for event in _llm_parser.run_async(ctx):
            yield event


paper_parser = PaperParserAgent(
    name="paper_parser",
    description="Extracts and structures text content from uploaded research papers.",
    sub_agents=[_llm_parser],
)
