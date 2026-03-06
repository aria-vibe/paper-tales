"""Tools for fact-checking generated stories against source papers."""

import logging
import math

from google import genai
from google.api_core.exceptions import GoogleAPIError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "gemini-embedding-001"
CHUNK_SIZE = 500  # words per chunk

_genai_client: genai.Client | None = None


def _get_genai_client() -> genai.Client:
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client()
    return _genai_client


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    retry=retry_if_exception_type((GoogleAPIError, ConnectionError)),
    before_sleep=lambda rs: logger.warning(
        "Embedding API retry attempt %d after %s", rs.attempt_number, rs.outcome.exception()
    ),
    reraise=True,
)
def _embed_content(client: genai.Client, text: str) -> list[float]:
    """Embed a single text chunk with retry on transient errors."""
    result = client.models.embed_content(model=EMBEDDING_MODEL, contents=text)
    return result.embeddings[0].values


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """Split text into roughly equal word-count chunks."""
    words = text.split()
    if not words:
        return []
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i : i + chunk_size]))
    return chunks


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    retry=retry_if_exception_type((GoogleAPIError, ConnectionError)),
    before_sleep=lambda rs: logger.warning(
        "Batch embedding API retry attempt %d after %s", rs.attempt_number, rs.outcome.exception()
    ),
    reraise=True,
)
def _batch_embed(client: genai.Client, chunks: list[str]) -> list[list[float]]:
    """Embed multiple text chunks in a single API call."""
    result = client.models.embed_content(model=EMBEDDING_MODEL, contents=chunks)
    return [e.values for e in result.embeddings]


def _average_vectors(vectors: list[list[float]]) -> list[float]:
    """Average a list of embedding vectors."""
    if not vectors:
        return []
    dim = len(vectors[0])
    avg = [0.0] * dim
    for v in vectors:
        for i in range(dim):
            avg[i] += v[i]
    n = len(vectors)
    return [x / n for x in avg]


def compare_semantic_similarity(
    original_text: str, generated_text: str
) -> dict:
    """Compare the semantic similarity between original paper and generated story.

    Uses embedding-based comparison with chunking for long texts.

    Args:
        original_text: The original research paper text.
        generated_text: The generated story text.

    Returns:
        A dict with similarity_score and interpretation.
    """
    if not original_text or not original_text.strip():
        return {"error": "Original text is empty."}
    if not generated_text or not generated_text.strip():
        return {"error": "Generated text is empty."}

    try:
        client = _get_genai_client()

        # Chunk and embed both texts (batch API for fewer round trips)
        original_chunks = _chunk_text(original_text)
        generated_chunks = _chunk_text(generated_text)

        original_embeddings = _batch_embed(client, original_chunks)
        generated_embeddings = _batch_embed(client, generated_chunks)

        # Average the chunk embeddings
        avg_original = _average_vectors(original_embeddings)
        avg_generated = _average_vectors(generated_embeddings)

        # Compute similarity
        score = _cosine_similarity(avg_original, avg_generated)

        if score > 0.8:
            interpretation = "high"
        elif score >= 0.6:
            interpretation = "moderate"
        else:
            interpretation = "low"

        return {
            "similarity_score": round(score, 4),
            "interpretation": interpretation,
        }

    except Exception as e:
        return {"error": f"Embedding comparison failed: {e}"}


# Words that indicate factual content worth extracting as claims
_FACTUAL_INDICATORS = {
    "found", "demonstrated", "showed", "revealed", "observed",
    "increased", "decreased", "reduced", "improved", "achieved",
    "significant", "significantly", "compared", "outperformed",
    "resulted", "confirmed", "concluded", "suggests", "indicates",
    "measured", "detected", "identified", "determined", "estimated",
}

# Section headers that contain the most important factual claims
_PRIORITY_SECTIONS = {
    "abstract", "results", "conclusion", "conclusions", "findings",
    "discussion", "summary", "key findings",
}


def _score_paragraph(paragraph: str) -> float:
    """Score a paragraph by factual indicator density."""
    words = paragraph.lower().split()
    if not words:
        return 0.0
    indicator_count = sum(1 for w in words if w.strip(".,;:()") in _FACTUAL_INDICATORS)
    # Also boost paragraphs with numbers/percentages (likely quantitative claims)
    has_numbers = any(c.isdigit() for c in paragraph)
    number_bonus = 0.3 if has_numbers else 0.0
    return (indicator_count / len(words)) + number_bonus


