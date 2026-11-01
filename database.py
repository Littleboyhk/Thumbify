import os
import aiosqlite
from config import Config

class Database:
    def __init__(self, db_path: str = Config.DB_PATH):
        self.db_path = db_path

    async def init(self):
        """Initialize database tables."""
        os.makedirs(os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else ".", exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    upload_mode TEXT DEFAULT 'original',
                    custom_caption TEXT DEFAULT NULL,
                    thumb_path TEXT DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    async def get_user(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
                # Auto create user record
                await db.execute(
                    "INSERT OR IGNORE INTO users (user_id, upload_mode) VALUES (?, 'original')",
                    (user_id,)
                )
                await db.commit()
                return {"user_id": user_id, "upload_mode": "original", "custom_caption": None, "thumb_path": None}

    async def set_thumb(self, user_id: int, thumb_path: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO users (user_id, thumb_path) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET thumb_path = excluded.thumb_path
                """,
                (user_id, thumb_path)
            )
            await db.commit()

    async def get_thumb(self, user_id: int) -> str | None:
        user = await self.get_user(user_id)
        path = user.get("thumb_path")
        if path and os.path.exists(path):
            return path
        return None

    async def del_thumb(self, user_id: int) -> bool:
        thumb = await self.get_thumb(user_id)
        if thumb and os.path.exists(thumb):
            try:
                os.remove(thumb)
            except OSError:
                pass
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET thumb_path = NULL WHERE user_id = ?", (user_id,))
            await db.commit()
        return True

    async def set_caption(self, user_id: int, caption: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO users (user_id, custom_caption) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET custom_caption = excluded.custom_caption
                """,
                (user_id, caption)
            )
            await db.commit()

    async def get_caption(self, user_id: int) -> str | None:
        user = await self.get_user(user_id)
        return user.get("custom_caption")

    async def del_caption(self, user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET custom_caption = NULL WHERE user_id = ?", (user_id,))
            await db.commit()
        return True

    async def set_upload_mode(self, user_id: int, mode: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO users (user_id, upload_mode) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET upload_mode = excluded.upload_mode
                """,
                (user_id, mode)
            )
            await db.commit()

    async def get_total_users(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                res = await cursor.fetchone()
                return res[0] if res else 0

db = Database()

