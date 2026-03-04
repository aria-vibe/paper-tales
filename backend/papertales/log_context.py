"""Structured logging with session/job correlation via contextvars."""

import contextvars
import logging

current_session_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_session_id", default=""
)
current_job_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_job_id", default=""
)


class SessionLogFilter(logging.Filter):
    """Injects session_id and job_id from contextvars into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.session_id = current_session_id.get()
        record.job_id = current_job_id.get()
        return True


def setup_structured_logging(level: int = logging.INFO) -> None:
    """Replace basicConfig with a root handler that includes session/job context."""
    root = logging.getLogger()
    root.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.addFilter(SessionLogFilter())
    handler.setFormatter(
        logging.Formatter("%(name)s %(levelname)s [sid=%(session_id)s job=%(job_id)s]: %(message)s")
    )
    root.addHandler(handler)
