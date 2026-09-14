import os
import re
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

db_pool = None


async def init_database():
    global db_pool

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


async def save_content(name, link):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO content (name, link)
            VALUES ($1, $2)
            ON CONFLICT (name)
            DO UPDATE SET link = EXCLUDED.link
        """, name, link)


async def find_content(query):
    async with db_pool.acquire() as conn:
        return await conn.fetch("""
            SELECT name, link
            FROM content
            WHERE name ILIKE $1
            ORDER BY name
            LIMIT 5
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

    await save_content(name, link)


async def group_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    query = update.message.text.strip()

    if len(query) < 2:
        return

    results = await find_content(query)

    if not results:
        return

    for item in results:

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "📥 Get Link",
                    url=item["link"]
                )
            ]
        ])

        sent = await update.message.reply_text(
            f"🎬 <b>{item['name']}</b>\n\n"
            f"📥 Click the button below to open the link.",
            parse_mode="HTML",
            reply_markup=keyboard
        )

        # Automatically delete bot reply after 10 minutes
        context.job_queue.run_once(
            delete_bot_message,
            600,
            data={
                "chat_id": sent.chat_id,
                "message_id": sent.message_id
            }
        )


async def delete_bot_message(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data

    try:
        await context.bot.delete_message(
            chat_id=data["chat_id"],
            message_id=data["message_id"]
        )
    except Exception:
        pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome!\n\n"
        "Send the content name in a group to search."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 How to use\n\n"
        "Simply type the content name in the group.\n"
        "If it is available, I will show the matching result."
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
        MessageHandler(
            filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND,
            group_search
        )
    )

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
