"""Firestore + GCS persistence for PaperTales stories."""

import base64
import hashlib
import json
import logging

from datetime import datetime, timezone

from fastapi import HTTPException
from google.cloud import firestore, storage

logger = logging.getLogger(__name__)

STORIES_COLLECTION = "stories"
DAILY_USAGE_COLLECTION = "daily_usage"
GCS_BUCKET = "papertales-media"
MAX_VERSIONS = 5
REGEN_VOTE_THRESHOLD = 10
REGEN_DOWNVOTE_RATIO = 0.5

QUOTA_ANONYMOUS = 3
QUOTA_LOGGED_IN = 10


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

        return self._load_story_content(story_id, data)

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
        session_id: str = "",
    ) -> dict:
        """Save story: media to GCS version folder, text+metadata to Firestore."""
        doc_ref = self._db.collection(STORIES_COLLECTION).document(story_id)
        doc = doc_ref.get()

        if doc.exists:
            current_version = doc.to_dict().get("current_version", 0)
        else:
            current_version = 0

        next_version = current_version + 1

        # Separate media from text content
        clean_story, media_items = self._extract_media_from_story(story_content)

        # Upload media files to GCS version folder
        if media_items:
            self._upload_media_to_gcs(story_id, next_version, media_items)

        # Upsert Firestore metadata + text content
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
            "title": clean_story.get("title", ""),
            "updated_at": now,
            "current_version": next_version,
            "flagged_for_regen": False,
            "session_id": session_id,
            # Text content (new format)
            "scenes": clean_story.get("scenes", []),
            "glossary": clean_story.get("glossary", {}),
            "fact_check": clean_story.get("factCheck", clean_story.get("fact_check", {})),
            "what_we_learned": clean_story.get("whatWeLearned", clean_story.get("what_we_learned", "")),
            "source_paper": clean_story.get("sourcePaper", clean_story.get("source_paper", {})),
            "ageGroup": clean_story.get("ageGroup", age_group),
            "createdAt": clean_story.get("createdAt", now.isoformat()),
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
        return self._load_story_content(story_id, data)

    def _load_story_content(self, story_id: str, data: dict) -> dict | None:
        """Load story content with backward-compatible format detection."""
        # New format: scenes stored directly in Firestore
        if isinstance(data.get("scenes"), list):
            return self._build_story_from_firestore(story_id, data)

        # Old format: monolithic JSON blob in GCS
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
        """Query top stories grouped by field of study.

        Uses a single query (no composite index required) and groups in Python.
        Falls back to recent stories if none have upvotes.
        """
        def _doc_to_entry(doc, data):
            return {
                "id": doc.id,
                "title": data.get("title", ""),
                "paperTitle": data.get("paper_title", ""),
                "upvotes": data.get("upvotes", 0),
                "downvotes": data.get("downvotes", 0),
                "ageGroup": data.get("age_group", ""),
                "style": data.get("style", ""),
                "archive": data.get("archive", ""),
            }

        # Try upvoted stories first (single-field index, no composite needed)
        query = (
            self._db.collection(STORIES_COLLECTION)
            .order_by("upvotes", direction=firestore.Query.DESCENDING)
            .limit(limit_per_field * 14)
        )

        result: dict[str, list[dict]] = {}
        for doc in query.stream():
            data = doc.to_dict()
            if data.get("upvotes", 0) <= 0:
                break  # Sorted desc, so no more upvoted stories
            field = data.get("field_of_study", "Other")
            bucket = result.setdefault(field, [])
            if len(bucket) < limit_per_field:
                bucket.append(_doc_to_entry(doc, data))

        if result:
            return result

        # Fallback: show recent stories regardless of upvotes
        query = (
            self._db.collection(STORIES_COLLECTION)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit_per_field * 14)
        )

        for doc in query.stream():
            data = doc.to_dict()
            field = data.get("field_of_study", "Other")
            bucket = result.setdefault(field, [])
            if len(bucket) < limit_per_field:
                bucket.append(_doc_to_entry(doc, data))

        return result

    # ------------------------------------------------------------------
    # Daily quota
    # ------------------------------------------------------------------

    def _daily_usage_doc_id(self, uid: str) -> str:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return f"{uid}_{today}"

    def check_and_increment_quota(self, uid: str, is_anonymous: bool) -> None:
        """Increment daily usage count. Raises HTTPException(429) if over limit."""
        limit = QUOTA_ANONYMOUS if is_anonymous else QUOTA_LOGGED_IN
        doc_id = self._daily_usage_doc_id(uid)
        doc_ref = self._db.collection(DAILY_USAGE_COLLECTION).document(doc_id)

        @firestore.transactional
        def _txn(transaction, doc_ref):
            doc = doc_ref.get(transaction=transaction)
            current = doc.to_dict().get("count", 0) if doc.exists else 0

            if current >= limit:
                raise HTTPException(
                    status_code=429,
                    detail=f"Daily limit reached ({limit} generations/day). Try again tomorrow.",
                )

            transaction.set(doc_ref, {
                "count": current + 1,
                "uid": uid,
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }, merge=True)

        transaction = self._db.transaction()
        _txn(transaction, doc_ref)

    def get_remaining_quota(self, uid: str, is_anonymous: bool) -> int:
        """Return how many generations the user has left today."""
        limit = QUOTA_ANONYMOUS if is_anonymous else QUOTA_LOGGED_IN
        doc_id = self._daily_usage_doc_id(uid)
        doc_ref = self._db.collection(DAILY_USAGE_COLLECTION).document(doc_id)
        doc = doc_ref.get()

        current = doc.to_dict().get("count", 0) if doc.exists else 0
        return max(0, limit - current)

    # ------------------------------------------------------------------
    # GCS helpers
    # ------------------------------------------------------------------

    def _gcs_path(self, story_id: str, version: int) -> str:
        """Legacy path for monolithic JSON blobs."""
        return f"stories/{story_id}/v{version}.json"

    def _gcs_media_prefix(self, story_id: str, version: int) -> str:
        return f"stories/{story_id}/v{version}/"

    def _gcs_image_path(self, story_id: str, version: int, scene_index: int) -> str:
        return f"stories/{story_id}/v{version}/scene_{scene_index}_image.png"

    def _gcs_audio_path(self, story_id: str, version: int, scene_index: int) -> str:
        return f"stories/{story_id}/v{version}/scene_{scene_index}_audio.mp3"

    def _gcs_title_audio_path(self, story_id: str, version: int) -> str:
        return f"stories/{story_id}/v{version}/title_audio.mp3"

    def _gcs_conclusion_audio_path(self, story_id: str, version: int) -> str:
        return f"stories/{story_id}/v{version}/conclusion_audio.mp3"

    def _extract_media_from_story(self, story_content: dict) -> tuple[dict, list[dict]]:
        """Strip base64 media from scenes + top-level audio, return (text_only_story, media_items)."""
        import copy
        clean_story = copy.deepcopy(story_content)
        media_items = []

        # Top-level title / conclusion audio
        for key, media_label in [("titleAudioBase64", "title_audio"), ("conclusionAudioBase64", "conclusion_audio")]:
            raw = clean_story.pop(key, None)
            if raw:
                try:
                    data = base64.b64decode(raw)
                    media_items.append({
                        "type": media_label,
                        "data": data,
                        "content_type": "audio/mpeg",
                    })
                except Exception:
                    logger.warning("Failed to decode %s base64", media_label)

        for i, scene in enumerate(clean_story.get("scenes", [])):
            if "imageBase64" in scene:
                raw = scene.pop("imageBase64")
                if raw:
                    try:
                        data = base64.b64decode(raw)
                        media_items.append({
                            "scene_index": i,
                            "type": "image",
                            "data": data,
                            "content_type": "image/png",
                        })
                    except Exception:
                        logger.warning("Failed to decode image base64 for scene %d", i)

            if "audioBase64" in scene:
                raw = scene.pop("audioBase64")
                if raw:
                    try:
                        data = base64.b64decode(raw)
                        media_items.append({
                            "scene_index": i,
                            "type": "audio",
                            "data": data,
                            "content_type": "audio/mpeg",
                        })
                    except Exception:
                        logger.warning("Failed to decode audio base64 for scene %d", i)

        return clean_story, media_items

    def _upload_media_to_gcs(self, story_id: str, version: int, media_items: list[dict]) -> None:
        """Upload extracted media items to individual GCS files."""
        for item in media_items:
            media_type = item["type"]
            if media_type == "image":
                path = self._gcs_image_path(story_id, version, item["scene_index"])
            elif media_type == "audio":
                path = self._gcs_audio_path(story_id, version, item["scene_index"])
            elif media_type == "title_audio":
                path = self._gcs_title_audio_path(story_id, version)
            elif media_type == "conclusion_audio":
                path = self._gcs_conclusion_audio_path(story_id, version)
            else:
                logger.warning("Unknown media type: %s", media_type)
                continue

            blob = self._bucket.blob(path)
            blob.upload_from_string(item["data"], content_type=item["content_type"])

    def _rehydrate_media(self, story_id: str, version: int, scenes: list[dict]) -> tuple[list[dict], dict]:
        """Attach media URLs (proxy paths) to scenes + return top-level audio URLs.

        Returns (hydrated_scenes, extra_audio) where extra_audio may contain
        ``titleAudioUrl`` and/or ``conclusionAudioUrl``.

        Instead of embedding base64 data (which can exceed Cloud Run response
        size limits), this returns relative URLs that the frontend fetches via
        the ``/api/stories/{id}/media/...`` proxy endpoint.
        """
        import copy
        hydrated = copy.deepcopy(scenes)
        extra_audio: dict = {}

        for i, scene in enumerate(hydrated):
            img_blob = self._bucket.blob(self._gcs_image_path(story_id, version, i))
            if img_blob.exists():
                scene["imageUrl"] = f"/api/stories/{story_id}/media/scene_{i}_image.png"

            audio_blob = self._bucket.blob(self._gcs_audio_path(story_id, version, i))
            if audio_blob.exists():
                scene["audioUrl"] = f"/api/stories/{story_id}/media/scene_{i}_audio.mp3"

        # Title / conclusion audio
        for path_fn, filename, key in [
            (self._gcs_title_audio_path, "title_audio.mp3", "titleAudioUrl"),
            (self._gcs_conclusion_audio_path, "conclusion_audio.mp3", "conclusionAudioUrl"),
        ]:
            blob = self._bucket.blob(path_fn(story_id, version))
            if blob.exists():
                extra_audio[key] = f"/api/stories/{story_id}/media/{filename}"

        return hydrated, extra_audio

    def get_media_blob(self, story_id: str, filename: str) -> bytes | None:
        """Download a media file from GCS for the given story's current version.

        Returns the raw bytes or None if not found.
        """
        doc_ref = self._db.collection(STORIES_COLLECTION).document(story_id)
        doc = doc_ref.get()
        if not doc.exists:
            return None

        version = doc.to_dict().get("current_version", 1)
        path = f"stories/{story_id}/v{version}/{filename}"
        blob = self._bucket.blob(path)

        if not blob.exists():
            return None

        return blob.download_as_bytes()

    def _build_story_from_firestore(self, story_id: str, data: dict) -> dict:
        """Reconstruct full story response from Firestore data + GCS media."""
        version = data.get("current_version", 1)
        scenes, extra_audio = self._rehydrate_media(story_id, version, data.get("scenes", []))

        story = {
            "id": story_id,
            "title": data.get("title", ""),
            "scenes": scenes,
            **extra_audio,
            "paperTitle": data.get("paper_title", ""),
            "authors": data.get("authors", ""),
            "fieldOfStudy": data.get("field_of_study", "Other"),
            "sourceUrl": data.get("source_url", ""),
            "version": version,
            "upvotes": data.get("upvotes", 0),
            "downvotes": data.get("downvotes", 0),
        }

        # Include optional text fields if present
        if "glossary" in data:
            story["glossary"] = data["glossary"]
        if "fact_check" in data:
            story["factCheck"] = data["fact_check"]
        if "what_we_learned" in data:
            story["whatWeLearned"] = data["what_we_learned"]
        if "source_paper" in data:
            story["sourcePaper"] = data["source_paper"]
        if "ageGroup" in data:
            story["ageGroup"] = data["ageGroup"]
        elif "age_group" in data:
            story["ageGroup"] = data["age_group"]
        if "style" in data:
            story["style"] = data["style"]
        if "createdAt" in data:
            story["createdAt"] = data["createdAt"]
        if data.get("session_id"):
            story["sessionId"] = data["session_id"]

        return story

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
        """Delete both old-format blob and new-format media folder."""
        # Old format: single JSON blob
        old_blob = self._bucket.blob(self._gcs_path(story_id, version))
        try:
            old_blob.delete()
        except Exception:
            pass  # May not exist in old format

        # New format: all blobs under version prefix
        prefix = self._gcs_media_prefix(story_id, version)
        try:
            blobs = list(self._bucket.list_blobs(prefix=prefix))
            for blob in blobs:
                try:
                    blob.delete()
                except Exception:
                    logger.warning("Failed to delete GCS blob: %s", blob.name)
        except Exception:
            logger.warning("Failed to list GCS blobs with prefix: %s", prefix)
