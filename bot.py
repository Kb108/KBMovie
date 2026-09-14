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

# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

DELETE_AFTER_SECONDS = 600  # 10 minutes


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

db = None


# =========================================================
# DATABASE
# =========================================================

async def init_database():

    global db

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing")

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing")

    db = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=5
    )

    async with db.acquire() as conn:

        # Create table if it does not exist
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS content (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                link TEXT,
                channel_id BIGINT,
                message_id BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Fix old database structure
        await conn.execute("""
            ALTER TABLE content
            ADD COLUMN IF NOT EXISTS link TEXT
        """)

        await conn.execute("""
            ALTER TABLE content
            ADD COLUMN IF NOT EXISTS channel_id BIGINT
        """)

        await conn.execute("""
            ALTER TABLE content
            ADD COLUMN IF NOT EXISTS message_id BIGINT
        """)

        await conn.execute("""
            ALTER TABLE content
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMP
            DEFAULT CURRENT_TIMESTAMP
        """)

    logger.info("DATABASE CONNECTED")


# =========================================================
# SAVE CHANNEL POST
# =========================================================

async def save_channel_post(
    name,
    channel_id,
    message_id
):

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
        """,
        name,
        channel_id,
        message_id)

    logger.info(
        "CONTENT SAVED: %s | channel=%s | message=%s",
        name,
        channel_id,
        message_id
    )


# =========================================================
# SEARCH DATABASE
# =========================================================

async def search_content(query):

    async with db.acquire() as conn:

        results = await conn.fetch("""
            SELECT
                name,
                channel_id,
                message_id
            FROM content
            WHERE name ILIKE $1
            ORDER BY
                LENGTH(name) ASC
            LIMIT 5
        """, f"%{query}%")

    return results


# =========================================================
# GET CONTENT NAME FROM CHANNEL POST
# =========================================================

def get_content_name(post):

    text = post.text or post.caption or ""

    if not text:
        return None

    lines = []

    for line in text.splitlines():

        line = line.strip()

        if line:
            lines.append(line)

    if not lines:
        return None

    # First non-empty line is used as the searchable name
    name = lines[0]

    # Remove common decorative characters
    name = name.strip("🎬🎥🍿📺⭐️🔥✅❌")

    name = name.strip()

    if len(name) < 2:
        return None

    # Keep database name reasonably short
    if len(name) > 200:
        name = name[:200].strip()

    return name


# =========================================================
# CHANNEL POST HANDLER
# =========================================================

async def channel_post(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    post = update.channel_post

    if not post:
        return

    logger.info(
        "CHANNEL POST RECEIVED: channel=%s message=%s",
        post.chat_id,
        post.message_id
    )

    name = get_content_name(post)

    if not name:

        logger.warning(
            "CHANNEL POST HAS NO SEARCHABLE NAME"
        )

        return

    await save_channel_post(
        name=name,
        channel_id=post.chat_id,
        message_id=post.message_id
    )


# =========================================================
# SEARCH HANDLER
# =========================================================

async def search_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not update.message.text:
        return

    query = update.message.text.strip()

    if len(query) < 2:
        return

    logger.info(
        "SEARCH RECEIVED: %s | chat=%s",
        query,
        update.message.chat_id
    )

    results = await search_content(query)

    if not results:

        logger.info(
            "NO MATCH FOUND: %s",
            query
        )

        return

    # Send first matching original post
    item = results[0]

    if not item["channel_id"] or not item["message_id"]:

        logger.warning(
            "DATABASE ENTRY HAS NO CHANNEL/MESSAGE ID: %s",
            item["name"]
        )

        await update.message.reply_text(
            "Sorry, this content is currently unavailable."
        )

        return

    try:

        copied_message = await context.bot.copy_message(
            chat_id=update.message.chat_id,
            from_chat_id=item["channel_id"],
            message_id=item["message_id"]
        )

        logger.info(
            "ORIGINAL POST COPIED: %s",
            item["name"]
        )

        # Schedule deletion after 10 minutes
        if context.job_queue:

            context.job_queue.run_once(
                delete_copied_message,
                DELETE_AFTER_SECONDS,
                data={
                    "chat_id": copied_message.chat_id,
                    "message_id": copied_message.message_id
                }
            )

    except Exception as error:

        logger.exception(
            "COPY MESSAGE ERROR: %s",
            error
        )

        await update.message.reply_text(
            "Sorry, I could not send this content right now."
        )


# =========================================================
# DELETE COPIED MESSAGE
# =========================================================

async def delete_copied_message(
    context: ContextTypes.DEFAULT_TYPE
):

    data = context.job.data

    chat_id = data["chat_id"]
    message_id = data["message_id"]

    try:

        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=message_id
        )

        logger.info(
            "COPIED MESSAGE DELETED: %s",
            message_id
        )

    except Exception as error:

        logger.warning(
            "DELETE MESSAGE ERROR: %s",
            error
        )


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "👋 Welcome!\n\n"
        "Send the content name to search."
    )


# =========================================================
# HELP
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "📖 How to use\n\n"
        "Simply send the content name.\n\n"
        "Example:\n"
        "Demo Video"
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    logger.exception(
        "BOT ERROR:",
        exc_info=context.error
    )


# =========================================================
# BOT STARTUP
# =========================================================

async def post_init(
    application: Application
):

    await init_database()

    logger.info(
        "BOT STARTED SUCCESSFULLY"
    )


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is missing"
        )

    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL environment variable is missing"
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # /start
    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    # /help
    application.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    # =====================================================
    # GROUP SEARCH
    # =====================================================

    application.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.TEXT
            & ~filters.COMMAND,
            search_handler
        )
    )

    # =====================================================
    # PRIVATE BOT SEARCH
    # =====================================================

    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE
            & filters.TEXT
            & ~filters.COMMAND,
            search_handler
        )
    )

    # =====================================================
    # PRIVATE CHANNEL POSTS
    # =====================================================

    application.add_handler(
        MessageHandler(
            filters.ChatType.CHANNEL,
            channel_post
        )
    )

    # Error handler
    application.add_error_handler(
        error_handler
    )

    logger.info(
        "STARTING TELEGRAM BOT..."
    )

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()
