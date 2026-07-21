"""Unified image provider abstraction — Cubence + Right Codes + ApiKeyFun + Unity2.

Privacy HARD RULE:
- Bot NEVER exposes provider name (cubence, rightcodes, apikey.fun, unity2, Right Codes, Cubence etc) to end-user.
- User sees only display_name from ai_models, or short code like AF/CB/RC/UN if needed.
- All ProviderError messages shown to user must be generic INDONESIAN, never contain provider id/name/domain.
- Internal logs may contain provider_id, but exceptions raised to handlers must be sanitized.

API keys stored in settings table:
  cubence_api_key, cubence_base_url,
  rightcodes_api_key, rightcodes_base_url,
  apikeyfun_api_key, apikeyfun_base_url,
  unity2_api_key, unity2_base_url

Production fix for duplicate model names across providers:
- ai_models.id = internal composite "provider_id:external_id" e.g. "cubence:gpt-image-2"
- external_id = real model name sent to upstream API
"""
from __future__ import annotations
import base64
import httpx
from typing import Optional, Dict, Any
import db

REQUEST_TIMEOUT = httpx.Timeout(280.0, connect=20.0)


class ProviderError(Exception):
    pass

# Generic user-facing messages — NEVER include provider name
ERR_NO_MODEL = "Tidak ada model aktif, hubungi admin."
ERR_NO_KEY = "Layanan AI belum dikonfigurasi, hubungi admin."
ERR_TIMEOUT = "Layanan AI timeout, coba lagi ya."
ERR_CONN = "Gagal menghubungi layanan AI, coba lagi."
ERR_BUSY = "Layanan AI sibuk, coba lagi beberapa saat."


def _real_model_id(model: Dict[str, Any]) -> str:
    ext = model.get("external_id")
    if ext:
        return ext
    mid = model.get("id", "")
    if ":" in mid:
        return mid.split(":", 1)[1]
    return mid


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
    elif provider_id == "apikeyfun":
        key = await db.get_setting("apikeyfun_api_key", "")
        base = await db.get_setting("apikeyfun_base_url", "https://api.apikey.fun/v1")
        if not key:
            try:
                import config
                key = getattr(config, "APIKEYFUN_API_KEY", "") or getattr(config, "APIKEY_FUN_API_KEY", "")
                base = getattr(config, "APIKEYFUN_BASE_URL", base) or base
            except Exception:
                pass
        return (key or "").strip(), (base or "https://api.apikey.fun/v1").rstrip("/")
    elif provider_id == "unity2":
        key = await db.get_setting("unity2_api_key", "")
        base = await db.get_setting("unity2_base_url", "https://api.unity2.ai/v1")
        if not key:
            try:
                import config
                key = getattr(config, "UNITY2_API_KEY", "") or getattr(config, "UNITY2_API_KEY_", "")
                base = getattr(config, "UNITY2_BASE_URL", base) or base
            except Exception:
                pass
        return (key or "").strip(), (base or "https://api.unity2.ai/v1").rstrip("/")
    else:
        raise ProviderError(ERR_NO_MODEL)


async def _cubence_generate(api_key: str, base_url: str, model_id: str, prompt: str, size: str, negative: str = "", seed: str | None = None, ref_images_b64: list[bytes] | None = None) -> bytes:
    url = f"{base_url}/v1/images/generations"
    # Cubence supports negative via extra field? For compatibility, append to prompt if provider doesn't support native
    full_prompt = prompt
    if negative:
        full_prompt = f"{prompt} -- avoid {negative}"
    # if ref images passed, use edit endpoint if available (fallback to generation)
    if ref_images_b64:
        # use edit variant if we have ref
        try:
            return await _cubence_edit(api_key, base_url, model_id, ref_images_b64[0], full_prompt, size)
        except Exception:
            pass
    payload: dict = {"model": model_id, "prompt": full_prompt, "n": 1, "size": size}
    if seed:
        try:
            payload["seed"] = int(seed)
        except Exception:
            payload["seed"] = seed
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException:
        raise ProviderError(ERR_TIMEOUT)
    except httpx.HTTPError:
        raise ProviderError(ERR_CONN)
    if resp.status_code != 200:
        raise ProviderError(f"{ERR_BUSY} ({resp.status_code})")
    try:
        data = resp.json()
        b64 = data["data"][0]["b64_json"]
    except Exception:
        raise ProviderError("Respon AI tidak valid, coba lagi.")
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
        raise ProviderError(ERR_TIMEOUT)
    except httpx.HTTPError:
        raise ProviderError(ERR_CONN)
    if resp.status_code != 200:
        raise ProviderError(f"{ERR_BUSY} ({resp.status_code})")
    try:
        j = resp.json()
        b64 = j["data"][0]["b64_json"]
    except Exception:
        raise ProviderError("Respon AI tidak valid, coba lagi.")
    return base64.b64decode(b64)


