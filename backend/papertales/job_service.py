"""Decoupled job lifecycle management for PaperTales."""

import logging
from datetime import datetime, timezone

from google.cloud import firestore

logger = logging.getLogger(__name__)

JOBS_COLLECTION = "jobs"
JOB_TIMEOUT_MINUTES = 15

# Maps agent name → (stage_number, human-readable label)
STAGE_MAP = {
    "paper_parser": (1, "Parsing paper"),
    "concept_extractor": (2, "Extracting concepts"),
    "language_simplifier": (3, "Simplifying language"),
    "narrative_designer": (4, "Designing narrative"),
    "story_illustrator": (5, "Writing & illustrating"),
    "audio_narrator": (6, "Narrating audio"),
    "fact_checker": (7, "Fact-checking"),
    "story_assembler": (8, "Assembling story"),
}

TOTAL_STAGES = 8


class JobService:
    """Manages the full job lifecycle in a dedicated Firestore collection."""

    def __init__(self, firestore_client=None):
        self._db = firestore_client or firestore.Client()

    def create_job(
        self,
        job_id: str,
        uid: str,
        paper_url: str,
        age_group: str,
        style: str,
    ) -> dict:
        """Create a job document with status=processing, stage=0."""
        now = datetime.now(timezone.utc)
        job = {
            "job_id": job_id,
            "uid": uid,
            "status": "processing",
            "current_stage": 0,
            "total_stages": TOTAL_STAGES,
            "stage_label": "Initializing",
            "current_agent": None,
            "story_id": job_id,
            "paper_url": paper_url,
            "age_group": age_group,
            "style": style,
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
            "processing_time_ms": None,
            "error": None,
        }
        self._db.collection(JOBS_COLLECTION).document(job_id).set(job)
        return job

    def advance_stage(self, job_id: str, agent_name: str) -> None:
        """Update stage fields when an agent completes. Skips unknown agents."""
        entry = STAGE_MAP.get(agent_name)
        if entry is None:
            return

        stage_number, label = entry
        self._db.collection(JOBS_COLLECTION).document(job_id).update({
            "current_stage": stage_number,
            "stage_label": label,
            "current_agent": agent_name,
            "updated_at": datetime.now(timezone.utc),
        })

    def complete_job(self, job_id: str) -> None:
        """Mark job as complete and compute processing time."""
        now = datetime.now(timezone.utc)
        doc_ref = self._db.collection(JOBS_COLLECTION).document(job_id)
        doc = doc_ref.get()

        processing_time_ms = None
        if doc.exists:
            created = doc.to_dict().get("created_at")
            if created:
                if hasattr(created, "timestamp"):
                    # Firestore Timestamp
                    delta = now - datetime.fromtimestamp(created.timestamp(), tz=timezone.utc)
                else:
                    delta = now - created
                processing_time_ms = int(delta.total_seconds() * 1000)

        doc_ref.update({
            "status": "complete",
            "current_stage": TOTAL_STAGES,
            "stage_label": "Complete",
            "completed_at": now,
            "updated_at": now,
            "processing_time_ms": processing_time_ms,
        })

    def fail_job(self, job_id: str, error: str) -> None:
        """Mark job as error with the given message."""
        self._db.collection(JOBS_COLLECTION).document(job_id).update({
            "status": "error",
            "error": error,
            "updated_at": datetime.now(timezone.utc),
        })

    def get_job(self, job_id: str) -> dict | None:
        """Read job; auto-transitions to timed_out if processing > 15min."""
        doc_ref = self._db.collection(JOBS_COLLECTION).document(job_id)
        doc = doc_ref.get()
        if not doc.exists:
            return None

        data = doc.to_dict()

        if data.get("status") == "processing":
            created = data.get("created_at")
            if created:
                if hasattr(created, "timestamp"):
                    created_dt = datetime.fromtimestamp(created.timestamp(), tz=timezone.utc)
                else:
                    created_dt = created
                elapsed = (datetime.now(timezone.utc) - created_dt).total_seconds() / 60
                if elapsed > JOB_TIMEOUT_MINUTES:
                    now = datetime.now(timezone.utc)
                    doc_ref.update({
                        "status": "timed_out",
                        "error": f"Job timed out after {JOB_TIMEOUT_MINUTES} minutes",
                        "updated_at": now,
                    })
                    data["status"] = "timed_out"
                    data["error"] = f"Job timed out after {JOB_TIMEOUT_MINUTES} minutes"
                    data["updated_at"] = now

        return data

    def get_active_job(self, uid: str) -> dict | None:
        """Return the user's active (processing) job, or None.

        Also performs timeout check on any found job.
        """
        query = (
            self._db.collection(JOBS_COLLECTION)
            .where("uid", "==", uid)
            .where("status", "==", "processing")
            .limit(1)
        )

        docs = list(query.stream())
        if not docs:
            return None

        job_data = docs[0].to_dict()
        job_id = job_data.get("job_id", docs[0].id)

        # Check timeout
        created = job_data.get("created_at")
        if created:
            if hasattr(created, "timestamp"):
                created_dt = datetime.fromtimestamp(created.timestamp(), tz=timezone.utc)
            else:
                created_dt = created
            elapsed = (datetime.now(timezone.utc) - created_dt).total_seconds() / 60
            if elapsed > JOB_TIMEOUT_MINUTES:
                self._db.collection(JOBS_COLLECTION).document(job_id).update({
                    "status": "timed_out",
                    "error": f"Job timed out after {JOB_TIMEOUT_MINUTES} minutes",
                    "updated_at": datetime.now(timezone.utc),
                })
                return None

        return job_data

    def get_user_jobs(self, uid: str, limit: int = 10) -> list[dict]:
        """Return recent jobs for a user, datetimes serialized to ISO strings."""
        query = (
            self._db.collection(JOBS_COLLECTION)
            .where("uid", "==", uid)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )

        jobs = []
        for doc in query.stream():
            data = doc.to_dict()
            # Serialize datetimes to ISO strings for JSON
            for key in ("created_at", "updated_at", "completed_at"):
                val = data.get(key)
                if val is not None:
                    if hasattr(val, "isoformat"):
                        data[key] = val.isoformat()
                    elif hasattr(val, "timestamp"):
                        data[key] = datetime.fromtimestamp(
                            val.timestamp(), tz=timezone.utc
                        ).isoformat()
            jobs.append(data)

        return jobs
