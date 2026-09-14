import os
import asyncio
import urllib.parse

import psycopg2
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# =========================================================
# RAILWAY VARIABLES
# =========================================================

API_ID_RAW = (
    os.getenv("API_ID")
    or os.getenv("api_id")
    or os.getenv("App api_id")
    or "0"
)

API_ID = int(API_ID_RAW) if str(API_ID_RAW).isdigit() else 0

API_HASH = (
    os.getenv("API_HASH")
    or os.getenv("api_hash")
    or os.getenv("App api_hash")
    or ""
)

BOT_TOKEN = (
    os.getenv("BOT_TOKEN")
    or os.getenv("token")
    or os.getenv("TOKEN")
    or ""
)

DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("database_url")
    or ""
)


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

def search_movies_from_db(query):
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

        results = cur.fetchall()

        return results

    except Exception as e:
        print(f"Database Search Error: {e}")
        return []

    finally:
        if cur:
            cur.close()

        if conn:
            conn.close()


# =========================================================
# AUTO DELETE AFTER 10 MINUTES
# =========================================================

async def delete_after_10_minutes(message):

    await asyncio.sleep(600)

    try:
        await message.delete()
        print("Message deleted after 10 minutes.")

    except Exception as e:
        print(f"Auto-delete error: {e}")


# =========================================================
# START COMMAND
# =========================================================

@app.on_message(filters.command("start"))
async def start_handler(client, message):

    user_name = (
        message.from_user.first_name
        if message.from_user
        else "User"
    )

    start_text = (
        f"👋 Hello **{user_name}** 🌾\n\n"

        "🎬 **KB Movie Bot**\n\n"

        "🔎 **Type any movie name to search.**\n\n"

        "👇 **Our Services**\n\n"

        "🚀 **KB Bot Service**\n"
        "🤖 Telegram Bot Service\n"
        "🔗 https://t.me/KbBotService\n\n"

        "🛍️ **Loot Deals**\n"
        "🔥 Shopping Mall | Best Deals & Offers\n"
        "🔗 https://t.me/loot_dells\n\n"

        "📥 **KB Downloader**\n"
        "⚡ Facebook & Instagram Video Downloader Bot\n"
        "🔗 https://t.me/KBDownloader_bot"
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
                url="https://t.me/your_owner_username"
            )
        ]
    ])

    sent_message = await message.reply_text(
        start_text,
        reply_markup=keyboard,
        disable_web_page_preview=True
    )

    # Delete bot message after 10 minutes
    asyncio.create_task(
        delete_after_10_minutes(sent_message)
    )

    # Delete user's /start message after 10 minutes
    asyncio.create_task(
        delete_after_10_minutes(message)
    )


# =========================================================
# MOVIE / MEDIA SEARCH
# =========================================================

@app.on_message(
    filters.text & ~filters.command(["start"])
)
async def movie_search_handler(client, message):

    query = message.text.strip()

    if len(query) < 2:
        return

    print(f"Searching: {query}")

    results = search_movies_from_db(query)


    # =====================================================
    # NOT FOUND
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

        not_found_message = await message.reply_text(
            f"❌ **Movie Not Found**\n\n"
            f"🔎 Searched: **{query}**\n\n"
            "Please check the spelling and search on Google.",
            reply_markup=keyboard
        )

        # Delete Google message after 10 minutes
        asyncio.create_task(
            delete_after_10_minutes(
                not_found_message
            )
        )

        # Delete user's search message
        asyncio.create_task(
            delete_after_10_minutes(
                message
            )
        )

        return


    # =====================================================
    # FOUND
    # =====================================================

    for search_text, message_id, channel_id in results:

        try:

            # Copy authorized media from source channel
            movie_message = await client.copy_message(
                chat_id=message.chat.id,
                from_chat_id=int(channel_id),
                message_id=int(message_id)
            )

            # Warning directly below the file
            warning_message = await message.reply_text(
                "⚠️ **This file will be automatically deleted "
                "after 10 minutes.**\n\n"
                "💾 **Please save or forward it before "
                "it gets deleted!**"
            )

            # Delete media after 10 minutes
            asyncio.create_task(
                delete_after_10_minutes(
                    movie_message
                )
            )

            # Delete warning after 10 minutes
            asyncio.create_task(
                delete_after_10_minutes(
                    warning_message
                )
            )

            # Delete user's search message
            asyncio.create_task(
                delete_after_10_minutes(
                    message
                )
            )

        except Exception as e:

            print(
                f"Error copying message "
                f"{message_id}: {e}"
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
        "Search available media by typing its name.\n\n"
        "🗑️ Files are automatically deleted "
        "after 10 minutes.",
        show_alert=True
    )


# =========================================================
# BOT START
# =========================================================

print("==========================================")
print("🤖 KB Movie Bot is starting...")
print("🔎 Database search enabled")
print("🗑️ 10-minute auto-delete enabled")
print("==========================================")

app.run()
