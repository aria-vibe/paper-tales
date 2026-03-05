"""Agent 1: Paper Parser — extracts text and metadata from research papers."""

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from google.genai import types

from ..config import MODEL_GEMINI_FLASH_LITE, STATE_PAPER_TEXT
from ..tools.pdf_tools import fetch_paper_from_url

PAPER_PARSER_INSTRUCTION = """\
You are a research paper parser. Your ONLY job is to download and organize
the content of a research paper using the provided tool.

## Input
Paper URL: {user_paper_url}

## CRITICAL INSTRUCTIONS
- You MUST call `fetch_paper_from_url` with the paper URL above. This is mandatory.
- Do NOT generate paper content from your own knowledge. Even if you recognize \
the paper, you MUST fetch it via the tool to get the complete, accurate text.
- Do NOT skip the tool call for any reason.

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

paper_parser = LlmAgent(
    name="paper_parser",
    model=MODEL_GEMINI_FLASH_LITE,
    description="Extracts and structures text content from uploaded research papers.",
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
