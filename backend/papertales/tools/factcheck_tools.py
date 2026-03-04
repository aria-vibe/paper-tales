"""Tools for fact-checking generated stories against source papers."""

import math

from google import genai

EMBEDDING_MODEL = "gemini-embedding-001"
CHUNK_SIZE = 500  # words per chunk


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
        client = genai.Client()

        # Chunk and embed both texts
        original_chunks = _chunk_text(original_text)
        generated_chunks = _chunk_text(generated_text)

        original_embeddings = []
        for chunk in original_chunks:
            result = client.models.embed_content(
                model=EMBEDDING_MODEL, contents=chunk
            )
            original_embeddings.append(result.embeddings[0].values)

        generated_embeddings = []
        for chunk in generated_chunks:
            result = client.models.embed_content(
                model=EMBEDDING_MODEL, contents=chunk
            )
            generated_embeddings.append(result.embeddings[0].values)

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


def extract_key_claims(paper_text: str, max_claims: int = 10) -> dict:
    """Extract key factual claims from the paper text.

    Splits the paper into paragraph-level chunks and returns the top
    paragraphs as claims for the LLM agent to reason about.

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
    claims = [p for p in paragraphs if len(p.split()) >= 10]

    # Limit to max_claims
    claims = claims[:max_claims]

    return {
        "claims": claims,
        "count": len(claims),
    }
