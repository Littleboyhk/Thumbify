from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
from database import db

def is_authorized(user_id: int) -> bool:
    if not Config.AUTH_USERS:
        return True
    return user_id in Config.AUTH_USERS

@Client.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        return await message.reply_text("⛔ **Access Denied!**\nYou are not authorized to use this bot.")

    # Ensure user exists in db
    await db.get_user(message.from_user.id)

    text = (
        f"👋 **Hello {message.from_user.first_name}!**\n\n"
        "I am an advanced **Telegram Thumbnail Changer & Renamer Bot**.\n\n"
        "✨ **What I can do:**\n"
        "• Change / replace thumbnail on any video or document file\n"
        "• Rename files with custom names & extensions\n"
        "• Convert documents to streamable videos (with duration/dimension metadata)\n"
        "• Custom captions template support\n"
        "• High speed downloading & uploading with live progress tracking\n\n"
        "👇 **Get started:**\n"
        "1. Send me any **Photo** to set as your custom thumbnail.\n"
        "2. Send or forward any **File/Video** to replace its thumbnail!"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🖼️ My Thumbnail", callback_data="view_thumb"),
            InlineKeyboardButton("⚙️ Settings", callback_data="open_settings")
        ],
        [
            InlineKeyboardButton("📖 Help & Commands", callback_data="open_help"),
            InlineKeyboardButton("ℹ️ About", callback_data="open_about")
        ]
    ])

    await message.reply_text(text, reply_markup=keyboard)


@Client.on_message(filters.command("help") & filters.private)
async def help_handler(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        return

    text = (
        "📖 **Telegram Thumbnail Bot - Help Guide**\n\n"
        "**Thumbnail Commands:**\n"
        "• Send any photo to set it as your thumbnail\n"
        "• `/setthumb` - Set thumbnail (reply to an image)\n"
        "• `/viewthumb` - View your currently saved thumbnail\n"
        "• `/delthumb` - Remove your custom thumbnail\n\n"
        "**Caption Commands:**\n"
        "• `/setcaption <text>` - Set a custom caption for uploaded files\n"
        "  *(Variables supported: `{filename}`, `{filesize}`)*\n"
        "• `/viewcaption` - View your custom caption\n"
        "• `/delcaption` - Delete your custom caption\n\n"
        "**File Processing:**\n"
        "• Send or forward any file/video (`.mkv`, `.mp4`, `.zip`, etc.)\n"
        "• Choose whether to keep the original name or rename it\n"
        "• Choose whether to upload as **Video** (streamable) or **Document**\n\n"
        "💡 **Tip:** Telegram requires thumbnails to be under 320x320 JPEG. Don't worry, this bot automatically resizes and optimizes your photo!"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Start", callback_data="back_start")]
    ])
    await message.reply_text(text, reply_markup=keyboard)


@Client.on_message(filters.command("settings") & filters.private)
async def settings_handler(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        return

    user = await db.get_user(message.from_user.id)
    mode = user.get("upload_mode", "original").capitalize()

    text = (
        "⚙️ **Bot Settings**\n\n"
        f"• **Current Upload Mode:** `{mode}`\n\n"
        "Choose how you want your media sent back:\n"
        "• **Original:** Matches incoming file type (Video -> Video, Document -> Document)\n"
        "• **Video:** Converts to streamable Telegram video player\n"
        "• **Document:** Sends as standard raw document file"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎬 Always Video", callback_data="mode_video"),
            InlineKeyboardButton("📁 Always Document", callback_data="mode_document")
        ],
        [
            InlineKeyboardButton("🔄 Original Match", callback_data="mode_original")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="back_start")
        ]
    ])
    await message.reply_text(text, reply_markup=keyboard)


@Client.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id

    if not is_authorized(user_id):
        return await query.answer("⛔ Access Denied!", show_alert=True)

    if data == "back_start":
        text = (
            f"👋 **Hello {query.from_user.first_name}!**\n\n"
            "I am an advanced **Telegram Thumbnail Changer & Renamer Bot**.\n\n"
            "Send me a **Photo** to save as thumbnail, then send any **File/Video** to change its thumbnail!"
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🖼️ My Thumbnail", callback_data="view_thumb"),
                InlineKeyboardButton("⚙️ Settings", callback_data="open_settings")
            ],
            [
                InlineKeyboardButton("📖 Help & Commands", callback_data="open_help"),
                InlineKeyboardButton("ℹ️ About", callback_data="open_about")
            ]
        ])
        await query.message.edit_text(text, reply_markup=keyboard)

    elif data == "open_help":
        await help_handler(client, query.message)

    elif data == "open_settings":
        await settings_handler(client, query.message)

    elif data == "open_about":
        text = (
            "ℹ️ **About This Bot**\n\n"
            "• **Framework:** Hydrogram (MTProto 2.0 Client)\n"
            "• **Engine:** Python 3 + Pillow + FFmpeg\n"
            "• **Capability:** Files up to 2GB (Standard Bot) / up to 4GB (Premium Session)\n"
            "• **Features:** Dynamic thumbnail swap, video streaming metadata, real-time speed progress bar"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="back_start")]
        ])
        await query.message.edit_text(text, reply_markup=keyboard)

    elif data.startswith("mode_"):
        new_mode = data.split("_")[1]
        await db.set_upload_mode(user_id, new_mode)
        await query.answer(f"✅ Upload mode changed to {new_mode.capitalize()}!", show_alert=True)
        await settings_handler(client, query.message)

