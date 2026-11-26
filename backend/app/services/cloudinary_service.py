"""Cloudinary upload helpers for publishing-ready public image URLs."""
from __future__ import annotations

import asyncio
import base64
import logging
import tempfile
from pathlib import Path
from typing import Iterable, Optional

import cloudinary
import cloudinary.uploader
import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
_configured = False


def _ensure_configured() -> None:
    global _configured
    if _configured:
        return
    settings = get_settings()
    if not (settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET):
        raise RuntimeError("Cloudinary credentials are not configured")
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )
    _configured = True


async def _resolve_upload_source(source: str) -> str:
    """Return a path/URL/data URI acceptable to Cloudinary uploader."""
    if source.startswith("data:"):
        header, _, b64data = source.partition(",")
        if not b64data:
            raise ValueError("Invalid data URL")
        # Prefer uploading decoded bytes via temp file for reliability
        suffix = ".png"
        if "image/jpeg" in header or "image/jpg" in header:
            suffix = ".jpg"
        elif "image/webp" in header:
            suffix = ".webp"
        data = base64.b64decode(b64data)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        try:
            tmp.write(data)
            tmp.flush()
            return tmp.name
        finally:
            tmp.close()

    if source.startswith("http://") or source.startswith("https://"):
        # If it's already a Cloudinary delivery URL, reuse it
        settings = get_settings()
        cloud_name = settings.CLOUDINARY_CLOUD_NAME or ""
        if cloud_name and f"res.cloudinary.com/{cloud_name}/" in source:
            return source
        # Cloudinary can fetch remote URLs directly, but downloading first is safer for signed/expiring URLs
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(source)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            suffix = ".png"
            if "jpeg" in content_type or "jpg" in content_type:
                suffix = ".jpg"
            elif "webp" in content_type:
                suffix = ".webp"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            try:
                tmp.write(resp.content)
                tmp.flush()
                return tmp.name
            finally:
                tmp.close()

    # Assume local file path
    if Path(source).exists():
        return source
    raise ValueError("Unsupported image source for Cloudinary upload")


async def upload_image_to_cloudinary(
    source: str,
    *,
    folder: str = "published",
    public_id: Optional[str] = None,
    tags: Optional[Iterable[str]] = None,
) -> str:
    """Upload an image (URL, data URL, or local path) and return secure public URL."""
    _ensure_configured()
    settings = get_settings()
    upload_source = await _resolve_upload_source(source)

    # Reuse existing Cloudinary URL
    if upload_source == source and source.startswith("http"):
        return source

    folder_map = {
        "published": settings.CLOUDINARY_FOLDER_PUBLISHED,
        "drafts": settings.CLOUDINARY_FOLDER_DRAFTS,
        "library": settings.CLOUDINARY_FOLDER_LIBRARY,
    }
    target_folder = folder_map.get(folder, folder)

    def _do_upload() -> dict:
        options = {
            "folder": target_folder,
            "resource_type": "image",
            "overwrite": True,
            "invalidate": True,
        }
        if public_id:
            # sanitize public_id for cloudinary
            safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in public_id)
            options["public_id"] = safe_id
        if tags:
            options["tags"] = list(tags)
        return cloudinary.uploader.upload(upload_source, **options)

    try:
        result = await asyncio.to_thread(_do_upload)
        secure_url = result.get("secure_url") or result.get("url")
        if not secure_url:
            raise RuntimeError("Cloudinary upload did not return a URL")
        return secure_url
    finally:
        # Clean up temp files we created
        try:
            p = Path(upload_source)
            if upload_source != source and p.exists() and p.name.startswith("tmp"):
                p.unlink(missing_ok=True)
        except Exception:
            pass


async def upload_text_to_cloudinary(
    text: str,
    *,
    filename: str = "source.txt",
    folder: str = "source_files",
    public_id: Optional[str] = None,
    tags: Optional[Iterable[str]] = None,
) -> str:
    """Upload text content as a raw Cloudinary asset and return secure public URL."""
    _ensure_configured()
    suffix = Path(filename).suffix or ".txt"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, mode="w", encoding="utf-8")
    try:
        tmp.write(text or "")
        tmp.flush()
        tmp_path = tmp.name
    finally:
        tmp.close()

    settings = get_settings()
    folder_map = {
        "published": settings.CLOUDINARY_FOLDER_PUBLISHED,
        "drafts": settings.CLOUDINARY_FOLDER_DRAFTS,
        "library": settings.CLOUDINARY_FOLDER_LIBRARY,
        "source_files": "source_files",
    }
    target_folder = folder_map.get(folder, folder)

    def _do_upload() -> dict:
        options = {
            "folder": target_folder,
            "resource_type": "raw",
            "overwrite": True,
            "invalidate": True,
            "use_filename": True,
            "unique_filename": False,
        }
        if public_id:
            safe_id = "".join(c if c.isalnum() or c in "-_/" else "_" for c in public_id)
            options["public_id"] = safe_id
        if tags:
            options["tags"] = list(tags)
        return cloudinary.uploader.upload(tmp_path, **options)

    try:
        result = await asyncio.to_thread(_do_upload)
        secure_url = result.get("secure_url") or result.get("url")
        if not secure_url:
            raise RuntimeError("Cloudinary raw upload did not return a URL")
        return secure_url
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass
