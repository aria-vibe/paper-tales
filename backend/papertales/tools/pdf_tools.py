"""Tools for extracting text from research papers."""


def extract_text_from_pdf(pdf_path: str) -> dict:
    """Extract text content from a PDF file.

    Args:
        pdf_path: Path to the PDF file to extract text from.

    Returns:
        A dict with 'text' (extracted content), 'pages' (page count),
        and 'metadata' (title, authors, etc.).
    """
    # TODO: Implement with pdfplumber / PyMuPDF
    return {
        "text": "[stub] Extracted paper text will appear here.",
        "pages": 0,
        "metadata": {"title": "", "authors": [], "abstract": ""},
    }


def fetch_arxiv_paper(arxiv_url: str) -> dict:
    """Download and extract text from an arXiv paper URL.

    Args:
        arxiv_url: URL of the arXiv paper (e.g. https://arxiv.org/abs/xxxx.xxxxx).

    Returns:
        A dict with 'text', 'pages', and 'metadata'.
    """
    # TODO: Implement arXiv PDF download + extraction
    return {
        "text": "[stub] ArXiv paper text will appear here.",
        "pages": 0,
        "metadata": {"title": "", "authors": [], "abstract": "", "arxiv_id": ""},
    }
