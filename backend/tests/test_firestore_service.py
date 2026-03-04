"""Tests for Firestore persistence service (mocked)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from papertales.firestore_service import (
    FirestoreService,
    MAX_VERSIONS,
    REGEN_DOWNVOTE_RATIO,
    REGEN_VOTE_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_firestore():
    """Create a mock Firestore client."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_storage():
    """Create a mock GCS client."""
    client = MagicMock()
    bucket = MagicMock()
    client.bucket.return_value = bucket
    return client


@pytest.fixture
def service(mock_firestore, mock_storage):
    """Create a FirestoreService with mocked clients."""
    return FirestoreService(
        firestore_client=mock_firestore,
        storage_client=mock_storage,
    )


# ---------------------------------------------------------------------------
# compute_story_id
# ---------------------------------------------------------------------------


class TestComputeStoryId:
    def test_deterministic(self):
        id1 = FirestoreService.compute_story_id("2301.12345", "10-13", "fairy_tale")
        id2 = FirestoreService.compute_story_id("2301.12345", "10-13", "fairy_tale")
        assert id1 == id2

    def test_different_inputs_different_ids(self):
        id1 = FirestoreService.compute_story_id("2301.12345", "10-13", "fairy_tale")
        id2 = FirestoreService.compute_story_id("2301.12345", "10-13", "adventure")
        assert id1 != id2

    def test_length_is_16(self):
        story_id = FirestoreService.compute_story_id("paper", "6-9", "sci_fi")
        assert len(story_id) == 16

    def test_hex_chars_only(self):
        story_id = FirestoreService.compute_story_id("paper", "6-9", "sci_fi")
        assert all(c in "0123456789abcdef" for c in story_id)


# ---------------------------------------------------------------------------
# get_cached_story
# ---------------------------------------------------------------------------


class TestGetCachedStory:
    def test_returns_none_when_not_exists(self, service, mock_firestore):
        doc = MagicMock()
        doc.exists = False
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc

        result = service.get_cached_story("nonexistent")
        assert result is None

    def test_returns_none_when_flagged_for_regen(self, service, mock_firestore, mock_storage):
        doc = MagicMock()
        doc.exists = True
        doc.to_dict.return_value = {
            "flagged_for_regen": True,
            "current_version": 1,
        }
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc

        result = service.get_cached_story("flagged-id")
        assert result is None

    def test_returns_story_when_cached(self, service, mock_firestore, mock_storage):
        doc = MagicMock()
        doc.exists = True
        doc.to_dict.return_value = {
            "flagged_for_regen": False,
            "current_version": 2,
            "paper_title": "Test Paper",
            "authors": "Author A",
            "field_of_study": "Physics",
            "upvotes": 5,
            "downvotes": 1,
        }
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc

        story_content = {"title": "Physics Story", "scenes": []}
        blob = MagicMock()
        blob.download_as_text.return_value = json.dumps(story_content)
        mock_storage.bucket.return_value.blob.return_value = blob

        result = service.get_cached_story("cached-id")
        assert result is not None
        assert result["title"] == "Physics Story"
        assert result["paperTitle"] == "Test Paper"
        assert result["upvotes"] == 5
        assert result["version"] == 2


# ---------------------------------------------------------------------------
# save_story
# ---------------------------------------------------------------------------


