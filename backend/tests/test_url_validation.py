"""Tests for URL validation and archive whitelist."""

import pytest

from papertales.url_validation import get_supported_archives, validate_archive_url


class TestValidateArchiveUrl:
    """Test URL validation against the archive whitelist."""

    # ------------------------------------------------------------------
    # arXiv
    # ------------------------------------------------------------------

    def test_arxiv_abs_url(self):
        url, archive, paper_id = validate_archive_url("https://arxiv.org/abs/2301.12345")
        assert archive == "arXiv"
        assert paper_id == "2301.12345"
        assert url.startswith("https://")

    def test_arxiv_pdf_url(self):
        url, archive, paper_id = validate_archive_url("https://arxiv.org/pdf/2301.12345")
        assert archive == "arXiv"
        assert paper_id == "2301.12345"

    def test_arxiv_with_version(self):
        url, archive, paper_id = validate_archive_url("https://arxiv.org/abs/2301.12345v2")
        assert archive == "arXiv"
        assert paper_id == "2301.12345"

    def test_arxiv_old_style(self):
        url, archive, paper_id = validate_archive_url("https://arxiv.org/abs/hep-th/9901001")
        assert archive == "arXiv"
        assert paper_id == "hep-th/9901001"

    def test_arxiv_http_normalized(self):
        url, archive, paper_id = validate_archive_url("http://arxiv.org/abs/2301.12345")
        assert url.startswith("https://")

    # ------------------------------------------------------------------
    # bioRxiv / medRxiv
    # ------------------------------------------------------------------

    def test_biorxiv(self):
        url, archive, paper_id = validate_archive_url(
            "https://biorxiv.org/content/2024.01.15.575634"
        )
        assert archive == "bioRxiv"
        assert paper_id == "2024.01.15.575634"

    def test_medrxiv(self):
        url, archive, paper_id = validate_archive_url(
            "https://medrxiv.org/content/2024.03.20.24304567"
        )
        assert archive == "medRxiv"
        assert paper_id == "2024.03.20.24304567"

    def test_medrxiv_with_version(self):
        url, archive, paper_id = validate_archive_url(
            "https://medrxiv.org/content/2024.03.20.24304567v1"
        )
        assert archive == "medRxiv"
        assert paper_id == "2024.03.20.24304567"

    # ------------------------------------------------------------------
    # SSRN
    # ------------------------------------------------------------------

    def test_ssrn(self):
        url, archive, paper_id = validate_archive_url(
            "https://ssrn.com/abstract=4567890"
        )
        assert archive == "SSRN"
        assert paper_id == "4567890"

    # ------------------------------------------------------------------
    # Other archives
    # ------------------------------------------------------------------

    def test_psyarxiv(self):
        url, archive, paper_id = validate_archive_url(
            "https://psyarxiv.com/abc12"
        )
        assert archive == "PsyArXiv"
        assert paper_id == "abc12"

    def test_osf_preprints(self):
        url, archive, paper_id = validate_archive_url(
            "https://osf.io/preprints/socarxiv/xyz99"
        )
        assert archive == "OSF Preprints"
        assert paper_id == "xyz99"

    # ------------------------------------------------------------------
    # Rejection cases
    # ------------------------------------------------------------------

    def test_rejects_non_whitelisted_url(self):
        with pytest.raises(ValueError, match="Unsupported archive"):
            validate_archive_url("https://example.com/paper.pdf")

    def test_rejects_random_domain(self):
        with pytest.raises(ValueError, match="Unsupported archive"):
            validate_archive_url("https://google.com/search?q=papers")

    def test_rejects_arxiv_invalid_path(self):
        with pytest.raises(ValueError, match="Could not extract paper ID"):
            validate_archive_url("https://arxiv.org/list/cs.AI/recent")

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_strips_whitespace(self):
        url, archive, paper_id = validate_archive_url("  https://arxiv.org/abs/2301.12345  ")
        assert paper_id == "2301.12345"

    def test_adds_https_if_missing(self):
        url, archive, paper_id = validate_archive_url("arxiv.org/abs/2301.12345")
        assert url.startswith("https://")
        assert paper_id == "2301.12345"

    def test_www_prefix_stripped(self):
        url, archive, paper_id = validate_archive_url("https://www.arxiv.org/abs/2301.12345")
        assert archive == "arXiv"
        assert paper_id == "2301.12345"


class TestGetSupportedArchives:
    def test_returns_sorted_list(self):
        archives = get_supported_archives()
        assert isinstance(archives, list)
        assert archives == sorted(archives)
        assert "arxiv.org" in archives
        assert "biorxiv.org" in archives

    def test_contains_all_archives(self):
        archives = get_supported_archives()
        assert len(archives) == 8
