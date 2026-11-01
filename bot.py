import os
import sys
import asyncio
import logging

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from hydrogram import Client
from config import Config
from database import db
from helpers.fast_engine import patch_hydrogram_upload

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
)
logger = logging.getLogger("ThumbnailBot")

async def main():
    logger.info("Initializing Telegram Thumbnail Changer Bot...")

    # Validate config
    errors = Config.validate()
    if errors:
        logger.error("Configuration errors detected:")
        for err in errors:
            logger.error(f"  • {err}")
        print("\n" + "=" * 60)
        print("⚠️  CONFIGURATION REQUIRED:")
        print("Please create or edit your '.env' file with your credentials:")
        print("  API_ID=your_api_id")
        print("  API_HASH=your_api_hash")
        print("  BOT_TOKEN=your_bot_token")
        print("See .env.example for guidance.")
        print("=" * 60 + "\n")
        return

    # Ensure required directories exist
    os.makedirs(Config.DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(Config.THUMB_DIR, exist_ok=True)

    # Initialize SQLite Database
    await db.init()
    logger.info("Database initialized successfully.")

    # Apply High-Speed Parallel Upload Patch
    patch_hydrogram_upload()
    logger.info("High-speed parallel transmission engine activated.")

    # Initialize standard Bot Client
    bot = Client(
        name="thumbnail_bot",
        api_id=Config.API_ID,
        api_hash=Config.API_HASH,
        bot_token=Config.BOT_TOKEN,
        plugins=dict(root="plugins"),
        workdir=Config.BASE_DIR,
        workers=16,
        max_concurrent_transmissions=10
    )

    # Initialize optional Premium User Client for 4GB uploads if STRING_SESSION is provided
    user_client = None
    if Config.STRING_SESSION:
        logger.info("Premium User Session found! Initializing 4GB client support...")
        user_client = Client(
            name="premium_user_session",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            session_string=Config.STRING_SESSION,
            no_updates=True,
            workers=16,
            max_concurrent_transmissions=10
        )
        bot.user_client = user_client

    logger.info("Starting Telegram Bot...")
    await bot.start()

    if user_client:
        try:
            await user_client.start()
            logger.info("Premium User Client started successfully (4GB uploads enabled)!")
        except Exception as e:
            logger.warning(f"Could not start Premium User Client: {e}")

    me = await bot.get_me()
    logger.info(f"Bot started successfully as @{me.username} (ID: {me.id})")
    print(f"\n🚀 Bot is live as @{me.username}!\n")

    # Run until interrupted
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