class TestSaveStory:
    def test_creates_new_story(self, service, mock_firestore, mock_storage):
        doc = MagicMock()
        doc.exists = False
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc

        result = service.save_story(
            story_id="new-id",
            paper_id="2301.12345",
            archive="arXiv",
            source_url="https://arxiv.org/abs/2301.12345",
            paper_title="Test Paper",
            authors="Author A",
            field_of_study="Physics",
            age_group="10-13",
            style="fairy_tale",
            story_content={"title": "Test", "scenes": []},
        )

        assert result["id"] == "new-id"
        assert result["version"] == 1

        # Verify GCS upload was called
        mock_storage.bucket.return_value.blob.assert_called()
        blob = mock_storage.bucket.return_value.blob.return_value
        blob.upload_from_string.assert_called_once()

        # Verify Firestore set was called with merge
        doc_ref = mock_firestore.collection.return_value.document.return_value
        doc_ref.set.assert_called_once()
        call_args = doc_ref.set.call_args
        assert call_args[1] == {"merge": True}
        metadata = call_args[0][0]
        assert metadata["paper_id"] == "2301.12345"
        assert metadata["current_version"] == 1
        assert metadata["upvotes"] == 0

    def test_increments_version(self, service, mock_firestore, mock_storage):
        doc = MagicMock()
        doc.exists = True
        doc.to_dict.return_value = {"current_version": 3}
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc

        result = service.save_story(
            story_id="existing-id",
            paper_id="paper1",
            archive="arXiv",
            source_url="url",
            paper_title="Title",
            authors="Author",
            field_of_study="Biology",
            age_group="6-9",
            style="adventure",
            story_content={"title": "Bio Story", "scenes": []},
        )

        assert result["version"] == 4

    def test_deletes_old_versions_beyond_cap(self, service, mock_firestore, mock_storage):
        doc = MagicMock()
        doc.exists = True
        doc.to_dict.return_value = {"current_version": MAX_VERSIONS}
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc

        service.save_story(
            story_id="old-id",
            paper_id="paper1",
            archive="arXiv",
            source_url="url",
            paper_title="Title",
            authors="Author",
            field_of_study="Physics",
            age_group="10-13",
            style="fairy_tale",
            story_content={"title": "Story", "scenes": []},
        )

        # Should delete version 1 (oldest)
        bucket = mock_storage.bucket.return_value
        # blob() is called for both write and delete
        blob_calls = bucket.blob.call_args_list
        delete_paths = [
            call[0][0] for call in blob_calls
            if "v1.json" in call[0][0]
        ]
        assert len(delete_paths) >= 1


# ---------------------------------------------------------------------------
# vote_on_story
# ---------------------------------------------------------------------------


class TestVoteOnStory:
    def _setup_vote_doc(self, mock_firestore, upvotes=0, downvotes=0, voter_ids=None):
        """Helper to set up a mock document for voting."""
        doc = MagicMock()
        doc.exists = True
        doc.to_dict.return_value = {
            "upvotes": upvotes,
            "downvotes": downvotes,
            "voter_ids": voter_ids or {},
        }

        doc_ref = MagicMock()
        doc_ref.get = MagicMock(return_value=doc)
        mock_firestore.collection.return_value.document.return_value = doc_ref
        mock_firestore.transaction.return_value = MagicMock()

        return doc_ref

    def test_upvote(self, service, mock_firestore):
        doc_ref = self._setup_vote_doc(mock_firestore)

        # Mock the transactional decorator to just call the function
        with patch("papertales.firestore_service.firestore.transactional",
                   lambda fn: fn):
            result = service.vote_on_story("story-1", "user-a", "up")

        assert result["upvotes"] == 1
        assert result["downvotes"] == 0
        assert result["userVote"] == "up"

    def test_downvote(self, service, mock_firestore):
        doc_ref = self._setup_vote_doc(mock_firestore)

        with patch("papertales.firestore_service.firestore.transactional",
                   lambda fn: fn):
            result = service.vote_on_story("story-1", "user-a", "down")

        assert result["upvotes"] == 0
        assert result["downvotes"] == 1
        assert result["userVote"] == "down"

    def test_change_vote(self, service, mock_firestore):
        doc_ref = self._setup_vote_doc(
            mock_firestore, upvotes=1, voter_ids={"user-a": "up"}
        )

        with patch("papertales.firestore_service.firestore.transactional",
                   lambda fn: fn):
            result = service.vote_on_story("story-1", "user-a", "down")

        assert result["upvotes"] == 0
        assert result["downvotes"] == 1
        assert result["userVote"] == "down"

    def test_separate_users(self, service, mock_firestore):
        doc_ref = self._setup_vote_doc(
            mock_firestore, upvotes=1, voter_ids={"user-a": "up"}
        )

        with patch("papertales.firestore_service.firestore.transactional",
                   lambda fn: fn):
            result = service.vote_on_story("story-1", "user-b", "up")

        assert result["upvotes"] == 2

    def test_regen_flag_at_threshold(self, service, mock_firestore):
        # Set up: 3 up, 7 down = 10 total, >50% down → flag
        doc_ref = self._setup_vote_doc(
            mock_firestore,
            upvotes=3,
            downvotes=6,
            voter_ids={f"u{i}": "up" if i < 3 else "down" for i in range(9)},
        )

        with patch("papertales.firestore_service.firestore.transactional",
                   lambda fn: fn):
            result = service.vote_on_story("story-1", "user-new", "down")

        # 3 up, 7 down, total=10, 70% down > 50%
        assert result["flaggedForRegen"] is True

    def test_no_regen_flag_under_threshold(self, service, mock_firestore):
        doc_ref = self._setup_vote_doc(
            mock_firestore, upvotes=2, downvotes=2,
            voter_ids={"u1": "up", "u2": "up", "u3": "down", "u4": "down"},
        )

        with patch("papertales.firestore_service.firestore.transactional",
                   lambda fn: fn):
            result = service.vote_on_story("story-1", "user-new", "down")

        # 2 up, 3 down, total=5 < threshold of 10
        assert result["flaggedForRegen"] is False


