import time
import math
from config import Config

# Dictionary to hold the last update time for each message ID
_last_update_times = {}

def human_readable_bytes(size: int | float) -> str:
    """Format bytes into readable units (KB, MB, GB, etc.)."""
    if not size:
        return "0 B"
    power = 1024
    n = 0
    units = ["B", "KB", "MB", "GB", "TB"]
    while size >= power and n < len(units) - 1:
        size /= power
        n += 1
    return f"{size:.2f} {units[n]}"

def human_readable_time(seconds: int | float) -> str:
    """Format seconds into HH:MM:SS or MM:SS."""
    if seconds <= 0:
        return "0s"
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"

def make_progress_bar(percentage: float, length: int = 10) -> str:
    """Generate an aesthetic progress bar string."""
    filled = int(round(length * percentage / 100))
    bar = "▰" * filled + "▱" * (length - filled)
    return bar

async def progress_for_pyrogram(
    current: int,
    total: int,
    action_text: str,
    message,
    start_time: float
):
    """
    Callback function used by Hydrogram/Pyrogram for download and upload progress.
    """
    now = time.time()
    msg_id = f"{message.chat.id}:{message.id}"
    
    # Throttle updates to avoid FloodWait
    last_update = _last_update_times.get(msg_id, 0)
    if (now - last_update) < Config.PROGRESS_UPDATE_DELAY and current < total:
        return

    _last_update_times[msg_id] = now

    percentage = (current * 100) / total if total > 0 else 0
    elapsed_time = now - start_time
    speed = current / elapsed_time if elapsed_time > 0 else 0
    eta = (total - current) / speed if speed > 0 else 0

    progress_bar = make_progress_bar(percentage)
    cur_str = human_readable_bytes(current)
    tot_str = human_readable_bytes(total)
    speed_str = f"{human_readable_bytes(speed)}/s"
    eta_str = human_readable_time(eta)

    text = (
        f"**{action_text}**\n\n"
        f"[{progress_bar}] `{percentage:.1f}%`\n"
        f"⚡ **Speed:** `{speed_str}`\n"
        f"📦 **Done:** `{cur_str}` of `{tot_str}`\n"
        f"⏳ **ETA:** `{eta_str}`"
    )

    try:
        await message.edit_text(text)
    except Exception:
        # Ignore Telegram MessageNotModified or transient network errors during progress
        pass

