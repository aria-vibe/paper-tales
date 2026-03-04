"""FastAPI entry point for PaperTales."""

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel

from papertales.auth import rate_limiter, verify_firebase_token
from papertales.config import (
    FIELD_TAXONOMY,
    STATE_CONCEPTS,
    STATE_FINAL,
    STATE_PAPER_TEXT,
    STATE_USER_AGE_GROUP,
    STATE_USER_PAPER_URL,
    STATE_USER_STYLE,
)
from papertales.url_validation import validate_archive_url

logger = logging.getLogger(__name__)

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")

# ADK debug UI app
app = get_fast_api_app(
    agents_dir=str(Path(__file__).parent),
    web=True,
    allow_origins=CORS_ORIGINS.split(","),
)

# Lazy-initialized singletons
_runner: InMemoryRunner | None = None
APP_NAME = "papertales"

_firestore_service = None


def _get_runner() -> InMemoryRunner:
    global _runner
    if _runner is None:
        from papertales.agent import root_agent

        _runner = InMemoryRunner(agent=root_agent, app_name=APP_NAME)
    return _runner


def _get_firestore_service():
    global _firestore_service
    if _firestore_service is None:
        from papertales.firestore_service import FirestoreService

        _firestore_service = FirestoreService()
    return _firestore_service


def _extract_field_of_study(concepts_text: str) -> str:
    """Extract field of study from concept extractor output."""
    match = re.search(r"\*\*Field\*\*:\s*(.+?)(?:\n|$)", concepts_text)
    if match:
        field = match.group(1).strip()
        if field in FIELD_TAXONOMY:
            return field
    return "Other"


def _extract_paper_metadata(paper_text: str) -> tuple[str, str]:
    """Extract title and authors from paper parser output."""
    title = ""
    authors = ""

    title_match = re.search(r"\*\*TITLE\*\*:\s*(.+?)(?:\n|$)", paper_text)
    if title_match:
        title = title_match.group(1).strip()

    authors_match = re.search(r"\*\*AUTHORS\*\*:\s*(.+?)(?:\n|$)", paper_text)
    if authors_match:
        authors = authors_match.group(1).strip()

    return title, authors


def _parse_final_story(raw: str, story_id: str) -> dict:
    """Parse agent output into frontend-compatible story JSON."""
    text = raw.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        first_newline = text.index("\n")
        text = text[first_newline + 1 :]
    if text.endswith("```"):
        text = text[:-3].rstrip()

    try:
        story = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        # Fallback: wrap raw text as a single-scene story
        story = {
            "title": "Generated Story",
            "scenes": [{"text": raw}],
        }

    # Normalize keys to camelCase for frontend
    if "age_group" in story:
        story["ageGroup"] = story.pop("age_group")
    if "story_style" in story:
        story["style"] = story.pop("story_style")
    if "source_title" in story:
        story["sourceTitle"] = story.pop("source_title")

    # Convert glossary array to Record<string, string> if needed
    if isinstance(story.get("glossary"), list):
        glossary_dict = {}
        for item in story["glossary"]:
            if isinstance(item, dict) and "term" in item and "definition" in item:
                glossary_dict[item["term"]] = item["definition"]
        story["glossary"] = glossary_dict

    story["id"] = story_id
    story["createdAt"] = datetime.now(timezone.utc).isoformat()

    return story


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/generate")
async def generate_story(
    uid: str = Depends(verify_firebase_token),
    paper_url: str = Form(...),
    age_group: str = Form("10-13"),
    style: str = Form("fairy_tale"),
):
    rate_limiter.check(uid)

    # Validate URL against whitelist
    try:
        normalized_url, archive_name, paper_id = validate_archive_url(paper_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Compute deterministic story ID for dedup
    from papertales.firestore_service import FirestoreService

    story_id = FirestoreService.compute_story_id(paper_id, age_group, style)

    # Check for cached story in Firestore
    fs = _get_firestore_service()
    cached = fs.get_cached_story(story_id)
    if cached:
        # Include user's vote if they have one
        user_vote = fs.get_user_vote(story_id, uid)
        if user_vote:
            cached["userVote"] = user_vote
        return cached

    # Run the pipeline
    runner = _get_runner()
    session = await runner.session_service.create_session(
        app_name=APP_NAME,
        user_id=uid,
        state={
            STATE_USER_PAPER_URL: normalized_url,
            STATE_USER_AGE_GROUP: age_group,
            STATE_USER_STYLE: style,
        },
    )

    trigger = types.Content(
        role="user",
        parts=[
            types.Part(
                text=f"Transform this research paper into an illustrated story for age group {age_group} in {style} style."
            )
        ],
    )

    async for event in runner.run_async(
        user_id=uid,
        session_id=session.id,
        new_message=trigger,
    ):
        pass  # Pipeline runs to completion

    # Retrieve final story from session state
    session = await runner.session_service.get_session(
        app_name=APP_NAME,
        user_id=uid,
        session_id=session.id,
    )
    raw_story = session.state.get(STATE_FINAL, "")

    if not raw_story:
        raise HTTPException(status_code=500, detail="Pipeline did not produce a final story.")

    story = _parse_final_story(str(raw_story), story_id)

    # Extract metadata from pipeline state
    field = _extract_field_of_study(session.state.get(STATE_CONCEPTS, ""))
    paper_title, authors = _extract_paper_metadata(session.state.get(STATE_PAPER_TEXT, ""))

    # Persist to Firestore + GCS
    fs.save_story(
        story_id=story_id,
        paper_id=paper_id,
        archive=archive_name,
        source_url=normalized_url,
        paper_title=paper_title,
        authors=authors,
        field_of_study=field,
        age_group=age_group,
        style=style,
        story_content=story,
    )

    return story


@app.get("/api/stories/{story_id}")
async def get_story(story_id: str, uid: str = Depends(verify_firebase_token)):
    fs = _get_firestore_service()
    story = fs.get_story_by_id(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found.")

    # Include user's vote
    user_vote = fs.get_user_vote(story_id, uid)
    if user_vote:
        story["userVote"] = user_vote

    return story


class VoteRequest(BaseModel):
    vote: str  # "up" or "down"


@app.post("/api/stories/{story_id}/vote")
async def vote_on_story(
    story_id: str,
    body: VoteRequest,
    uid: str = Depends(verify_firebase_token),
):
    if body.vote not in ("up", "down"):
        raise HTTPException(status_code=400, detail="Vote must be 'up' or 'down'.")

    fs = _get_firestore_service()

    # Verify story exists
    doc = fs.get_story_by_id(story_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Story not found.")

    result = fs.vote_on_story(story_id, uid, body.vote)
    return result


# ---------------------------------------------------------------------------
# Top papers endpoint with TTL cache
# ---------------------------------------------------------------------------

_top_papers_cache: dict | None = None
_top_papers_cache_time: float = 0
TOP_PAPERS_TTL = 300  # 5 minutes

import time


@app.get("/api/top-papers")
async def get_top_papers(uid: str = Depends(verify_firebase_token)):
    global _top_papers_cache, _top_papers_cache_time

    now = time.time()
    if _top_papers_cache is not None and (now - _top_papers_cache_time) < TOP_PAPERS_TTL:
        return _top_papers_cache

    fs = _get_firestore_service()
    result = fs.get_top_papers_by_field(limit_per_field=3)

    _top_papers_cache = result
    _top_papers_cache_time = now

    return result
