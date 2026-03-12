"""Natural language paper search via arXiv API + Gemini query refinement."""

import asyncio
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

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


@dataclass
class RefinedQuery:
    """Structured output from query refinement LLM call."""
    arxiv_id: str | None = None  # Direct arXiv ID if LLM knows it
    title: str | None = None     # Exact paper title if LLM knows it
    keywords: str = ""           # Fallback search keywords


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


_ARXIV_ID_RE = re.compile(r"^\d{4}\.\d{4,5}$")


def _parse_refined_response(text: str) -> RefinedQuery:
    """Parse the structured LLM response into a RefinedQuery."""
    for line in text.strip().splitlines():
        line = line.strip()
        if line.upper().startswith("ARXIV:"):
            raw_id = line.split(":", 1)[1].strip()
            if _ARXIV_ID_RE.match(raw_id):
                return RefinedQuery(arxiv_id=raw_id)
        elif line.upper().startswith("TITLE:"):
            title = line.split(":", 1)[1].strip()
            if title:
                return RefinedQuery(title=title)
        elif line.upper().startswith("KEYWORDS:"):
            kw = line.split(":", 1)[1].strip()
            if kw:
                return RefinedQuery(keywords=kw)
    # Fallback: treat entire response as keywords
    return RefinedQuery(keywords=text.strip())


async def refine_query_with_llm(question: str) -> RefinedQuery:
    """Use Gemini to determine the best arXiv search strategy for a question."""
    try:
        text = await asyncio.to_thread(
            _call_llm,
            "You are helping find the most relevant academic paper on arXiv for a user's question.\n\n"
            "Return ONE of these three formats:\n\n"
            "1. If you know the EXACT arXiv ID of the foundational/seminal paper, return:\n"
            "   ARXIV:<id>\n"
            "   Example: ARXIV:1706.03762\n\n"
            "2. If you know the exact TITLE of the relevant paper but not the ID, return:\n"
            "   TITLE:<exact paper title>\n"
            "   Example: TITLE:Attention Is All You Need\n\n"
            "3. Otherwise, return 3-5 search keywords:\n"
            "   KEYWORDS:<keyword1> <keyword2> <keyword3>\n"
            "   Example: KEYWORDS:reinforcement learning survey policy gradient\n\n"
            "Guidelines:\n"
            "- For 'what is X?' questions, find the paper that INTRODUCED or DEFINED X\n"
            "- Prefer foundational/seminal papers over recent applied papers\n"
            "- Only use ARXIV: if you are CERTAIN of the exact ID\n"
            "- Only use TITLE: if you are CERTAIN of the exact title\n"
            "- Use KEYWORDS: when you're unsure — include 'survey' or 'overview' for definitional questions\n\n"
            "Examples:\n"
            "Q: what is LLM? -> ARXIV:1706.03762\n"
            "Q: what is BERT? -> ARXIV:1810.04805\n"
            "Q: what is GPT? -> ARXIV:2005.14165\n"
            "Q: what is diffusion model? -> ARXIV:2006.11239\n"
            "Q: what is AlphaFold? -> TITLE:Highly accurate protein structure prediction with AlphaFold\n"
            "Q: what is CRISPR? -> KEYWORDS:CRISPR Cas9 genome editing survey\n"
            "Q: how do vaccines work? -> KEYWORDS:vaccine immune response mechanism review\n\n"
            f"Q: {question} ->",
        )
        result = _parse_refined_response(text)
        if not result.arxiv_id and not result.title and not result.keywords:
            return RefinedQuery(keywords=question)
        return result
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


async def fetch_arxiv_by_id(arxiv_id: str) -> list[ArxivResult]:
    """Fetch a specific paper by arXiv ID using the id_list parameter."""
    params = {"id_list": arxiv_id}
    try:
        text = await _rate_limited_arxiv_get(params)
    except httpx.HTTPError as exc:
        logger.error("arXiv ID lookup failed for %s: %s", arxiv_id, exc)
        return []
    results = _parse_arxiv_xml(text)
    return results


async def search_arxiv(query: str, max_results: int = 10) -> list[ArxivResult]:
    """Search arXiv by keyword query (all fields)."""
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    try:
        text = await _rate_limited_arxiv_get(params)
    except httpx.HTTPError as exc:
        logger.error("arXiv API request failed: %s", exc)
        raise SearchServiceError("Paper search temporarily unavailable. Try a direct URL.") from exc
    return _parse_arxiv_xml(text)


async def search_arxiv_by_title(title: str, max_results: int = 5) -> list[ArxivResult]:
    """Search arXiv by exact title match."""
    # Use quoted phrase for exact title search
    params = {
        "search_query": f'ti:"{title}"',
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    try:
        text = await _rate_limited_arxiv_get(params)
    except httpx.HTTPError as exc:
        logger.error("arXiv title search failed: %s", exc)
        return []
    return _parse_arxiv_xml(text)


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

    Three-tier strategy:
    1. Direct arXiv ID lookup (fastest, most accurate for known papers)
    2. Exact title search (fast, reliable when LLM knows the title)
    3. Keyword search with LLM selection (fallback for unknown papers)

    Raises:
        PaperNotFoundError: If no papers match the query.
        SearchServiceError: If arXiv API or LLM is unavailable.
    """
    question = question.strip()
    if not question:
        raise PaperNotFoundError('No papers found for "". Try rephrasing.')

    refined = await refine_query_with_llm(question)
    logger.info("Refined query for %r: id=%s title=%s keywords=%r",
                question, refined.arxiv_id, refined.title, refined.keywords)

    # Tier 1: Direct ID lookup — instant, most accurate
    if refined.arxiv_id:
        results = await fetch_arxiv_by_id(refined.arxiv_id)
        if results:
            r = results[0]
            logger.info("Direct ID hit: %s (%s)", r.title, r.url)
            return SearchResult(
                paper_url=r.url, paper_title=r.title,
                arxiv_id=r.arxiv_id, authors=r.authors,
            )
        logger.warning("Direct ID %s not found, falling through", refined.arxiv_id)

    # Tier 2: Exact title search
    if refined.title:
        results = await search_arxiv_by_title(refined.title)
        if results:
            best = await select_best_result(question, results)
            if best:
                logger.info("Title search hit: %s (%s)", best.title, best.url)
                return SearchResult(
                    paper_url=best.url, paper_title=best.title,
                    arxiv_id=best.arxiv_id, authors=best.authors,
                )
        logger.warning("Title search for %r returned no results, falling through", refined.title)

    # Tier 3: Keyword search (fallback)
    keywords = refined.keywords or question
    results = await search_arxiv(keywords)
    if not results:
        raise PaperNotFoundError(f'No papers found for "{question}". Try rephrasing.')

    best = await select_best_result(question, results)
    if best is None:
        raise PaperNotFoundError(f'No papers found for "{question}". Try rephrasing.')

    logger.info("Keyword search selected: %s (%s)", best.title, best.url)
    return SearchResult(
        paper_url=best.url,
        paper_title=best.title,
        arxiv_id=best.arxiv_id,
        authors=best.authors,
    )
