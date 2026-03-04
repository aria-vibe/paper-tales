"""URL whitelist for supported research paper archives."""

import re
from urllib.parse import urlparse

ARCHIVE_WHITELIST: dict[str, dict] = {
    "arxiv.org": {
        "name": "arXiv",
        "id_pattern": r"/(?:abs|pdf|html)/([a-z\-]+/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?",
    },
    "medrxiv.org": {
        "name": "medRxiv",
        "id_pattern": r"/content/([0-9]{4}\.[0-9]{2}\.[0-9]{2}\.[0-9]+)(?:v\d+)?",
    },
    "biorxiv.org": {
        "name": "bioRxiv",
        "id_pattern": r"/content/([0-9]{4}\.[0-9]{2}\.[0-9]{2}\.[0-9]+)(?:v\d+)?",
    },
    "chemrxiv.org": {
        "name": "ChemRxiv",
        "id_pattern": r"/engage/(?:chemrxiv/)?article-details/([a-f0-9\-]+)",
    },
    "ssrn.com": {
        "name": "SSRN",
        "id_pattern": r"/abstract=(\d+)",
    },
    "eartharxiv.org": {
        "name": "EarthArXiv",
        "id_pattern": r"/repository/view/(\d+)",
    },
    "psyarxiv.com": {
        "name": "PsyArXiv",
        "id_pattern": r"/([a-z0-9]+)/?$",
    },
    "osf.io": {
        "name": "OSF Preprints",
        "id_pattern": r"/(?:preprints/[^/]+/)?([a-z0-9]+)/?$",
    },
}


def validate_archive_url(url: str) -> tuple[str, str, str]:
    """Validate URL against archive whitelist and extract paper ID.

    Args:
        url: The URL to validate.

    Returns:
        Tuple of (normalized_url, archive_name, paper_id).

    Raises:
        ValueError: If URL is not from a supported archive or ID can't be extracted.
    """
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    # Strip www. prefix
    if hostname.startswith("www."):
        hostname = hostname[4:]

    archive = ARCHIVE_WHITELIST.get(hostname)
    if not archive:
        supported = ", ".join(sorted(ARCHIVE_WHITELIST.keys()))
        raise ValueError(
            f"Unsupported archive: {hostname}. Supported: {supported}"
        )

    match = re.search(archive["id_pattern"], parsed.path)
    if not match:
        raise ValueError(
            f"Could not extract paper ID from {archive['name']} URL: {url}"
        )

    paper_id = match.group(1)

    # Normalize to https
    normalized = url.replace("http://", "https://")

    return normalized, archive["name"], paper_id


def get_supported_archives() -> list[str]:
    """Return list of supported archive domain names."""
    return sorted(ARCHIVE_WHITELIST.keys())
