# 🎬 Telegram Thumbnail Changer & Renamer Bot

An advanced, asynchronous Telegram bot built with **Hydrogram (MTProto)**, **Pillow**, and **FFmpeg** to change file thumbnails, rename media, and convert documents into streamable videos.

Designed specifically to handle large video files (like the MKV/MP4 files common in media channels), with support for files up to **2.0 GB** (standard bot) and up to **4.0 GB** (with Telegram Premium session).

---

## ✨ Features

- 🖼️ **Thumbnail Management**:
  - Send any photo to set it as your persistent custom thumbnail.
  - Automatically crops and optimizes thumbnails to Telegram's 320x320 JPEG standard.
  - Commands to view (`/viewthumb`) and delete (`/delthumb`) your saved thumbnail.
- 📁 **File & Video Processing**:
  - Change thumbnails on any video, document, or audio file (`.mkv`, `.mp4`, `.avi`, `.zip`, etc.).
  - Choose between sending as **Streamable Video** (playable in Telegram player) or **Raw Document**.
  - Automatically extracts duration, width, and height using FFmpeg and Hachoir so videos stream properly with a seekbar.
- ✏️ **File Renaming**:
  - Rename files before sending while automatically preserving file extensions.
- 📝 **Custom Captions**:
  - Set custom caption templates with `{filename}` and `{filesize}` placeholders (`/setcaption`).
- ⚡ **Live Animated Progress Bar**:
  - Displays percentage, speed (MB/s), downloaded/total size, and ETA during both download and upload.
  - Throttled to prevent Telegram API `FloodWait` rate-limiting.
- 🚀 **Large File Support (2GB - 4GB)**:
  - Standard Bot API token: files up to 2.0 GB.
  - Optional Telegram Premium `STRING_SESSION`: handles files up to 4.0 GB.
- 🧹 **Automatic Cleanup**:
  - Automatically removes temporary files from disk after processing to prevent filling up storage.

---

## 📋 Requirements

- **Python 3.10+** (Python 3.12 recommended)
- **FFmpeg** installed and added to system PATH
- Telegram API Credentials:
  - `API_ID` & `API_HASH` from [my.telegram.org](https://my.telegram.org)
  - `BOT_TOKEN` from [@BotFather](https://t.me/BotFather)

---

## 🚀 Setup & Installation

### 1. Clone or Open the Project
Open terminal / command prompt in this directory:
```bash
cd "TG thumbnail bot"
```

### 2. Activate the Virtual Environment
Windows:
```powershell
.\venv\Scripts\Activate.ps1
```
Linux / macOS:
```bash
source venv/bin/activate
```

*(If you ever need to reinstall dependencies: `pip install -r requirements.txt`)*

### 3. Configure `.env`
Copy `.env.example` to `.env`:
```bash
copy .env.example .env
```
Open `.env` in a text editor and fill in your details:
```env
API_ID=12345678
API_HASH=abcdef1234567890abcdef1234567890
BOT_TOKEN=123456789:ABCDefGhIJklMNopQRstUVwxyz
BOT_OWNER=123456789
AUTH_USERS=123456789
STRING_SESSION=
```

### 4. (Optional) 4GB Telegram Premium Support
If you want the bot to upload files larger than 2GB (up to 4GB):
1. Run the session generator script:
   ```bash
   python generate_session.py
   ```
2. Log in with your Telegram account (must have Telegram Premium).
3. Copy the output session string and paste it into `STRING_SESSION=` in `.env`.

### 5. Run the Bot
```bash
python bot.py
```

---

## 🤖 Bot Commands

| Command | Description |
| :--- | :--- |
| `/start` | Open the main menu and dashboard |
| `/help` | View help and command instructions |
| `/settings` | Switch upload mode (Original / Video / Document) |
| `/setthumb` | Set custom thumbnail (or reply to an image) |
| `/viewthumb` | View your currently active thumbnail |
| `/delthumb` | Delete your saved thumbnail |
| `/setcaption <text>` | Set custom caption with `{filename}` and `{filesize}` |
| `/viewcaption` | View your active custom caption |
| `/delcaption` | Delete your custom caption |

---

## 📂 Project Structure

```
TG thumbnail bot/
├── bot.py                # Main entry point & client runner
├── config.py             # Environment config and settings
├── database.py           # SQLite async database
├── requirements.txt      # Python dependencies
├── generate_session.py   # Optional Telegram Premium session string generator
├── .env.example          # Sample environment variables
├── helpers/
│   ├── progress.py       # Live progress bar with ETA & speed
│   ├── media_helper.py   # Thumbnail optimizer (320x320) & FFmpeg metadata
│   └── user_states.py    # Conversation state tracker
└── plugins/
    ├── start.py          # /start, /help, /settings
    ├── thumb.py          # Photo receiver, /viewthumb, /delthumb
    ├── caption.py        # /setcaption, /delcaption
    └── file_processor.py # File downloader, thumbnail replacer, uploader
```

