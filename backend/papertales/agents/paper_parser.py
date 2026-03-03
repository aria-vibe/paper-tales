"""Agent 1: Paper Parser — extracts text and metadata from research papers."""

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from ..config import MODEL_GEMINI_FLASH, STATE_PAPER_TEXT
from ..tools.pdf_tools import extract_text_from_pdf, fetch_arxiv_paper

paper_parser = LlmAgent(
    name="paper_parser",
    model=MODEL_GEMINI_FLASH,
    description="Extracts and structures text content from uploaded research papers.",
    instruction="""You are a research paper parser. Your job is to extract and organize
the content of a research paper into a structured format.

The user has provided a paper. Use the available tools to extract the text.
Then organize the extracted content into these sections:
- Title
- Authors
- Abstract
- Key sections (Introduction, Methods, Results, Discussion, Conclusion)
- References (if available)

Return the organized content as a clear, structured text output.
If the paper path is provided as: {user_pdf_path}
""",
    tools=[
        FunctionTool(extract_text_from_pdf),
        FunctionTool(fetch_arxiv_paper),
    ],
    output_key=STATE_PAPER_TEXT,
)