# ---------------------------------------------------------------------------
# get_user_vote
# ---------------------------------------------------------------------------


class TestGetUserVote:
    def test_returns_vote_when_exists(self, service, mock_firestore):
        doc = MagicMock()
        doc.exists = True
        doc.to_dict.return_value = {"voter_ids": {"user-a": "up"}}
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc

        assert service.get_user_vote("story-1", "user-a") == "up"

    def test_returns_none_when_no_vote(self, service, mock_firestore):
        doc = MagicMock()
        doc.exists = True
        doc.to_dict.return_value = {"voter_ids": {}}
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc

        assert service.get_user_vote("story-1", "user-a") is None

    def test_returns_none_when_doc_missing(self, service, mock_firestore):
        doc = MagicMock()
        doc.exists = False
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc

        assert service.get_user_vote("story-1", "user-a") is None


# ---------------------------------------------------------------------------
# get_top_papers_by_field
# ---------------------------------------------------------------------------


class TestGetTopPapersByField:
    def test_returns_grouped_results(self, service, mock_firestore):
        # Mock query chain
        mock_doc = MagicMock()
        mock_doc.id = "story-abc"
        mock_doc.to_dict.return_value = {
            "title": "Quantum Fun",
            "paper_title": "Quantum Paper",
            "upvotes": 10,
            "downvotes": 2,
            "age_group": "10-13",
            "style": "adventure",
            "archive": "arXiv",
        }

        query = MagicMock()
        query.where.return_value = query
        query.order_by.return_value = query
        query.limit.return_value = query
        query.stream.return_value = [mock_doc]
        mock_firestore.collection.return_value = query

        result = service.get_top_papers_by_field(limit_per_field=3)

        # Should have entries for each field that has papers
        assert isinstance(result, dict)
        # Each field with results should have our mock doc
        for field, papers in result.items():
            assert papers[0]["id"] == "story-abc"
            assert papers[0]["upvotes"] == 10

    def test_filters_zero_upvotes(self, service, mock_firestore):
        mock_doc = MagicMock()
        mock_doc.id = "zero-votes"
        mock_doc.to_dict.return_value = {
            "title": "Unpopular",
            "paper_title": "Paper",
            "upvotes": 0,
            "downvotes": 0,
            "age_group": "6-9",
            "style": "fairy_tale",
            "archive": "arXiv",
        }

        query = MagicMock()
        query.where.return_value = query
        query.order_by.return_value = query
        query.limit.return_value = query
        query.stream.return_value = [mock_doc]
        mock_firestore.collection.return_value = query

        result = service.get_top_papers_by_field()
        # Should be empty since all papers have 0 upvotes
        assert all(len(papers) == 0 for papers in result.values()) if result else True
