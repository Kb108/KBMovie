import os
import asyncio
import urllib.parse

import psycopg2
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# তোমার Telegram username এখানে বসাও
OWNER_USERNAME = "your_owner_username"


# =========================================================
# CHECK VARIABLES
# =========================================================

if API_ID == 0:
    raise RuntimeError("API_ID is missing.")

if not API_HASH:
    raise RuntimeError("API_HASH is missing.")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing.")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing.")


# =========================================================
# TELEGRAM CLIENT
# =========================================================

app = Client(
    "kb_movie_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# =========================================================
# DATABASE SEARCH
# =========================================================

def search_movies(query):

    conn = None
    cur = None

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        cur.execute(
            """
            SELECT search_text, message_id, channel_id
            FROM kb_movies_v2
            WHERE search_text ILIKE %s
            LIMIT 10
            """,
            (f"%{query}%",)
        )

        return cur.fetchall()

    except Exception as e:
        print("DATABASE ERROR:", e)
        return []

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()


# =========================================================
# AUTO DELETE
# =========================================================

async def delete_after_10_minutes(message):

    await asyncio.sleep(600)

    try:
        await message.delete()
        print("Message deleted after 10 minutes.")

    except Exception as e:
        print("Delete error:", e)


# =========================================================
# START
# =========================================================

@app.on_message(filters.command("start"))
async def start_handler(client, message):

    user_name = (
        message.from_user.first_name
        if message.from_user
        else "User"
    )

    text = (
        f"👋 Hello **{user_name}**!\n\n"

        "🎬 **KB Movie Bot**\n\n"

        "🔎 Send me the name of a movie to search.\n\n"

        "👇 **Our Services**\n\n"

        "🚀 **KB Bot Service**\n"
        "🤖 Telegram Bot Service\n\n"

        "🛍️ **Loot Deals**\n"
        "🔥 Shopping Mall | Best Deals & Offers\n\n"

        "📥 **KB Downloader**\n"
        "⚡ Facebook & Instagram Video Downloader Bot"
    )

    keyboard = InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "➕ ADD ME TO YOUR GROUP",
                url=f"https://t.me/{client.me.username}?startgroup=true"
            )
        ],

        [
            InlineKeyboardButton(
                "🚀 KB Bot Service",
                url="https://t.me/KbBotService"
            ),

            InlineKeyboardButton(
                "🛍️ Loot Deals",
                url="https://t.me/loot_dells"
            )
        ],

        [
            InlineKeyboardButton(
                "📥 KB Downloader",
                url="https://t.me/KBDownloader_bot"
            )
        ],

        [
            InlineKeyboardButton(
                "✨ ABOUT",
                callback_data="about"
            ),

            InlineKeyboardButton(
                "👑 OWNER",
                url=f"https://t.me/{OWNER_USERNAME}"
            )
        ]
    ])

    sent = await message.reply_text(
        text,
        reply_markup=keyboard
    )

    # Start message delete after 10 minutes
    asyncio.create_task(
        delete_after_10_minutes(sent)
    )

    # User's /start message delete after 10 minutes
    asyncio.create_task(
        delete_after_10_minutes(message)
    )


# =========================================================
# MEDIA SEARCH
# =========================================================

@app.on_message(
    filters.text & ~filters.command("start")
)
async def search_handler(client, message):

    query = message.text.strip()

    if len(query) < 2:
        return

    print(f"Searching: {query}")

    results = search_movies(query)


    # =====================================================
    # NOTHING FOUND
    # =====================================================

    if not results:

        google_query = urllib.parse.quote_plus(
            f"{query} movie"
        )

        google_url = (
            f"https://www.google.com/search?q={google_query}"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔍 SEARCH ON GOOGLE",
                    url=google_url
                )
            ]
        ])

        not_found = await message.reply_text(
            f"❌ **Movie Not Found**\n\n"
            f"🔎 Search: **{query}**\n\n"
            "Please check the spelling and try again.",
            reply_markup=keyboard
        )

        asyncio.create_task(
            delete_after_10_minutes(not_found)
        )

        asyncio.create_task(
            delete_after_10_minutes(message)
        )

        return


    # =====================================================
    # MEDIA FOUND
    # =====================================================

    for search_text, message_id, channel_id in results:

        try:

            # Copy authorized media from source channel
            media_message = await client.copy_message(
                chat_id=message.chat.id,
                from_chat_id=int(channel_id),
                message_id=int(message_id)
            )

            # Warning below the media
            warning = await message.reply_text(
                "⚠️ **This file will be automatically deleted "
                "after 10 minutes.**\n\n"
                "💾 **Please save or forward it before "
                "it gets deleted!**"
            )

            # Delete copied media
            asyncio.create_task(
                delete_after_10_minutes(
                    media_message
                )
            )

            # Delete warning
            asyncio.create_task(
                delete_after_10_minutes(
                    warning
                )
            )

            # Delete user's search
            asyncio.create_task(
                delete_after_10_minutes(
                    message
                )
            )

        except Exception as e:

            print(
                f"MEDIA COPY ERROR: {e}"
            )


# =========================================================
# ABOUT BUTTON
# =========================================================

@app.on_callback_query(
    filters.regex("^about$")
)
async def about_handler(client, callback_query):

    await callback_query.answer(
        "🎬 KB Movie Bot\n\n"
        "Search for available media by name.\n\n"
        "🗑️ Files are automatically deleted "
        "after 10 minutes.",
        show_alert=True
    )


# =========================================================
# START BOT
# =========================================================

print("======================================")
print("🤖 KB Movie Bot is starting...")
print("🗑️ 10-minute auto-delete enabled")
print("🔎 Database search enabled")
print("======================================")

app.run()
