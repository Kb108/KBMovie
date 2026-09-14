import os
import re
import sqlite3
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")

db = sqlite3.connect("movies.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS movies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    link TEXT
)
""")
db.commit()


def save_movie(name, link):
    cursor.execute(
        "INSERT OR REPLACE INTO movies (name, link) VALUES (?, ?)",
        (name, link)
    )
    db.commit()


async def channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.channel_post:
        return

    text = update.channel_post.text or update.channel_post.caption or ""

    links = re.findall(r"https?://\S+", text)

    if not links:
        return

    link = links[0]

    lines = [x.strip() for x in text.splitlines() if x.strip()]

    if not lines:
        return

    name = lines[0]

    save_movie(name, link)


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args).strip()

    if not query:
        await update.message.reply_text(
            "🎬 Movie name লিখুন।\n\nExample:\n/search Demo Movie"
        )
        return

    cursor.execute(
        "SELECT name, link FROM movies WHERE name LIKE ?",
        (f"%{query}%",)
    )

    results = cursor.fetchall()

    if not results:
        await update.message.reply_text(
            "❌ Movie পাওয়া যায়নি।"
        )
        return

    message = "🎬 Movie Found!\n\n"

    for name, link in results[:10]:
        message += f"🎬 {name}\n"
        message += f"📥 Download: {link}\n\n"

    await update.message.reply_text(message)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome!\n\n"
        "Movie খুঁজতে লিখুন:\n"
        "/search Movie Name"
    )


app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("search", search))
app.add_handler(
    MessageHandler(filters.ChatType.CHANNEL, channel_post)
)

app.run_polling()
