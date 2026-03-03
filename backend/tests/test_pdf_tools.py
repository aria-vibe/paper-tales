"""Tests for papertales.tools.pdf_tools."""

import pytest

from papertales.tools.pdf_tools import (
    _extract_arxiv_id,
    extract_text_from_pdf,
    fetch_arxiv_paper,
)


# ---------------------------------------------------------------------------
# _extract_arxiv_id
# ---------------------------------------------------------------------------


class TestExtractArxivId:
    def test_abs_url(self):
        assert _extract_arxiv_id("https://arxiv.org/abs/2301.12345") == "2301.12345"

    def test_pdf_url(self):
        assert _extract_arxiv_id("https://arxiv.org/pdf/2301.12345") == "2301.12345"

    def test_versioned_url(self):
        assert _extract_arxiv_id("https://arxiv.org/abs/2301.12345v2") == "2301.12345"

    def test_old_style_url(self):
        assert _extract_arxiv_id("https://arxiv.org/abs/hep-th/9901001") == "hep-th/9901001"

    def test_bare_id(self):
        assert _extract_arxiv_id("2301.12345") == "2301.12345"

    def test_invalid_url(self):
        assert _extract_arxiv_id("https://example.com/paper") is None

    def test_http_url(self):
        assert _extract_arxiv_id("http://arxiv.org/abs/2301.12345") == "2301.12345"


# ---------------------------------------------------------------------------
# extract_text_from_pdf
# ---------------------------------------------------------------------------


class TestExtractTextFromPdf:
    def test_file_not_found(self):
        result = extract_text_from_pdf("/nonexistent/path.pdf")
        assert "error" in result

    def test_extracts_text_from_generated_pdf(self, sample_pdf):
        result = extract_text_from_pdf(sample_pdf)

        assert "error" not in result
        assert result["pages"] == 2
        assert "automated testing" in result["text"]
        assert result["metadata"]["title"] == "On the Importance of Testing"
        assert "Alice Smith" in result["metadata"]["authors"]

    def test_abstract_extraction(self, sample_pdf):
        result = extract_text_from_pdf(sample_pdf)
        abstract = result["metadata"]["abstract"]
        assert "automated testing" in abstract or "test suites" in abstract


# ---------------------------------------------------------------------------
# fetch_arxiv_paper (integration — requires network)
# ---------------------------------------------------------------------------


class TestFetchArxivPaper:
    def test_invalid_url_returns_error(self):
        result = fetch_arxiv_paper("not-a-valid-url")
        assert "error" in result

    @pytest.mark.integration
    def test_fetch_known_paper(self):
        """Fetch 'Attention Is All You Need' — requires network access."""
        result = fetch_arxiv_paper("https://arxiv.org/abs/1706.03762")

        assert "error" not in result, f"Got error: {result.get('error')}"
        assert result["pages"] > 0
        assert result["metadata"]["arxiv_id"] == "1706.03762"
        assert "attention" in result["text"].lower()