async def _rc_generate(api_key: str, base_url: str, model_id: str, prompt: str, size: str, negative: str = "", seed: str | None = None, ref_images_b64: list[bytes] | None = None) -> bytes:
    import rightcodes as rc
    import asyncio
    try:
        # rightcodes supports ref_images_b64 optional
        kwargs: dict = {}
        if ref_images_b64:
            kwargs["ref_images_b64"] = ref_images_b64
        full = prompt + (f" -- negative {negative}" if negative else "")
        return await asyncio.wait_for(
            rc.generate_image(api_key, base_url, model_id, full, size, **kwargs),
            timeout=420,
        )
    except asyncio.TimeoutError:
        raise ProviderError("Layanan AI timeout setelah 7 menit, coba lagi. Hasil mungkin sudah tersedia.")


async def _rc_edit(api_key: str, base_url: str, model_id: str, image_bytes: bytes, prompt: str, size: str) -> bytes:
    import rightcodes as rc
    try:
        return await rc.generate_image(api_key, base_url, model_id, prompt, size, ref_images_b64=[image_bytes])
    except Exception as e:
        msg = str(e)
        if "Layanan AI" in msg or "Gagal" in msg:
            raise
        raise ProviderError(f"Gagal edit gambar: {msg[:300]}")


async def _akf_generate(api_key: str, base_url: str, model_id: str, prompt: str, size: str, negative: str = "", seed: str | None = None, ref_images_b64: list[bytes] | None = None) -> bytes:
    import apikeyfun as akf
    try:
        # akf client supports negative_prompt, seed, image
        return await akf.generate_image(api_key, base_url, model_id, prompt, size, negative_prompt=negative, seed=seed, ref_image=ref_images_b64[0] if ref_images_b64 else None)
    except TypeError:
        # fallback to old signature
        try:
            return await akf.generate_image(api_key, base_url, model_id, prompt, size)
        except Exception as e:
            from apikeyfun import ApiKeyFunError as AFErr
            if isinstance(e, AFErr):
                raise ProviderError(str(e))
            raise ProviderError(f"Gagal generate gambar: {str(e)[:300]}")
    except Exception as e:
        from apikeyfun import ApiKeyFunError as AFErr
        if isinstance(e, AFErr):
            raise ProviderError(str(e))
        raise ProviderError(f"Gagal generate gambar: {str(e)[:300]}")


async def _akf_edit(api_key: str, base_url: str, model_id: str, image_bytes: bytes, prompt: str, size: str) -> bytes:
    import apikeyfun as akf
    try:
        return await akf.edit_image(api_key, base_url, model_id, image_bytes, prompt, size)
    except Exception as e:
        from apikeyfun import ApiKeyFunError as AFErr
        if isinstance(e, AFErr):
            raise ProviderError(str(e))
        raise ProviderError(f"Gagal edit gambar: {str(e)[:300]}")


async def _unity2_generate(api_key: str, base_url: str, model_id: str, prompt: str, size: str, negative: str = "", seed: str | None = None, ref_images_b64: list[bytes] | None = None) -> bytes:
    import unity2 as u2
    try:
        return await u2.generate_image(api_key, base_url, model_id, prompt, size, negative_prompt=negative, seed=seed, ref_image=ref_images_b64[0] if ref_images_b64 else None)
    except TypeError:
        try:
            return await u2.generate_image(api_key, base_url, model_id, prompt, size)
        except Exception as e:
            from unity2 import Unity2Error as U2Err
            if isinstance(e, U2Err):
                raise ProviderError(str(e))
            raise ProviderError(f"Gagal generate gambar: {str(e)[:300]}")
    except Exception as e:
        from unity2 import Unity2Error as U2Err
        if isinstance(e, U2Err):
            raise ProviderError(str(e))
        raise ProviderError(f"Gagal generate gambar: {str(e)[:300]}")


async def _unity2_edit(api_key: str, base_url: str, model_id: str, image_bytes: bytes, prompt: str, size: str) -> bytes:
    import unity2 as u2
    try:
        return await u2.edit_image(api_key, base_url, model_id, image_bytes, prompt, size)
    except Exception as e:
        from unity2 import Unity2Error as U2Err
        if isinstance(e, U2Err):
            raise ProviderError(str(e))
        raise ProviderError(f"Gagal edit gambar: {str(e)[:300]}")


def _is_hard_provider_error(err: Exception) -> bool:
    msg = str(err).lower()
    if any(x in msg for x in ("502", "503", "504", "timeout", "timed out", "bad gateway", "sibuk (502)", "sibuk (503)", "sibuk (504)", "429")):
        return True
    return False


def _status_from_err(err: Exception) -> int | None:
    import re
    m = re.search(r"\((\d{3})\)", str(err))
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None


