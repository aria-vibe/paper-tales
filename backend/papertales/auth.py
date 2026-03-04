"""Firebase Auth verification for PaperTales API."""

from dataclasses import dataclass

import firebase_admin
import firebase_admin.auth
from fastapi import Header, HTTPException

# ---------------------------------------------------------------------------
# Firebase Admin SDK — lazy singleton
# ---------------------------------------------------------------------------

_firebase_app: firebase_admin.App | None = None


def _get_firebase_app() -> firebase_admin.App:
    """Initialize Firebase Admin SDK once (uses ADC on Cloud Run)."""
    global _firebase_app
    if _firebase_app is None:
        _firebase_app = firebase_admin.initialize_app()
    return _firebase_app


# ---------------------------------------------------------------------------
# User info returned by token verification
# ---------------------------------------------------------------------------


@dataclass
class UserInfo:
    uid: str
    is_anonymous: bool


# ---------------------------------------------------------------------------
# Token verification — FastAPI dependency
# ---------------------------------------------------------------------------


async def verify_firebase_token(authorization: str = Header(None)) -> UserInfo:
    """Verify Firebase ID token from Authorization header. Returns UserInfo."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")

    token = authorization[len("Bearer "):]
    _get_firebase_app()

    try:
        decoded = firebase_admin.auth.verify_id_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    is_anonymous = (
        decoded.get("firebase", {}).get("sign_in_provider") == "anonymous"
    )

    return UserInfo(uid=decoded["uid"], is_anonymous=is_anonymous)
