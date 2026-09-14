import os
import re
import asyncpg

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    InlineQueryHandler,
)
from telegram import InlineQueryResultArticle, InputTextMessageContent


BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

db_pool = None


async def init_database():
    global db_pool

    db_pool = await asyncpg.create_pool(DATABASE_URL)

    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                link TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


async def save_movie(name, link):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO movies (name, link)
            VALUES ($1, $2)
            ON CONFLICT (name)
            DO UPDATE SET link = EXCLUDED.link
        """, name, link)


async def search_movies(query):
    async with db_pool.acquire() as conn:
        return await conn.fetch("""
            SELECT name, link
            FROM movies
            WHERE name ILIKE $1
            ORDER BY name
            LIMIT 10
        """, f"%{query}%")


async def channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):

    post = update.channel_post

    if not post:
        return

    text = post.text or post.caption or ""

    urls = re.findall(r"https?://\S+", text)

    if not urls:
        return

    link = urls[0].rstrip(".,)")

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if not lines:
        return

    name = lines[0]

    await save_movie(name, link)


async def inline_search(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.inline_query.query.strip()

    if not query:
        return

    results = await search_movies(query)

    articles = []

    for movie in results:

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "📥 Get Link",
                    url=movie["link"]
                )
            ]
        ])

        message = (
            f"🎬 <b>{movie['name']}</b>\n\n"
            f"Click the button below to open the link."
        )

        article = InlineQueryResultArticle(
            id=str(movie["id"]),
            title=movie["name"],
            description="Get the available link",
            input_message_content=InputTextMessageContent(
                message,
                parse_mode=ParseMode.HTML
            ),
            reply_markup=keyboard
        )

        articles.append(article)

    await update.inline_query.answer(
        articles,
        cache_time=5,
        is_personal=True
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "👋 Welcome!\n\n"
        "Search from the bot's database using:\n\n"
        "@YourBot Movie Name"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "📖 How to use this bot\n\n"
        "1. Open any Telegram group.\n"
        "2. Type @YourBot followed by the content name.\n"
        "3. Select a result.\n"
        "4. Press Get Link."
    )


async def post_init(application):

    await init_database()


def main():

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("help", help_command)
    )

    application.add_handler(
        InlineQueryHandler(inline_search)
    )

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
