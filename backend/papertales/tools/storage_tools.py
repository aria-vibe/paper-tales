"""Tools for persisting stories and media to GCP."""


def save_to_firestore(collection: str, document_id: str, data: dict) -> dict:
    """Save a document to Firestore.

    Args:
        collection: Firestore collection name.
        document_id: Document ID.
        data: The document data to save.

    Returns:
        A dict with 'success' and 'document_path'.
    """
    # TODO: Implement with google-cloud-firestore
    return {
        "success": True,
        "document_path": f"{collection}/{document_id}",
    }


def upload_to_gcs(
    bucket_name: str, blob_path: str, file_content: str
) -> dict:
    """Upload a file to Google Cloud Storage.

    Args:
        bucket_name: GCS bucket name.
        blob_path: Destination path in the bucket.
        file_content: Content to upload (base64-encoded for binary).

    Returns:
        A dict with 'success' and 'public_url'.
    """
    # TODO: Implement with google-cloud-storage
    return {
        "success": True,
        "public_url": f"https://storage.googleapis.com/{bucket_name}/{blob_path}",
    }
