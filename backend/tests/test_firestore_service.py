"""Tests for Firestore persistence service (mocked)."""

import base64
import json
from unittest.mock import MagicMock, call, patch

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


# Helper: create sample story content with base64 media
SAMPLE_IMAGE_BYTES = b"\x89PNG\r\n\x1a\nfake-image-data"
SAMPLE_AUDIO_BYTES = b"ID3fake-audio-data"
SAMPLE_IMAGE_B64 = base64.b64encode(SAMPLE_IMAGE_BYTES).decode("utf-8")
SAMPLE_AUDIO_B64 = base64.b64encode(SAMPLE_AUDIO_BYTES).decode("utf-8")


def _story_with_media():
    return {
        "title": "Test Story",
        "ageGroup": "10-13",
        "style": "fairy_tale",
        "scenes": [
            {
                "scene_number": 1,
                "title": "Scene 1",
                "text": "Once upon a time...",
                "imageBase64": SAMPLE_IMAGE_B64,
                "audioBase64": SAMPLE_AUDIO_B64,
            },
            {
                "scene_number": 2,
                "title": "Scene 2",
                "text": "And then...",
                "imageBase64": SAMPLE_IMAGE_B64,
            },
        ],
        "glossary": {"photon": "a particle of light"},
        "factCheck": {"accuracy_rating": 0.9, "summary": "Good"},
        "whatWeLearned": "Light is fast",
        "sourcePaper": {"title": "Paper A", "authors": "Author A"},
        "createdAt": "2026-01-01T00:00:00Z",
    }


def _story_without_media():
    return {
        "title": "Text Only",
        "scenes": [
            {"scene_number": 1, "text": "Hello"},
        ],
        "glossary": {},
    }


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
# Media extraction
# ---------------------------------------------------------------------------


class TestMediaExtraction:
    def test_extracts_image_and_audio(self, service):
        story = _story_with_media()
        clean, media = service._extract_media_from_story(story)

        # Scenes should have no base64 keys
        for scene in clean["scenes"]:
            assert "imageBase64" not in scene
            assert "audioBase64" not in scene

        # Should have 3 media items: 2 images + 1 audio
        assert len(media) == 3
        images = [m for m in media if m["type"] == "image"]
        audios = [m for m in media if m["type"] == "audio"]
        assert len(images) == 2
        assert len(audios) == 1

    def test_media_bytes_decoded_correctly(self, service):
        story = _story_with_media()
        _, media = service._extract_media_from_story(story)

        img = next(m for m in media if m["type"] == "image" and m["scene_index"] == 0)
        assert img["data"] == SAMPLE_IMAGE_BYTES
        assert img["content_type"] == "image/png"

        aud = next(m for m in media if m["type"] == "audio")
        assert aud["data"] == SAMPLE_AUDIO_BYTES
        assert aud["content_type"] == "audio/mpeg"

    def test_no_media_returns_empty_list(self, service):
        story = _story_without_media()
        clean, media = service._extract_media_from_story(story)

        assert media == []
        assert clean["scenes"][0]["text"] == "Hello"

    def test_empty_base64_skipped(self, service):
        story = {
            "title": "T",
            "scenes": [{"text": "Hi", "imageBase64": "", "audioBase64": ""}],
        }
        _, media = service._extract_media_from_story(story)
        assert media == []

    def test_original_not_mutated(self, service):
        story = _story_with_media()
        original_b64 = story["scenes"][0]["imageBase64"]
        service._extract_media_from_story(story)
        # Original should be untouched
        assert story["scenes"][0]["imageBase64"] == original_b64


# ---------------------------------------------------------------------------
# Media rehydration
# ---------------------------------------------------------------------------


