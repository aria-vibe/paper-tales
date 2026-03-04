"""Tests for the PaperTales API endpoints."""

import io
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

    from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
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
        file: UploadFile | None = File(None),
        arxiv_url: str | None = Form(None),
        age_group: str = Form("10-13"),
        style: str = Form("fairy_tale"),
    ):
        return await main.generate_story(uid, file, arxiv_url, age_group, style)

    @test_app.get("/api/stories/{story_id}")
    async def get_story(story_id: str, uid: str = Depends(mock_verify_token)):
        return await main.get_story(story_id, uid)

    main._story_cache.clear()
    # Reset rate limiter for each test
    from papertales import auth
    auth.rate_limiter = RateLimiter()

    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


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
# API endpoint tests
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestGenerateEndpoint:
    def test_requires_input(self, client):
        resp = client.post(
            "/api/generate",
            data={"age_group": "10-13", "style": "fairy_tale"},
        )
        assert resp.status_code == 400
        assert "Provide either" in resp.json()["detail"]

    def test_with_arxiv_url(self, client):
        fake_story = json.dumps({
            "title": "Quantum for Kids",
            "scenes": [{"text": "Once upon a time..."}],
            "age_group": "10-13",
        })

        mock_session = MagicMock()
        mock_session.id = "test-session-123"
        mock_session.state = {"final_story": fake_story}

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

        resp = client.post(
            "/api/generate",
            data={
                "arxiv_url": "https://arxiv.org/abs/2301.00001",
                "age_group": "10-13",
                "style": "fairy_tale",
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Quantum for Kids"
        assert body["id"] == "test-session-123"
        assert "createdAt" in body

        main._runner = None

    def test_with_pdf_upload(self, client):
        fake_story = json.dumps({
            "title": "PDF Story",
            "scenes": [{"text": "A story from PDF"}],
        })

        mock_session = MagicMock()
        mock_session.id = "pdf-session-456"
        mock_session.state = {"final_story": fake_story}

        mock_session_service = AsyncMock()
        mock_session_service.create_session = AsyncMock(return_value=mock_session)
        mock_session_service.get_session = AsyncMock(return_value=mock_session)

        mock_runner = MagicMock()
        mock_runner.session_service = mock_session_service

        async def fake_run_async(**kwargs):
            return
            yield

        mock_runner.run_async = fake_run_async

        import main
        main._runner = mock_runner

        pdf_content = b"%PDF-1.4 fake content"
        resp = client.post(
            "/api/generate",
            data={"age_group": "6-9", "style": "adventure"},
            files={"file": ("paper.pdf", io.BytesIO(pdf_content), "application/pdf")},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "PDF Story"
        assert body["id"] == "pdf-session-456"

        main._runner = None

    def test_pdf_size_limit(self, client):
        # 21 MB of data — over the 20 MB limit
        big_content = b"x" * (21 * 1024 * 1024)
        resp = client.post(
            "/api/generate",
            data={"age_group": "10-13", "style": "fairy_tale"},
            files={"file": ("huge.pdf", io.BytesIO(big_content), "application/pdf")},
        )
        assert resp.status_code == 400
        assert "20 MB" in resp.json()["detail"]


class TestGetStoryEndpoint:
    def test_not_found(self, client):
        resp = client.get("/api/stories/nonexistent")
        assert resp.status_code == 404

    def test_after_generate(self, client):
        import main

        main._story_cache["cached-id"] = {
            "id": "cached-id",
            "title": "Cached Story",
            "scenes": [{"text": "Hello"}],
            "createdAt": "2024-01-01T00:00:00Z",
        }

        resp = client.get("/api/stories/cached-id")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Cached Story"


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
