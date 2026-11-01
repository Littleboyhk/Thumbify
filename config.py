import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Telegram API credentials from https://my.telegram.org
    _api_id_raw = os.getenv("API_ID", "").strip()
    API_ID = int(_api_id_raw) if _api_id_raw.isdigit() else 0
    API_HASH = os.getenv("API_HASH", "").strip()

    # Telegram Bot Token from @BotFather
    BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

    # Bot Owner / Admin User ID
    _owner_raw = os.getenv("BOT_OWNER", "").strip()
    BOT_OWNER = int(_owner_raw) if _owner_raw.isdigit() else 0

    # Authorized user IDs (comma-separated, leave blank to allow all users)
    _auth_users_raw = os.getenv("AUTH_USERS", "")
    AUTH_USERS = (
        {int(x.strip()) for x in _auth_users_raw.split(",") if x.strip().isdigit()}
        if _auth_users_raw
        else set()
    )
    if BOT_OWNER:
        AUTH_USERS.add(BOT_OWNER)

    # Optional Telegram Premium user session string for 4GB upload support
    STRING_SESSION = os.getenv("STRING_SESSION", "").strip()

    # Directories
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
    THUMB_DIR = os.path.join(BASE_DIR, "thumbnails")
    DB_PATH = os.path.join(BASE_DIR, "bot_data.db")

    # Progress update frequency (seconds) to prevent Telegram FloodWait
    PROGRESS_UPDATE_DELAY = 3.5

    @classmethod
    def validate(cls):
        """Validates that necessary configuration keys are set."""
        errors = []
        if not cls.API_ID:
            errors.append("API_ID is missing or invalid in .env")
        if not cls.API_HASH:
            errors.append("API_HASH is missing in .env")
        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN is missing in .env")
        return errors

