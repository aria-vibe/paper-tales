"""Shared fixtures for PaperTales backend tests."""

import tempfile

import fitz
import pytest


@pytest.fixture
def sample_pdf(tmp_path):
    """Generate a minimal test PDF with metadata, abstract, and body text."""
    pdf_path = tmp_path / "test_paper.pdf"

    doc = fitz.open()

    # Set metadata
    doc.set_metadata({
        "title": "On the Importance of Testing",
        "author": "Alice Smith, Bob Jones",
    })

    # Page 1 — abstract + intro
    page = doc.new_page(width=612, height=792)
    text = (
        "Abstract\n\n"
        "This paper investigates the role of automated testing in modern "
        "software engineering. We demonstrate that comprehensive test suites "
        "reduce defect rates by 40%.\n\n"
        "1. Introduction\n\n"
        "Software testing is a critical practice in engineering reliable systems. "
        "In this work, we present a framework for evaluating test effectiveness."
    )
    page.insert_text((72, 72), text, fontsize=11)

    # Page 2 — methods
    page2 = doc.new_page(width=612, height=792)
    text2 = (
        "2. Methods\n\n"
        "We collected data from 50 open-source projects and measured defect "
        "density before and after introducing automated test suites."
    )
    page2.insert_text((72, 72), text2, fontsize=11)

    doc.save(str(pdf_path))
    doc.close()

    return str(pdf_path)
