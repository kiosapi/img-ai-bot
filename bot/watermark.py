"""Watermark helpers — premium @imgaai_bot frosted glass pill (iOS-style)."""
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
    # Spec: text-only @imgaai_bot — ignore "Buat di" legacy stored text
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
    """Load bundled premium fonts first (Space Grotesk / Manrope / Inter), then system."""
    names = [
        "SpaceGrotesk-Bold.ttf",
        "SpaceGrotesk-SemiBold.ttf",
        "Manrope-ExtraBold.ttf",
        "Manrope-Bold.ttf",
        "Satoshi-Bold.ttf",
        "Inter-Bold.ttf",
        "InterTight-Bold.ttf",
        "DejaVuSans-Bold.ttf",
        "NotoSans-Bold.ttf",
        "Arial_Bold.ttf",
        "Arial.ttf",
    ]
    # 1) bundled fonts/ next to this module
    for name in names:
        p = _FONT_DIR / name
        if p.is_file():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    # 2) bare filename (system / cwd)
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    # 3) common linux paths in slim images
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)  # type: ignore
    except Exception:
        return ImageFont.load_default()


def apply_watermark_image(image_bytes: bytes, watermark_text: str) -> bytes:
    """iOS-style frosted glass pill — text only @imgaai_bot.

    - Premium font from bot/fonts (Space Grotesk Bold preferred)
    - Real Gaussian blur of image region under pill
    - Translucent dark glass fill + top specular highlight + soft white stroke
    - Bottom-right, responsive scale, no emoji/icon
    """
    if not PIL_OK or not watermark_text:
        return image_bytes
    text = WATERMARK_DEFAULT  # hard lock per product spec

    try:
        im = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        w, h = im.size
        base = max(w, h)

        font_size = max(20, int(base / 36))
        pad_x = max(18, int(base / 48))
        pad_y = max(10, int(base / 88))
        radius = max(14, int(font_size * 1.05))
        margin = max(18, int(base / 42))

        font = _load_premium_font(font_size)

        # Measure
        probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
        try:
            bb = probe.textbbox((0, 0), text, font=font)
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
        except Exception:
            tw, th = int(len(text) * font_size * 0.58), font_size

        pill_w = tw + pad_x * 2
        pill_h = th + pad_y * 2 + 4
        max_w = int(w * 0.55)
        if pill_w > max_w:
            scale = max_w / pill_w
            font_size = max(16, int(font_size * scale))
            font = _load_premium_font(font_size)
            pad_x = max(14, int(pad_x * scale))
            pad_y = max(8, int(pad_y * scale))
            radius = max(12, int(font_size * 1.05))
            try:
                bb = probe.textbbox((0, 0), text, font=font)
                tw, th = bb[2] - bb[0], bb[3] - bb[1]
            except Exception:
                tw, th = int(len(text) * font_size * 0.58), font_size
            pill_w = tw + pad_x * 2
            pill_h = th + pad_y * 2 + 4

        x1 = max(margin, w - pill_w - margin)
        y1 = max(margin, h - pill_h - margin)
        x2 = min(w - margin, x1 + pill_w)
        y2 = min(h - margin, y1 + pill_h)
        # re-sync size from clamped box
        pill_w = x2 - x1
        pill_h = y2 - y1

        # --- Frosted glass: strong blur of region under pill ---
        expand = max(8, int(base / 120))
        cx1 = max(0, x1 - expand)
        cy1 = max(0, y1 - expand)
        cx2 = min(w, x2 + expand)
        cy2 = min(h, y2 + expand)
        try:
            crop = im.crop((cx1, cy1, cx2, cy2))
            blur_r = max(8, int(base / 90))  # stronger = more iOS glass
            frosted = crop.filter(ImageFilter.GaussianBlur(radius=blur_r))
            # slightly brighten frosted area (iOS sheen)
            frosted = ImageEnhance.Brightness(frosted).enhance(1.08)
            frosted = ImageEnhance.Contrast(frosted).enhance(0.92)
            im.paste(frosted, (cx1, cy1))
        except Exception:
            pass

        # Masked pill composite
        overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        mask = Image.new("L", im.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        try:
            mask_draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=255)
        except Exception:
            mask_draw.rectangle([x1, y1, x2, y2], fill=255)

        # Glass body: deep charcoal translucent (iOS Control Center vibe)
        glass = Image.new("RGBA", im.size, (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glass)
        try:
            gdraw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=(22, 22, 24, 150))
        except Exception:
            gdraw.rectangle([x1, y1, x2, y2], fill=(22, 22, 24, 150))

        # Soft white veil for frosted feel
        veil = Image.new("RGBA", im.size, (0, 0, 0, 0))
        vdraw = ImageDraw.Draw(veil)
        try:
            vdraw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=(255, 255, 255, 28))
        except Exception:
            vdraw.rectangle([x1, y1, x2, y2], fill=(255, 255, 255, 28))

        # Top specular highlight (glass reflection)
        hi_h = max(3, pill_h // 2)
        hi = Image.new("RGBA", im.size, (0, 0, 0, 0))
        hdraw = ImageDraw.Draw(hi)
        try:
            hdraw.rounded_rectangle(
                [x1 + 1, y1 + 1, x2 - 1, y1 + hi_h],
                radius=max(6, radius - 2),
                fill=(255, 255, 255, 38),
            )
        except Exception:
            pass

        # Stroke
        stroke = Image.new("RGBA", im.size, (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(stroke)
        try:
            sdraw.rounded_rectangle(
                [x1 + 0.5, y1 + 0.5, x2 - 0.5, y2 - 0.5],
                radius=radius,
                outline=(255, 255, 255, 55),
                width=1,
            )
        except Exception:
            pass

        # Apply layers
        for layer in (glass, veil, hi, stroke):
            overlay = Image.alpha_composite(overlay, layer)

        # Text with soft shadow
        tdraw = ImageDraw.Draw(overlay)
        # vertical center text
        try:
            bb = tdraw.textbbox((0, 0), text, font=font)
            th = bb[3] - bb[1]
            ty_off = bb[1]
        except Exception:
            th, ty_off = font_size, 0
        text_x = x1 + (pill_w - tw) // 2
        text_y = y1 + (pill_h - th) // 2 - ty_off
        tdraw.text((text_x + 1, text_y + 1), text, font=font, fill=(0, 0, 0, 90))
        tdraw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 245))

        combined = Image.alpha_composite(im, overlay)
        out = io.BytesIO()
        combined.convert("RGB").save(out, format="PNG", optimize=True)
        return out.getvalue()
    except Exception:
        return image_bytes
