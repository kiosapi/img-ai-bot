"""Unified image provider abstraction — Cubence + Right Codes.

Privacy: bot NEVER exposes provider name. User sees only display_name from ai_models.
API keys stored in settings table: cubence_api_key, cubence_base_url, rightcodes_api_key, rightcodes_base_url
Right Codes flow async: POST async=true -> task_id -> poll GET /v1/tasks/{id}

Docs: https://docs.right.codes/docs/rc_draw/
- POST https://www.right.codes/draw/v1/images/generations {model, prompt, size, imageSize, async:true}
- response {task_id}
- GET https://www.right.codes/v1/tasks/{task_id} -> statuses queued/in_progress/completed/failed
"""
from __future__ import annotations
import base64
import httpx
from typing import Optional, Dict, Any
import db

REQUEST_TIMEOUT = httpx.Timeout(280.0, connect=20.0)


class ProviderError(Exception):
    pass


async def _resolve_credentials(provider_id: str) -> tuple[str, str]:
    if provider_id == "cubence":
        key = await db.get_setting("cubence_api_key", "")
        base = await db.get_setting("cubence_base_url", "https://api-dmit.cubence.com")
        if not key:
            try:
                import config
                key = getattr(config, "CUBENCE_API_KEY", "")
                base = getattr(config, "CUBENCE_BASE_URL", base) or base
            except Exception:
                pass
        return key or "", (base or "https://api-dmit.cubence.com").rstrip("/")
    elif provider_id == "rightcodes":
        key = await db.get_setting("rightcodes_api_key", "")
        base = await db.get_setting("rightcodes_base_url", "https://www.right.codes/draw")
        return (key or "").strip(), (base or "https://www.right.codes/draw").rstrip("/")
    else:
        raise ProviderError(f"Unknown provider {provider_id}")


# ---------- Cubence (sync) ----------
async def _cubence_generate(api_key: str, base_url: str, model_id: str, prompt: str, size: str) -> bytes:
    url = f"{base_url}/v1/images/generations"
    payload = {"model": model_id, "prompt": prompt, "n": 1, "size": size}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException:
        raise ProviderError("Server AI kelamaan merespons (timeout). Coba lagi ya.")
    except httpx.HTTPError as e:
        raise ProviderError(f"Gagal menghubungi provider: {e}")
    if resp.status_code != 200:
        raise ProviderError(f"API {resp.status_code}: {resp.text[:400]}")
    try:
        data = resp.json()
        b64 = data["data"][0]["b64_json"]
    except Exception as e:
        raise ProviderError(f"Unexpected response: {e} | {resp.text[:200]}")
    return base64.b64decode(b64)


async def _cubence_edit(api_key: str, base_url: str, model_id: str, image_bytes: bytes, prompt: str, size: str) -> bytes:
    url = f"{base_url}/v1/images/edits"
    headers = {"Authorization": f"Bearer {api_key}"}
    files = {"image": ("image.png", image_bytes, "image/png")}
    data = {"model": model_id, "prompt": prompt, "n": "1", "size": size}
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, data=data, files=files)
    except httpx.TimeoutException:
        raise ProviderError("Server AI kelamaan merespons (timeout).")
    except httpx.HTTPError as e:
        raise ProviderError(f"Gagal menghubungi provider: {e}")
    if resp.status_code != 200:
        raise ProviderError(f"API {resp.status_code}: {resp.text[:400]}")
    try:
        j = resp.json()
        b64 = j["data"][0]["b64_json"]
    except Exception as e:
        raise ProviderError(f"Unexpected response: {e}")
    return base64.b64decode(b64)