class TestMediaRehydration:
    def test_rehydrates_image_and_audio(self, service, mock_storage):
        bucket = mock_storage.bucket.return_value
        blob = MagicMock()

        def make_blob(path):
            b = MagicMock()
            if "image" in path:
                b.download_as_bytes.return_value = SAMPLE_IMAGE_BYTES
            elif "audio" in path:
                b.download_as_bytes.return_value = SAMPLE_AUDIO_BYTES
            else:
                b.download_as_bytes.side_effect = Exception("not found")
            return b

        bucket.blob.side_effect = make_blob

        scenes = [{"text": "Hello", "scene_number": 1}]
        hydrated = service._rehydrate_media("s1", 1, scenes)

        assert hydrated[0]["imageBase64"] == SAMPLE_IMAGE_B64
        assert hydrated[0]["audioBase64"] == SAMPLE_AUDIO_B64

    def test_missing_media_omitted(self, service, mock_storage):
        bucket = mock_storage.bucket.return_value
        blob = MagicMock()
        blob.download_as_bytes.side_effect = Exception("not found")
        bucket.blob.return_value = blob

        scenes = [{"text": "Hello"}]
        hydrated = service._rehydrate_media("s1", 1, scenes)

        assert "imageBase64" not in hydrated[0]
        assert "audioBase64" not in hydrated[0]

    def test_original_scenes_not_mutated(self, service, mock_storage):
        bucket = mock_storage.bucket.return_value
        blob = MagicMock()
        blob.download_as_bytes.side_effect = Exception("not found")
        bucket.blob.return_value = blob

        scenes = [{"text": "Hello"}]
        service._rehydrate_media("s1", 1, scenes)
        assert "imageBase64" not in scenes[0]


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

    def test_returns_story_new_format(self, service, mock_firestore, mock_storage):
        """New format: scenes in Firestore, media rehydrated from GCS."""
        bucket = mock_storage.bucket.return_value
        blob = MagicMock()
        blob.download_as_bytes.side_effect = Exception("not found")
        bucket.blob.return_value = blob

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
            "title": "Physics Story",
            "scenes": [{"text": "Scene text", "scene_number": 1}],
            "glossary": {"atom": "tiny thing"},
        }
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc

        result = service.get_cached_story("cached-id")
        assert result is not None
        assert result["title"] == "Physics Story"
        assert result["paperTitle"] == "Test Paper"
        assert result["upvotes"] == 5
        assert result["version"] == 2
        assert result["glossary"] == {"atom": "tiny thing"}

    def test_returns_story_old_format(self, service, mock_firestore, mock_storage):
        """Old format: no scenes in Firestore, read from GCS JSON blob."""
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
    def test_creates_new_story_with_media(self, service, mock_firestore, mock_storage):
        doc = MagicMock()
        doc.exists = False
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc

        bucket = mock_storage.bucket.return_value

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
            story_content=_story_with_media(),
        )

        assert result["id"] == "new-id"
        assert result["version"] == 1

        # Verify media upload to GCS (2 images + 1 audio = 3 uploads)
        upload_calls = bucket.blob.return_value.upload_from_string.call_args_list
        assert len(upload_calls) == 3

        # Verify Firestore set was called with scenes (no base64)
        doc_ref = mock_firestore.collection.return_value.document.return_value
        doc_ref.set.assert_called_once()
        call_args = doc_ref.set.call_args
        assert call_args[1] == {"merge": True}
        metadata = call_args[0][0]
        assert metadata["paper_id"] == "2301.12345"
        assert metadata["current_version"] == 1
        assert metadata["upvotes"] == 0
        assert isinstance(metadata["scenes"], list)
        assert len(metadata["scenes"]) == 2
        # Scenes should NOT contain base64
        for scene in metadata["scenes"]:
            assert "imageBase64" not in scene
            assert "audioBase64" not in scene
        assert metadata["glossary"] == {"photon": "a particle of light"}

    def test_creates_story_without_media(self, service, mock_firestore, mock_storage):
        doc = MagicMock()
        doc.exists = False
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc

        bucket = mock_storage.bucket.return_value

        result = service.save_story(
            story_id="no-media",
            paper_id="paper1",
            archive="arXiv",
            source_url="url",
            paper_title="Title",
            authors="Author",
            field_of_study="Biology",
            age_group="6-9",
            style="adventure",
            story_content=_story_without_media(),
        )

        assert result["version"] == 1
        # No media uploads should happen
        bucket.blob.return_value.upload_from_string.assert_not_called()

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
            story_content=_story_without_media(),
        )

        assert result["version"] == 4

    def test_deletes_old_versions_beyond_cap(self, service, mock_firestore, mock_storage):
        doc = MagicMock()
        doc.exists = True
        doc.to_dict.return_value = {"current_version": MAX_VERSIONS}
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc

        bucket = mock_storage.bucket.return_value
        bucket.list_blobs.return_value = []  # No blobs in prefix

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
            story_content=_story_without_media(),
        )

        # Should attempt to delete version 1 (old blob + list prefix)
        blob_calls = bucket.blob.call_args_list
        delete_paths = [c[0][0] for c in blob_calls if "v1.json" in c[0][0]]
        assert len(delete_paths) >= 1

    def test_stores_text_content_in_firestore(self, service, mock_firestore, mock_storage):
        """Verify all text fields are written to Firestore metadata."""
        doc = MagicMock()
        doc.exists = False
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc

        service.save_story(
            story_id="text-id",
            paper_id="p1",
            archive="arXiv",
            source_url="url",
            paper_title="Title",
            authors="Auth",
            field_of_study="CS",
            age_group="10-13",
            style="sci_fi",
            story_content=_story_with_media(),
        )

        doc_ref = mock_firestore.collection.return_value.document.return_value
        metadata = doc_ref.set.call_args[0][0]
        assert metadata["glossary"] == {"photon": "a particle of light"}
        assert metadata["fact_check"] == {"accuracy_rating": 0.9, "summary": "Good"}
        assert metadata["what_we_learned"] == "Light is fast"
        assert metadata["source_paper"] == {"title": "Paper A", "authors": "Author A"}
        assert metadata["ageGroup"] == "10-13"
        assert metadata["createdAt"] == "2026-01-01T00:00:00Z"


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    def test_old_format_reads_from_gcs(self, service, mock_firestore, mock_storage):
        """Old format: no 'scenes' list in Firestore → read JSON from GCS."""
        doc = MagicMock()
        doc.exists = True
        doc.to_dict.return_value = {
            "current_version": 1,
            "paper_title": "Old Paper",
            "authors": "Author",
            "field_of_study": "Math",
            "upvotes": 3,
            "downvotes": 0,
        }
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc

        gcs_content = {"title": "Old Story", "scenes": [{"text": "Chapter 1"}]}
        blob = MagicMock()
        blob.download_as_text.return_value = json.dumps(gcs_content)
        mock_storage.bucket.return_value.blob.return_value = blob

        result = service.get_story_by_id("old-story")
        assert result["title"] == "Old Story"
        assert result["paperTitle"] == "Old Paper"
        assert result["version"] == 1

    def test_new_format_reads_from_firestore(self, service, mock_firestore, mock_storage):
        """New format: 'scenes' list in Firestore → build from Firestore + GCS media."""
        bucket = mock_storage.bucket.return_value
        blob = MagicMock()
        blob.download_as_bytes.side_effect = Exception("not found")
        bucket.blob.return_value = blob

        doc = MagicMock()
        doc.exists = True
        doc.to_dict.return_value = {
            "current_version": 2,
            "paper_title": "New Paper",
            "authors": "Author B",
            "field_of_study": "Biology",
            "upvotes": 10,
            "downvotes": 2,
            "title": "New Story",
            "scenes": [
                {"text": "Once...", "scene_number": 1},
                {"text": "Then...", "scene_number": 2},
            ],
            "glossary": {"cell": "basic unit of life"},
            "ageGroup": "6-9",
            "style": "adventure",
        }
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc

        result = service.get_story_by_id("new-story")
        assert result["title"] == "New Story"
        assert result["paperTitle"] == "New Paper"
        assert result["version"] == 2
        assert len(result["scenes"]) == 2
        assert result["glossary"] == {"cell": "basic unit of life"}
        assert result["ageGroup"] == "6-9"

    def test_old_format_gcs_failure_returns_none(self, service, mock_firestore, mock_storage):
        """If old-format GCS read fails, return None."""
        doc = MagicMock()
        doc.exists = True
        doc.to_dict.return_value = {
            "current_version": 1,
            "paper_title": "P",
            "authors": "A",
            "field_of_study": "Other",
            "upvotes": 0,
            "downvotes": 0,
        }
        mock_firestore.collection.return_value.document.return_value.get.return_value = doc

        blob = MagicMock()
        blob.download_as_text.side_effect = Exception("GCS error")
        mock_storage.bucket.return_value.blob.return_value = blob

        result = service.get_story_by_id("fail-story")
        assert result is None


