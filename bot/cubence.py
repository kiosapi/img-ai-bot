"""Client for the Cubence image API (OpenAI-compatible)."""
import base64
import httpx

from config import CUBENCE_API_KEY, CUBENCE_BASE_URL, IMAGE_MODEL


class CubenceError(Exception):
    pass


async def generate_image(prompt: str, size: str = "1024x1024") -> bytes:
    """Text-to-image. Returns raw PNG bytes."""
    url = f"{CUBENCE_BASE_URL}/v1/images/generations"
    payload = {"model": IMAGE_MODEL, "prompt": prompt, "n": 1, "size": size}
    headers = {
        "Authorization": f"Bearer {CUBENCE_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(url, json=payload, headers=headers)
    return _parse_image_response(resp)


async def edit_image(image_bytes: bytes, prompt: str, size: str = "1024x1024",
                     filename: str = "image.png") -> bytes:
    """Image-to-image / edit. Returns raw PNG bytes."""
    url = f"{CUBENCE_BASE_URL}/v1/images/edits"
    headers = {"Authorization": f"Bearer {CUBENCE_API_KEY}"}
    files = {"image": (filename, image_bytes, "image/png")}
    data = {"model": IMAGE_MODEL, "prompt": prompt, "n": "1", "size": size}
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(url, headers=headers, data=data, files=files)
    return _parse_image_response(resp)


def _parse_image_response(resp: httpx.Response) -> bytes:
    if resp.status_code != 200:
        text = resp.text[:400]
        raise CubenceError(f"API {resp.status_code}: {text}")
    try:
        data = resp.json()
        b64 = data["data"][0]["b64_json"]
    except Exception as e:
        raise CubenceError(f"Unexpected response: {e}")
    return base64.b64decode(b64)
