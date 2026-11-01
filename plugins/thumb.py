import os
from hydrogram import Client, filters
from hydrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from PIL import Image

from config import Config
from database import db
from helpers.media_helper import fix_thumbnail
from helpers.progress import human_readable_bytes
from plugins.start import is_authorized

os.makedirs(Config.THUMB_DIR, exist_ok=True)

@Client.on_message(filters.photo & filters.private)
async def photo_save_handler(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        return

    msg = await message.reply_text("⏳ **Processing and saving your thumbnail...**")
    user_id = message.from_user.id
    target_path = os.path.join(Config.THUMB_DIR, f"{user_id}.jpg")

    try:
        # Download the highest resolution photo version
        downloaded = await message.download(file_name=target_path)
        
        # Optimize and resize to 320x320 JPEG (Telegram specification)
        fixed = fix_thumbnail(downloaded, max_size=320)
        if fixed != downloaded and os.path.exists(fixed):
            os.replace(fixed, target_path)

        await db.set_thumb(user_id, target_path)

        # Get image metadata
        size = human_readable_bytes(os.path.getsize(target_path))
        with Image.open(target_path) as img:
            w, h = img.size

        text = (
            "✅ **Custom Thumbnail Saved Successfully!**\n\n"
            f"📐 **Resolution:** `{w}x{h}`\n"
            f"📦 **Size:** `{size}`\n\n"
            "Now send or forward any video or document file to apply this thumbnail!"
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("👁️ View Thumbnail", callback_data="view_thumb"),
                InlineKeyboardButton("🗑️ Delete", callback_data="del_thumb")
            ]
        ])
        await msg.edit_text(text, reply_markup=keyboard)
    except Exception as e:
        await msg.edit_text(f"❌ **Failed to save thumbnail:**\n`{e}`")


@Client.on_message(filters.command(["setthumb", "set_thumb"]) & filters.private)
async def setthumb_command_handler(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        return

    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply_text(
            "⚠️ **Please reply to a photo with `/setthumb` to save it as your thumbnail!**\n"
            "Or simply send the photo directly to this chat."
        )

    # Reuse photo handler logic
    await photo_save_handler(client, message.reply_to_message)


@Client.on_message(filters.command(["viewthumb", "view_thumb", "showthumb"]) & filters.private)
async def viewthumb_command_handler(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        return
    await send_user_thumbnail(client, message.chat.id, message.from_user.id)


@Client.on_message(filters.command(["delthumb", "del_thumb", "deletethumb"]) & filters.private)
async def delthumb_command_handler(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        return
    await delete_user_thumbnail(message.from_user.id, message)


async def send_user_thumbnail(client: Client, chat_id: int, user_id: int):
    thumb_path = await db.get_thumb(user_id)
    if not thumb_path or not os.path.exists(thumb_path):
        return await client.send_message(
            chat_id,
            "⚠️ **You don't have a custom thumbnail saved yet!**\n\n"
            "Send me any photo to save it as your custom thumbnail."
        )

    try:
        size = human_readable_bytes(os.path.getsize(thumb_path))
        with Image.open(thumb_path) as img:
            w, h = img.size

        caption = (
            "🖼️ **Your Current Saved Thumbnail**\n\n"
            f"📐 **Resolution:** `{w}x{h}`\n"
            f"📦 **Size:** `{size}`"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑️ Delete Thumbnail", callback_data="del_thumb")]
        ])
        await client.send_photo(chat_id, photo=thumb_path, caption=caption, reply_markup=keyboard)
    except Exception as e:
        await client.send_message(chat_id, f"❌ **Error retrieving thumbnail:**\n`{e}`")


async def delete_user_thumbnail(user_id: int, message_or_query):
    thumb_path = await db.get_thumb(user_id)
    if not thumb_path or not os.path.exists(thumb_path):
        text = "⚠️ **You do not have any saved thumbnail to delete.**"
        if isinstance(message_or_query, CallbackQuery):
            return await message_or_query.answer(text, show_alert=True)
        return await message_or_query.reply_text(text)

    await db.del_thumb(user_id)
    text = "🗑️ **Your custom thumbnail has been removed successfully!**"
    if isinstance(message_or_query, CallbackQuery):
        await message_or_query.answer("Thumbnail deleted!", show_alert=True)
        try:
            await message_or_query.message.delete()
        except Exception:
            pass
    else:
        await message_or_query.reply_text(text)


@Client.on_callback_query(filters.regex("^(view_thumb|del_thumb)$"))
async def thumb_callbacks(client: Client, query: CallbackQuery):
    if not is_authorized(query.from_user.id):
        return await query.answer("⛔ Access Denied!", show_alert=True)

    if query.data == "view_thumb":
        await send_user_thumbnail(client, query.message.chat.id, query.from_user.id)
        await query.answer()
    elif query.data == "del_thumb":
        await delete_user_thumbnail(query.from_user.id, query)