# ---------------------------------------------------------------------------
# Delete version
# ---------------------------------------------------------------------------


class TestDeleteVersion:
    def test_deletes_old_format_blob(self, service, mock_storage):
        bucket = mock_storage.bucket.return_value
        old_blob = MagicMock()
        bucket.blob.return_value = old_blob
        bucket.list_blobs.return_value = []

        service._delete_version_from_gcs("s1", 1)

        old_blob.delete.assert_called_once()

    def test_deletes_new_format_folder(self, service, mock_storage):
        bucket = mock_storage.bucket.return_value
        old_blob = MagicMock()
        old_blob.delete.side_effect = Exception("not found")  # No old blob

        media_blob1 = MagicMock()
        media_blob1.name = "stories/s1/v1/scene_0_image.png"
        media_blob2 = MagicMock()
        media_blob2.name = "stories/s1/v1/scene_0_audio.mp3"

        bucket.blob.return_value = old_blob
        bucket.list_blobs.return_value = [media_blob1, media_blob2]

        service._delete_version_from_gcs("s1", 1)

        media_blob1.delete.assert_called_once()
        media_blob2.delete.assert_called_once()

    def test_handles_both_formats(self, service, mock_storage):
        """Should try deleting both old blob and new folder."""
        bucket = mock_storage.bucket.return_value
        old_blob = MagicMock()
        bucket.blob.return_value = old_blob
        bucket.list_blobs.return_value = []

        service._delete_version_from_gcs("s1", 2)

        # Old blob deletion attempted
        old_blob.delete.assert_called_once()
        # Prefix listing attempted
        bucket.list_blobs.assert_called_once_with(prefix="stories/s1/v2/")


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
        # Set up: 3 up, 7 down = 10 total, >50% down -> flag
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


# ---------------------------------------------------------------------------
# GCS path helpers
# ---------------------------------------------------------------------------


class TestGcsPathHelpers:
    def test_gcs_path_legacy(self, service):
        assert service._gcs_path("abc", 2) == "stories/abc/v2.json"

    def test_gcs_media_prefix(self, service):
        assert service._gcs_media_prefix("abc", 3) == "stories/abc/v3/"

    def test_gcs_image_path(self, service):
        assert service._gcs_image_path("abc", 1, 0) == "stories/abc/v1/scene_0_image.png"
        assert service._gcs_image_path("abc", 2, 3) == "stories/abc/v2/scene_3_image.png"

    def test_gcs_audio_path(self, service):
        assert service._gcs_audio_path("abc", 1, 0) == "stories/abc/v1/scene_0_audio.mp3"
        assert service._gcs_audio_path("abc", 2, 3) == "stories/abc/v2/scene_3_audio.mp3"

