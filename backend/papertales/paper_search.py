"""Natural language paper search via arXiv API + Gemini query refinement."""

import asyncio
import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import httpx
from google import genai

logger = logging.getLogger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
LLM_MODEL = "gemini-2.5-flash-lite"

# Rate limiting: max 1 arXiv request per 3 seconds
_arxiv_lock = asyncio.Lock()
_last_arxiv_request: float = 0.0

_genai_client: genai.Client | None = None


def _get_genai_client() -> genai.Client:
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client()
    return _genai_client


def init_genai_client() -> None:
    """Eagerly initialize the genai client (call at app startup)."""
    _get_genai_client()


class PaperNotFoundError(Exception):
    """Raised when no papers match the search query."""


class SearchServiceError(Exception):
    """Raised when search infrastructure (arXiv API, LLM) fails."""


@dataclass
class ArxivResult:
    title: str
    arxiv_id: str
    url: str
    summary: str
    authors: list[str]


@dataclass
class SearchResult:
    paper_url: str
    paper_title: str
    arxiv_id: str
    authors: list[str]


def is_url_input(user_input: str) -> bool:
    """Check if input looks like a URL rather than a natural language query."""
    stripped = user_input.strip()
    if stripped.startswith(("http://", "https://")):
        return True
    # Check for known archive domains without protocol
    archive_domains = [
        "arxiv.org", "biorxiv.org", "medrxiv.org", "chemrxiv.org",
        "ssrn.com", "eartharxiv.org", "psyarxiv.com", "osf.io",
    ]
    for domain in archive_domains:
        if domain in stripped:
            return True
    return False


def _call_llm(contents: str) -> str:
    """Synchronous LLM call — meant to be run via asyncio.to_thread."""
    client = _get_genai_client()
    response = client.models.generate_content(model=LLM_MODEL, contents=contents)
    return response.text.strip()


async def refine_query_with_llm(question: str) -> str:
    """Use Gemini flash-lite to convert a natural language question into arXiv search terms."""
    try:
        refined = await asyncio.to_thread(
            _call_llm,
            "You are helping search for academic papers on arXiv. "
            "Convert the user's question into an effective arXiv search query.\n\n"
            "Guidelines:\n"
            "- For definitional questions ('what is X?', 'explain X'), include the "
            "concept name and add 'survey' or 'overview' to find explanatory papers. "
            "If you know the seminal paper that introduced the concept, use its key terms.\n"
            "- For applied questions ('how to do X with Y'), focus on methodology keywords.\n"
            "- Return 3-5 keywords/phrases separated by spaces.\n"
            "- Return ONLY the search terms, nothing else.\n\n"
            "Examples:\n"
            "Q: what is LLM -> large language model attention transformer\n"
            "Q: what is CRISPR -> CRISPR Cas9 genome editing\n"
            "Q: how do neural networks learn -> neural network backpropagation training\n"
            "Q: what is reinforcement learning -> reinforcement learning survey policy reward\n\n"
            f"Q: {question} ->",
        )
        if not refined:
            return question
        return refined
    except Exception as exc:
        logger.warning("LLM query refinement failed, using raw query: %s", exc)
        raise SearchServiceError("Search service temporarily unavailable. Try a direct URL.") from exc


async def _rate_limited_arxiv_get(params: dict) -> str:
    """Execute a single rate-limited arXiv API request, return response text."""
    global _last_arxiv_request

    async with _arxiv_lock:
        now = time.monotonic()
        elapsed = now - _last_arxiv_request
        if elapsed < 3.0:
            await asyncio.sleep(3.0 - elapsed)
        _last_arxiv_request = time.monotonic()

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        resp = await client.get(ARXIV_API_URL, params=params)
        resp.raise_for_status()
    return resp.text


