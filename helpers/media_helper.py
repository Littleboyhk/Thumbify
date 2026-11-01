import os
import asyncio
import subprocess
from PIL import Image
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser

def fix_thumbnail(image_path: str, max_size: int = 320) -> str:
    """
    Validates and resizes an image to fit Telegram thumbnail requirements:
    - JPEG format
    - Dimensions within max_size x max_size (default 320x320)
    - Aspect ratio preserved
    """
    if not os.path.exists(image_path):
        return image_path

    out_path = f"{os.path.splitext(image_path)[0]}_fixed.jpg"
    try:
        with Image.open(image_path) as img:
            # Convert RGBA / P / LA to RGB
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            # Resize while preserving aspect ratio if dimensions exceed max_size
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Save optimized JPEG
            img.save(out_path, "JPEG", quality=85, optimize=True)
            return out_path
    except Exception as e:
        print(f"Error fixing thumbnail {image_path}: {e}")
        return image_path

def get_video_metadata(video_path: str) -> dict:
    """
    Extracts duration (seconds), width, and height from a video file.
    Uses hachoir first, and falls back to ffprobe/ffmpeg if needed.
    """
    duration = 0
    width = 0
    height = 0

    if not os.path.exists(video_path):
        return {"duration": 0, "width": 0, "height": 0}

    # 1. Try hachoir
    try:
        parser = createParser(video_path)
        if parser:
            with parser:
                metadata = extractMetadata(parser)
                if metadata:
                    if metadata.has("duration"):
                        duration = int(metadata.get("duration").seconds)
                    if metadata.has("width"):
                        width = int(metadata.get("width"))
                    if metadata.has("height"):
                        height = int(metadata.get("height"))
    except Exception:
        pass

    # 2. If duration/width/height still missing, fallback to ffprobe
    if not (duration and width and height):
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,duration",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            lines = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
            for item in lines:
                try:
                    val = float(item)
                    if width == 0 and val.is_integer() and val > 100:
                        width = int(val)
                    elif height == 0 and val.is_integer() and val > 100:
                        height = int(val)
                    elif duration == 0:
                        duration = int(val)
                except ValueError:
                    pass
        except Exception:
            pass

    return {
        "duration": duration,
        "width": width,
        "height": height
    }

async def generate_thumbnail_from_video(video_path: str, output_thumb_path: str, at_second: int = 5) -> str | None:
    """
    Captures a frame from video using ffmpeg at a specific second.
    """
    if not os.path.exists(video_path):
        return None

    cmd = [
        "ffmpeg",
        "-ss", str(at_second),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        "-y",
        output_thumb_path
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
        if os.path.exists(output_thumb_path):
            return fix_thumbnail(output_thumb_path)
    except Exception as e:
        print(f"Error capturing frame from video: {e}")
    return None

def clean_up(*file_paths):
    """Safely remove files if they exist."""
    for path in file_paths:
        if path and isinstance(path, str) and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

