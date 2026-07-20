import os

BOT_TOKEN = os.environ["BOT_TOKEN"]
CUBENCE_API_KEY = os.environ["CUBENCE_API_KEY"]
CUBENCE_BASE_URL = os.environ.get("CUBENCE_BASE_URL", "https://api-dmit.cubence.com")

# Optional second provider
RIGHTCODES_API_KEY = os.environ.get("RIGHTCODES_API_KEY", "") or os.environ.get("RIGHT_CODES_API_KEY", "")
RIGHTCODES_BASE_URL = os.environ.get("RIGHTCODES_BASE_URL", os.environ.get("RIGHT_CODES_BASE_URL", "https://www.right.codes/draw"))

# Optional third provider — apikey.fun (OpenAI-compatible + SSE streaming)
APIKEYFUN_API_KEY = os.environ.get("APIKEYFUN_API_KEY", "") or os.environ.get("APIKEY_FUN_API_KEY", "")
APIKEYFUN_BASE_URL = os.environ.get("APIKEYFUN_BASE_URL", os.environ.get("APIKEY_FUN_BASE_URL", "https://api.apikey.fun/v1"))

# Optional fourth provider — unity2.ai (OpenAI-compatible, verified 2026-07-20 gpt-image-2 b64 3.2MB 51s)
UNITY2_API_KEY = os.environ.get("UNITY2_API_KEY", "") or os.environ.get("UNITY2_API_KEY_", "")
UNITY2_BASE_URL = os.environ.get("UNITY2_BASE_URL", os.environ.get("UNITY2_BASE_URL_", "https://api.unity2.ai/v1"))

# Channel that users must join before using the bot (e.g. "@imgaai_official")
REQUIRED_CHANNEL = os.environ.get("REQUIRED_CHANNEL", "@imgaai_official")

# Admin telegram user id(s), comma separated
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]

# Database
DATABASE_URL = os.environ["DATABASE_URL"]

# Default daily limit (can be overridden at runtime from the dashboard / DB settings)
DEFAULT_DAILY_LIMIT = int(os.environ.get("DEFAULT_DAILY_LIMIT", "20"))

# Model + allowed sizes — production aspect ratio set
# All must be mapped to provider-compatible sizes; provider fallback handles unknown via closest match
ALLOWED_SIZES = [
    "1024x1024",   # 1:1 Square
    "1024x1792",   # 9:16 Portrait tall
    "1792x1024",   # 16:9 Landscape wide
    "1024x1536",   # 2:3 Portrait
    "1536x1024",   # 3:2 Landscape
    "1152x1536",   # 3:4 Portrait
    "1536x1152",   # 4:3 Landscape
]
DEFAULT_SIZE = "1024x1024"

# Map aspect UI to size for frontend
ASPECT_MAP = {
    "1:1": "1024x1024",
    "9:16": "1024x1792",
    "16:9": "1792x1024",
    "2:3": "1024x1536",
    "3:2": "1536x1024",
    "3:4": "1152x1536",
    "4:3": "1536x1152",
}

# Allowed batch counts production (cost control)
ALLOWED_BATCHES = [1, 2, 4]
DEFAULT_BATCH = 1

# Negative prompt defaults empty
DEFAULT_NEGATIVE = ""
# Seed: None = random
DEFAULT_SEED = None

IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "gpt-image-2")
