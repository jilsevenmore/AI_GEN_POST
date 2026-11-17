"""Prompt enhancement with local Ollama, Hugging Face, and OpenAI fallback."""
from __future__ import annotations

import logging
from typing import Optional

from openai import AsyncOpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)

MAX_PROMPT_ENHANCE_INPUT_CHARS = 6000


def _truncate_for_enhancement(text: str, max_chars: int = MAX_PROMPT_ENHANCE_INPUT_CHARS) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[Input truncated for prompt enhancement]"


async def enhance_prompt(user_prompt: str, purpose: str = "image generation prompt") -> str:
    """Enhance a prompt using local Ollama (if enabled), Hugging Face, then GPT-4o mini fallback."""
    settings = get_settings()
    prompt = _truncate_for_enhancement(user_prompt or "")
    if not prompt:
        return (user_prompt or "").strip()

    system = (
        "You are an expert prompt engineer. Rewrite and enhance the user's prompt to be clear, specific, and high-quality "
        f"for {purpose}. Preserve intent, key details, brand/style constraints, and requested outputs. "
        "Return only the enhanced prompt text."
    )

    # Primary option A: Local Ollama (free, offline after model download)
    if settings.OLLAMA_PROMPT_ENHANCE_ENABLED and settings.OLLAMA_MODEL:
        try:
            client = AsyncOpenAI(api_key="ollama", base_url=settings.OLLAMA_BASE_URL)
            resp = await client.chat.completions.create(
                model=settings.OLLAMA_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
            )
            content = (resp.choices[0].message.content or "").strip()
            if content:
                return content
        except Exception as e:
            logger.warning("Ollama prompt enhancement failed, trying next provider: %s", e)

    # Primary option B: MiniMax via Hugging Face Inference Providers (OpenAI-compatible router)
    if settings.MINIMAX_PROMPT_ENHANCE_ENABLED:
        hf_token = settings.MINIMAX_API_KEY or settings.HF_TOKEN
        hf_base_url = settings.MINIMAX_BASE_URL or settings.HF_BASE_URL or "https://router.huggingface.co/v1"
        hf_model = settings.MINIMAX_MODEL or settings.HF_PROMPT_MODEL or "MiniMaxAI/MiniMax-M2.7"
        if hf_token:
            try:
                client = AsyncOpenAI(api_key=hf_token, base_url=hf_base_url)
                resp = await client.chat.completions.create(
                    model=hf_model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.4,
                )
                content = (resp.choices[0].message.content or "").strip()
                if content:
                    return content
            except Exception as e:
                logger.warning("MiniMax (Hugging Face) prompt enhancement failed, falling back to GPT-4o mini: %s", e)

    # Fallback: GPT-4o mini
    if settings.OPENAI_API_KEY:
        try:
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            resp = await client.chat.completions.create(
                model=settings.OPENAI_MODEL or "gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
            )
            content = (resp.choices[0].message.content or "").strip()
            if content:
                return content
        except Exception as e:
            logger.warning("GPT-4o mini prompt enhancement fallback failed: %s", e)

    return prompt
