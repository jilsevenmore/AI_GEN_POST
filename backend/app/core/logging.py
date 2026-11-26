"""Structured logging for AI Gen Post.

Two logger channels:

* ``app``   -- general backend software (requests, jobs, publishing, DB/Redis)
* ``llm``   -- LLM calls and outputs (provider, model, prompt, response, latency, fallback)

Every record is one JSON line, so an agent or operator can read the logs and
diagnose problems. Files (relative to the backend folder):

* ``logs/backend.log``  -- app channel
* ``logs/llm.log``      -- LLM channel
* ``logs/errors.log``   -- ERROR + records that reach the root logger
* ``logs/frontend.log`` -- frontend logs ingested via POST /api/v1/logs
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any, Optional

from app.services.security import mask_secrets, sanitize_for_logging

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_LOG_DIR = os.path.join(BACKEND_DIR, "logs")

# LogRecord attributes injected by the logging machinery -- never emitted as fields.
RESERVED_ATTRS = {
    "name", "msg", "args", "created", "filename", "funcName", "levelname",
    "levelno", "lineno", "module", "msecs", "message", "pathname",
    "process", "processName", "relativeCreated", "thread", "threadName",
    "exc_info", "exc_text", "stack_info", "channel", "request_id", "taskName",
}

# Async-safe request context (thread-local is unsafe under FastAPI/asyncio).
_request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_channel_var: ContextVar[Optional[str]] = ContextVar("channel", default=None)


class RequestContext:
    """Current request context, propagated into every log record of the task."""

    @classmethod
    def set_request_id(cls, request_id: str) -> None:
        _request_id_var.set(request_id)

    @classmethod
    def get_request_id(cls) -> Optional[str]:
        return _request_id_var.get()

    @classmethod
    def set_channel(cls, channel: str) -> None:
        _channel_var.set(channel)

    @classmethod
    def get_channel(cls) -> Optional[str]:
        return _channel_var.get()

    @classmethod
    def clear_request_id(cls) -> None:
        _request_id_var.set(None)
        _channel_var.set(None)


class ChannelFilter(logging.Filter):
    """Stamps a fixed channel name on every record handled by a channel logger."""

    def __init__(self, channel: str):
        super().__init__()
        self.channel = channel

    def filter(self, record: logging.LogRecord) -> bool:
        record.channel = getattr(record, "channel", None) or self.channel
        return True


class StructuredFormatter(logging.Formatter):
    """Emits one JSON object per log record, with secrets masked."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "channel": getattr(record, "channel", None) or _channel_var.get() or "app",
            "service": "backend",
            "request_id": getattr(record, "request_id", None) or _request_id_var.get(),
            "message": mask_secrets(record.getMessage()),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        for key, value in record.__dict__.items():
            if key in RESERVED_ATTRS:
                continue
            if key in ("channel", "request_id"):
                continue
            log_data[key] = mask_secrets(value) if isinstance(value, str) else value

        if record.exc_info and record.exc_info[0]:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


def _make_file_handler(path: str, level: int, fmt: logging.Formatter) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        path,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(fmt)
    return handler


def setup_logging(settings: Optional[Any] = None) -> None:
    """Configure the structured logging system.

    Safe to call multiple times; replaces root handlers each time.
    Intended to be called once at application startup (FastAPI lifespan).
    """
    level_name = getattr(settings, "LOG_LEVEL", "INFO") if settings else "INFO"
    try:
        level = getattr(logging, level_name.upper(), logging.INFO)
    except AttributeError:
        level = logging.INFO
    log_dir = getattr(settings, "LOG_DIR", "logs") if settings else "logs"
    if not os.path.isabs(log_dir):
        log_dir = os.path.join(BACKEND_DIR, log_dir)
    log_to_file = getattr(settings, "LOG_TO_FILE", True) if settings else True
    json_format = getattr(settings, "LOG_JSON", True) if settings else True
    max_bytes = getattr(settings, "LOG_ROTATION_MAX_BYTES", 10 * 1024 * 1024) if settings else 10 * 1024 * 1024
    backup_count = getattr(settings, "LOG_ROTATION_BACKUP_COUNT", 5) if settings else 5

    os.makedirs(log_dir, exist_ok=True)

    fmt: logging.Formatter = StructuredFormatter() if json_format else logging.Formatter(
        "%(asctime)s %(levelname)s [%(channel)s] %(name)s: %(message)s"
    )

    root = logging.getLogger()
    root.handlers = []
    root.setLevel(level)

    # Console (stderr) -- always on so logs are visible in terminals/docker.
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(fmt)
    root.addHandler(console)

    def _channel_logger(name: str, filename: str) -> logging.Logger:
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.setLevel(level)
        logger.propagate = True  # records also reach root console + errors.log
        if log_to_file:
            fh = _make_file_handler(os.path.join(log_dir, filename), level, fmt)
            fh.maxBytes = max_bytes
            fh.backupCount = backup_count
            fh.addFilter(ChannelFilter(name))
            logger.addHandler(fh)
        return logger

    _channel_logger("app", "backend.log")
    _channel_logger("llm", "llm.log")
    _channel_logger("frontend", "frontend.log")

    # Errors from any logger that propagates to root (uvicorn, unhandled, etc.)
    if log_to_file:
        errors = _make_file_handler(os.path.join(log_dir, "errors.log"), logging.ERROR, fmt)
        root.addHandler(errors)

    logging.getLogger("app").info("Structured logging configured", extra={"channel": "app"})


