"""FastAPI entry point for PaperTales."""

import asyncio
import base64
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

# Configure structured logging before any other imports
from papertales.log_context import current_job_id, current_session_id, setup_structured_logging

setup_structured_logging()

from fastapi import Depends, FastAPI, Form, HTTPException
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel

from papertales.auth import UserInfo, verify_firebase_token
from papertales.config import (
    FIELD_TAXONOMY,
    STATE_AUDIO,
    STATE_CONCEPTS,
    STATE_FACTCHECK,
    STATE_FINAL,
    STATE_NARRATIVE,
    STATE_PAPER_TEXT,
    STATE_SIMPLIFIED,
    STATE_STORY,
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
                # Pre-populate intermediate keys so downstream agent
                # instruction templates don't crash if an upstream agent
                # produces no text output (e.g. audio_narrator with only
                # tool calls).
                STATE_PAPER_TEXT: "",
                STATE_CONCEPTS: "",
                STATE_SIMPLIFIED: "",
                STATE_NARRATIVE: "",
                STATE_STORY: "",
                STATE_AUDIO: "",
                STATE_FACTCHECK: "",
            },
        )

        # Set correlation context for all downstream loggers
        current_session_id.set(session.id)
        current_job_id.set(job_id)

        logger.info(
            "Pipeline started: url=%s age=%s style=%s uid=%s",
            normalized_url, age_group, style, uid,
        )

        trigger = types.Content(
            role="user",
            parts=[
                types.Part(text="Begin processing.")
            ],
        )

        # Track per-agent output stats and Gemini response timing
        current_agent = None
        agent_text_chars = 0
        agent_image_count = 0
        agent_start_time = 0.0
        agent_first_token_time: float | None = None
        pipeline_start = time.monotonic()

        # Collect media from event stream for GCS persistence
        collected_images: list[str] = []  # base64 strings in scene order
        collected_audio: list[dict] = []   # {"label": str, "audio_base64": str}

        async for event in runner.run_async(
            user_id=uid,
            session_id=session.id,
            new_message=trigger,
        ):
            # Detect agent transitions
            author = getattr(event, "author", None)
            if author and author != current_agent:
                if current_agent is not None:
                    elapsed_ms = int((time.monotonic() - agent_start_time) * 1000)
                    ttft_ms = int((agent_first_token_time - agent_start_time) * 1000) if agent_first_token_time else None
                    logger.info(
                        "Agent %s completed: %d text chars, %d images, gemini_ms=%d, ttft_ms=%s",
                        current_agent, agent_text_chars, agent_image_count, elapsed_ms, ttft_ms,
                    )
                current_agent = author
                agent_text_chars = 0
                agent_image_count = 0
                agent_start_time = time.monotonic()
                agent_first_token_time = None
                logger.info("Agent %s started", current_agent)
                js.advance_stage(job_id, current_agent)

            # Accumulate output stats and capture media from event content
            content = getattr(event, "content", None)
            if content and hasattr(content, "parts") and content.parts:
                for part in content.parts:
                    if hasattr(part, "text") and part.text:
                        agent_text_chars += len(part.text)
                    if hasattr(part, "inline_data") and part.inline_data:
                        agent_image_count += 1
                        # Capture image bytes for GCS storage
                        img_data = part.inline_data.data
                        if img_data:
                            if isinstance(img_data, bytes):
                                collected_images.append(base64.b64encode(img_data).decode("utf-8"))
                            elif isinstance(img_data, str):
                                collected_images.append(img_data)
                    # Capture audio from TTS tool responses
                    fr = getattr(part, "function_response", None)
                    if fr and getattr(fr, "name", "") == "synthesize_speech":
                        resp = fr.response if isinstance(getattr(fr, "response", None), dict) else {}
                        if resp.get("audio_base64"):
                            collected_audio.append({
                                "label": resp.get("label", ""),
                                "audio_base64": resp["audio_base64"],
                            })
                # Record time-to-first-token
                if agent_first_token_time is None:
                    agent_first_token_time = time.monotonic()

        # Log final agent stats
        if current_agent is not None:
            elapsed_ms = int((time.monotonic() - agent_start_time) * 1000)
            ttft_ms = int((agent_first_token_time - agent_start_time) * 1000) if agent_first_token_time else None
            logger.info(
                "Agent %s completed: %d text chars, %d images, gemini_ms=%d, ttft_ms=%s",
                current_agent, agent_text_chars, agent_image_count, elapsed_ms, ttft_ms,
            )

        pipeline_elapsed_ms = int((time.monotonic() - pipeline_start) * 1000)

        # Retrieve final story from session state
        session = await runner.session_service.get_session(
            app_name=APP_NAME,
            user_id=uid,
            session_id=session.id,
        )
        raw_story = session.state.get(STATE_FINAL, "")

        # Log pipeline summary
        parsed_paper = session.state.get(STATE_PAPER_TEXT, "")
        logger.info("Pipeline complete: parsed_paper=%d chars, final_story=%d chars, total_ms=%d",
                     len(str(parsed_paper)), len(str(raw_story)), pipeline_elapsed_ms)
        parsed_paper_len = len(str(parsed_paper))
        if parsed_paper_len < 500:
            logger.error(
                "Paper parser output too short (%d chars) — paper was not fetched properly. Full output:\n%s",
                parsed_paper_len, str(parsed_paper),
            )
            js.fail_job(job_id, f"Paper content could not be fetched properly ({parsed_paper_len} chars extracted).")
            return
        if parsed_paper_len < 1000:
            logger.warning(
                "Paper parser produced short output (%d chars) — paper may not have been fetched properly. Full output:\n%s",
                parsed_paper_len, str(parsed_paper),
            )

        if not raw_story:
            js.fail_job(job_id, "Pipeline did not produce a final story.")
            return

        story = _parse_final_story(str(raw_story), job_id)

        # Inject captured media into story scenes for GCS persistence
        scenes = story.get("scenes", [])
        if collected_images:
            logger.info("Injecting %d captured images into %d scenes", len(collected_images), len(scenes))
            for i, scene in enumerate(scenes):
                if i < len(collected_images):
                    scene["imageBase64"] = collected_images[i]
        if collected_audio:
            logger.info("Injecting %d captured audio clips (scenes=%d)", len(collected_audio), len(scenes))
            for item in collected_audio:
                label = item["label"]
                audio = item["audio_base64"]
                if label == "title":
                    story["titleAudioBase64"] = audio
                elif label == "conclusion":
                    story["conclusionAudioBase64"] = audio
                elif label.startswith("scene_"):
                    idx = int(label.split("_", 1)[1])
                    if idx < len(scenes):
                        scenes[idx]["audioBase64"] = audio

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
            session_id=session.id,
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

    # Create job and launch pipeline in a dedicated thread with its own event
    # loop so that blocking tool functions (TTS, embeddings) don't starve the
    # main event loop that serves poll requests.
    job = js.create_job(story_id, uid, normalized_url, age_group, style)

    def _run_pipeline_in_thread() -> None:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_run_pipeline_task(
                job_id=story_id,
                uid=uid,
                normalized_url=normalized_url,
                archive_name=archive_name,
                paper_id=paper_id,
                age_group=age_group,
                style=style,
            ))
        finally:
            loop.close()

    threading.Thread(target=_run_pipeline_in_thread, daemon=True).start()

    return {
        "jobId": story_id,
        "status": "processing",
        "currentStage": job.get("current_stage", 0),
        "totalStages": job.get("total_stages", 8),
        "stageLabel": job.get("stage_label", "Initializing"),
    }


