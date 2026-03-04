"""Tests for papertales.tools.factcheck_tools."""

from unittest.mock import MagicMock, patch

import pytest

from papertales.tools.factcheck_tools import (
    _average_vectors,
    _chunk_text,
    _cosine_similarity,
    compare_semantic_similarity,
    extract_key_claims,
)


# ===========================================================================
# Unit tests for helper functions
# ===========================================================================


class TestChunkText:
    def test_short_text_single_chunk(self):
        text = "hello world foo bar"
        chunks = _chunk_text(text, chunk_size=10)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_multiple_chunks(self):
        words = ["word"] * 25
        text = " ".join(words)
        chunks = _chunk_text(text, chunk_size=10)
        assert len(chunks) == 3
        assert len(chunks[0].split()) == 10
        assert len(chunks[2].split()) == 5

    def test_empty_text(self):
        assert _chunk_text("") == []
        assert _chunk_text("   ") == []


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert _cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert _cosine_similarity(a, b) == pytest.approx(0.0)

    def test_zero_vector(self):
        a = [0.0, 0.0]
        b = [1.0, 2.0]
        assert _cosine_similarity(a, b) == 0.0


class TestAverageVectors:
    def test_single_vector(self):
        result = _average_vectors([[1.0, 2.0, 3.0]])
        assert result == [1.0, 2.0, 3.0]

    def test_two_vectors(self):
        result = _average_vectors([[2.0, 4.0], [4.0, 6.0]])
        assert result == [3.0, 5.0]

    def test_empty_list(self):
        assert _average_vectors([]) == []


# ===========================================================================
# TestCompareSemanticSimilarity (mocked embeddings)
# ===========================================================================


class TestCompareSemanticSimilarity:
    @patch("papertales.tools.factcheck_tools.genai.Client")
    def test_valid_inputs_returns_similarity(self, mock_client_cls):
        """Two texts should produce a similarity score and interpretation."""
        mock_client = mock_client_cls.return_value
        mock_embedding = MagicMock()
        mock_embedding.values = [0.5, 0.5, 0.5]
        mock_result = MagicMock()
        mock_result.embeddings = [mock_embedding]
        mock_client.models.embed_content.return_value = mock_result

        result = compare_semantic_similarity(
            "Photosynthesis converts sunlight into energy.",
            "Plants use sunshine to make food.",
        )

        assert "error" not in result
        assert "similarity_score" in result
        assert 0.0 <= result["similarity_score"] <= 1.0
        assert result["interpretation"] in ("high", "moderate", "low")
        assert mock_client.models.embed_content.call_count >= 2

    @patch("papertales.tools.factcheck_tools.genai.Client")
    def test_identical_text_high_similarity(self, mock_client_cls):
        """Identical texts with identical embeddings should yield score ~1.0."""
        mock_client = mock_client_cls.return_value
        mock_embedding = MagicMock()
        mock_embedding.values = [1.0, 0.0, 1.0]
        mock_result = MagicMock()
        mock_result.embeddings = [mock_embedding]
        mock_client.models.embed_content.return_value = mock_result

        result = compare_semantic_similarity("same text", "same text")

        assert result["similarity_score"] == pytest.approx(1.0)
        assert result["interpretation"] == "high"

    def test_empty_original_returns_error(self):
        result = compare_semantic_similarity("", "Some story text.")
        assert "error" in result

    def test_empty_generated_returns_error(self):
        result = compare_semantic_similarity("Some paper text.", "")
        assert "error" in result

    def test_whitespace_only_returns_error(self):
        result = compare_semantic_similarity("   \n  ", "Some text.")
        assert "error" in result

    @patch("papertales.tools.factcheck_tools.genai.Client")
    def test_api_exception_returns_error(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.models.embed_content.side_effect = Exception("API rate limit")

        result = compare_semantic_similarity("Paper text.", "Story text.")

        assert "error" in result
        assert "API rate limit" in result["error"]

    @patch("papertales.tools.factcheck_tools.genai.Client")
    def test_low_similarity_interpretation(self, mock_client_cls):
        """Different embeddings should yield lower similarity."""
        mock_client = mock_client_cls.return_value

        call_count = [0]

        def side_effect(**kwargs):
            call_count[0] += 1
            mock_embedding = MagicMock()
            if call_count[0] <= 1:
                mock_embedding.values = [1.0, 0.0, 0.0]
            else:
                mock_embedding.values = [0.0, 0.0, 1.0]
            mock_result = MagicMock()
            mock_result.embeddings = [mock_embedding]
            return mock_result

        mock_client.models.embed_content.side_effect = side_effect

        result = compare_semantic_similarity("Paper about X.", "Story about Y.")

        assert result["similarity_score"] < 0.6
        assert result["interpretation"] == "low"


# ===========================================================================
# TestExtractKeyClaims
# ===========================================================================


class TestExtractKeyClaims:
    def test_valid_text_returns_claims(self):
        text = (
            "Photosynthesis is the process by which plants convert sunlight "
            "into chemical energy stored in glucose molecules.\n\n"
            "The light-dependent reactions occur in the thylakoid membranes "
            "and produce ATP and NADPH as energy carriers.\n\n"
            "The Calvin cycle uses these energy carriers to fix carbon dioxide "
            "into organic molecules through a series of enzymatic reactions."
        )
        result = extract_key_claims(text)

        assert "error" not in result
        assert "claims" in result
        assert "count" in result
        assert result["count"] > 0
        assert len(result["claims"]) == result["count"]

    def test_empty_text_returns_error(self):
        result = extract_key_claims("")
        assert "error" in result

    def test_whitespace_only_returns_error(self):
        result = extract_key_claims("   \n\t  ")
        assert "error" in result

    def test_max_claims_respected(self):
        paragraphs = [
            f"This is paragraph number {i} with enough words to pass the minimum filter threshold easily."
            for i in range(20)
        ]
        text = "\n\n".join(paragraphs)
        result = extract_key_claims(text, max_claims=5)

        assert result["count"] <= 5
        assert len(result["claims"]) <= 5

    def test_short_paragraphs_filtered(self):
        """Paragraphs with fewer than 10 words should be filtered out."""
        text = "Short line.\n\nAnother short.\n\nThis is a paragraph with more than ten words in it so it should pass the filter."
        result = extract_key_claims(text)

        assert result["count"] == 1
        assert "more than ten words" in result["claims"][0]

    def test_single_newline_fallback(self):
        """If no double-newline paragraphs, fall back to single newline split."""
        text = (
            "First claim with enough words to be considered a valid paragraph in the system.\n"
            "Second claim also with enough words to make it past the minimum word count filter."
        )
        result = extract_key_claims(text)

        assert result["count"] == 2
