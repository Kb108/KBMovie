import os
import logging
import asyncpg

from telegram import Update
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
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

db = None


async def init_database():
    global db

    db = await asyncpg.create_pool(DATABASE_URL)

    async with db.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS content (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                channel_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL
            )
        """)

    logger.info("DATABASE CONNECTED")


async def save_content(name, channel_id, message_id):
    async with db.acquire() as conn:
        await conn.execute("""
            INSERT INTO content
                (name, channel_id, message_id)
            VALUES
                ($1, $2, $3)
            ON CONFLICT (name)
            DO UPDATE SET
                channel_id = EXCLUDED.channel_id,
                message_id = EXCLUDED.message_id
        """, name, channel_id, message_id)

    logger.info("SAVED: %s", name)


async def find_content(query):
    async with db.acquire() as conn:
        return await conn.fetch("""
            SELECT name, channel_id, message_id
            FROM content
            WHERE name ILIKE $1
            LIMIT 1
        """, f"%{query}%")


async def channel_post(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    post = update.channel_post

    if not post:
        return

    text = post.text or post.caption or ""

    if not text:
        return

    logger.info("CHANNEL POST: %s", text)

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if not lines:
        return

    # First line is treated as the content name
    name = lines[0]

    await save_content(
        name,
        post.chat_id,
        post.message_id
    )


async def send_original_post(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    query = update.message.text.strip()

    if len(query) < 2:
        return

    logger.info("SEARCH: %s", query)

    results = await find_content(query)

    if not results:
        logger.info("NO RESULT: %s", query)
        return

    item = results[0]

    try:

        copied = await context.bot.copy_message(
            chat_id=update.message.chat_id,
            from_chat_id=item["channel_id"],
            message_id=item["message_id"]
        )

        logger.info("ORIGINAL POST COPIED")

        # Delete copied post after 10 minutes
        if context.job_queue:

            context.job_queue.run_once(
                delete_copied_post,
                600,
                data={
                    "chat_id": copied.chat_id,
                    "message_id": copied.message_id
                }
            )

    except Exception as e:

        logger.error(
            "COPY ERROR: %s",
            e
        )


async def delete_copied_post(
    context: ContextTypes.DEFAULT_TYPE
):

    data = context.job.data

    try:

        await context.bot.delete_message(
            chat_id=data["chat_id"],
            message_id=data["message_id"]
        )

        logger.info("COPIED POST DELETED")

    except Exception as e:

        logger.error(
            "DELETE ERROR: %s",
            e
        )


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "👋 Welcome!\n\n"
        "Send the content name to search."
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "📖 How to use\n\n"
        "Simply send the content name.\n"
        "If it is available, I will send the original post."
    )


async def post_init(application):

    await init_database()

    logger.info("BOT STARTED")


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

    # Group messages
    application.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.TEXT
            & ~filters.COMMAND,
            send_original_post
        )
    )

    # Private chat messages
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE
            & filters.TEXT
            & ~filters.COMMAND,
            send_original_post
        )
    )

    # Channel posts
    application.add_handler(
        MessageHandler(
            filters.ChatType.CHANNEL,
            channel_post
        )
    )

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