async def generate_image(model: Dict[str, Any] | None, prompt: str, size: str, user_id: Optional[int] = None, negative: str = "", seed: str | None = None, ref_images_b64: list[bytes] | None = None) -> bytes:
    # Smart failover: skip providers with recent 502/timeout, prefer higher success rate 1h
    from provider_health import HEALTH

    async def _generate_with_model(m: Dict[str, Any]) -> bytes:
        pid = m["provider_id"]
        rid = _real_model_id(m)
        if HEALTH.is_skipped(pid):
            raise ProviderError(ERR_BUSY)
        api_key, base_url = await _resolve_credentials(pid)
        if not api_key:
            raise ProviderError(ERR_NO_KEY)
        try:
            if pid == "cubence":
                out = await _cubence_generate(api_key, base_url, rid, prompt, size, negative=negative, seed=seed, ref_images_b64=ref_images_b64)
            elif pid == "rightcodes":
                out = await _rc_generate(api_key, base_url, rid, prompt, size, negative=negative, seed=seed, ref_images_b64=ref_images_b64)
            elif pid == "apikeyfun":
                out = await _akf_generate(api_key, base_url, rid, prompt, size, negative=negative, seed=seed, ref_images_b64=ref_images_b64)
            elif pid == "unity2":
                out = await _unity2_generate(api_key, base_url, rid, prompt, size, negative=negative, seed=seed, ref_images_b64=ref_images_b64)
            else:
                raise ProviderError(ERR_NO_MODEL)
            HEALTH.record_success(pid)
            return out
        except ProviderError as e:
            HEALTH.record_failure(pid, hard=_is_hard_provider_error(e), status_code=_status_from_err(e))
            raise
        except Exception as e:
            HEALTH.record_failure(pid, hard=_is_hard_provider_error(e), status_code=_status_from_err(e))
            raise ProviderError(ERR_BUSY) from e

    if model is None:
        model = await db.get_default_model()
        if not model:
            try:
                from cubence import generate_image as legacy_gen
                return await legacy_gen(prompt, size)
            except Exception:
                raise ProviderError(ERR_NO_MODEL)

    tried: set[str] = set()
    errors: list[str] = []

    # Primary model first if not skipped
    primary_pid = model.get("provider_id") if model else None
    if model and primary_pid and not HEALTH.is_skipped(primary_pid):
        try:
            return await _generate_with_model(model)
        except ProviderError as e:
            tried.add(primary_pid)
            errors.append(str(e)[:120])
        except Exception as e:
            tried.add(primary_pid or "")
            errors.append(str(e)[:120])
    elif primary_pid:
        tried.add(primary_pid)

    # Failover: priority ASC then re-rank by health (skip + success rate)
    try:
        all_providers = await db.list_providers_failover() if hasattr(db, "list_providers_failover") else await db.list_providers()
        active_ids = [p["id"] for p in all_providers if p.get("is_active") and p["id"] not in tried]
        ordered = HEALTH.sort_provider_ids(active_ids)
        # keep original priority as secondary sort already in list; sort_provider_ids prioritizes non-skipped + rate
        all_models = await db.list_models(active_only=True)
        for pid in ordered:
            if HEALTH.is_skipped(pid):
                continue
            fallback_model = None
            for mm in all_models:
                if mm.get("provider_id") == pid:
                    fallback_model = mm
                    break
            if not fallback_model:
                continue
            try:
                return await _generate_with_model(fallback_model)
            except Exception as e:
                tried.add(pid)
                errors.append(str(e)[:80])
                continue
    except Exception:
        pass

    # last resort: raise first/last error generic
    if errors:
        raise ProviderError(errors[0] if errors else ERR_BUSY)
    raise ProviderError(ERR_BUSY)


async def edit_image(model: Dict[str, Any] | None, image_bytes: bytes, prompt: str, size: str, user_id: Optional[int] = None) -> bytes:
    if model is None:
        model = await db.get_default_model()
        if not model:
            try:
                from cubence import edit_image as legacy_edit
                return await legacy_edit(image_bytes, prompt, size)
            except Exception:
                raise ProviderError(ERR_NO_MODEL)

    provider_id = model["provider_id"]
    real_id = _real_model_id(model)
    api_key, base_url = await _resolve_credentials(provider_id)
    if not api_key:
        raise ProviderError(ERR_NO_KEY)

    if provider_id == "cubence":
        return await _cubence_edit(api_key, base_url, real_id, image_bytes, prompt, size)
    elif provider_id == "rightcodes":
        return await _rc_edit(api_key, base_url, real_id, image_bytes, prompt, size)
    elif provider_id == "apikeyfun":
        return await _akf_edit(api_key, base_url, real_id, image_bytes, prompt, size)
    elif provider_id == "unity2":
        return await _unity2_edit(api_key, base_url, real_id, image_bytes, prompt, size)
    else:
        raise ProviderError(ERR_NO_MODEL)


async def list_remote_models(provider_id: str) -> list[dict]:
    api_key, base_url = await _resolve_credentials(provider_id)
    if not api_key:
        raise ProviderError(ERR_NO_KEY)

    if provider_id == "rightcodes":
        import rightcodes as rc
        return await rc.list_models(api_key, base_url)
    elif provider_id == "apikeyfun":
        import apikeyfun as akf
        return await akf.list_models(api_key, base_url)
    elif provider_id == "unity2":
        import unity2 as u2
        return await u2.list_models(api_key, base_url)
    elif provider_id == "cubence":
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
        return [{"id": "gpt-image-2", "object": "model"}]
    else:
        raise ProviderError(ERR_NO_MODEL)
