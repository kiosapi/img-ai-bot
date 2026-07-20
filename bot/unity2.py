"""unity2.ai provider client — OpenAI compatible + SSE streaming.

Base URL: https://api.unity2.ai/v1 (also https://unity2.ai/v1)
Privacy: NEVER expose provider domain/name to end-user. All user-facing errors generic Indonesian.
Endpoints:
  POST /v1/images/generations
  POST /v1/images/edits
  GET  /v1/models
Verified 2026-07-20:
  - GET /v1/models -> 5 models inc gpt-image-2
  - POST /v1/images/generations gpt-image-2 -> 200 b64_json 3.2MB after 51s
"""

from __future__ import annotations
import base64
import json
import asyncio
import httpx
from typing import Optional

REQUEST_TIMEOUT = httpx.Timeout(280.0, connect=20.0)
DOWNLOAD_TIMEOUT = httpx.Timeout(90.0, connect=15.0)


class Unity2Error(Exception):
    pass


def _gen_base(base_url: str) -> str:
    b = (base_url or "https://api.unity2.ai/v1").strip().rstrip("/")
    if "/v1" not in b:
        b = b + "/v1"
    return b


def _images_gen_url(base_url: str) -> str:
    return f"{_gen_base(base_url)}/images/generations"


def _images_edit_url(base_url: str) -> str:
    return f"{_gen_base(base_url)}/images/edits"


def _models_url(base_url: str) -> str:
    return f"{_gen_base(base_url)}/models"


async def _download_image(url: str) -> bytes:
    last_err = ""
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT, follow_redirects=True) as dl:
                r = await dl.get(url)
                if r.status_code == 200 and len(r.content) > 500:
                    return r.content
                last_err = f"HTTP {r.status_code}"
        except Exception as e:
            last_err = str(e)[:200]
        await asyncio.sleep(1.0 * (attempt + 1))
    raise Unity2Error(f"Gagal mengunduh hasil gambar: {last_err}")


def _extract_b64_from_json(j: dict) -> Optional[bytes]:
    try:
        data = j.get("data")
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                if first.get("b64_json"):
                    return base64.b64decode(first["b64_json"])
        if j.get("b64_json"):
            return base64.b64decode(j["b64_json"])
    except Exception:
        pass
    return None


def _extract_url_from_data(j: dict) -> Optional[str]:
    data = j.get("data")
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            u = first.get("url") or first.get("image_url")
            if u:
                return u
    return None


async def _parse_sse_stream(resp: httpx.Response) -> bytes:
    text = resp.text if hasattr(resp, "text") else ""
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload_raw = line[5:].strip()
        if not payload_raw or payload_raw == "[DONE]":
            continue
        try:
            ev = json.loads(payload_raw)
        except Exception:
            continue
        try:
            if ev.get("b64_json"):
                return base64.b64decode(ev["b64_json"])
        except Exception:
            pass
        data = ev.get("data")
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict) and first.get("b64_json"):
                try:
                    return base64.b64decode(first["b64_json"])
                except Exception:
                    pass
            if isinstance(first, dict) and first.get("url"):
                return await _download_image(first["url"])
        if ev.get("type") == "image_generation.completed":
            url = _extract_url_from_data(ev)
            if url:
                return await _download_image(url)
            b = _extract_b64_from_json(ev)
            if b:
                return b
    raise Unity2Error("Gambar gagal diproses, coba lagi ya.")


async def _try_parse_response(resp: httpx.Response) -> bytes:
    content_type = resp.headers.get("content-type", "").lower()
    if "text/event-stream" in content_type or ("event-stream" in (resp.text[:500] if resp.text else "")):
        try:
            b = await _parse_sse_stream(resp)
            if b:
                return b
        except Unity2Error:
            raise
        except Exception:
            raise Unity2Error("Gagal memproses stream gambar, coba lagi.")
    try:
        j = resp.json()
    except Exception:
        if "data:" in (resp.text or ""):
            try:
                return await _parse_sse_stream(resp)
            except Exception:
                pass
        raise Unity2Error(f"Layanan AI error {resp.status_code}, coba lagi.")
    b = _extract_b64_from_json(j)
    if b:
        return b
    url = _extract_url_from_data(j)
    if url:
        return await _download_image(url)
    if j.get("url") and isinstance(j["url"], str) and j["url"].startswith("http"):
        return await _download_image(j["url"])
    raise Unity2Error("Respon tidak valid dari layanan AI, coba lagi.")