def _identify_section(text: str, position: int) -> str | None:
    """Try to identify which section a paragraph belongs to by looking backwards."""
    # Look at the text before this position for section headers
    preceding = text[:position].lower()
    best_section = None
    best_pos = -1
    for section in _PRIORITY_SECTIONS:
        pos = preceding.rfind(section)
        if pos > best_pos:
            best_pos = pos
            best_section = section
    return best_section


def extract_key_claims(paper_text: str, max_claims: int = 15) -> dict:
    """Extract key factual claims from the paper text.

    Uses section-aware extraction (prioritizing Abstract/Results/Conclusion)
    and factual indicator scoring to find the most important claims.

    Args:
        paper_text: The full text of the research paper.
        max_claims: Maximum number of claims to extract.

    Returns:
        A dict with claims list and count.
    """
    if not paper_text or not paper_text.strip():
        return {"error": "Paper text is empty."}

    # Split into paragraphs (double newline or single newline with blank)
    paragraphs = [
        p.strip() for p in paper_text.split("\n\n") if p.strip()
    ]

    # If few paragraphs, try single newline split
    if len(paragraphs) < 3:
        paragraphs = [
            p.strip() for p in paper_text.split("\n") if p.strip()
        ]

    # Filter out very short paragraphs (likely headers/labels)
    paragraphs = [p for p in paragraphs if len(p.split()) >= 10]

    if not paragraphs:
        return {"claims": [], "count": 0}

    # Score and rank paragraphs
    scored: list[tuple[float, str]] = []
    for para in paragraphs:
        # Find position in original text for section identification
        pos = paper_text.find(para[:50])
        section = _identify_section(paper_text, pos) if pos >= 0 else None

        score = _score_paragraph(para)
        # Boost paragraphs from priority sections
        if section in _PRIORITY_SECTIONS:
            score += 0.5

        scored.append((score, para))

    # Sort by score descending, take top claims
    scored.sort(key=lambda x: x[0], reverse=True)
    claims = [para for _, para in scored[:max_claims]]

    return {
        "claims": claims,
        "count": len(claims),
    }


def compare_claim_coverage(
    paper_text: str, story_text: str, claims: list[str] | str | None = None
) -> dict:
    """Compare individual claims from the paper against story text chunks.

    Embeds each claim individually and finds the best-matching 200-word chunk
    in the story. Returns per-claim coverage scores.

    Args:
        paper_text: The original research paper text (used if claims not provided).
        story_text: The generated story text.
        claims: Optional pre-extracted claims. If not provided, extracts from paper_text.

    Returns:
        A dict with per-claim scores and overall coverage summary.
    """
    if not story_text or not story_text.strip():
        return {"error": "Story text is empty."}

    # Handle claims passed as JSON string (ADK FunctionTool behavior)
    if isinstance(claims, str):
        import json
        try:
            claims = json.loads(claims)
        except (json.JSONDecodeError, TypeError):
            claims = None

    # Extract claims if not provided
    if not claims:
        if not paper_text or not paper_text.strip():
            return {"error": "Paper text is empty and no claims provided."}
        result = extract_key_claims(paper_text)
        if "error" in result:
            return result
        claims = result["claims"]

    if not claims:
        return {"error": "No claims extracted."}

    try:
        client = _get_genai_client()

        # Chunk story into 200-word overlapping windows
        story_chunks = _chunk_text(story_text, chunk_size=200)
        if not story_chunks:
            return {"error": "Story text produced no chunks."}

        # Embed all story chunks in one batch
        story_embeddings = _batch_embed(client, story_chunks)

        # Embed all claims in one batch
        claim_embeddings = _batch_embed(client, claims)

        # For each claim, find the best-matching story chunk
        coverage_threshold = 0.65
        claim_results = []
        covered_count = 0

        for i, claim_emb in enumerate(claim_embeddings):
            best_score = 0.0
            for story_emb in story_embeddings:
                sim = _cosine_similarity(claim_emb, story_emb)
                if sim > best_score:
                    best_score = sim

            status = "covered" if best_score >= coverage_threshold else "missing"
            if status == "covered":
                covered_count += 1

            # Truncate claim for readability
            claim_preview = claims[i][:120] + "..." if len(claims[i]) > 120 else claims[i]
            claim_results.append({
                "claim": claim_preview,
                "best_match_score": round(best_score, 4),
                "status": status,
            })

        total = len(claims)
        coverage_pct = round(covered_count / total * 100, 1) if total > 0 else 0.0

        return {
            "claim_results": claim_results,
            "total_claims": total,
            "covered_claims": covered_count,
            "coverage_percentage": coverage_pct,
            "overall_status": "good" if coverage_pct >= 60 else "needs_improvement",
        }

    except Exception as e:
        return {"error": f"Claim coverage comparison failed: {e}"}
