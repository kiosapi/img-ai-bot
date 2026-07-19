"""Prompt enhancer — OpenAI-compatible via Cubence.

Uses CUBENCE_BASE_URL + /v1/chat/completions with same API key.
Model taken from DB setting `enhance_model`, default gpt-4o-mini.
Falls back to original prompt on any failure.
"""
from __future__ import annotations

import logging

import httpx

import db
import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a prompt enhancer for AI image generation. Enhance the user prompt "
    "to be more detailed, vivid, with style details, lighting, composition. "
    "Keep under 300 chars, return only enhanced prompt, no extra explanation."
)

REQUEST_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


async def enhance_prompt(prompt: str) -> str:
    """Enhance user prompt via chat completions. Returns original on failure."""
    if not prompt or not prompt.strip():
        return prompt
    try:
        model = await db.get_enhance_model()
    except Exception:
        model = "gpt-4o-mini"

    url = f"{config.CUBENCE_BASE_URL.rstrip('/')}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.CUBENCE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 400,
        "temperature": 0.7,
    }
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            logger.warning("enhance_prompt HTTP %s: %s", resp.status_code, resp.text[:400])
            return prompt
        data = resp.json()
        # standard OpenAI chat completion shape
        choices = data.get("choices") or []
        if not choices:
            return prompt
        content = choices[0].get("message", {}).get("content")
        if not content or not content.strip():
            return prompt
        # trim quotes/newlines, enforce limit ~500 chars but spec says 300, keep lenient
        enhanced = content.strip().strip('"').strip("'").strip()
        # if model added extra explanation, take first non-empty paragraph
        if "\n" in enhanced:
            # keep whole if short, else first line
            lines = [ln.strip() for ln in enhanced.splitlines() if ln.strip()]
            if lines:
                # prefer first line, but if it is very short and second exists, join?
                enhanced = lines[0]
        if len(enhanced) > 600:
            enhanced = enhanced[:600].rsplit(" ", 1)[0]
        return enhanced or prompt
    except Exception as e:
        logger.warning("enhance_prompt failed: %s", e)
        return prompt
