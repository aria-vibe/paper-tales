"""Firebase Auth verification and rate limiting for PaperTales API."""

import time
from collections import deque

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
# Token verification — FastAPI dependency
# ---------------------------------------------------------------------------


async def verify_firebase_token(authorization: str = Header(None)) -> str:
    """Verify Firebase ID token from Authorization header. Returns uid."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")

    token = authorization[len("Bearer "):]
    _get_firebase_app()

    try:
        decoded = firebase_admin.auth.verify_id_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    return decoded["uid"]


# ---------------------------------------------------------------------------
# Rate limiter — in-memory, per-user
# ---------------------------------------------------------------------------

_RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds
_RATE_LIMIT_MAX = 5  # max requests per window


class RateLimiter:
    """Simple in-memory per-user rate limiter."""

    def __init__(self, window: int = _RATE_LIMIT_WINDOW, max_requests: int = _RATE_LIMIT_MAX):
        self.window = window
        self.max_requests = max_requests
        self._requests: dict[str, deque[float]] = {}

    def check(self, uid: str) -> None:
        """Raise 429 if user has exceeded rate limit."""
        now = time.time()
        cutoff = now - self.window

        if uid not in self._requests:
            self._requests[uid] = deque()

        q = self._requests[uid]

        # Evict old entries
        while q and q[0] < cutoff:
            q.popleft()

        if len(q) >= self.max_requests:
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")

        q.append(now)


# Module-level singleton
rate_limiter = RateLimiter()
