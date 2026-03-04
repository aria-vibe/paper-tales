"""Tests for the PaperTales API endpoints."""

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# We need to mock the ADK imports before importing main
@pytest.fixture(autouse=True)
def _mock_adk_app(monkeypatch):
    """Replace get_fast_api_app so tests don't need a real agent directory."""
    from fastapi import FastAPI

    def fake_get_fast_api_app(**kwargs):
        return FastAPI()

    monkeypatch.setattr("main.get_fast_api_app", fake_get_fast_api_app)


MOCK_UID = "test-user-abc123"


@pytest.fixture
def app():
    """Create a fresh app for each test."""
    import importlib
    import main

    importlib.reload(main)

    from fastapi import Depends, FastAPI, Form, HTTPException
    from pydantic import BaseModel
    from papertales.auth import RateLimiter, verify_firebase_token

    test_app = FastAPI()

    # Override auth dependency to return a fixed uid
    async def mock_verify_token():
        return MOCK_UID

    @test_app.get("/health")
    async def health():
        return await main.health()

    @test_app.post("/api/generate")
    async def generate_story(
        uid: str = Depends(mock_verify_token),
        paper_url: str = Form(...),
        age_group: str = Form("10-13"),
        style: str = Form("fairy_tale"),
    ):
        return await main.generate_story(uid, paper_url, age_group, style)

    @test_app.get("/api/stories/{story_id}")
    async def get_story(story_id: str, uid: str = Depends(mock_verify_token)):
        return await main.get_story(story_id, uid)

    class VoteRequest(BaseModel):
        vote: str

    @test_app.post("/api/stories/{story_id}/vote")
    async def vote_on_story(story_id: str, body: VoteRequest, uid: str = Depends(mock_verify_token)):
        return await main.vote_on_story(story_id, body, uid)

    @test_app.get("/api/top-papers")
    async def get_top_papers(uid: str = Depends(mock_verify_token)):
        return await main.get_top_papers(uid)

    # Reset singletons
    main._firestore_service = None
    main._top_papers_cache = None
    main._top_papers_cache_time = 0

    # Reset rate limiter for each test
    from papertales import auth
    auth.rate_limiter = RateLimiter()

    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def mock_fs():
    """Create a mock FirestoreService."""
    fs = MagicMock()
    fs.get_cached_story.return_value = None
    fs.get_story_by_id.return_value = None
    fs.get_user_vote.return_value = None
    fs.save_story.return_value = {"id": "test-id", "version": 1}
    return fs


# ---------------------------------------------------------------------------
# parse helper tests
# ---------------------------------------------------------------------------


class TestParseFinalStory:
    def test_strips_json_fences(self):
        from main import _parse_final_story

        raw = '```json\n{"title": "Test", "scenes": [{"text": "Hello"}]}\n```'
        result = _parse_final_story(raw, "sess-1")
        assert result["title"] == "Test"
        assert result["id"] == "sess-1"
        assert "createdAt" in result

    def test_invalid_json_fallback(self):
        from main import _parse_final_story

        raw = "This is not JSON at all"
        result = _parse_final_story(raw, "sess-2")
        assert result["title"] == "Generated Story"
        assert result["scenes"][0]["text"] == raw
        assert result["id"] == "sess-2"

    def test_normalizes_keys(self):
        from main import _parse_final_story

        raw = json.dumps({
            "title": "My Story",
            "age_group": "6-9",
            "story_style": "adventure",
            "source_title": "A Paper",
            "scenes": [{"text": "Once upon a time"}],
        })
        result = _parse_final_story(raw, "sess-3")
        assert result["ageGroup"] == "6-9"
        assert result["style"] == "adventure"
        assert result["sourceTitle"] == "A Paper"
        assert "age_group" not in result
        assert "story_style" not in result

    def test_converts_glossary_array_to_dict(self):
        from main import _parse_final_story

        raw = json.dumps({
            "title": "Glossary Test",
            "scenes": [],
            "glossary": [
                {"term": "photon", "definition": "a particle of light"},
                {"term": "cell", "definition": "basic unit of life"},
            ],
        })
        result = _parse_final_story(raw, "sess-4")
        assert result["glossary"] == {
            "photon": "a particle of light",
            "cell": "basic unit of life",
        }


