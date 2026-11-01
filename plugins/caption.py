from hydrogram import Client, filters
from hydrogram.types import Message
from database import db
from plugins.start import is_authorized

@Client.on_message(filters.command(["setcaption", "set_caption"]) & filters.private)
async def set_caption_handler(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        return

    if len(message.command) < 2:
        return await message.reply_text(
            "⚠️ **Usage:** `/setcaption <your custom caption>`\n\n"
            "**Supported Placeholders:**\n"
            "• `{filename}` - Replaced with file name\n"
            "• `{filesize}` - Replaced with human-readable file size\n\n"
            "**Example:**\n"
            "`/setcaption 🎬 {filename}\n📦 Size: {filesize}\n\nJoin @MyChannel`"
        )

    caption_text = message.text.split(None, 1)[1]
    await db.set_caption(message.from_user.id, caption_text)
    await message.reply_text(
        "✅ **Custom caption saved successfully!**\n\n"
        f"**Preview:**\n{caption_text}"
    )


@Client.on_message(filters.command(["viewcaption", "view_caption"]) & filters.private)
async def view_caption_handler(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        return

    caption = await db.get_caption(message.from_user.id)
    if not caption:
        return await message.reply_text(
            "⚠️ **You haven't set a custom caption yet.**\n"
            "Use `/setcaption <text>` to set one."
        )

    await message.reply_text(f"📝 **Your Custom Caption:**\n\n{caption}")


@Client.on_message(filters.command(["delcaption", "del_caption"]) & filters.private)
async def del_caption_handler(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        return

    await db.del_caption(message.from_user.id)
    await message.reply_text("🗑️ **Your custom caption has been removed.**")

