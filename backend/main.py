"""FastAPI entry point for PaperTales."""

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel

from papertales.auth import UserInfo, verify_firebase_token
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

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000,https://gen-lang-client-0383770485.web.app")

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
_job_service = None


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


def _get_job_service():
    global _job_service
    if _job_service is None:
        from papertales.job_service import JobService

        _job_service = JobService()
    return _job_service


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
            if isinstance(item, dict) and "term" in item:
                definition = item.get("definition") or item.get("meaning", "")
                glossary_dict[item["term"]] = definition
        story["glossary"] = glossary_dict

    story["id"] = story_id
    story["createdAt"] = datetime.now(timezone.utc).isoformat()

    return story


@app.get("/health")
async def health():
    return {"status": "ok"}


async def _run_pipeline_task(
    job_id: str,
    uid: str,
    normalized_url: str,
    archive_name: str,
    paper_id: str,
    age_group: str,
    style: str,
) -> None:
    """Background task that runs the agent pipeline and updates job status."""
    fs = _get_firestore_service()
    js = _get_job_service()
    try:
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
            if hasattr(event, "actions") and event.actions and event.actions.end_of_agent and event.author:
                js.advance_stage(job_id, event.author)

        # Retrieve final story from session state
        session = await runner.session_service.get_session(
            app_name=APP_NAME,
            user_id=uid,
            session_id=session.id,
        )
        raw_story = session.state.get(STATE_FINAL, "")

        if not raw_story:
            js.fail_job(job_id, "Pipeline did not produce a final story.")
            return

        story = _parse_final_story(str(raw_story), job_id)

        # Extract metadata from pipeline state
        field = _extract_field_of_study(session.state.get(STATE_CONCEPTS, ""))
        paper_title, authors = _extract_paper_metadata(session.state.get(STATE_PAPER_TEXT, ""))

        # Persist to Firestore + GCS
        fs.save_story(
            story_id=job_id,
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

        js.complete_job(job_id)

    except Exception as exc:
        logger.exception("Pipeline failed for job %s", job_id)
        js.fail_job(job_id, str(exc))


@app.post("/api/generate")
async def generate_story(
    user_info: UserInfo = Depends(verify_firebase_token),
    paper_url: str = Form(...),
    age_group: str = Form("10-13"),
    style: str = Form("fairy_tale"),
):
    uid = user_info.uid

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
        # Cached content does NOT count against quota
        user_vote = fs.get_user_vote(story_id, uid)
        if user_vote:
            cached["userVote"] = user_vote
        return cached

    # Check daily quota AFTER cache check — only actual generations count
    fs.check_and_increment_quota(uid, user_info.is_anonymous)

    # Check if user already has an active job
    js = _get_job_service()
    active_job = js.get_active_job(uid)
    if active_job:
        active_job_id = active_job.get("job_id", active_job.get("story_id"))
        if active_job_id == story_id:
            # Same story already processing — return its status
            return {
                "jobId": story_id,
                "status": "processing",
                "currentStage": active_job.get("current_stage", 0),
                "totalStages": active_job.get("total_stages", 8),
                "stageLabel": active_job.get("stage_label", "Processing"),
            }
        # Different story — reject concurrent job
        raise HTTPException(
            status_code=409,
            detail="You already have a story being generated. Please wait for it to finish.",
        )

    # Create job and launch pipeline in background
    job = js.create_job(story_id, uid, normalized_url, age_group, style)
    asyncio.create_task(_run_pipeline_task(
        job_id=story_id,
        uid=uid,
        normalized_url=normalized_url,
        archive_name=archive_name,
        paper_id=paper_id,
        age_group=age_group,
        style=style,
    ))

    return {
        "jobId": story_id,
        "status": "processing",
        "currentStage": job.get("current_stage", 0),
        "totalStages": job.get("total_stages", 8),
        "stageLabel": job.get("stage_label", "Initializing"),
    }


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str, user_info: UserInfo = Depends(verify_firebase_token)):
    js = _get_job_service()
    job = js.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    response = {
        "jobId": job_id,
        "status": job["status"],
        "currentStage": job.get("current_stage", 0),
        "totalStages": job.get("total_stages", 8),
        "stageLabel": job.get("stage_label", ""),
    }

    if job["status"] == "complete":
        if job.get("processing_time_ms") is not None:
            response["processingTimeMs"] = job["processing_time_ms"]
        fs = _get_firestore_service()
        story = fs.get_cached_story(job_id)
        if story:
            user_vote = fs.get_user_vote(job_id, user_info.uid)
            if user_vote:
                story["userVote"] = user_vote
            response["story"] = story
        return response

    if job["status"] in ("error", "timed_out"):
        response["error"] = job.get("error", "Unknown error")
        return response

    return response


@app.get("/api/jobs")
async def list_user_jobs(
    user_info: UserInfo = Depends(verify_firebase_token),
    limit: int = 10,
):
    js = _get_job_service()
    jobs = js.get_user_jobs(user_info.uid, limit=limit)
    return {"jobs": jobs}


@app.get("/api/stories/{story_id}")
async def get_story(story_id: str, user_info: UserInfo = Depends(verify_firebase_token)):
    fs = _get_firestore_service()
    story = fs.get_story_by_id(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found.")

    # Include user's vote
    user_vote = fs.get_user_vote(story_id, user_info.uid)
    if user_vote:
        story["userVote"] = user_vote

    return story


class VoteRequest(BaseModel):
    vote: str  # "up" or "down"


@app.post("/api/stories/{story_id}/vote")
async def vote_on_story(
    story_id: str,
    body: VoteRequest,
    user_info: UserInfo = Depends(verify_firebase_token),
):
    if body.vote not in ("up", "down"):
        raise HTTPException(status_code=400, detail="Vote must be 'up' or 'down'.")

    fs = _get_firestore_service()

    # Verify story exists
    doc = fs.get_story_by_id(story_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Story not found.")

    result = fs.vote_on_story(story_id, user_info.uid, body.vote)
    return result


# ---------------------------------------------------------------------------
# Quota endpoint
# ---------------------------------------------------------------------------


@app.get("/api/quota")
async def get_quota(user_info: UserInfo = Depends(verify_firebase_token)):
    fs = _get_firestore_service()
    remaining = fs.get_remaining_quota(user_info.uid, user_info.is_anonymous)
    limit = 3 if user_info.is_anonymous else 10
    return {
        "remaining": remaining,
        "limit": limit,
        "isAnonymous": user_info.is_anonymous,
    }


# ---------------------------------------------------------------------------
# Top papers endpoint with TTL cache
# ---------------------------------------------------------------------------

_top_papers_cache: dict | None = None
_top_papers_cache_time: float = 0
TOP_PAPERS_TTL = 300  # 5 minutes


@app.get("/api/top-papers")
async def get_top_papers(user_info: UserInfo = Depends(verify_firebase_token)):
    global _top_papers_cache, _top_papers_cache_time

    now = time.time()
    if _top_papers_cache is not None and (now - _top_papers_cache_time) < TOP_PAPERS_TTL:
        return _top_papers_cache

    fs = _get_firestore_service()
    result = fs.get_top_papers_by_field(limit_per_field=3)

    _top_papers_cache = result
    _top_papers_cache_time = now

    return result
