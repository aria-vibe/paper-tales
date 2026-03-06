"""Tests for the JobService."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from papertales.job_service import (
    JOB_TIMEOUT_MINUTES,
    JOBS_COLLECTION,
    STAGE_MAP,
    TOTAL_STAGES,
    JobService,
)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def js(mock_db):
    return JobService(firestore_client=mock_db)


class TestCreateJob:
    def test_creates_job_with_correct_schema(self, js, mock_db):
        result = js.create_job("job-1", "uid-1", "https://arxiv.org/abs/123", "10-13", "fairy_tale")

        assert result["job_id"] == "job-1"
        assert result["uid"] == "uid-1"
        assert result["status"] == "processing"
        assert result["current_stage"] == 0
        assert result["total_stages"] == TOTAL_STAGES
        assert result["stage_label"] == "Initializing"
        assert result["current_agent"] is None
        assert result["story_id"] == "job-1"
        assert result["paper_url"] == "https://arxiv.org/abs/123"
        assert result["age_group"] == "10-13"
        assert result["style"] == "fairy_tale"
        assert result["completed_at"] is None
        assert result["processing_time_ms"] is None
        assert result["error"] is None
        assert isinstance(result["created_at"], datetime)

        mock_db.collection.assert_called_with(JOBS_COLLECTION)
        mock_db.collection().document.assert_called_with("job-1")
        mock_db.collection().document().set.assert_called_once()


class TestAdvanceStage:
    def test_known_agent_updates_stage(self, js, mock_db):
        js.advance_stage("job-1", "paper_parser")

        call_args = mock_db.collection().document().update.call_args[0][0]
        assert call_args["current_stage"] == 1
        assert call_args["stage_label"] == "Parsing paper"
        assert call_args["current_agent"] == "paper_parser"

    def test_unknown_agent_is_skipped(self, js, mock_db):
        js.advance_stage("job-1", "unknown_agent")

        mock_db.collection().document().update.assert_not_called()

    def test_all_agents_in_stage_map(self):
        """Verify all 8 agents are mapped."""
        assert len(STAGE_MAP) == TOTAL_STAGES
        stages = [v[0] for v in STAGE_MAP.values()]
        assert sorted(stages) == list(range(1, TOTAL_STAGES + 1))


class TestCompleteJob:
    def test_marks_complete_with_processing_time(self, js, mock_db):
        created = datetime.now(timezone.utc) - timedelta(seconds=30)
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"created_at": created}
        mock_db.collection().document().get.return_value = mock_doc

        js.complete_job("job-1")

        call_args = mock_db.collection().document().update.call_args[0][0]
        assert call_args["status"] == "complete"
        assert call_args["current_stage"] == TOTAL_STAGES
        assert call_args["stage_label"] == "Complete"
        assert call_args["completed_at"] is not None
        assert call_args["processing_time_ms"] is not None
        assert call_args["processing_time_ms"] >= 30000  # at least 30s


class TestFailJob:
    def test_marks_error(self, js, mock_db):
        js.fail_job("job-1", "Something broke")

        call_args = mock_db.collection().document().update.call_args[0][0]
        assert call_args["status"] == "error"
        assert call_args["error"] == "Something broke"


class TestGetJob:
    def test_returns_none_for_missing(self, js, mock_db):
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection().document().get.return_value = mock_doc

        assert js.get_job("nonexistent") is None

    def test_returns_processing_job(self, js, mock_db):
        now = datetime.now(timezone.utc)
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "status": "processing",
            "created_at": now,
            "current_stage": 3,
        }
        mock_db.collection().document().get.return_value = mock_doc

        result = js.get_job("job-1")
        assert result["status"] == "processing"
        assert result["current_stage"] == 3

    def test_auto_transitions_to_timed_out(self, js, mock_db):
        old_time = datetime.now(timezone.utc) - timedelta(minutes=JOB_TIMEOUT_MINUTES + 1)
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "status": "processing",
            "created_at": old_time,
            "completed_at": None,
        }
        # Both initial read and re-read return the same stale doc
        mock_db.collection().document().get.return_value = mock_doc

        result = js.get_job("job-1")
        assert result["status"] == "timed_out"
        assert "timed out" in result["error"]
        mock_db.collection().document().update.assert_called_once()

    def test_does_not_timeout_if_completed_at_set(self, js, mock_db):
        """If completed_at is already set, skip the timeout — pipeline just finished."""
        old_time = datetime.now(timezone.utc) - timedelta(minutes=JOB_TIMEOUT_MINUTES + 1)
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "status": "processing",
            "created_at": old_time,
            "completed_at": datetime.now(timezone.utc),
        }
        mock_db.collection().document().get.return_value = mock_doc

        result = js.get_job("job-1")
        assert result["status"] == "processing"  # not overwritten to timed_out
        mock_db.collection().document().update.assert_not_called()

    def test_re_read_prevents_race_with_complete_job(self, js, mock_db):
        """If re-read shows the job was completed between reads, return fresh data."""
        old_time = datetime.now(timezone.utc) - timedelta(minutes=JOB_TIMEOUT_MINUTES + 1)
        now = datetime.now(timezone.utc)

        stale_doc = MagicMock()
        stale_doc.exists = True
        stale_doc.to_dict.return_value = {
            "status": "processing",
            "created_at": old_time,
            "completed_at": None,
        }

        fresh_doc = MagicMock()
        fresh_doc.exists = True
        fresh_doc.to_dict.return_value = {
            "status": "complete",
            "created_at": old_time,
            "completed_at": now,
        }

        # First get() returns stale, second get() (re-read) returns fresh
        mock_db.collection().document().get.side_effect = [stale_doc, fresh_doc]

        result = js.get_job("job-1")
        assert result["status"] == "complete"
        mock_db.collection().document().update.assert_not_called()


class TestGetActiveJob:
    def test_returns_none_when_no_active(self, js, mock_db):
        mock_db.collection().where().where().limit().stream.return_value = []

        result = js.get_active_job("uid-1")
        assert result is None

    def test_returns_active_job(self, js, mock_db):
        now = datetime.now(timezone.utc)
        mock_doc = MagicMock()
        mock_doc.id = "job-1"
        mock_doc.to_dict.return_value = {
            "job_id": "job-1",
            "uid": "uid-1",
            "status": "processing",
            "created_at": now,
        }
        mock_db.collection().where().where().limit().stream.return_value = [mock_doc]

        result = js.get_active_job("uid-1")
        assert result is not None
        assert result["job_id"] == "job-1"

    def test_returns_none_for_timed_out_job(self, js, mock_db):
        old_time = datetime.now(timezone.utc) - timedelta(minutes=JOB_TIMEOUT_MINUTES + 1)
        mock_doc = MagicMock()
        mock_doc.id = "job-1"
        mock_doc.to_dict.return_value = {
            "job_id": "job-1",
            "uid": "uid-1",
            "status": "processing",
            "created_at": old_time,
            "completed_at": None,
        }
        mock_db.collection().where().where().limit().stream.return_value = [mock_doc]
        # Re-read also returns stale (still processing)
        fresh_doc = MagicMock()
        fresh_doc.exists = True
        fresh_doc.to_dict.return_value = {
            "status": "processing",
            "completed_at": None,
        }
        mock_db.collection().document().get.return_value = fresh_doc

        result = js.get_active_job("uid-1")
        assert result is None

    def test_returns_none_if_completed_at_set(self, js, mock_db):
        """If completed_at is set, the pipeline finished — don't return as active."""
        now = datetime.now(timezone.utc)
        mock_doc = MagicMock()
        mock_doc.id = "job-1"
        mock_doc.to_dict.return_value = {
            "job_id": "job-1",
            "uid": "uid-1",
            "status": "processing",
            "created_at": now - timedelta(minutes=5),
            "completed_at": now,
        }
        mock_db.collection().where().where().limit().stream.return_value = [mock_doc]

        result = js.get_active_job("uid-1")
        assert result is None

    def test_active_job_re_read_prevents_race(self, js, mock_db):
        """If re-read shows complete, don't write timed_out."""
        old_time = datetime.now(timezone.utc) - timedelta(minutes=JOB_TIMEOUT_MINUTES + 1)
        mock_doc = MagicMock()
        mock_doc.id = "job-1"
        mock_doc.to_dict.return_value = {
            "job_id": "job-1",
            "uid": "uid-1",
            "status": "processing",
            "created_at": old_time,
            "completed_at": None,
        }
        mock_db.collection().where().where().limit().stream.return_value = [mock_doc]
        # Re-read shows job was completed by the pipeline thread
        fresh_doc = MagicMock()
        fresh_doc.exists = True
        fresh_doc.to_dict.return_value = {
            "status": "complete",
            "completed_at": datetime.now(timezone.utc),
        }
        mock_db.collection().document().get.return_value = fresh_doc

        result = js.get_active_job("uid-1")
        assert result is None
        mock_db.collection().document().update.assert_not_called()


class TestGetUserJobs:
    def test_serializes_datetimes(self, js, mock_db):
        now = datetime.now(timezone.utc)
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = {
            "job_id": "job-1",
            "status": "complete",
            "created_at": now,
            "updated_at": now,
            "completed_at": now,
        }
        mock_db.collection().where().order_by().limit().stream.return_value = [mock_doc]

        jobs = js.get_user_jobs("uid-1")
        assert len(jobs) == 1
        assert isinstance(jobs[0]["created_at"], str)
        assert isinstance(jobs[0]["updated_at"], str)
        assert isinstance(jobs[0]["completed_at"], str)

    def test_handles_none_completed_at(self, js, mock_db):
        now = datetime.now(timezone.utc)
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = {
            "job_id": "job-2",
            "status": "processing",
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
        }
        mock_db.collection().where().order_by().limit().stream.return_value = [mock_doc]

        jobs = js.get_user_jobs("uid-1")
        assert len(jobs) == 1
        assert jobs[0]["completed_at"] is None
