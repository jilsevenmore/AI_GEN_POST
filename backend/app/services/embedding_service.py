"""Embedding service using Hugging Face sentence-transformers (BAAI/bge-base-en-v1.5)."""
from __future__ import annotations

import asyncio
import logging
import threading
from functools import lru_cache
from typing import Iterable, List, Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()


def _load_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            settings = get_settings()
            try:
                from sentence_transformers import SentenceTransformer
            except Exception as e:
                raise RuntimeError(
                    "sentence-transformers is not installed. Install dependencies (sentence-transformers, torch) to enable embeddings."
                ) from e
            logger.info("Loading embedding model %s on %s", settings.EMBEDDING_MODEL, settings.EMBEDDING_DEVICE)
            model_kwargs = {}
            if settings.HF_TOKEN:
                model_kwargs["token"] = settings.HF_TOKEN
            try:
                _model = SentenceTransformer(settings.EMBEDDING_MODEL, device=settings.EMBEDDING_DEVICE, **model_kwargs)
            except TypeError:
                # Older sentence-transformers versions may use use_auth_token
                if settings.HF_TOKEN:
                    _model = SentenceTransformer(settings.EMBEDDING_MODEL, device=settings.EMBEDDING_DEVICE, use_auth_token=settings.HF_TOKEN)
                else:
                    _model = SentenceTransformer(settings.EMBEDDING_MODEL, device=settings.EMBEDDING_DEVICE)
    return _model


def _embed_sync(texts: List[str], is_query: bool = False) -> List[List[float]]:
    settings = get_settings()
    model = _load_model()
    # BGE v1.5 retrieval: add instruction prefix for queries
    if is_query and "bge" in settings.EMBEDDING_MODEL.lower():
        texts = [f"Represent this sentence for searching relevant passages: {t}" for t in texts]
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return [emb.tolist() for emb in embeddings]


MAX_EMBED_TEXT_CHARS = 2000
MAX_EMBED_INPUT_CHARS = 12000
EMBED_CHUNK_CHARS = 1500
EMBED_CHUNK_OVERLAP = 200


def _chunk_text_for_embedding(text: str, chunk_size: int = EMBED_CHUNK_CHARS, overlap: int = EMBED_CHUNK_OVERLAP) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks: List[str] = []
    start = 0
    step = max(chunk_size - overlap, 1)
    while start < len(text):
        chunk = text[start:start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        if start + chunk_size >= len(text):
            break
        start += step
    return chunks[:20]  # safety cap


def _mean_pool(vectors: List[List[float]]) -> List[float]:
    if not vectors:
        return []
    dim = len(vectors[0])
    acc = [0.0] * dim
    for vec in vectors:
        for i, v in enumerate(vec):
            acc[i] += float(v)
    n = float(len(vectors))
    # normalize for cosine similarity
    norm = sum(x * x for x in acc) ** 0.5 or 1.0
    return [x / norm for x in acc]


async def embed_texts(texts: Iterable[str], is_query: bool = False) -> List[List[float]]:
    # For batch embedding keep simple truncation (used for short texts/queries)
    items = []
    for t in texts:
        s = (t or "").strip()
        if not s:
            continue
        items.append(s[:MAX_EMBED_TEXT_CHARS] if len(s) > MAX_EMBED_TEXT_CHARS else s)
    if not items:
        return []
    return await asyncio.to_thread(_embed_sync, items, is_query)


async def embed_text(text: str, is_query: bool = False) -> Optional[List[float]]:
    text = (text or "").strip()
    if not text:
        return None
    # For queries, keep single-vector behavior with truncation
    if is_query or len(text) <= MAX_EMBED_TEXT_CHARS:
        single = text[:MAX_EMBED_TEXT_CHARS]
        vectors = await asyncio.to_thread(_embed_sync, [single], is_query)
        return vectors[0] if vectors else None

    # For long document/index texts, chunk and mean-pool embeddings to reduce truncation loss
    capped = text[:MAX_EMBED_INPUT_CHARS]
    chunks = _chunk_text_for_embedding(capped)
    if not chunks:
        return None
    vectors = await asyncio.to_thread(_embed_sync, chunks, False)
    if not vectors:
        return None
    if len(vectors) == 1:
        return vectors[0]
    return _mean_pool(vectors)
