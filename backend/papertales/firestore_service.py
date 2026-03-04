"""Firestore + GCS persistence for PaperTales stories."""

import hashlib
import json
import logging

from datetime import datetime, timezone

from google.cloud import firestore, storage

logger = logging.getLogger(__name__)

STORIES_COLLECTION = "stories"
GCS_BUCKET = "papertales-media"
MAX_VERSIONS = 5
REGEN_VOTE_THRESHOLD = 10
REGEN_DOWNVOTE_RATIO = 0.5


class FirestoreService:
    """Manages story persistence in Firestore (metadata) + GCS (content)."""

    def __init__(self, firestore_client=None, storage_client=None):
        self._db = firestore_client or firestore.Client()
        self._storage = storage_client or storage.Client()
        self._bucket = self._storage.bucket(GCS_BUCKET)

    @staticmethod
    def compute_story_id(paper_id: str, age_group: str, style: str) -> str:
        """Compute deterministic story ID from paper+age+style."""
        key = f"{paper_id}:{age_group}:{style}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def get_cached_story(self, story_id: str) -> dict | None:
        """Return cached story or None if not exists / flagged for regen."""
        doc_ref = self._db.collection(STORIES_COLLECTION).document(story_id)
        doc = doc_ref.get()

        if not doc.exists:
            return None

        data = doc.to_dict()

        # If flagged for regeneration, treat as cache miss
        if data.get("flagged_for_regen", False):
            return None

        # Fetch latest version content from GCS
        version = data.get("current_version", 1)
        content = self._read_version_from_gcs(story_id, version)
        if content is None:
            return None

        # Merge metadata into content
        content["id"] = story_id
        content["paperTitle"] = data.get("paper_title", "")
        content["authors"] = data.get("authors", "")
        content["fieldOfStudy"] = data.get("field_of_study", "Other")
        content["version"] = version
        content["upvotes"] = data.get("upvotes", 0)
        content["downvotes"] = data.get("downvotes", 0)

        return content

    def save_story(
        self,
        story_id: str,
        paper_id: str,
        archive: str,
        source_url: str,
        paper_title: str,
        authors: str,
        field_of_study: str,
        age_group: str,
        style: str,
        story_content: dict,
    ) -> dict:
        """Save story content to GCS and metadata to Firestore."""
        doc_ref = self._db.collection(STORIES_COLLECTION).document(story_id)
        doc = doc_ref.get()

        if doc.exists:
            current_version = doc.to_dict().get("current_version", 0)
        else:
            current_version = 0

        next_version = current_version + 1

        # Upload content to GCS
        self._write_version_to_gcs(story_id, next_version, story_content)

        # Upsert Firestore metadata
        now = datetime.now(timezone.utc)
        metadata = {
            "paper_id": paper_id,
            "archive": archive,
            "source_url": source_url,
            "paper_title": paper_title,
            "authors": authors,
            "field_of_study": field_of_study,
            "age_group": age_group,
            "style": style,
            "title": story_content.get("title", ""),
            "updated_at": now,
            "current_version": next_version,
            "flagged_for_regen": False,
        }

        if not doc.exists:
            metadata["created_at"] = now
            metadata["upvotes"] = 0
            metadata["downvotes"] = 0
            metadata["voter_ids"] = {}

        doc_ref.set(metadata, merge=True)

        # Clean up old versions if exceeding cap
        if next_version > MAX_VERSIONS:
            oldest = next_version - MAX_VERSIONS
            for v in range(1, oldest + 1):
                self._delete_version_from_gcs(story_id, v)

        return {"id": story_id, "version": next_version}

    def get_story_by_id(self, story_id: str) -> dict | None:
        """Read story metadata + latest content."""
        doc_ref = self._db.collection(STORIES_COLLECTION).document(story_id)
        doc = doc_ref.get()

        if not doc.exists:
            return None

        data = doc.to_dict()
        version = data.get("current_version", 1)
        content = self._read_version_from_gcs(story_id, version)

        if content is None:
            return None

        content["id"] = story_id
        content["paperTitle"] = data.get("paper_title", "")
        content["authors"] = data.get("authors", "")
        content["fieldOfStudy"] = data.get("field_of_study", "Other")
        content["version"] = version
        content["upvotes"] = data.get("upvotes", 0)
        content["downvotes"] = data.get("downvotes", 0)

        return content

    # ------------------------------------------------------------------
    # Voting
    # ------------------------------------------------------------------

    def vote_on_story(self, story_id: str, uid: str, vote: str) -> dict:
        """Record a vote on a story using a Firestore transaction."""
        doc_ref = self._db.collection(STORIES_COLLECTION).document(story_id)

        @firestore.transactional
        def _vote_txn(transaction, doc_ref):
            doc = doc_ref.get(transaction=transaction)
            if not doc.exists:
                raise ValueError("Story not found")

            data = doc.to_dict()
            upvotes = data.get("upvotes", 0)
            downvotes = data.get("downvotes", 0)
            voter_ids = data.get("voter_ids", {})

            old_vote = voter_ids.get(uid)

            # Remove old vote if exists
            if old_vote == "up":
                upvotes -= 1
            elif old_vote == "down":
                downvotes -= 1

            # Apply new vote
            if vote == "up":
                upvotes += 1
            else:
                downvotes += 1

            voter_ids[uid] = vote

            # Check regen threshold
            total = upvotes + downvotes
            flagged = total >= REGEN_VOTE_THRESHOLD and (downvotes / total) > REGEN_DOWNVOTE_RATIO

            transaction.update(doc_ref, {
                "upvotes": upvotes,
                "downvotes": downvotes,
                "voter_ids": voter_ids,
                "flagged_for_regen": flagged,
            })

            return {
                "upvotes": upvotes,
                "downvotes": downvotes,
                "userVote": vote,
                "flaggedForRegen": flagged,
            }

        transaction = self._db.transaction()
        return _vote_txn(transaction, doc_ref)

    def get_user_vote(self, story_id: str, uid: str) -> str | None:
        """Get a user's existing vote on a story."""
        doc_ref = self._db.collection(STORIES_COLLECTION).document(story_id)
        doc = doc_ref.get()

        if not doc.exists:
            return None

        voter_ids = doc.to_dict().get("voter_ids", {})
        return voter_ids.get(uid)

    # ------------------------------------------------------------------
    # Top papers query
    # ------------------------------------------------------------------

    def get_top_papers_by_field(self, limit_per_field: int = 3) -> dict[str, list[dict]]:
        """Query top upvoted stories grouped by field of study."""
        from papertales.config import FIELD_TAXONOMY

        result = {}
        for field in FIELD_TAXONOMY:
            query = (
                self._db.collection(STORIES_COLLECTION)
                .where("field_of_study", "==", field)
                .order_by("upvotes", direction=firestore.Query.DESCENDING)
                .limit(limit_per_field)
            )

            papers = []
            for doc in query.stream():
                data = doc.to_dict()
                if data.get("upvotes", 0) <= 0:
                    continue
                papers.append({
                    "id": doc.id,
                    "title": data.get("title", ""),
                    "paperTitle": data.get("paper_title", ""),
                    "upvotes": data.get("upvotes", 0),
                    "downvotes": data.get("downvotes", 0),
                    "ageGroup": data.get("age_group", ""),
                    "style": data.get("style", ""),
                    "archive": data.get("archive", ""),
                })

            if papers:
                result[field] = papers

        return result

    # ------------------------------------------------------------------
    # GCS helpers
    # ------------------------------------------------------------------

    def _gcs_path(self, story_id: str, version: int) -> str:
        return f"stories/{story_id}/v{version}.json"

    def _write_version_to_gcs(self, story_id: str, version: int, content: dict) -> None:
        blob = self._bucket.blob(self._gcs_path(story_id, version))
        blob.upload_from_string(
            json.dumps(content, default=str),
            content_type="application/json",
        )

    def _read_version_from_gcs(self, story_id: str, version: int) -> dict | None:
        blob = self._bucket.blob(self._gcs_path(story_id, version))
        try:
            data = blob.download_as_text()
            return json.loads(data)
        except Exception:
            logger.warning("Failed to read GCS blob: %s", self._gcs_path(story_id, version))
            return None

    def _delete_version_from_gcs(self, story_id: str, version: int) -> None:
        blob = self._bucket.blob(self._gcs_path(story_id, version))
        try:
            blob.delete()
        except Exception:
            logger.warning("Failed to delete GCS blob: %s", self._gcs_path(story_id, version))
