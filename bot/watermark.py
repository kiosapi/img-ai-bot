"""Watermark — premium @imgaai_bot iOS frosted glass pill (clean single layer)."""
from __future__ import annotations
import io
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance  # type: ignore
    PIL_OK = True
except ImportError:
    PIL_OK = False

import db
import feature_flags as ff

WATERMARK_DEFAULT = "@imgaai_bot"
_FONT_DIR = Path(__file__).resolve().parent / "fonts"


async def should_watermark(user_id: int) -> tuple[bool, str]:
    enabled = await ff.watermark_enabled()
    if not enabled:
        return False, ""
    text = WATERMARK_DEFAULT
    free_only = await ff.watermark_free_only()
    if free_only:
        try:
            if await db.is_premium(user_id):
                return False, ""
        except Exception:
            pass
    return True, text


def _load_premium_font(size: int):
    """Prefer Medium/SemiBold (cleaner than ExtraBold at small sizes)."""
    names = [
        "Manrope-Medium.ttf",
        "Manrope-SemiBold.ttf",
        "Inter-Medium.ttf",
        "Inter-SemiBold.ttf",
        "SpaceGrotesk-Medium.ttf",
        "SpaceGrotesk-SemiBold.ttf",
        "Manrope-ExtraBold.ttf",
        "SpaceGrotesk-Bold.ttf",
        "Inter-Bold.ttf",
        "DejaVuSans.ttf",
        "Arial.ttf",
    ]
    for name in names:
        p = _FONT_DIR / name
        if p.is_file():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)  # type: ignore
    except Exception:
        return ImageFont.load_default()


def _rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    """L mask full white rounded rect on black."""
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    try:
        d.rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255)
    except Exception:
        d.rectangle([0, 0, size[0] - 1, size[1] - 1], fill=255)
    return m


def apply_watermark_image(image_bytes: bytes, watermark_text: str) -> bytes:
    """Clean iOS-style frosted pill — single text layer, no double shadow.

    Technique:
    1) Crop pill region → strong Gaussian blur → paste back only under rounded mask
    2) Semi-transparent dark glass fill (soft, not solid black box)
    3) Thin white stroke + subtle top sheen
    4) Text rendered 2x supersampled then downscaled (crisp premium look)
    5) NO text shadow (was looking like double text)
    """
    if not PIL_OK or not watermark_text:
        return image_bytes
    text = WATERMARK_DEFAULT

    try:
        im = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        w, h = im.size
        base = max(w, h)

        # Smaller, subtler than before
        font_size = max(15, int(base / 48))
        pad_x = max(14, int(base / 56))
        pad_y = max(8, int(base / 100))
        radius = max(10, int(font_size * 0.9))
        margin = max(14, int(base / 50))

        font = _load_premium_font(font_size)

        probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
        try:
            bb = probe.textbbox((0, 0), text, font=font)
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
            ty0 = bb[1]
        except Exception:
            tw, th, ty0 = int(len(text) * font_size * 0.55), font_size, 0

        pill_w = tw + pad_x * 2
        pill_h = th + pad_y * 2
        max_w = int(w * 0.48)
        if pill_w > max_w:
            scale = max_w / pill_w
            font_size = max(13, int(font_size * scale))
            font = _load_premium_font(font_size)
            pad_x = max(12, int(pad_x * scale))
            pad_y = max(6, int(pad_y * scale))
            radius = max(9, int(font_size * 0.9))
            try:
                bb = probe.textbbox((0, 0), text, font=font)
                tw, th, ty0 = bb[2] - bb[0], bb[3] - bb[1], bb[1]
            except Exception:
                tw, th, ty0 = int(len(text) * font_size * 0.55), font_size, 0
            pill_w = tw + pad_x * 2
            pill_h = th + pad_y * 2

        x1 = max(margin, w - pill_w - margin)
        y1 = max(margin, h - pill_h - margin)
        x2 = min(w - margin, x1 + pill_w)
        y2 = min(h - margin, y1 + pill_h)
        pill_w = x2 - x1
        pill_h = y2 - y1

        # --- Frosted glass: blur crop, mask to rounded pill only ---
        box = (int(x1), int(y1), int(x2), int(y2))
        try:
            crop = im.crop(box)
            blur_r = max(10, int(base / 70))
            frosted = crop.filter(ImageFilter.GaussianBlur(radius=blur_r))
            frosted = ImageEnhance.Brightness(frosted).enhance(1.05)
            # slight desat for glass
            frosted = ImageEnhance.Color(frosted).enhance(0.85)
            rmask = _rounded_mask((pill_w, pill_h), radius)
            # paste frosted only where mask is white
            region = im.crop(box)
            region = Image.composite(frosted, region, rmask)
            im.paste(region, box)
        except Exception:
            pass

        # Glass fill — soft charcoal, NOT solid black box
        glass_layer = Image.new("RGBA", (pill_w, pill_h), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glass_layer)
        try:
            gd.rounded_rectangle([0, 0, pill_w - 1, pill_h - 1], radius=radius, fill=(18, 18, 20, 110))
        except Exception:
            gd.rectangle([0, 0, pill_w - 1, pill_h - 1], fill=(18, 18, 20, 110))

        # Top sheen (subtle)
        try:
            hi_h = max(2, pill_h // 2)
            gd.rounded_rectangle(
                [1, 1, pill_w - 2, hi_h],
                radius=max(4, radius - 2),
                fill=(255, 255, 255, 22),
            )
        except Exception:
            pass

        # Hairline stroke
        try:
            gd.rounded_rectangle(
                [0, 0, pill_w - 1, pill_h - 1],
                radius=radius,
                outline=(255, 255, 255, 48),
                width=1,
            )
        except Exception:
            pass

        # --- Text: 2x supersample for crisp premium edges, SINGLE layer (no shadow) ---
        ss = 2
        tw_ss = pill_w * ss
        th_ss = pill_h * ss
        text_layer = Image.new("RGBA", (tw_ss, th_ss), (0, 0, 0, 0))
        font_ss = _load_premium_font(font_size * ss)
        td = ImageDraw.Draw(text_layer)
        try:
            bb = td.textbbox((0, 0), text, font=font_ss)
            tw2, th2, ty2 = bb[2] - bb[0], bb[3] - bb[1], bb[1]
        except Exception:
            tw2, th2, ty2 = int(len(text) * font_size * ss * 0.55), font_size * ss, 0
        tx = (tw_ss - tw2) // 2
        ty = (th_ss - th2) // 2 - ty2
        # single white text only — no offset shadow (shadow = "double" look)
        td.text((tx, ty), text, font=font_ss, fill=(255, 255, 255, 235))
        text_layer = text_layer.resize((pill_w, pill_h), Image.Resampling.LANCZOS)

        glass_layer = Image.alpha_composite(glass_layer, text_layer)

        # Composite pill onto full image
        overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        overlay.paste(glass_layer, (int(x1), int(y1)), glass_layer)
        combined = Image.alpha_composite(im, overlay)

        out = io.BytesIO()
        combined.convert("RGB").save(out, format="PNG", optimize=True)
        return out.getvalue()
    except Exception:
        return image_bytes
