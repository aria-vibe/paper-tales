"""Tools for extracting text from research papers."""

import os
import re
import tempfile

import fitz
import httpx
import pdfplumber


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _extract_arxiv_id(url: str) -> str | None:
    """Extract arXiv paper ID from various URL formats or bare IDs.

    Handles:
        https://arxiv.org/abs/2301.12345
        https://arxiv.org/pdf/2301.12345
        https://arxiv.org/abs/2301.12345v2
        http://arxiv.org/abs/2301.12345
        https://arxiv.org/abs/hep-th/9901001  (old-style)
        2301.12345  (bare ID)
    """
    url = url.strip()

    # Full URL patterns
    m = re.match(
        r"https?://arxiv\.org/(?:abs|pdf)/([a-z\-]+/\d{7}|\d{4}\.\d{4,5})(v\d+)?",
        url,
    )
    if m:
        return m.group(1)

    # Bare new-style ID (e.g. 2301.12345)
    m = re.match(r"^(\d{4}\.\d{4,5})(v\d+)?$", url)
    if m:
        return m.group(1)

    # Bare old-style ID (e.g. hep-th/9901001)
    m = re.match(r"^([a-z\-]+/\d{7})(v\d+)?$", url)
    if m:
        return m.group(1)

    return None


def _extract_metadata_with_fitz(pdf_path: str) -> dict:
    """Extract metadata (title, authors) using PyMuPDF."""
    try:
        doc = fitz.open(pdf_path)
        meta = doc.metadata or {}
        doc.close()
        return {
            "title": (meta.get("title") or "").strip(),
            "authors": [
                a.strip()
                for a in (meta.get("author") or "").split(",")
                if a.strip()
            ],
        }
    except Exception as exc:
        return {"title": "", "authors": [], "_meta_error": str(exc)}


def _extract_text_with_pdfplumber(pdf_path: str) -> tuple[str, int]:
    """Extract text using pdfplumber (better multi-column handling)."""
    pages_text: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages_text.append(f"--- Page {i} ---\n{text}")
        page_count = len(pdf.pages)
    return "\n\n".join(pages_text), page_count


def _extract_abstract_from_text(text: str) -> str:
    """Best-effort regex extraction of abstract from paper text."""
    m = re.search(
        r"(?i)\babstract\b[\s.:—\-]*\n?(.*?)(?=\n\s*\n|\n\s*(?:1[\.\s]|introduction|keywords))",
        text,
        re.DOTALL,
    )
    if m:
        return m.group(1).strip()[:2000]
    return ""


# ---------------------------------------------------------------------------
# Public tool functions (called by ADK FunctionTool)
# ---------------------------------------------------------------------------

MAX_TEXT_CHARS = 100_000


def extract_text_from_pdf(pdf_path: str) -> dict:
    """Extract text content from a PDF file.

    Args:
        pdf_path: Path to the PDF file to extract text from.

    Returns:
        A dict with 'text' (extracted content), 'pages' (page count),
        and 'metadata' (title, authors, abstract).
    """
    if not os.path.isfile(pdf_path):
        return {"error": f"File not found: {pdf_path}"}

    try:
        metadata = _extract_metadata_with_fitz(pdf_path)
    except Exception as exc:
        metadata = {"title": "", "authors": [], "_meta_error": str(exc)}

    try:
        text, page_count = _extract_text_with_pdfplumber(pdf_path)
    except Exception as exc:
        return {"error": f"Failed to extract text: {exc}"}

    abstract = _extract_abstract_from_text(text)

    # Truncate for safety
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + "\n\n[... truncated at 100k characters ...]"

    return {
        "text": text,
        "pages": page_count,
        "metadata": {
            "title": metadata.get("title", ""),
            "authors": metadata.get("authors", []),
            "abstract": abstract,
        },
    }


def fetch_arxiv_paper(arxiv_url: str) -> dict:
    """Download and extract text from an arXiv paper URL.

    Args:
        arxiv_url: URL of the arXiv paper (e.g. https://arxiv.org/abs/xxxx.xxxxx)
                   or a bare arXiv ID.

    Returns:
        A dict with 'text', 'pages', and 'metadata' (including 'arxiv_id').
    """
    arxiv_id = _extract_arxiv_id(arxiv_url)
    if not arxiv_id:
        return {"error": f"Could not extract arXiv ID from: {arxiv_url}"}

    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
    tmp_path = None

    try:
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            resp = client.get(pdf_url)
            resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "pdf" not in content_type and not resp.content[:5] == b"%PDF-":
            return {"error": f"Response is not a PDF (content-type: {content_type})"}

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(resp.content)
            tmp_path = tmp.name

        result = extract_text_from_pdf(tmp_path)
        result["metadata"]["arxiv_id"] = arxiv_id
        return result

    except httpx.HTTPStatusError as exc:
        return {"error": f"HTTP {exc.response.status_code} fetching {pdf_url}"}
    except httpx.RequestError as exc:
        return {"error": f"Network error fetching arXiv paper: {exc}"}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def fetch_paper_from_url(paper_url: str) -> dict:
    """Download and extract text from a whitelisted research paper archive URL.

    Validates the URL against supported archives (arXiv, bioRxiv, medRxiv, etc.),
    downloads the PDF, and extracts text content.

    Args:
        paper_url: URL of the paper on a supported archive.

    Returns:
        A dict with 'text', 'pages', 'metadata' (including 'paper_id',
        'archive', 'source_url').
    """
    from ..url_validation import validate_archive_url

    try:
        normalized_url, archive_name, paper_id = validate_archive_url(paper_url)
    except ValueError as exc:
        return {"error": str(exc)}

    # For arXiv, use the dedicated fetcher (handles PDF URL construction)
    if archive_name == "arXiv":
        result = fetch_arxiv_paper(normalized_url)
        result["metadata"]["paper_id"] = paper_id
        result["metadata"]["archive"] = archive_name
        result["metadata"]["source_url"] = normalized_url
        return result

    # Generic archive: try to download PDF directly
    # Many archives serve PDF at the same URL or with /pdf suffix
    pdf_urls_to_try = [normalized_url]
    if not normalized_url.endswith(".pdf"):
        pdf_urls_to_try.append(normalized_url.rstrip("/") + ".pdf")

    tmp_path = None
    try:
        resp = None
        for pdf_url in pdf_urls_to_try:
            try:
                with httpx.Client(timeout=60, follow_redirects=True) as client:
                    resp = client.get(pdf_url)
                    resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")
                if "pdf" in content_type or resp.content[:5] == b"%PDF-":
                    break
                resp = None
            except (httpx.HTTPStatusError, httpx.RequestError):
                resp = None
                continue

        if resp is None:
            return {"error": f"Could not download PDF from {archive_name}: {normalized_url}"}

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(resp.content)
            tmp_path = tmp.name

        result = extract_text_from_pdf(tmp_path)
        result["metadata"]["paper_id"] = paper_id
        result["metadata"]["archive"] = archive_name
        result["metadata"]["source_url"] = normalized_url
        return result

    except Exception as exc:
        return {"error": f"Error fetching paper from {archive_name}: {exc}"}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