@app.get("/api/jobs/active")
async def get_active_job(user_info: UserInfo = Depends(verify_firebase_token)):
    js = _get_job_service()
    active = js.get_active_job(user_info.uid)
    if not active:
        return {"active": False}

    job_id = active.get("job_id", active.get("story_id"))
    return {
        "active": True,
        "jobId": job_id,
        "status": "processing",
        "currentStage": active.get("current_stage", 0),
        "totalStages": active.get("total_stages", 8),
        "stageLabel": active.get("stage_label", "Processing"),
        "paperUrl": active.get("paper_url", ""),
        "ageGroup": active.get("age_group", ""),
        "style": active.get("style", ""),
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


MEDIA_CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
}

MEDIA_FILENAME_RE = re.compile(r"^(scene_\d+_(image|audio)|title_audio|conclusion_audio)\.\w+$")


@app.get("/api/stories/{story_id}/media/{filename}")
async def get_story_media(
    story_id: str,
    filename: str,
    user_info: UserInfo = Depends(verify_firebase_token),
):
    """Stream a media file (image/audio) from GCS for the given story."""
    if not MEDIA_FILENAME_RE.match(filename):
        raise HTTPException(status_code=400, detail="Invalid media filename.")

    ext = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""
    content_type = MEDIA_CONTENT_TYPES.get(ext)
    if not content_type:
        raise HTTPException(status_code=400, detail="Unsupported media type.")

    fs = _get_firestore_service()
    data = fs.get_media_blob(story_id, filename)
    if data is None:
        raise HTTPException(status_code=404, detail="Media not found.")

    from fastapi.responses import Response

    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=86400"},
    )


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

    try:
        fs = _get_firestore_service()
        result = fs.get_top_papers_by_field(limit_per_field=3)
    except Exception as exc:
        logger.exception("Failed to fetch top papers")
        raise HTTPException(status_code=503, detail="Top papers temporarily unavailable.") from exc

    _top_papers_cache = result
    _top_papers_cache_time = now

    return result
