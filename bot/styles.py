"""
Style presets for image generation.
"""

STYLES: dict[str, dict] = {
    "none": {
        "id": "none",
        "label_id": "Default",
        "label_en": "Default",
        "emoji": "⚪",
        "prompt_suffix": "",
    },
    "anime": {
        "id": "anime",
        "label_id": "Anime",
        "label_en": "Anime",
        "emoji": "🎌",
        "prompt_suffix": "anime style, vibrant colors, detailed",
    },
    "realistic": {
        "id": "realistic",
        "label_id": "Realistis",
        "label_en": "Realistic",
        "emoji": "🧑‍🎨",
        "prompt_suffix": "photorealistic, highly detailed, 8k",
    },
    "cyberpunk": {
        "id": "cyberpunk",
        "label_id": "Cyberpunk",
        "label_en": "Cyberpunk",
        "emoji": "🌃",
        "prompt_suffix": "cyberpunk style, neon lights, futuristic",
    },
    "ghibli": {
        "id": "ghibli",
        "label_id": "Ghibli",
        "label_en": "Ghibli",
        "emoji": "🌿",
        "prompt_suffix": "Studio Ghibli style, soft colors, whimsical",
    },
    "watercolor": {
        "id": "watercolor",
        "label_id": "Aquarel",
        "label_en": "Watercolor",
        "emoji": "🎨",
        "prompt_suffix": "watercolor painting style",
    },
    "3d": {
        "id": "3d",
        "label_id": "3D Render",
        "label_en": "3D Render",
        "emoji": "🧊",
        "prompt_suffix": "3D render, octane, highly detailed, studio lighting",
    },
    "oil": {
        "id": "oil",
        "label_id": "Lukisan Minyak",
        "label_en": "Oil Painting",
        "emoji": "🖼️",
        "prompt_suffix": "oil painting style, textured brush strokes",
    },
    "minimalist": {
        "id": "minimalist",
        "label_id": "Minimalis",
        "label_en": "Minimalist",
        "emoji": "◻️",
        "prompt_suffix": "minimalist style, clean, simple",
    },
    "fantasy": {
        "id": "fantasy",
        "label_id": "Fantasi",
        "label_en": "Fantasy",
        "emoji": "🧚",
        "prompt_suffix": "fantasy art style, magical, epic lighting",
    },
    "photo": {
        "id": "photo",
        "label_id": "Fotografi",
        "label_en": "Photo",
        "emoji": "📷",
        "prompt_suffix": "professional photography, DSLR, sharp focus",
    },
}


def get_style(style_id: str) -> dict:
    """Return style dict by id, fallback to 'none'."""
    return STYLES.get(style_id) or STYLES["none"]


def apply_style(prompt: str, style_id: str) -> str:
    """Apply style suffix to prompt. Returns original prompt if style is 'none' or has empty suffix."""
    style = get_style(style_id)
    suffix = style.get("prompt_suffix", "")
    if style_id == "none" or not suffix:
        return prompt
    return f"{prompt}, {suffix}"


def list_styles() -> list[dict]:
    """Return list of all style dicts."""
    return list(STYLES.values())
