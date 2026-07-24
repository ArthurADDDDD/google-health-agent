"""Secret-safe production logging primitives."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Iterable
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

REDACTED = "[REDACTED]"
SENSITIVE_PATTERNS = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s,;]+"),
    re.compile(
        r'(?i)(["\']?(?:access_token|refresh_token|client_secret|smtp_password|'
        r'password|oauth_code)["\']?\s*[:=]\s*["\']?)[^"\'\s,;&]+'
    ),
    re.compile(r"(?i)([a-z][a-z0-9+.-]*://[^:/\s]+:)[^@\s/]+(@)"),
)


def redact_text(value: str, secret_values: Iterable[str] = ()) -> str:
    redacted = value
    for secret in secret_values:
        if secret:
            redacted = redacted.replace(secret, REDACTED)
    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub(
            rf"\1{REDACTED}\2" if pattern.groups == 2 else rf"\1{REDACTED}", redacted
        )
    return redacted


class RedactingFilter(logging.Filter):
    def __init__(self, secret_values: Iterable[str] = ()) -> None:
        super().__init__()
        self.secret_values = tuple(value for value in secret_values if value)

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage(), self.secret_values)
        record.args = ()
        return True


def configure_safe_logging(secret_values: Iterable[str] = ()) -> None:
    logging.basicConfig(level=logging.INFO)
    redactor = RedactingFilter(secret_values)
    for logger_name in ("", "uvicorn", "uvicorn.access", "uvicorn.error", "mcp"):
        logger = logging.getLogger(logger_name)
        logger.disabled = False
        for handler in logger.handlers:
            handler.addFilter(redactor)


class SafeRequestLoggingMiddleware:
    """Log request metadata without inspecting headers, query strings, or bodies."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = logging.getLogger("google_health_agent.requests")
        self.logger.disabled = False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.monotonic()
        request_id = uuid4().hex
        status_code = 500

        async def safe_send(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, safe_send)
        finally:
            self.logger.info(
                "request_id=%s method=%s path=%s status=%s duration_ms=%s",
                request_id,
                scope.get("method", "UNKNOWN"),
                scope.get("path", ""),
                status_code,
                round((time.monotonic() - started) * 1000, 2),
            )
