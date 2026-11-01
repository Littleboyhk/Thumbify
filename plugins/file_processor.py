import os
import time
import asyncio
from hydrogram import Client, filters
from hydrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import Config
from database import db
from helpers.progress import progress_for_pyrogram, human_readable_bytes
from helpers.media_helper import fix_thumbnail, get_video_metadata, generate_thumbnail_from_video, clean_up
from helpers.fast_engine import fast_download_media
from helpers.user_states import state_manager
from plugins.start import is_authorized

# In-memory storage: {msg_id: {"message": Message, "filename": str, "size": int, ...}}
pending_files = {}

@Client.on_message((filters.document | filters.video | filters.audio) & filters.private)
async def incoming_file_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if not is_authorized(user_id):
        return await message.reply_text("⛔ **Access Denied!**")

    media = message.document or message.video or message.audio
    if not media:
        return

    # Extract filename
    original_name = getattr(media, "file_name", None)
    if not original_name:
        ext = ".mp4" if message.video else (".mp3" if message.audio else ".bin")
        original_name = f"file_{message.id}{ext}"

    file_size = media.file_size
    size_str = human_readable_bytes(file_size)

    # Check 2GB / 4GB limit
    is_large = file_size > (2000 * 1024 * 1024)
    if is_large and not Config.STRING_SESSION:
        return await message.reply_text(
            f"⚠️ **File Size Limit Warning!**\n\n"
            f"📁 **File:** `{original_name}`\n"
            f"📦 **Size:** `{size_str}`\n\n"
            "Telegram limits standard bot tokens to **2.0 GB**.\n"
            "To process files up to **4.0 GB**, please configure a Telegram Premium `STRING_SESSION` in `.env`."
        )

    # Check if user has a custom thumbnail
    user_thumb = await db.get_thumb(user_id)
    thumb_status = "✅ Custom Thumbnail Set" if user_thumb else "⚠️ No Custom Thumbnail"

    msg_id = message.id
    pending_files[msg_id] = {
        "message": message,
        "user_id": user_id,
        "filename": original_name,
        "size": file_size,
        "size_str": size_str,
        "is_video": bool(message.video or original_name.lower().endswith((".mkv", ".mp4", ".avi", ".mov", ".webm", ".flv", ".ts")))
    }

    text = (
        f"📁 **File:** `{original_name}`\n"
        f"📦 **Size:** `{size_str}`\n"
        f"🖼️ **Thumbnail:** `{thumb_status}`\n\n"
        "Choose an action below:"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎬 Send as Video", callback_data=f"p_vid:{msg_id}"),
            InlineKeyboardButton("📁 Send as Document", callback_data=f"p_doc:{msg_id}")
        ],
        [
            InlineKeyboardButton("✏️ Rename & Change", callback_data=f"p_ren:{msg_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"p_can:{msg_id}")
        ]
    ])

    await message.reply_text(text, reply_markup=keyboard, quote=True)


@Client.on_message(filters.text & filters.private & ~filters.command(["start", "help", "settings", "setthumb", "viewthumb", "delthumb", "setcaption", "viewcaption", "delcaption"]))
async def text_input_handler(client: Client, message: Message):
    user_id = message.from_user.id
    state = state_manager.get_state(user_id)

    if not state or state.get("state") != "WAITING_RENAME":
        return

    target_msg_id = state.get("data", {}).get("target_msg_id")
    state_manager.clear_state(user_id)

    if not target_msg_id or target_msg_id not in pending_files:
        return await message.reply_text("⚠️ **Session expired or file not found. Please re-send the file.**")

    new_name = message.text.strip()
    old_name = pending_files[target_msg_id]["filename"]
    _, old_ext = os.path.splitext(old_name)

    # Automatically preserve extension if omitted by user
    if not os.path.splitext(new_name)[1] and old_ext:
        new_name += old_ext

    pending_files[target_msg_id]["filename"] = new_name
    is_video = bool(new_name.lower().endswith((".mkv", ".mp4", ".avi", ".mov", ".webm", ".flv", ".ts")))
    pending_files[target_msg_id]["is_video"] = is_video

    text = (
        f"✏️ **New Name:** `{new_name}`\n"
        f"📦 **Size:** `{pending_files[target_msg_id]['size_str']}`\n\n"
        "Now choose upload format:"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎬 Send as Video", callback_data=f"p_vid:{target_msg_id}"),
            InlineKeyboardButton("📁 Send as Document", callback_data=f"p_doc:{target_msg_id}")
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data=f"p_can:{target_msg_id}")
        ]
    ])

    await message.reply_text(text, reply_markup=keyboard, quote=True)