# ---------- Right Codes delegates to rightcodes.py ----------
async def _rc_generate(api_key: str, base_url: str, model_id: str, prompt: str, size: str) -> bytes:
    # map bot sizes 1024x1024 -> ratio or keep? Right Codes doc says supports both ratio 1:1,16:9 and pixel 1024x1024
    # Keep pixel as is, but normalize: if size is 1024x1024 -> map to 1:1? doc shows size can be 1:1 etc OR 1024x1024, we keep original.
    # We'll pass as-is; rightcodes.py will handle.
    import rightcodes as rc
    # size translation: bot 1024x1024 -> Right Codes accepts either; keep but also try ratio fallback if API rejects?
    # For now keep original, but if contains 'x' convert to ratio-ish? Keep pixel for best compatibility.
    return await rc.generate_image(api_key, base_url, model_id, prompt, size)


async def _rc_edit(api_key: str, base_url: str, model_id: str, image_bytes: bytes, prompt: str, size: str) -> bytes:
    # Right Codes edit: use generations with reference image (doc: 带参考图) or edits endpoint.
    # Our rightcodes.py currently only has generate, but edit can be done via generate with ref image.
    # For simplicity, delegate to generate with ref image if needed, else use direct edit endpoint via rightcodes.py if we add.
    # Right Codes docs in images-generations.html: param image: data URL array (reference image)
    # So we can implement edit as generate with image.
    import rightcodes as rc
    # Use new edit helper that sends image as data URL array
    try:
        return await rc.generate_image(api_key, base_url, model_id, prompt, size, ref_images_b64=[image_bytes])
    except Exception:
        # fallback try edits endpoint if we add later -> for now raise
        raise


# ---------- Public ----------
async def generate_image(model: Dict[str, Any] | None, prompt: str, size: str, user_id: Optional[int] = None) -> bytes:
    if model is None:
        model = await db.get_default_model()
        if not model:
            # fallback legacy cubence.py directly
            try:
                import config
                from cubence import generate_image as legacy_gen
                return await legacy_gen(prompt, size)
            except Exception as e:
                raise ProviderError(f"No active model: {e}")

    provider_id = model["provider_id"]
    model_id = model["id"]
    api_key, base_url = await _resolve_credentials(provider_id)
    if not api_key:
        raise ProviderError(f"API key untuk provider {provider_id} belum di-set di admin.")

    if provider_id == "cubence":
        return await _cubence_generate(api_key, base_url, model_id, prompt, size)
    elif provider_id == "rightcodes":
        return await _rc_generate(api_key, base_url, model_id, prompt, size)
    else:
        raise ProviderError(f"Provider {provider_id} tidak dikenal")


async def edit_image(model: Dict[str, Any] | None, image_bytes: bytes, prompt: str, size: str, user_id: Optional[int] = None) -> bytes:
    if model is None:
        model = await db.get_default_model()
        if not model:
            try:
                from cubence import edit_image as legacy_edit
                return await legacy_edit(image_bytes, prompt, size)
            except Exception as e:
                raise ProviderError(f"No active model: {e}")

    provider_id = model["provider_id"]
    model_id = model["id"]
    api_key, base_url = await _resolve_credentials(provider_id)
    if not api_key:
        raise ProviderError(f"API key {provider_id} belum di-set.")

    if provider_id == "cubence":
        return await _cubence_edit(api_key, base_url, model_id, image_bytes, prompt, size)
    elif provider_id == "rightcodes":
        return await _rc_edit(api_key, base_url, model_id, image_bytes, prompt, size)
    else:
        raise ProviderError(f"Provider {provider_id} tidak dikenal")


async def list_remote_models(provider_id: str) -> list[dict]:
    api_key, base_url = await _resolve_credentials(provider_id)
    if not api_key:
        raise ProviderError(f"API key {provider_id} belum di-set.")

    if provider_id == "rightcodes":
        import rightcodes as rc
        return await rc.list_models(api_key, base_url)
    elif provider_id == "cubence":
        # cubence models endpoint
        url = f"{base_url.rstrip('/')}/v1/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                j = resp.json()
                if isinstance(j, dict) and "data" in j:
                    return j["data"]
                if isinstance(j, list):
                    return j
        except Exception:
            pass
        # fallback known
        return [{"id": "gpt-image-2", "object": "model"}]
    else:
        raise ProviderError(f"Unknown provider {provider_id}")

