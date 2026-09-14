import os
import logging
import urllib.parse
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters

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
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Database Initialization Error: {e}")

init_db()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """স্টার্ট বাটন ক্লিক করলে বা /start লিখলে এই ফাংশনটি কাজ করবে"""
    user_name = update.effective_user.first_name
    
    # প্রোমোশনাল বাটনগুলো তৈরি করা
    keyboard = [
        [
            InlineKeyboardButton("🎁 Join Loot Deals", url="https://t.me/loot_dells")
        ],
        [
            InlineKeyboardButton("🤖 Join KB Bot Service", url="https://t.me/KbBotService")
        ],
        [
            InlineKeyboardButton("🔍 How to Search Movie?", callback_data="help_btn")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ওয়েলকাম মেসেজ
    welcome_text = (
        f"👋 Hello, **{user_name}**!\n\n"
        "Welcome to the **Movie Search Bot** 🎬.\n"
        "Just type the name of the movie you are looking for, and I will find it for you instantly.\n\n"
        "👇 **Please join our official channels below to get latest updates and support us:**"
    )
    
    await update.message.reply_text(
        text=welcome_text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def save_movie_to_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """চ্যানেলে পোস্ট দিলে তা ডাটাবেজে সেভ করবে"""
    message = update.channel_post or update.effective_message
    if not message:
        return

    if message.text or message.caption:
        full_text = message.text or message.caption
        message_link = message.link if message.link else "No Link Available"

        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO movies (file_name, file_id, chat_id) VALUES (%s, %s, %s)",
                (full_text, message_link, message.chat_id)
            )
            conn.commit()
            cur.close()
            conn.close()
            logger.info("New Post/Link saved successfully!")
        except Exception as e:
            logger.error(f"Database Save Error: {e}")

async def search_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """মুভি সার্চ করলে ডাটাবেজ থেকে রেজাল্ট দেবে"""
    query = update.message.text
    if not query or query.startswith("/"):
        return

    searching_msg = await update.message.reply_text("🔍 Searching for the movie...")

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT file_name, file_id FROM movies WHERE file_name ILIKE %s", (f"%{query}%",))
        results = cur.fetchall()
        cur.close()
        conn.close()

        await searching_msg.delete()

        if results:
            for full_text, message_link in results[:3]:
                title = full_text.split('\n')[0][:50]
                
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"🎬 **Found:** {title}...\n\n📥 **Download / Watch Link:**\n{message_link}\n\n🌟 *Provided by Movie Bot*",
                    parse_mode="HTML",
                    disable_web_page_preview=False 
                )
        else:
            encoded_query = urllib.parse.quote(query)
            google_search_url = f"https://www.google.com/search?q={encoded_query}"
            
            keyboard = [[InlineKeyboardButton("🌐 Search on Google (Check Spelling)", url=google_search_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"❌ Sorry, no movie found matching **'{query}'** in our database.\n\n"
                "Please check if the spelling is correct by clicking the button below:",
                reply_markup=reply_markup,
                parse_mode="HTML"
            )

    except Exception as e:
        logger.error(f"Search Error: {e}")
        await searching_msg.delete()
        
        encoded_query = urllib.parse.quote(query)
        google_search_url = f"https://www.google.com/search?q={encoded_query}"
        
        keyboard = [[InlineKeyboardButton("🌐 Search on Google", url=google_search_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "⚠️ An error occurred while searching for the movie.\n\n"
            "In the meantime, you can search for it on Google using the button below:",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

def main():
    application = ApplicationBuilder().token(TOKEN).build()

    # স্টার্ট কমান্ড হ্যান্ডলার
    application.add_handler(CommandHandler("start", start_command))

    # চ্যানেলের পোস্ট সেভ করার হ্যান্ডলার
    application.add_handler(MessageHandler(
        filters.Chat(DB_CHANNEL_ID) & (filters.TEXT | filters.CAPTION), 
        save_movie_to_db
    ))

    # মুভি সার্চ করার হ্যান্ডলার
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), search_movie))

    print("Movie Bot is running with Start Menu...")
    application.run_polling()

if __name__ == "__main__":
    main()
