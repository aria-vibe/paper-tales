"""Tests for paper search module."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from papertales.paper_search import (
    ArxivResult,
    PaperNotFoundError,
    SearchResult,
    SearchServiceError,
    _parse_arxiv_xml,
    is_url_input,
    refine_query_with_llm,
    search_arxiv,
    search_paper,
    select_best_result,
)


# ---------------------------------------------------------------------------
# is_url_input
# ---------------------------------------------------------------------------


class TestIsUrlInput:
    def test_https_url(self):
        assert is_url_input("https://arxiv.org/abs/2301.12345") is True

    def test_http_url(self):
        assert is_url_input("http://arxiv.org/abs/2301.12345") is True

    def test_domain_without_protocol(self):
        assert is_url_input("arxiv.org/abs/2301.12345") is True

    def test_biorxiv_domain(self):
        assert is_url_input("biorxiv.org/content/123") is True

    def test_natural_language_question(self):
        assert is_url_input("what is a transformer") is False

    def test_whitespace_url(self):
        assert is_url_input("  https://arxiv.org/abs/123  ") is True

    def test_empty_string(self):
        assert is_url_input("") is False

    def test_random_text(self):
        assert is_url_input("how do vaccines work") is False


# ---------------------------------------------------------------------------
# _parse_arxiv_xml
# ---------------------------------------------------------------------------

SAMPLE_ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1706.03762v7</id>
    <title>Attention Is All You Need</title>
    <summary>The dominant sequence transduction models are based on complex recurrent neural networks.</summary>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2005.14165v4</id>
    <title>Language Models are Few-Shot Learners</title>
    <summary>Recent work has demonstrated substantial gains on NLP tasks.</summary>
    <author><name>Tom Brown</name></author>
  </entry>
</feed>"""

EMPTY_ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
</feed>"""


class TestParseArxivXml:
    def test_parses_two_entries(self):
        results = _parse_arxiv_xml(SAMPLE_ARXIV_XML)
        assert len(results) == 2

    def test_extracts_title(self):
        results = _parse_arxiv_xml(SAMPLE_ARXIV_XML)
        assert results[0].title == "Attention Is All You Need"

    def test_extracts_arxiv_id_strips_version(self):
        results = _parse_arxiv_xml(SAMPLE_ARXIV_XML)
        assert results[0].arxiv_id == "1706.03762"

    def test_constructs_url(self):
        results = _parse_arxiv_xml(SAMPLE_ARXIV_XML)
        assert results[0].url == "https://arxiv.org/abs/1706.03762"

    def test_extracts_authors(self):
        results = _parse_arxiv_xml(SAMPLE_ARXIV_XML)
        assert results[0].authors == ["Ashish Vaswani", "Noam Shazeer"]

    def test_empty_feed(self):
        results = _parse_arxiv_xml(EMPTY_ARXIV_XML)
        assert results == []


# ---------------------------------------------------------------------------
# refine_query_with_llm
# ---------------------------------------------------------------------------


class TestRefineQueryWithLlm:
    @patch("papertales.paper_search.genai.Client")
    def test_returns_refined_keywords(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_response = MagicMock()
        mock_response.text = "transformer attention mechanism self-attention"
        mock_client.models.generate_content.return_value = mock_response
        # Reset singleton
        import papertales.paper_search as ps
        ps._genai_client = None

        result = asyncio.get_event_loop().run_until_complete(
            refine_query_with_llm("what is a transformer")
        )
        assert result == "transformer attention mechanism self-attention"
        ps._genai_client = None

    @patch("papertales.paper_search.genai.Client")
    def test_raises_on_llm_failure(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.models.generate_content.side_effect = Exception("API error")
        import papertales.paper_search as ps
        ps._genai_client = None

        with pytest.raises(SearchServiceError):
            asyncio.get_event_loop().run_until_complete(
                refine_query_with_llm("what is a transformer")
            )
        ps._genai_client = None


# ---------------------------------------------------------------------------
# select_best_result
# ---------------------------------------------------------------------------


class TestSelectBestResult:
    def test_returns_none_for_empty_list(self):
        result = asyncio.get_event_loop().run_until_complete(
            select_best_result("test", [])
        )
        assert result is None

    def test_returns_single_result_without_llm(self):
        single = ArxivResult(
            title="Test Paper", arxiv_id="2301.00001",
            url="https://arxiv.org/abs/2301.00001", summary="Test", authors=["Author"]
        )
        result = asyncio.get_event_loop().run_until_complete(
            select_best_result("test", [single])
        )
        assert result == single

    @patch("papertales.paper_search.genai.Client")
    def test_selects_llm_choice(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_response = MagicMock()
        mock_response.text = "2"
        mock_client.models.generate_content.return_value = mock_response
        import papertales.paper_search as ps
        ps._genai_client = None

        results = [
            ArxivResult(title="Paper A", arxiv_id="001", url="url1", summary="A", authors=[]),
            ArxivResult(title="Paper B", arxiv_id="002", url="url2", summary="B", authors=[]),
        ]
        best = asyncio.get_event_loop().run_until_complete(
            select_best_result("test", results)
        )
        assert best == results[1]
        ps._genai_client = None

    @patch("papertales.paper_search.genai.Client")
    def test_falls_back_to_first_on_llm_error(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.models.generate_content.side_effect = Exception("fail")
        import papertales.paper_search as ps
        ps._genai_client = None

        results = [
            ArxivResult(title="Paper A", arxiv_id="001", url="url1", summary="A", authors=[]),
            ArxivResult(title="Paper B", arxiv_id="002", url="url2", summary="B", authors=[]),
        ]
        best = asyncio.get_event_loop().run_until_complete(
            select_best_result("test", results)
        )
        assert best == results[0]
        ps._genai_client = None


# ---------------------------------------------------------------------------
# search_paper (end-to-end with mocks)
# ---------------------------------------------------------------------------


class TestSearchPaper:
    @patch("papertales.paper_search.search_arxiv")
    @patch("papertales.paper_search.refine_query_with_llm")
    def test_end_to_end(self, mock_refine, mock_search):
        mock_refine.return_value = "transformer attention"
        mock_search.return_value = [
            ArxivResult(
                title="Attention Is All You Need",
                arxiv_id="1706.03762",
                url="https://arxiv.org/abs/1706.03762",
                summary="The dominant sequence...",
                authors=["Vaswani"],
            )
        ]

        result = asyncio.get_event_loop().run_until_complete(
            search_paper("what is a transformer")
        )
        assert isinstance(result, SearchResult)
        assert result.paper_url == "https://arxiv.org/abs/1706.03762"
        assert result.paper_title == "Attention Is All You Need"

    def test_empty_query_raises(self):
        with pytest.raises(PaperNotFoundError):
            asyncio.get_event_loop().run_until_complete(search_paper(""))

    @patch("papertales.paper_search.search_arxiv")
    @patch("papertales.paper_search.refine_query_with_llm")
    def test_no_results_raises(self, mock_refine, mock_search):
        mock_refine.return_value = "xyznonexistent"
        mock_search.return_value = []

        with pytest.raises(PaperNotFoundError):
            asyncio.get_event_loop().run_until_complete(
                search_paper("xyznonexistent gibberish query")
            )
