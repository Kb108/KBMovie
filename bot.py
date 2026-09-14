import os
import asyncio
import urllib.parse
from difflib import SequenceMatcher

import psycopg2
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

API_ID_RAW = (
    os.getenv("API_ID")
    or os.getenv("api_id")
    or os.getenv("App api_id")
    or ""
)

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
# VALIDATE API ID
# =========================================================

try:
    API_ID = int(str(API_ID_RAW).strip())
except (ValueError, TypeError):
    API_ID = 0


if API_ID <= 0:
    raise RuntimeError(
        "API_ID is missing or invalid. "
        "Please check your Railway Variables."
    )

if not API_HASH:
    raise RuntimeError(
        "API_HASH is missing. "
        "Please check your Railway Variables."
    )

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is missing. "
        "Please check your Railway Variables."
    )

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is missing. "
        "Please check your Railway Variables."
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

    connection = None
    cursor = None

    try:
        connection = psycopg2.connect(
            DATABASE_URL,
            connect_timeout=10
        )

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT search_text, message_id, channel_id
            FROM kb_movies_v2
            WHERE search_text ILIKE %s
            LIMIT 20
            """,
            (f"%{query}%",)
        )

        return cursor.fetchall()

    except Exception as error:
        print(f"Database Search Error: {error}")
        return []

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# =========================================================
# NORMALIZE TEXT
# =========================================================

def normalize_text(text):

    text = str(text).lower().strip()

    for character in [
        "-", "_", ".", ",", ":", ";",
        "!", "?", "(", ")", "[", "]"
    ]:
        text = text.replace(character, " ")

    return " ".join(text.split())


# =========================================================
# FIND BEST MATCH
# =========================================================

def get_best_match(query, results):

    if not results:
        return None

    query_normalized = normalize_text(query)

    best_result = None
    best_score = 0.0

    for result in results:

        search_text = result[0]

        if not search_text:
            continue

        movie_normalized = normalize_text(search_text)

        # Exact match
        if movie_normalized == query_normalized:
            return result

        # Similarity match
        score = SequenceMatcher(
            None,
            query_normalized,
            movie_normalized
        ).ratio()

        # Partial match
        if (
            query_normalized in movie_normalized
            or movie_normalized in query_normalized
        ):
            score = max(score, 0.80)

        if score > best_score:
            best_score = score
            best_result = result

    # Accept only a reasonably good match
    if best_score >= 0.72:
        return best_result

    return None


# =========================================================
# AUTO DELETE AFTER 10 MINUTES
# =========================================================

async def delete_after_10_minutes(message):

    await asyncio.sleep(600)

    try:
        await message.delete()
        print("Message deleted after 10 minutes.")

    except Exception as error:
        print(f"Auto-delete error: {error}")


# =========================================================
# GOOGLE SEARCH BUTTON
# =========================================================

def google_search_keyboard(query):

    encoded_query = urllib.parse.quote_plus(
        f"{query} movie"
    )

    google_url = (
        "https://www.google.com/search?q="
        + encoded_query
    )

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔍 SEARCH ON GOOGLE",
                url=google_url
            )
        ]
    ])


# =========================================================
# START COMMAND
# =========================================================

@app.on_message(filters.command("start"))
async def start_handler(client, message):

    try:

        me = await client.get_me()

        bot_username = me.username or ""

        user_name = (
            message.from_user.first_name
            if message.from_user
            else "User"
        )

        start_text = (
            f"👋 Hello **{user_name}**!\n\n"

            "🎬 **KB Movie Bot**\n\n"

            "🔎 **Search for a movie by typing "
            "its name below.**\n\n"

            "👇 **OUR SERVICES**\n\n"

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
                    url=(
                        f"https://t.me/{bot_username}"
                        "?startgroup=true"
                    )
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
                    url="https://t.me/KbBotService"
                )
            ]
        ])

        sent_message = await message.reply_text(
            start_text,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

        asyncio.create_task(
            delete_after_10_minutes(sent_message)
        )

        asyncio.create_task(
            delete_after_10_minutes(message)
        )

    except Exception as error:

        print(f"Start Handler Error: {error}")


# =========================================================
# MOVIE SEARCH
# =========================================================

@app.on_message(
    filters.text & ~filters.command(["start"])
)
async def movie_search_handler(client, message):

    query = message.text.strip()

    if len(query) < 2:
        return

    print(f"Movie search: {query}")

    results = search_movies_from_db(query)

    best_match = get_best_match(
        query,
        results
    )


    # =====================================================
    # NO GOOD MATCH
    # =====================================================

    if best_match is None:

        keyboard = google_search_keyboard(query)

        not_found_message = await message.reply_text(
            f"❌ **Movie Not Found**\n\n"
            f"🔎 Search: **{query}**\n\n"
            "Please check the spelling and try again.",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

        asyncio.create_task(
            delete_after_10_minutes(
                not_found_message
            )
        )

        asyncio.create_task(
            delete_after_10_minutes(
                message
            )
        )

        return


    # =====================================================
    # GOOD MATCH FOUND
    # =====================================================

    search_text, message_id, channel_id = best_match

    try:

        movie_message = await client.copy_message(
            chat_id=message.chat.id,
            from_chat_id=int(channel_id),
            message_id=int(message_id)
        )

        warning_message = await message.reply_text(
            "⚠️ **This file will be automatically deleted "
            "after 10 minutes.**\n\n"
            "💾 **Please save or forward it before "
            "it gets deleted!**"
        )

        # Delete the movie message after 10 minutes
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

        # Delete user's search message after 10 minutes
        asyncio.create_task(
            delete_after_10_minutes(
                message
            )
        )

        print(
            f"Movie sent successfully: {search_text}"
        )

    except Exception as error:

        print(
            f"Movie Copy Error: {error}"
        )

        try:
            await message.reply_text(
                "❌ **Sorry, something went wrong "
                "while sending the file.**"
            )
        except Exception:
            pass


# =========================================================
# ABOUT BUTTON
# =========================================================

@app.on_callback_query(
    filters.regex("^about$")
)
async def about_handler(client, callback_query):

    await callback_query.answer(
        "🎬 KB Movie Bot\n\n"
        "Search available movies by typing "
        "their name.\n\n"
        "🗑️ Files are automatically deleted "
        "after 10 minutes.",
        show_alert=True
    )


# =========================================================
# START BOT
# =========================================================

print("==========================================")
print("🤖 KB Movie Bot is starting...")
print("🔎 Database search: ON")
print("🔍 Google fallback: ON")
print("🗑️ 10-minute auto-delete: ON")
print("==========================================")

app.run()
