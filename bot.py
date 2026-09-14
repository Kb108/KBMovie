import os
import asyncio
import urllib.parse

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import psycopg2


# =========================================================
# ENVIRONMENT VARIABLES
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
# PYROGRAM CLIENT
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

        return cur.fetchall()

    except Exception as e:
        print(f"Database Search Error: {e}")
        return []

    finally:
        if cur:
            cur.close()

        if conn:
            conn.close()


# =========================================================
# AUTO DELETE
# =========================================================

async def schedule_message_deletion(message, delay_seconds=600):
    await asyncio.sleep(delay_seconds)

    try:
        await message.delete()
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
        "Search for any movie by simply typing its name.\n\n"
        "👇 **Choose an option below or search for a movie:**"
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

    sent_msg = await message.reply_text(
        start_text,
        reply_markup=keyboard
    )

    asyncio.create_task(
        schedule_message_deletion(sent_msg, 600)
    )

    asyncio.create_task(
        schedule_message_deletion(message, 600)
    )


# =========================================================
# MOVIE SEARCH
# =========================================================

@app.on_message(filters.text & ~filters.command(["start"]))
async def movie_search_handler(client, message):

    query = message.text.strip()

    if len(query) < 2:
        return

    print(f"Movie search: {query}")

    results = search_movies_from_db(query)


    # =====================================================
    # MOVIE NOT FOUND
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

        sent_msg = await message.reply_text(
            f"❌ **Movie Not Found**\n\n"
            f"🔎 Searched: **{query}**\n\n"
            "Please check the spelling and search it on Google.",
            reply_markup=keyboard
        )

        asyncio.create_task(
            schedule_message_deletion(sent_msg, 600)
        )

        asyncio.create_task(
            schedule_message_deletion(message, 600)
        )

        return


    # =====================================================
    # MOVIE FOUND
    # =====================================================

    for text, msg_id, channel_id in results:

        try:

            movie_msg = await client.copy_message(
                chat_id=message.chat.id,
                from_chat_id=channel_id,
                message_id=msg_id
            )

            # Warning directly below movie
            warning_msg = await message.reply_text(
                "⚠️ **This file will be automatically deleted "
                "after 10 minutes.**\n\n"
                "💾 **Please save or forward it before "
                "it gets deleted!**"
            )

            # Delete movie after 10 minutes
            asyncio.create_task(
                schedule_message_deletion(
                    movie_msg,
                    600
                )
            )

            # Delete warning after 10 minutes
            asyncio.create_task(
                schedule_message_deletion(
                    warning_msg,
                    600
                )
            )

            # Delete user's search message after 10 minutes
            asyncio.create_task(
                schedule_message_deletion(
                    message,
                    600
                )
            )

        except Exception as e:

            print(
                f"Error copying movie "
                f"message: {e}"
            )


# =========================================================
# ABOUT BUTTON
# =========================================================

@app.on_callback_query()
async def callback_handler(client, callback_query):

    if callback_query.data == "about":

        await callback_query.answer(
            "🎬 KB Movie Bot\n\n"
            "Search any movie by typing its name.\n\n"
            "🗑️ Movie files are automatically "
            "deleted after 10 minutes.",
            show_alert=True
        )


# =========================================================
# START BOT
# =========================================================

print(
    "🤖 KB Movie Bot started successfully!"
)

print(
    "🗑️ 10-minute auto-delete system is active."
)

app.run()