# ---------------------------------------------------------------------------
# Field extraction helpers
# ---------------------------------------------------------------------------


class TestExtractFieldOfStudy:
    def test_extracts_valid_field(self):
        from main import _extract_field_of_study

        text = "Some analysis...\n**Field**: Physics\nMore text"
        assert _extract_field_of_study(text) == "Physics"

    def test_returns_other_for_invalid(self):
        from main import _extract_field_of_study

        text = "No field here"
        assert _extract_field_of_study(text) == "Other"

    def test_returns_other_for_unknown_field(self):
        from main import _extract_field_of_study

        text = "**Field**: Underwater Basket Weaving"
        assert _extract_field_of_study(text) == "Other"


class TestExtractPaperMetadata:
    def test_extracts_title_and_authors(self):
        from main import _extract_paper_metadata

        text = "**TITLE**: Quantum Computing\n**AUTHORS**: Alice, Bob\n**ABSTRACT**: ..."
        title, authors = _extract_paper_metadata(text)
        assert title == "Quantum Computing"
        assert authors == "Alice, Bob"

    def test_missing_fields(self):
        from main import _extract_paper_metadata

        title, authors = _extract_paper_metadata("no structured data here")
        assert title == ""
        assert authors == ""


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestGenerateEndpoint:
    def test_rejects_non_whitelisted_url(self, client):
        resp = client.post(
            "/api/generate",
            data={
                "paper_url": "https://example.com/paper.pdf",
                "age_group": "10-13",
                "style": "fairy_tale",
            },
        )
        assert resp.status_code == 400
        assert "Unsupported archive" in resp.json()["detail"]

    def test_returns_cached_story(self, client, mock_fs):
        import main

        cached_story = {
            "id": "cached-123",
            "title": "Cached Story",
            "scenes": [{"text": "cached"}],
            "createdAt": "2024-01-01T00:00:00Z",
        }
        mock_fs.get_cached_story.return_value = cached_story
        main._firestore_service = mock_fs

        resp = client.post(
            "/api/generate",
            data={
                "paper_url": "https://arxiv.org/abs/2301.12345",
                "age_group": "10-13",
                "style": "fairy_tale",
            },
        )

        assert resp.status_code == 200
        assert resp.json()["title"] == "Cached Story"
        main._firestore_service = None

    def test_with_arxiv_url_runs_pipeline(self, client, mock_fs):
        fake_story = json.dumps({
            "title": "Quantum for Kids",
            "scenes": [{"text": "Once upon a time..."}],
            "age_group": "10-13",
        })

        mock_session = MagicMock()
        mock_session.id = "test-session-123"
        mock_session.state = {
            "final_story": fake_story,
            "extracted_concepts": "**Field**: Physics",
            "parsed_paper": "**TITLE**: Quantum\n**AUTHORS**: Alice",
        }

        mock_session_service = AsyncMock()
        mock_session_service.create_session = AsyncMock(return_value=mock_session)
        mock_session_service.get_session = AsyncMock(return_value=mock_session)

        mock_runner = MagicMock()
        mock_runner.session_service = mock_session_service

        async def fake_run_async(**kwargs):
            return
            yield  # Make it an async generator

        mock_runner.run_async = fake_run_async

        import main
        main._runner = mock_runner
        main._firestore_service = mock_fs

        resp = client.post(
            "/api/generate",
            data={
                "paper_url": "https://arxiv.org/abs/2301.00001",
                "age_group": "10-13",
                "style": "fairy_tale",
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Quantum for Kids"
        assert "createdAt" in body

        # Verify save was called
        mock_fs.save_story.assert_called_once()

        main._runner = None
        main._firestore_service = None


class TestGetStoryEndpoint:
    def test_not_found(self, client, mock_fs):
        import main
        main._firestore_service = mock_fs

        resp = client.get("/api/stories/nonexistent")
        assert resp.status_code == 404

        main._firestore_service = None

    def test_returns_story(self, client, mock_fs):
        import main

        mock_fs.get_story_by_id.return_value = {
            "id": "story-123",
            "title": "Test Story",
            "scenes": [{"text": "Hello"}],
            "createdAt": "2024-01-01T00:00:00Z",
        }
        main._firestore_service = mock_fs

        resp = client.get("/api/stories/story-123")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Test Story"

        main._firestore_service = None


class TestVoteEndpoint:
    def test_vote_on_story(self, client, mock_fs):
        import main

        mock_fs.get_story_by_id.return_value = {"id": "story-1", "title": "Story"}
        mock_fs.vote_on_story.return_value = {
            "upvotes": 1,
            "downvotes": 0,
            "userVote": "up",
            "flaggedForRegen": False,
        }
        main._firestore_service = mock_fs

        resp = client.post(
            "/api/stories/story-1/vote",
            json={"vote": "up"},
        )

        assert resp.status_code == 200
        assert resp.json()["upvotes"] == 1

        main._firestore_service = None

    def test_vote_invalid_value(self, client, mock_fs):
        import main
        main._firestore_service = mock_fs

        resp = client.post(
            "/api/stories/story-1/vote",
            json={"vote": "invalid"},
        )

        assert resp.status_code == 400

        main._firestore_service = None

    def test_vote_on_nonexistent_story(self, client, mock_fs):
        import main

        mock_fs.get_story_by_id.return_value = None
        main._firestore_service = mock_fs

        resp = client.post(
            "/api/stories/nonexistent/vote",
            json={"vote": "up"},
        )

        assert resp.status_code == 404

        main._firestore_service = None


class TestTopPapersEndpoint:
    def test_returns_top_papers(self, client, mock_fs):
        import main

        mock_fs.get_top_papers_by_field.return_value = {
            "Physics": [{"id": "p1", "title": "Physics Story", "upvotes": 10}],
        }
        main._firestore_service = mock_fs
        main._top_papers_cache = None

        resp = client.get("/api/top-papers")
        assert resp.status_code == 200
        data = resp.json()
        assert "Physics" in data

        main._firestore_service = None


# ---------------------------------------------------------------------------
# Rate limiter tests
# ---------------------------------------------------------------------------


class TestRateLimiter:
    def test_allows_under_limit(self):
        from papertales.auth import RateLimiter

        limiter = RateLimiter(window=3600, max_requests=5)
        for _ in range(5):
            limiter.check("user1")  # Should not raise

    def test_blocks_over_limit(self):
        from papertales.auth import RateLimiter
        from fastapi import HTTPException

        limiter = RateLimiter(window=3600, max_requests=5)
        for _ in range(5):
            limiter.check("user1")

        with pytest.raises(HTTPException) as exc_info:
            limiter.check("user1")
        assert exc_info.value.status_code == 429

    def test_separate_users(self):
        from papertales.auth import RateLimiter

        limiter = RateLimiter(window=3600, max_requests=2)
        limiter.check("alice")
        limiter.check("alice")
        # Alice is at limit, but Bob should be fine
        limiter.check("bob")

    def test_evicts_old_entries(self):
        from papertales.auth import RateLimiter

        limiter = RateLimiter(window=1, max_requests=1)  # 1-second window
        limiter.check("user1")
        time.sleep(1.1)
        limiter.check("user1")  # Should succeed — old entry evicted


# ---------------------------------------------------------------------------
# Auth verification tests
# ---------------------------------------------------------------------------


class TestVerifyFirebaseToken:
    @pytest.mark.asyncio
    async def test_missing_header_returns_401(self):
        from fastapi import HTTPException
        from papertales.auth import verify_firebase_token

        with pytest.raises(HTTPException) as exc_info:
            await verify_firebase_token(None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_format_returns_401(self):
        from fastapi import HTTPException
        from papertales.auth import verify_firebase_token

        with pytest.raises(HTTPException) as exc_info:
            await verify_firebase_token("NotBearer token")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_token(self):
        from papertales.auth import verify_firebase_token

        with patch("papertales.auth._get_firebase_app"), \
             patch("firebase_admin.auth.verify_id_token", return_value={"uid": "user-xyz"}):
            uid = await verify_firebase_token("Bearer valid-token-here")
            assert uid == "user-xyz"

    @pytest.mark.asyncio
    async def test_expired_token_returns_401(self):
        from fastapi import HTTPException
        from papertales.auth import verify_firebase_token

        with patch("papertales.auth._get_firebase_app"), \
             patch("firebase_admin.auth.verify_id_token", side_effect=Exception("Token expired")):
            with pytest.raises(HTTPException) as exc_info:
                await verify_firebase_token("Bearer expired-token")
            assert exc_info.value.status_code == 401
