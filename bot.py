import os
import re
import logging
import asyncpg

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

db_pool = None


async def init_database():
    global db_pool

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing")

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing")

    db_pool = await asyncpg.create_pool(DATABASE_URL)

    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS content (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                link TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    logger.info("DATABASE CONNECTED")


async def save_content(name, link):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO content (name, link)
            VALUES ($1, $2)
            ON CONFLICT (name)
            DO UPDATE SET link = EXCLUDED.link
        """, name, link)

    logger.info("CONTENT SAVED: %s", name)


async def search_content(query):
    async with db_pool.acquire() as conn:
        return await conn.fetch("""
            SELECT id, name, link
            FROM content
            WHERE name ILIKE $1
            ORDER BY name
            LIMIT 10
        """, f"%{query}%")


async def channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):

    post = update.channel_post

    if not post:
        return

    text = post.text or post.caption or ""

    logger.info("CHANNEL POST RECEIVED: %s", text)

    urls = re.findall(r"https?://[^\s]+", text)

    if not urls:
        logger.warning("CHANNEL POST HAS NO URL")
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

    await save_content(name, link)


async def group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message:
        return

    if not update.message.text:
        return

    query = update.message.text.strip()

    if not query:
        return

    logger.info(
        "GROUP MESSAGE RECEIVED: chat=%s text=%s",
        update.message.chat_id,
        query,
    )

    results = await search_content(query)

    if not results:
        logger.info("NO MATCH FOUND: %s", query)
        return

    logger.info("MATCH FOUND: %s", query)

    for item in results:

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "📥 Get Link",
                    url=item["link"]
                )
            ]
        ])

        sent_message = await update.message.reply_text(
            f"🎬 <b>{item['name']}</b>\n\n"
            f"📥 Click the button below to open the link.",
            parse_mode="HTML",
            reply_markup=keyboard
        )

        # Delete the bot reply after 10 minutes
        if context.job_queue:

            context.job_queue.run_once(
                delete_message,
                600,
                data={
                    "chat_id": sent_message.chat_id,
                    "message_id": sent_message.message_id,
                }
            )

        break


async def delete_message(context: ContextTypes.DEFAULT_TYPE):

    data = context.job.data

    try:
        await context.bot.delete_message(
            chat_id=data["chat_id"],
            message_id=data["message_id"]
        )

        logger.info(
            "MESSAGE DELETED: chat=%s message=%s",
            data["chat_id"],
            data["message_id"]
        )

    except Exception as e:
        logger.error("DELETE ERROR: %s", e)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "👋 Welcome!\n\n"
        "Send a content name to search."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "📖 How to use\n\n"
        "Simply send the content name.\n"
        "If a matching result exists, I will show it."
    )


async def error_handler(update, context):

    logger.error(
        "BOT ERROR: %s",
        context.error,
        exc_info=True
    )


async def post_init(application):

    await init_database()

    logger.info("BOT STARTED SUCCESSFULLY")


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

    # Normal messages from groups/supergroups
    application.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.TEXT
            & ~filters.COMMAND,
            group_message
        )
    )

    # New posts from channels
    application.add_handler(
        MessageHandler(
            filters.ChatType.CHANNEL,
            channel_post
        )
    )

    application.add_error_handler(error_handler)

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
