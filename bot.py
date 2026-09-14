import os
import logging
import urllib.parse
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# Logging Setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Railway Environment Variables or Configuration placeholders
TOKEN = os.getenv("TOKEN", "YOUR_BOT_TOKEN_HERE")
DATABASE_URL = os.getenv("DATABASE_URL", "YOUR_POSTGRES_DATABASE_URL_HERE")
DB_CHANNEL_ID = int(os.getenv("DB_CHANNEL_ID", "-100xxxxxxxxxx"))  # Your private channel ID (with minus sign)

# Initialize PostgreSQL Database and Table
def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            id SERIAL PRIMARY KEY,
            file_name TEXT,
            file_id TEXT,
            chat_id BIGINT
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

init_db()

async def save_movie_to_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves new movies uploaded to the private channel into the database automatically."""
    message = update.channel_post or update.effective_message
    if not message:
        return

    media = message.video or message.document or message.audio
    if media:
        file_id = media.file_id
        file_name = media.file_name or message.caption or "Unknown Movie"
        
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO movies (file_name, file_id, chat_id) VALUES (%s, %s, %s)",
                (file_name, file_id, message.chat_id)
            )
            conn.commit()
            cur.close()
            conn.close()
            logger.info(f"Movie saved: {file_name}")
        except Exception as e:
            logger.error(f"Database Error: {e}")

async def search_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Searches for movies in the database when a user types a name in a group or PM."""
    query = update.message.text
    if query.startswith("/"):
        return

    searching_msg = await update.message.reply_text("🔍 Searching for the movie...")

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT file_id, file_name FROM movies WHERE file_name ILIKE %s", (f"%{query}%",))
        results = cur.fetchall()
        cur.close()
        conn.close()

        await searching_msg.delete()

        if results:
            for file_id, file_name in results[:5]:  # Sends up to 5 matching files
                await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=file_id,
                    caption=f"🎬 **{file_name}**\n\n📥 Provided by Movie Bot"
                )
        else:
            # If movie is not found, generate a Google search link to check the spelling
            encoded_query = urllib.parse.quote(query)
            google_search_url = f"https://www.google.com/search?q={encoded_query}"
            
            keyboard = [[InlineKeyboardButton("🌐 Search on Google (Check Spelling)", url=google_search_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"❌ Sorry, no movie found matching **'{query}'**.\n\n"
                "Please check if the spelling is correct using the button below:",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

    except Exception as e:
        logger.error(f"Search Error: {e}")
        await searching_msg.delete()
        await update.message.reply_text("An error occurred while searching for the movie.")

def main():
    application = ApplicationBuilder().token(TOKEN).build()

    # 1. Handler to track new uploads in the private channel
    application.add_handler(MessageHandler(filters.Chat(DB_CHANNEL_ID) & (filters.VIDEO | filters.DOCUMENT | filters.AUDIO), save_movie_to_db))

    # 2. Handler to search movies in groups or private chat
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), search_movie))

    print("Movie Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
