"""Helper for short provider code — privacy friendly."""
# map real provider_id -> short code shown to user
SHORT_CODE = {
    "cubence": "CB",
    "rightcodes": "RC",
    "apikeyfun": "AF",
    "unity2": "UN",
}

def short_code(provider_id: str) -> str:
    return SHORT_CODE.get(provider_id, provider_id[:2].upper())

def format_model_label(provider_id: str, external_id: str, display_name: str | None = None) -> str:
    """Format as CB/gpt-image-2 — always use external_id to avoid duplicate display like CB/GPT Image 2 double."""
    code = short_code(provider_id)
    real = (external_id or display_name or "").strip()
    # normalize to lower for consistent display, keep original case if needed but lower looks cleaner
    # Keep external_id as primary to avoid GPT Image 2 vs gpt-image-2 duplicate perception
    real = real.split(":")[-1]  # strip provider prefix if any
    return f"{code}/{real}" if real else code

def format_model_short(provider_id: str, external_id: str) -> str:
    """Shortest privacy version: RC/xxx"""
    return f"{short_code(provider_id)}/{external_id.split(':')[-1]}"
