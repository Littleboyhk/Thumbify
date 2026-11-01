"""
Session String Generator for Telegram Premium Accounts
Allows uploading files between 2GB and 4GB.
"""
import sys
import asyncio

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from hydrogram import Client

async def main():
    print("=" * 60)
    print(" Telegram Premium Session String Generator (for 4GB Support)")
    print("=" * 60)
    print("You can get API_ID and API_HASH from https://my.telegram.org\n")

    api_id_str = input("Enter API_ID: ").strip()
    if not api_id_str.isdigit():
        print("❌ Invalid API_ID!")
        return
    api_id = int(api_id_str)
    api_hash = input("Enter API_HASH: ").strip()

    print("\nStarting login process... Telegram will send you an OTP code in Telegram.")
    async with Client(":memory:", api_id=api_id, api_hash=api_hash) as app:
        session_str = await app.export_session_string()
        print("\n" + "=" * 60)
        print("✅ SUCCESS! Here is your STRING_SESSION:")
        print("=" * 60)
        print(session_str)
        print("=" * 60)
        print("\nCopy the above string and paste it into your .env file as:")
        print(f"STRING_SESSION={session_str}\n")

if __name__ == "__main__":
    asyncio.run(main())

