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

# Railway Environment Variables 
TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
DB_CHANNEL_ID = int(os.getenv("DB_CHANNEL_ID", "0"))

# Database Initialization
def init_db():
    try:
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
        
        # Add link column if it doesn't exist
        cur.execute('ALTER TABLE movies ADD COLUMN IF NOT EXISTS message_link TEXT;')
        
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Database Initialization Error: {e}")

init_db()

async def save_movie_to_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves new channel posts (text or links) to the database"""
    message = update.channel_post or update.effective_message
    if not message:
        return

    if message.text or message.caption:
        full_text = message.text or message.caption
        file_name = full_text.split('\n')[0] 
        
        message_link = message.link if message.link else "No Link Available"

        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO movies (file_name, file_id, chat_id, message_link) VALUES (%s, %s, %s, %s)",
                (file_name, "text_post", message.chat_id, message_link)
            )
            conn.commit()
            cur.close()
            conn.close()
            logger.info(f"Text Post/Link saved: {file_name}")
        except Exception as e:
            logger.error(f"Database Save Error: {e}")

async def search_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Searches for movies and replies with results or a Google search button"""
    query = update.message.text
    if not query or query.startswith("/"):
        return

    searching_msg = await update.message.reply_text("🔍 Searching for the movie...")

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT file_name, message_link FROM movies WHERE file_name ILIKE %s", (f"%{query}%",))
        results = cur.fetchall()
        cur.close()
        conn.close()

        await searching_msg.delete()

        if results:
            for file_name, message_link in results[:5]:  
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"🎬 **Movie Found:** {file_name}\n\n📥 **Download / Watch Link:**\n{message_link}\n\n🌟 *Provided by Movie Bot*",
                    parse_mode="Markdown",
                    disable_web_page_preview=False 
                )
        else:
            # If movie is not found, show Google Search button
            encoded_query = urllib.parse.quote(query)
            google_search_url = f"https://www.google.com/search?q={encoded_query}"
            
            keyboard = [[InlineKeyboardButton("🌐 Search on Google (Check Spelling)", url=google_search_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"❌ Sorry, no movie found matching **'{query}'** in our database.\n\n"
                "Please check if the spelling is correct by clicking the button below:",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

    except Exception as e:
        logger.error(f"Search Error: {e}")
        await searching_msg.delete()
        
        # If an internal ERROR occurs, still show the Google Search button
        encoded_query = urllib.parse.quote(query)
        google_search_url = f"https://www.google.com/search?q={encoded_query}"
        
        keyboard = [[InlineKeyboardButton("🌐 Search on Google", url=google_search_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "⚠️ An error occurred while searching for the movie.\n\n"
            "In the meantime, you can search for it on Google using the button below:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(MessageHandler(
        filters.Chat(DB_CHANNEL_ID) & (filters.TEXT | filters.CAPTION), 
        save_movie_to_db
    ))

    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), search_movie))

    print("Movie Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
