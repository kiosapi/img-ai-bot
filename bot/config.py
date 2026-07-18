import os

BOT_TOKEN = os.environ["BOT_TOKEN"]
CUBENCE_API_KEY = os.environ["CUBENCE_API_KEY"]
CUBENCE_BASE_URL = os.environ.get("CUBENCE_BASE_URL", "https://api-dmit.cubence.com")

# Channel that users must join before using the bot (e.g. "@imgaai_official")
REQUIRED_CHANNEL = os.environ.get("REQUIRED_CHANNEL", "@imgaai_official")

# Admin telegram user id(s), comma separated
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]

# Database
DATABASE_URL = os.environ["DATABASE_URL"]

# Default daily limit (can be overridden at runtime from the dashboard / DB settings)
DEFAULT_DAILY_LIMIT = int(os.environ.get("DEFAULT_DAILY_LIMIT", "20"))

# Model + allowed sizes
IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "gpt-image-2")
ALLOWED_SIZES = ["1024x1024", "1024x1536", "1536x1024"]
DEFAULT_SIZE = "1024x1024"
