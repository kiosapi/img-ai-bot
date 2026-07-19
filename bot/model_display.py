"""Helper for short provider code — privacy friendly."""
# map real provider_id -> short code shown to user
SHORT_CODE = {
    "cubence": "CB",
    "rightcodes": "RC",
}

def short_code(provider_id: str) -> str:
    return SHORT_CODE.get(provider_id, provider_id[:2].upper())

def format_model_label(provider_id: str, external_id: str, display_name: str | None = None) -> str:
    """Format as CB/model or RC/model — never leak full provider name."""
    code = short_code(provider_id)
    real = external_id or ""
    # user wants RC/Gpt-image-2 style
    if display_name and display_name != external_id:
        # prefer display_name if not same as external? But still with code prefix to distinguish duplicates
        # Use code/display_name for clarity
        return f"{code}/{display_name}"
    return f"{code}/{real}" if real else code

def format_model_short(provider_id: str, external_id: str) -> str:
    """Shortest privacy version: RC/xxx"""
    return f"{short_code(provider_id)}/{external_id}"