@Client.on_callback_query(filters.regex(r"^p_(vid|doc|ren|can):(\d+)$"))
async def file_action_callback(client: Client, query: CallbackQuery):
    action = query.matches[0].group(1)
    msg_id = int(query.matches[0].group(2))
    user_id = query.from_user.id

    if msg_id not in pending_files:
        return await query.answer("⚠️ Session expired or file already processed.", show_alert=True)

    file_info = pending_files[msg_id]

    if action == "can":
        pending_files.pop(msg_id, None)
        state_manager.clear_state(user_id)
        await query.message.edit_text("❌ **Operation cancelled.**")
        return await query.answer("Cancelled")

    if action == "ren":
        state_manager.set_state(user_id, "WAITING_RENAME", {"target_msg_id": msg_id})
        old_name = file_info["filename"]
        text = (
            f"✏️ **Current name:** `{old_name}`\n\n"
            "Please send the **new filename** as a text message:\n"
            "*(e.g. `My Movie (2026) 720p.mkv`)*"
        )
        await query.message.edit_text(text)
        return await query.answer()

    # If action is 'vid' or 'doc'
    upload_mode = "video" if action == "vid" else "document"
    file_data = pending_files.pop(msg_id, None)
    state_manager.clear_state(user_id)

    await query.answer("Processing file...")
    await execute_file_processing(client, query.message, file_data, upload_mode)


async def execute_file_processing(client: Client, status_msg: Message, file_info: dict, upload_mode: str):
    user_id = status_msg.chat.id
    target_msg: Message = file_info["message"]
    file_name: str = file_info["filename"]
    file_size: int = file_info["size"]

    os.makedirs(Config.DOWNLOAD_DIR, exist_ok=True)
    temp_download_path = os.path.join(Config.DOWNLOAD_DIR, f"{user_id}_{int(time.time())}_{file_name}")
    generated_thumb = None
    fixed_thumb = None

    start_time = time.time()
    await status_msg.edit_text("⏳ **Initializing download...**")

    try:
        # Step 1: Download Media (Parallel Multi-Worker Engine)
        download_start = time.time()
        file_path = await fast_download_media(
            client=client,
            message=target_msg,
            file_name=temp_download_path,
            progress=progress_for_pyrogram,
            progress_args=("📥 Downloading File...", status_msg, download_start)
        )

        if not file_path or not os.path.exists(file_path):
            return await status_msg.edit_text("❌ **Download failed or was cancelled.**")

        await status_msg.edit_text("⚙️ **Processing thumbnail & metadata...**")

        # Step 2: Determine & prepare thumbnail
        user_thumb_path = await db.get_thumb(user_id)
        final_thumb = None

        if user_thumb_path and os.path.exists(user_thumb_path):
            fixed_thumb = fix_thumbnail(user_thumb_path)
            final_thumb = fixed_thumb
        elif upload_mode == "video" or file_info.get("is_video"):
            # Try to grab a frame from the video if no custom thumbnail
            generated_thumb = os.path.join(Config.DOWNLOAD_DIR, f"gen_thumb_{user_id}_{int(time.time())}.jpg")
            final_thumb = await generate_thumbnail_from_video(file_path, generated_thumb, at_second=5)

        # Step 3: Determine caption
        custom_caption = await db.get_caption(user_id)
        if custom_caption:
            caption = custom_caption.replace("{filename}", file_name).replace("{filesize}", human_readable_bytes(file_size))
        elif target_msg.caption:
            caption = target_msg.caption
        else:
            caption = f"**{file_name}**"

        # Step 4: Video metadata (if uploading as video)
        duration = 0
        width = 0
        height = 0
        if upload_mode == "video":
            meta = get_video_metadata(file_path)
            duration = meta.get("duration", 0)
            width = meta.get("width", 0)
            height = meta.get("height", 0)

        # Step 5: Select uploading client (Premium Client for >2GB if configured)
        upload_client = client
        if file_size > (2000 * 1024 * 1024) and hasattr(client, "user_client") and client.user_client:
            upload_client = client.user_client

        # Step 6: Upload Media
        upload_start = time.time()
        if upload_mode == "video":
            await upload_client.send_video(
                chat_id=user_id,
                video=file_path,
                caption=caption,
                thumb=final_thumb,
                duration=duration,
                width=width,
                height=height,
                supports_streaming=True,
                file_name=file_name,
                progress=progress_for_pyrogram,
                progress_args=("📤 Uploading Video...", status_msg, upload_start)
            )
        else:
            await upload_client.send_document(
                chat_id=user_id,
                document=file_path,
                caption=caption,
                thumb=final_thumb,
                file_name=file_name,
                force_document=True,
                progress=progress_for_pyrogram,
                progress_args=("📤 Uploading Document...", status_msg, upload_start)
            )

        total_elapsed = int(time.time() - start_time)
        await status_msg.edit_text(
            f"✅ **Completed Successfully in {total_elapsed}s!**\n\n"
            f"📁 **File:** `{file_name}`\n"
            f"📦 **Size:** `{human_readable_bytes(file_size)}`\n"
            f"🖼️ **Thumbnail:** {'Custom Applied' if final_thumb else 'Default'}"
        )

    except Exception as e:
        await status_msg.edit_text(f"❌ **An error occurred during processing:**\n`{e}`")
    finally:
        # Clean up temporary downloaded file and generated frames
        clean_up(temp_download_path, generated_thumb)
        if fixed_thumb and fixed_thumb != user_thumb_path:
            clean_up(fixed_thumb)
