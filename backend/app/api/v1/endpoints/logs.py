"""Frontend log ingestion.

The browser frontend posts structured log entries here so they land in
``logs/frontend.log`` alongside the backend's ``app`` and ``llm`` channels,
giving a single structured place for an agent to diagnose problems.

No auth is required by design: the frontend may post logs before sign-in or
after sign-out. In production, sit this behind a reverse-proxy rate limit.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.logging import get_frontend_logger

router = APIRouter()


class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str
    service: str = "frontend"
    request_id: Optional[str] = None
    url: Optional[str] = None
    component: Optional[str] = None
    extra: Optional[dict] = None


class LogBatch(BaseModel):
    entries: List[LogEntry]


@router.post("", status_code=204, tags=["Logs"])
async def ingest_frontend_logs(batch: LogBatch, request: Request) -> None:
    """Receive a batch of frontend log records and write them to logs/frontend.log."""
    logger = get_frontend_logger()
    client_ip = request.client.host if request.client else None

    for entry in batch.entries:
        level = getattr(logging, entry.level.upper(), logging.INFO)
        fields: dict[str, object] = {
            "channel": "frontend",
            "service": "frontend",
        }
        if entry.request_id:
            fields["request_id"] = entry.request_id
        if entry.url:
            fields["url"] = entry.url
        if entry.component:
            fields["component"] = entry.component
        if client_ip:
            fields["client_ip"] = client_ip
        if entry.extra:
            fields.update(entry.extra)
        # Strip None values so extra fields stay clean.
        fields = {k: v for k, v in fields.items() if v is not None}
        logger.log(level, entry.message, extra=fields)