async def generate_image(api_key: str, base_url: str, model_id: str, prompt: str, size: str = "1024x1024", negative_prompt: str = "", seed: str | None = None, ref_image: bytes | None = None) -> bytes:
    gen_url = _images_gen_url(base_url)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

    def _build_payload(use_stream: bool) -> dict:
        p: dict = {
            "model": model_id,
            "prompt": prompt,
            "n": 1,
            "size": size,
            "response_format": "b64_json",
        }
        if negative_prompt:
            p["negative_prompt"] = negative_prompt
        if seed:
            try:
                p["seed"] = int(str(seed).strip())
            except Exception:
                p["seed"] = str(seed).strip()
        if use_stream:
            p["stream"] = True
            headers["Accept"] = "text/event-stream"
        else:
            headers["Accept"] = "application/json"
        return p

    if ref_image:
        try:
            return await edit_image(api_key, base_url, model_id, ref_image, prompt, size)
        except Exception:
            pass

    for use_stream in (False, True):
        payload = _build_payload(use_stream)
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.post(gen_url, json=payload, headers=headers)
        except httpx.TimeoutException:
            raise Unity2Error("Layanan AI timeout — coba lagi ya.")
        except httpx.HTTPError:
            raise Unity2Error("Gagal menghubungi layanan AI, coba lagi.")
        if resp.status_code != 200:
            if not use_stream and resp.status_code in (400, 422):
                continue
            raise Unity2Error(f"Layanan AI sibuk ({resp.status_code}), coba lagi beberapa saat.")
        try:
            return await _try_parse_response(resp)
        except Unity2Error as e:
            if not use_stream and "tidak valid" in str(e).lower():
                continue
            raise
    raise Unity2Error("Gagal generate gambar, coba lagi.")


async def edit_image(api_key: str, base_url: str, model_id: str, image_bytes: bytes, prompt: str, size: str = "1024x1024", filename: str = "image.png") -> bytes:
    edit_url = _images_edit_url(base_url)
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "text/event-stream, application/json"}
    for use_stream in (False, True):
        files = {"image": (filename, image_bytes, "image/png")}
        data = {
            "model": model_id,
            "prompt": prompt,
            "n": "1",
            "size": size,
            "response_format": "b64_json",
        }
        if use_stream:
            data["stream"] = "true"
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.post(edit_url, headers=headers, data=data, files=files)
        except httpx.TimeoutException:
            raise Unity2Error("Layanan AI timeout saat edit, coba lagi.")
        except httpx.HTTPError:
            raise Unity2Error("Gagal menghubungi layanan AI untuk edit.")
        if resp.status_code != 200:
            if not use_stream and resp.status_code in (400, 422):
                continue
            raise Unity2Error(f"Layanan AI sibuk saat edit ({resp.status_code}), coba lagi.")
        try:
            return await _try_parse_response(resp)
        except Unity2Error:
            if not use_stream:
                continue
            raise
    raise Unity2Error("Gagal edit gambar, coba lagi.")


IMAGE_KEYWORDS = ["gpt-image", "dall-e", "dalle", "flux", "imagen", "stable", "sdxl", "midjourney", "image", "nano-banana"]
FALLBACK_IMAGE_MODELS = [
    {"id": "gpt-image-2", "object": "model", "display_name": "GPT Image 2", "owned_by": "openai", "description": "Verified 2026-07-20 unity2 200 b64 51s"},
    {"id": "gpt-image-1", "object": "model", "display_name": "GPT Image 1", "owned_by": "openai", "description": "High quality"},
    {"id": "gpt-image-1-mini", "object": "model", "display_name": "GPT Image 1 Mini", "owned_by": "openai", "description": "Fast mini"},
]

def _is_image_model(mid: str) -> bool:
    ml = mid.lower()
    return any(k in ml for k in IMAGE_KEYWORDS)

async def list_models(api_key: str, base_url: str) -> list[dict]:
    url = _models_url(base_url)
    headers = {"Authorization": f"Bearer {api_key}"}
    last_err = ""
    remote: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                j = resp.json()
                if isinstance(j, dict) and "data" in j and isinstance(j["data"], list):
                    remote = j["data"]
                elif isinstance(j, list):
                    remote = j
                else:
                    remote = [j]
            else:
                last_err = f"{resp.status_code}"
    except Exception as e:
        last_err = str(e)[:200]

    if remote:
        filtered = [m for m in remote if _is_image_model(m.get("id") or m.get("model") or "")]
        if filtered:
            return filtered

    if remote and len(remote) <= 10:
        # mix of chat+image, return fallback image only to avoid chat pollution
        return FALLBACK_IMAGE_MODELS

    if remote:
        return FALLBACK_IMAGE_MODELS

    if not remote:
        if last_err:
            return FALLBACK_IMAGE_MODELS
        raise Unity2Error(f"Gagal sync model: {last_err}")
    return remote
