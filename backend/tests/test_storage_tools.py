"""Tests for papertales.tools.storage_tools."""

import base64
import json
from unittest.mock import MagicMock, patch

import pytest

from papertales.tools.storage_tools import save_to_firestore, upload_to_gcs


@pytest.fixture(autouse=True)
def _reset_singletons():
    import papertales.tools.storage_tools as m
    m._firestore_client = None
    m._storage_client = None
    yield
    m._firestore_client = None
    m._storage_client = None


# ===========================================================================
# TestSaveToFirestore
# ===========================================================================


class TestSaveToFirestore:
    @patch("papertales.tools.storage_tools.firestore.Client")
    def test_valid_json_saves_successfully(self, mock_fs_cls):
        mock_db = mock_fs_cls.return_value
        mock_doc = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc

        data = json.dumps({"title": "My Story", "scenes": [1, 2, 3]})
        result = save_to_firestore("stories", "story-123", data)

        assert result["success"] is True
        assert result["document_path"] == "stories/story-123"
        mock_db.collection.assert_called_once_with("stories")
        mock_db.collection.return_value.document.assert_called_once_with("story-123")
        mock_doc.set.assert_called_once_with({"title": "My Story", "scenes": [1, 2, 3]})

    def test_invalid_json_returns_error(self):
        result = save_to_firestore("stories", "story-123", "not valid json {{{")
        assert "error" in result
        assert "Invalid JSON" in result["error"]

    @patch("papertales.tools.storage_tools.firestore.Client")
    def test_firestore_exception_returns_error(self, mock_fs_cls):
        mock_db = mock_fs_cls.return_value
        mock_db.collection.return_value.document.return_value.set.side_effect = (
            Exception("Permission denied")
        )

        data = json.dumps({"key": "value"})
        result = save_to_firestore("stories", "story-123", data)

        assert "error" in result
        assert "Permission denied" in result["error"]

    @patch("papertales.tools.storage_tools.firestore.Client")
    def test_empty_data_dict_saves(self, mock_fs_cls):
        """An empty JSON object should still be saveable."""
        mock_db = mock_fs_cls.return_value
        mock_doc = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc

        result = save_to_firestore("col", "doc", "{}")
        assert result["success"] is True
        mock_doc.set.assert_called_once_with({})


# ===========================================================================
# TestUploadToGcs
# ===========================================================================


class TestUploadToGcs:
    @patch("papertales.tools.storage_tools.storage.Client")
    def test_json_upload_succeeds(self, mock_gcs_cls):
        mock_client = mock_gcs_cls.return_value
        mock_blob = MagicMock()
        mock_client.bucket.return_value.blob.return_value = mock_blob

        result = upload_to_gcs(
            "my-bucket", "stories/story.json", '{"hello": "world"}'
        )

        assert result["success"] is True
        assert result["gcs_uri"] == "gs://my-bucket/stories/story.json"
        assert "storage.googleapis.com" in result["public_url"]
        mock_blob.upload_from_string.assert_called_once_with(
            '{"hello": "world"}', content_type="application/json"
        )

    @patch("papertales.tools.storage_tools.storage.Client")
    def test_binary_upload_decodes_base64(self, mock_gcs_cls):
        mock_client = mock_gcs_cls.return_value
        mock_blob = MagicMock()
        mock_client.bucket.return_value.blob.return_value = mock_blob

        raw_bytes = b"\x89PNG\r\n\x1a\n"
        b64_content = base64.b64encode(raw_bytes).decode()

        result = upload_to_gcs(
            "my-bucket", "images/pic.png", b64_content, content_type="image/png"
        )

        assert result["success"] is True
        mock_blob.upload_from_string.assert_called_once_with(
            raw_bytes, content_type="image/png"
        )

    @patch("papertales.tools.storage_tools.storage.Client")
    def test_audio_upload_decodes_base64(self, mock_gcs_cls):
        mock_client = mock_gcs_cls.return_value
        mock_blob = MagicMock()
        mock_client.bucket.return_value.blob.return_value = mock_blob

        raw_bytes = b"\xff\xfb\x90\x00" * 10
        b64_content = base64.b64encode(raw_bytes).decode()

        result = upload_to_gcs(
            "my-bucket", "audio/scene1.mp3", b64_content, content_type="audio/mpeg"
        )

        assert result["success"] is True
        mock_blob.upload_from_string.assert_called_once_with(
            raw_bytes, content_type="audio/mpeg"
        )

    @patch("papertales.tools.storage_tools.storage.Client")
    def test_gcs_exception_returns_error(self, mock_gcs_cls):
        mock_client = mock_gcs_cls.return_value
        mock_client.bucket.side_effect = Exception("Bucket not found")

        result = upload_to_gcs("bad-bucket", "path.json", "{}")

        assert "error" in result
        assert "Bucket not found" in result["error"]

    @patch("papertales.tools.storage_tools.storage.Client")
    def test_text_content_not_decoded(self, mock_gcs_cls):
        """Text content types should be passed as-is, not base64-decoded."""
        mock_client = mock_gcs_cls.return_value
        mock_blob = MagicMock()
        mock_client.bucket.return_value.blob.return_value = mock_blob

        result = upload_to_gcs(
            "bucket", "file.txt", "plain text content", content_type="text/plain"
        )

        assert result["success"] is True
        mock_blob.upload_from_string.assert_called_once_with(
            "plain text content", content_type="text/plain"
        )
