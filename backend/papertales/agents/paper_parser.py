"""Agent 1: Paper Parser — extracts text and metadata from research papers."""

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from ..config import MODEL_GEMINI_FLASH, STATE_PAPER_TEXT
from ..tools.pdf_tools import fetch_paper_from_url

PAPER_PARSER_INSTRUCTION = """\
You are a research paper parser. Your job is to extract and organize
the content of a research paper into a structured format.

## Input
The user has provided a research paper URL from a supported archive.

Paper URL: {user_paper_url}

## Steps
1. Call `fetch_paper_from_url` with the paper URL above.
2. If the tool returns an error, report it clearly — do NOT fabricate content.
3. Organize the extracted text into the structured format below.

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
    model=MODEL_GEMINI_FLASH,
    description="Extracts and structures text content from uploaded research papers.",
    instruction=PAPER_PARSER_INSTRUCTION,
    tools=[
        FunctionTool(fetch_paper_from_url),
    ],
    output_key=STATE_PAPER_TEXT,
)
