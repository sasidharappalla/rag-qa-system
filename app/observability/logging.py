"""Structured JSON logging + a FastAPI middleware that tags every request.

The format is intentionally plain JSON (no external deps) so we can pipe stdout into
any log aggregator. Sensitive fields (raw question text, document bodies) are NOT logged —
only shapes and metadata. See CLAUDE.md "Common Pitfalls" #5.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class _JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON so they ship cleanly to any log collector."""

    _RESERVED = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = _request_id_var.get()
        if request_id:
            payload["request_id"] = request_id
        # Merge any `extra=` fields the caller attached.
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON formatter on the root logger. Safe to call multiple times."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    # Drop any pre-existing handlers so we don't double-log.
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root.addHandler(handler)
    # Tame noisy libraries (still visible if level is DEBUG).
    for noisy in ("chromadb", "httpx", "urllib3", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request_id, time the request, and emit one structured access log line."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._logger = logging.getLogger("app.access")

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = _request_id_var.set(request_id)
        start = time.perf_counter()
        status_code = 500
        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            response.headers["x-request-id"] = request_id
            return response
        finally:
            latency_ms = int((time.perf_counter() - start) * 1000)
            self._logger.info(
                "request",
                extra={
                    "route": request.url.path,
                    "method": request.method,
                    "status_code": status_code,
                    "latency_ms": latency_ms,
                },
            )
            _request_id_var.reset(token)
