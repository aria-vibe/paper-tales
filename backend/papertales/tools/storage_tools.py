"""Tools for persisting stories and media to GCP."""

import base64
import json

from google.cloud import firestore, storage


def save_to_firestore(collection: str, document_id: str, data: str) -> dict:
    """Save a document to Firestore.

    Args:
        collection: Firestore collection name.
        document_id: Document ID.
        data: JSON string of the document data to save.

    Returns:
        A dict with 'success' and 'document_path', or 'error'.
    """
    try:
        data_dict = json.loads(data)
    except (json.JSONDecodeError, TypeError) as e:
        return {"error": f"Invalid JSON data: {e}"}

    try:
        db = firestore.Client()
        db.collection(collection).document(document_id).set(data_dict)
        return {
            "success": True,
            "document_path": f"{collection}/{document_id}",
        }
    except Exception as e:
        return {"error": f"Firestore save failed: {e}"}


def upload_to_gcs(
    bucket_name: str,
    blob_path: str,
    content: str,
    content_type: str = "application/json",
) -> dict:
    """Upload content to Google Cloud Storage.

    Args:
        bucket_name: GCS bucket name.
        blob_path: Destination path in the bucket.
        content: Content to upload. For binary types (image/png, audio/mpeg),
                 this should be base64-encoded.
        content_type: MIME type of the content.

    Returns:
        A dict with 'success', 'gcs_uri', and 'public_url', or 'error'.
    """
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)

        # Decode base64 for binary content types
        binary_types = ("image/", "audio/", "application/octet-stream")
        if any(content_type.startswith(bt) for bt in binary_types):
            data = base64.b64decode(content)
        else:
            data = content

        blob.upload_from_string(data, content_type=content_type)

        return {
            "success": True,
            "gcs_uri": f"gs://{bucket_name}/{blob_path}",
            "public_url": f"https://storage.googleapis.com/{bucket_name}/{blob_path}",
        }
    except Exception as e:
        return {"error": f"GCS upload failed: {e}"}