def new_request_id() -> str:
    return uuid.uuid4().hex


_llm_logger = logging.getLogger("llm")


def _truncate(text: Optional[str], max_chars: int = 4000) -> Optional[str]:
    if text is None:
        return None
    return sanitize_for_logging(text, max_length=max_chars)


def log_llm_call(
    provider: str,
    model: str,
    *,
    prompt: Optional[str] = None,
    request_id: Optional[str] = None,
    require_json: Optional[bool] = None,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    """Log an outgoing LLM call before it happens."""
    fields: dict[str, Any] = {
        "event": "llm.call",
        "provider": provider,
        "model": model,
        "prompt": _truncate(prompt),
        "prompt_chars": len(prompt) if prompt else 0,
    }
    if require_json is not None:
        fields["require_json"] = require_json
    if request_id:
        fields["request_id"] = request_id
    if extra:
        fields.update(extra)
    _llm_logger.info("LLM call %s/%s", provider, model, extra=fields)


def log_llm_response(
    provider: str,
    model: str,
    *,
    response: Optional[str] = None,
    latency_ms: Optional[float] = None,
    request_id: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    """Log an LLM response after it completes."""
    fields: dict[str, Any] = {
        "event": "llm.response",
        "provider": provider,
        "model": model,
        "response": _truncate(response),
        "response_chars": len(response) if response else 0,
    }
    if latency_ms is not None:
        fields["latency_ms"] = round(latency_ms, 2)
    if request_id:
        fields["request_id"] = request_id
    if extra:
        fields.update(extra)
    _llm_logger.info(
        "LLM response %s/%s (%.1fms)", provider, model, latency_ms or 0, extra=fields
    )


def log_llm_error(
    provider: str,
    model: str,
    error: BaseException,
    *,
    latency_ms: Optional[float] = None,
    request_id: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    """Log a failed LLM call."""
    fields: dict[str, Any] = {
        "event": "llm.error",
        "provider": provider,
        "model": model,
        "error_type": type(error).__name__,
        "error_message": mask_secrets(str(error)),
    }
    if latency_ms is not None:
        fields["latency_ms"] = round(latency_ms, 2)
    if request_id:
        fields["request_id"] = request_id
    if extra:
        fields.update(extra)
    _llm_logger.error(
        "LLM error %s/%s: %s", provider, model, error, extra=fields, exc_info=True
    )


def log_llm_fallback(
    from_provider: str,
    to_provider: str,
    reason: str,
    *,
    request_id: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    """Log an LLM provider fallback."""
    fields: dict[str, Any] = {
        "event": "llm.fallback",
        "from_provider": from_provider,
        "to_provider": to_provider,
        "reason": reason,
    }
    if request_id:
        fields["request_id"] = request_id
    if extra:
        fields.update(extra)
    _llm_logger.warning(
        "LLM fallback %s -> %s: %s", from_provider, to_provider, reason, extra=fields
    )


def get_llm_logger() -> logging.Logger:
    return _llm_logger


def get_app_logger() -> logging.Logger:
    return logging.getLogger("app")


def get_frontend_logger() -> logging.Logger:
    return logging.getLogger("frontend")
