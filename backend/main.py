"""FastAPI entry point for PaperTales."""

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import InMemoryRunner
from google.genai import types

from papertales.auth import rate_limiter, verify_firebase_token
from papertales.config import STATE_FINAL, STATE_USER_AGE_GROUP, STATE_USER_PDF, STATE_USER_STYLE

logger = logging.getLogger(__name__)

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")

# ADK debug UI app
app = get_fast_api_app(
    agents_dir=str(Path(__file__).parent),
    web=True,
    allow_origins=CORS_ORIGINS.split(","),
)

# In-memory story cache (production would use Firestore)
_story_cache: dict[str, dict] = {}

# Lazy-initialized runner (avoids import-time agent instantiation issues)
_runner: InMemoryRunner | None = None
APP_NAME = "papertales"


def _get_runner() -> InMemoryRunner:
    global _runner
    if _runner is None:
        from papertales.agent import root_agent

        _runner = InMemoryRunner(agent=root_agent, app_name=APP_NAME)
    return _runner


def _parse_final_story(raw: str, session_id: str) -> dict:
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

    story["id"] = session_id
    story["createdAt"] = datetime.now(timezone.utc).isoformat()

    return story


@app.get("/health")
async def health():
    return {"status": "ok"}


MAX_PDF_SIZE = 20 * 1024 * 1024  # 20 MB


@app.post("/api/generate")
async def generate_story(
    uid: str = Depends(verify_firebase_token),
    file: UploadFile | None = File(None),
    arxiv_url: str | None = Form(None),
    age_group: str = Form("10-13"),
    style: str = Form("fairy_tale"),
):
    rate_limiter.check(uid)

    if not file and not arxiv_url:
        raise HTTPException(status_code=400, detail="Provide either a PDF file or an arxiv_url.")

    runner = _get_runner()
    tmp_path = None

    try:
        # Handle PDF upload
        pdf_path = ""
        if file:
            content = await file.read()
            if len(content) > MAX_PDF_SIZE:
                raise HTTPException(status_code=400, detail="PDF file exceeds 20 MB limit.")
            suffix = ".pdf"
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp.write(content)
            tmp.close()
            tmp_path = tmp.name
            pdf_path = tmp_path
        elif arxiv_url:
            pdf_path = arxiv_url

        # Create session with initial state
        user_id = uid
        session = await runner.session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            state={
                STATE_USER_PDF: pdf_path,
                STATE_USER_AGE_GROUP: age_group,
                STATE_USER_STYLE: style,
            },
        )

        # Trigger the pipeline
        trigger = types.Content(
            role="user",
            parts=[
                types.Part(
                    text=f"Transform this research paper into an illustrated story for age group {age_group} in {style} style."
                )
            ],
        )

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=trigger,
        ):
            pass  # Pipeline runs to completion

        # Retrieve final story from session state
        session = await runner.session_service.get_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session.id,
        )
        raw_story = session.state.get(STATE_FINAL, "")

        if not raw_story:
            raise HTTPException(status_code=500, detail="Pipeline did not produce a final story.")

        story = _parse_final_story(str(raw_story), session.id)
        _story_cache[session.id] = story

        return story

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.get("/api/stories/{story_id}")
async def get_story(story_id: str, uid: str = Depends(verify_firebase_token)):
    story = _story_cache.get(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found.")
    return story
