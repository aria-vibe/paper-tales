"""Tests for paper search module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from papertales.paper_search import (
    ArxivResult,
    PaperNotFoundError,
    RefinedQuery,
    SearchResult,
    SearchServiceError,
    _parse_arxiv_xml,
    _parse_refined_response,
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
# _parse_refined_response
# ---------------------------------------------------------------------------


class TestParseRefinedResponse:
    def test_parses_arxiv_id(self):
        r = _parse_refined_response("ARXIV:1706.03762")
        assert r.arxiv_id == "1706.03762"
        assert r.title is None
        assert r.keywords == ""

    def test_parses_title(self):
        r = _parse_refined_response("TITLE:Attention Is All You Need")
        assert r.title == "Attention Is All You Need"
        assert r.arxiv_id is None

    def test_parses_keywords(self):
        r = _parse_refined_response("KEYWORDS:transformer attention mechanism")
        assert r.keywords == "transformer attention mechanism"
        assert r.arxiv_id is None
        assert r.title is None

    def test_fallback_to_keywords_on_unrecognized(self):
        r = _parse_refined_response("transformer attention mechanism")
        assert r.keywords == "transformer attention mechanism"

    def test_rejects_invalid_arxiv_id(self):
        r = _parse_refined_response("ARXIV:not-a-real-id")
        assert r.arxiv_id is None
        # Falls through to treat as raw keywords
        assert r.keywords == "ARXIV:not-a-real-id"

    def test_case_insensitive_prefix(self):
        r = _parse_refined_response("arxiv:1706.03762")
        assert r.arxiv_id == "1706.03762"

    def test_handles_5_digit_id(self):
        r = _parse_refined_response("ARXIV:2301.12345")
        assert r.arxiv_id == "2301.12345"

    def test_handles_whitespace(self):
        r = _parse_refined_response("  ARXIV:1706.03762  ")
        assert r.arxiv_id == "1706.03762"


# ---------------------------------------------------------------------------
# refine_query_with_llm
# ---------------------------------------------------------------------------


class TestRefineQueryWithLlm:
    @patch("papertales.paper_search._call_llm")
    def test_returns_arxiv_id_when_known(self, mock_call_llm):
        mock_call_llm.return_value = "ARXIV:1706.03762"

        result = asyncio.get_event_loop().run_until_complete(
            refine_query_with_llm("what is LLM")
        )
        assert result.arxiv_id == "1706.03762"

    @patch("papertales.paper_search._call_llm")
    def test_returns_title_when_known(self, mock_call_llm):
        mock_call_llm.return_value = "TITLE:Attention Is All You Need"

        result = asyncio.get_event_loop().run_until_complete(
            refine_query_with_llm("what is a transformer")
        )
        assert result.title == "Attention Is All You Need"

    @patch("papertales.paper_search._call_llm")
    def test_returns_keywords_fallback(self, mock_call_llm):
        mock_call_llm.return_value = "KEYWORDS:vaccine immune response survey"

        result = asyncio.get_event_loop().run_until_complete(
            refine_query_with_llm("how do vaccines work")
        )
        assert result.keywords == "vaccine immune response survey"

    @patch("papertales.paper_search._call_llm")
    def test_raises_on_llm_failure(self, mock_call_llm):
        mock_call_llm.side_effect = Exception("API error")

        with pytest.raises(SearchServiceError):
            asyncio.get_event_loop().run_until_complete(
                refine_query_with_llm("what is a transformer")
            )

    @patch("papertales.paper_search._call_llm")
    def test_prompt_includes_strategy_instructions(self, mock_call_llm):
        mock_call_llm.return_value = "KEYWORDS:test"
        asyncio.get_event_loop().run_until_complete(
            refine_query_with_llm("what is X")
        )
        prompt = mock_call_llm.call_args[0][0]
        assert "ARXIV:" in prompt
        assert "TITLE:" in prompt
        assert "KEYWORDS:" in prompt
        assert "foundational" in prompt.lower() or "seminal" in prompt.lower()


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

    @patch("papertales.paper_search._call_llm")
    def test_selects_llm_choice(self, mock_call_llm):
        mock_call_llm.return_value = "2"

        results = [
            ArxivResult(title="Paper A", arxiv_id="001", url="url1", summary="A", authors=[]),
            ArxivResult(title="Paper B", arxiv_id="002", url="url2", summary="B", authors=[]),
        ]
        best = asyncio.get_event_loop().run_until_complete(
            select_best_result("test", results)
        )
        assert best == results[1]

    @patch("papertales.paper_search._call_llm")
    def test_prefers_foundational_papers_in_prompt(self, mock_call_llm):
        mock_call_llm.return_value = "1"

        results = [
            ArxivResult(title="Paper A", arxiv_id="001", url="url1", summary="A", authors=[]),
            ArxivResult(title="Paper B", arxiv_id="002", url="url2", summary="B", authors=[]),
        ]
        asyncio.get_event_loop().run_until_complete(
            select_best_result("what is X", results)
        )
        prompt = mock_call_llm.call_args[0][0]
        assert "INTRODUCE" in prompt or "DEFINE" in prompt or "EXPLAIN" in prompt

    @patch("papertales.paper_search._call_llm")
    def test_falls_back_to_first_on_llm_error(self, mock_call_llm):
        mock_call_llm.side_effect = Exception("fail")

        results = [
            ArxivResult(title="Paper A", arxiv_id="001", url="url1", summary="A", authors=[]),
            ArxivResult(title="Paper B", arxiv_id="002", url="url2", summary="B", authors=[]),
        ]
        best = asyncio.get_event_loop().run_until_complete(
            select_best_result("test", results)
        )
        assert best == results[0]


# ---------------------------------------------------------------------------
# search_paper (end-to-end with mocks)
# ---------------------------------------------------------------------------


class TestSearchPaper:
    @patch("papertales.paper_search.fetch_arxiv_by_id")
    @patch("papertales.paper_search.refine_query_with_llm")
    def test_tier1_direct_id_lookup(self, mock_refine, mock_fetch_id):
        """When LLM returns an arXiv ID, fetch directly without keyword search."""
        mock_refine.return_value = RefinedQuery(arxiv_id="1706.03762")
        mock_fetch_id.return_value = [
            ArxivResult(
                title="Attention Is All You Need",
                arxiv_id="1706.03762",
                url="https://arxiv.org/abs/1706.03762",
                summary="The dominant sequence...",
                authors=["Vaswani"],
            )
        ]

        result = asyncio.get_event_loop().run_until_complete(
            search_paper("what is LLM")
        )
        assert result.paper_title == "Attention Is All You Need"
        assert result.arxiv_id == "1706.03762"
        mock_fetch_id.assert_called_once_with("1706.03762")

    @patch("papertales.paper_search.search_arxiv_by_title")
    @patch("papertales.paper_search.fetch_arxiv_by_id")
    @patch("papertales.paper_search.refine_query_with_llm")
    def test_tier2_title_search(self, mock_refine, mock_fetch_id, mock_title_search):
        """When LLM returns a title, search by title."""
        mock_refine.return_value = RefinedQuery(title="Attention Is All You Need")
        mock_fetch_id.return_value = []  # No direct ID
        mock_title_search.return_value = [
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
        assert result.paper_title == "Attention Is All You Need"

    @patch("papertales.paper_search.search_arxiv")
    @patch("papertales.paper_search.refine_query_with_llm")
    def test_tier3_keyword_fallback(self, mock_refine, mock_search):
        """When LLM returns only keywords, fall back to keyword search."""
        mock_refine.return_value = RefinedQuery(keywords="vaccine immune response survey")
        mock_search.return_value = [
            ArxivResult(
                title="A Survey of Vaccine Mechanisms",
                arxiv_id="2301.00001",
                url="https://arxiv.org/abs/2301.00001",
                summary="Vaccines work by...",
                authors=["Author"],
            )
        ]

        result = asyncio.get_event_loop().run_until_complete(
            search_paper("how do vaccines work")
        )
        assert result.paper_title == "A Survey of Vaccine Mechanisms"

    @patch("papertales.paper_search.search_arxiv")
    @patch("papertales.paper_search.fetch_arxiv_by_id")
    @patch("papertales.paper_search.refine_query_with_llm")
    def test_tier1_miss_falls_to_tier3(self, mock_refine, mock_fetch_id, mock_search):
        """When direct ID lookup fails, fall through to keyword search."""
        mock_refine.return_value = RefinedQuery(arxiv_id="9999.99999", keywords="test query")
        mock_fetch_id.return_value = []  # ID not found
        mock_search.return_value = [
            ArxivResult(
                title="Fallback Paper",
                arxiv_id="2301.00001",
                url="https://arxiv.org/abs/2301.00001",
                summary="Found via keywords",
                authors=["Author"],
            )
        ]

        result = asyncio.get_event_loop().run_until_complete(
            search_paper("some question")
        )
        assert result.paper_title == "Fallback Paper"

    def test_empty_query_raises(self):
        with pytest.raises(PaperNotFoundError):
            asyncio.get_event_loop().run_until_complete(search_paper(""))

    @patch("papertales.paper_search.search_arxiv")
    @patch("papertales.paper_search.refine_query_with_llm")
    def test_no_results_raises(self, mock_refine, mock_search):
        mock_refine.return_value = RefinedQuery(keywords="xyznonexistent")
        mock_search.return_value = []

        with pytest.raises(PaperNotFoundError):
            asyncio.get_event_loop().run_until_complete(
                search_paper("xyznonexistent gibberish query")
            )