async def search_arxiv(query: str, max_results: int = 10) -> list[ArxivResult]:
    """Search arXiv with dual strategy: title search + full-text search, merged and deduped."""

    # Build two queries: title-focused and all-fields
    ti_params = {
        "search_query": f"ti:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    all_params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }

    try:
        # Run both searches with rate limiting (sequentially to respect arXiv rate limit)
        ti_text = await _rate_limited_arxiv_get(ti_params)
        all_text = await _rate_limited_arxiv_get(all_params)
    except httpx.HTTPError as exc:
        logger.error("arXiv API request failed: %s", exc)
        raise SearchServiceError("Paper search temporarily unavailable. Try a direct URL.") from exc

    ti_results = _parse_arxiv_xml(ti_text)
    all_results = _parse_arxiv_xml(all_text)

    # Merge: title matches first (more likely to be about the topic), then all-field matches
    seen_ids: set[str] = set()
    merged: list[ArxivResult] = []
    for r in ti_results + all_results:
        if r.arxiv_id not in seen_ids:
            seen_ids.add(r.arxiv_id)
            merged.append(r)

    return merged


def _parse_arxiv_xml(xml_text: str) -> list[ArxivResult]:
    """Parse arXiv Atom XML response into ArxivResult list."""
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_text)
    results = []

    for entry in root.findall("atom:entry", ns):
        title_el = entry.find("atom:title", ns)
        summary_el = entry.find("atom:summary", ns)
        id_el = entry.find("atom:id", ns)

        if title_el is None or id_el is None:
            continue

        title = " ".join((title_el.text or "").split())
        summary = " ".join((summary_el.text or "").split()) if summary_el is not None else ""
        raw_id = (id_el.text or "").strip()

        # Extract arXiv ID from URL like http://arxiv.org/abs/2301.12345v1
        arxiv_id = raw_id.rsplit("/", 1)[-1] if "/" in raw_id else raw_id
        # Strip version suffix (e.g., v1, v2)
        if arxiv_id and arxiv_id[-1].isdigit() and "v" in arxiv_id:
            base, _, ver = arxiv_id.rpartition("v")
            if ver.isdigit() and base:
                arxiv_id = base

        url = f"https://arxiv.org/abs/{arxiv_id}"

        authors = []
        for author_el in entry.findall("atom:author", ns):
            name_el = author_el.find("atom:name", ns)
            if name_el is not None and name_el.text:
                authors.append(name_el.text.strip())

        results.append(ArxivResult(
            title=title,
            arxiv_id=arxiv_id,
            url=url,
            summary=summary,
            authors=authors,
        ))

    return results


async def select_best_result(question: str, results: list[ArxivResult]) -> ArxivResult | None:
    """Use Gemini flash-lite to pick the most relevant paper from search results."""
    if not results:
        return None
    if len(results) == 1:
        return results[0]

    options = "\n".join(
        f"{i+1}. \"{r.title}\" — {r.summary[:200]}"
        for i, r in enumerate(results)
    )

    try:
        text = await asyncio.to_thread(
            _call_llm,
            f"A user asked: \"{question}\"\n\n"
            "Select the paper that BEST helps the user understand the topic. "
            "Prefer papers that INTRODUCE, DEFINE, or EXPLAIN the concept "
            "(foundational papers, surveys, or seminal works) over papers that "
            "merely USE or APPLY it as a tool. "
            f"Return ONLY the number (1-{len(results)}).\n\n"
            f"{options}",
        )
        # Extract first digit sequence
        for ch in text:
            if ch.isdigit():
                idx = int(ch) - 1
                if 0 <= idx < len(results):
                    return results[idx]
        # Fallback to first result
        return results[0]
    except Exception as exc:
        logger.warning("LLM selection failed, using first result: %s", exc)
        return results[0]


async def search_paper(question: str) -> SearchResult:
    """Top-level orchestrator: refine query, search arXiv, select best result.

    Raises:
        PaperNotFoundError: If no papers match the query.
        SearchServiceError: If arXiv API or LLM is unavailable.
    """
    question = question.strip()
    if not question:
        raise PaperNotFoundError('No papers found for "". Try rephrasing.')

    refined_query = await refine_query_with_llm(question)
    logger.info("Refined query: %r -> %r", question, refined_query)

    results = await search_arxiv(refined_query)
    if not results:
        raise PaperNotFoundError(f'No papers found for "{question}". Try rephrasing.')

    best = await select_best_result(question, results)
    if best is None:
        raise PaperNotFoundError(f'No papers found for "{question}". Try rephrasing.')

    logger.info("Selected paper: %s (%s)", best.title, best.url)
    return SearchResult(
        paper_url=best.url,
        paper_title=best.title,
        arxiv_id=best.arxiv_id,
        authors=best.authors,
    )
