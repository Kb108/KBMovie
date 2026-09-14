import os
import logging
import urllib.parse
import html
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

def init_db():
    try:
        # 'with' ব্যবহার করা হয়েছে যাতে কানেকশন লিক না হয়
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS movies (
                        id SERIAL PRIMARY KEY,
                        file_name TEXT,
                        file_id TEXT,
                        chat_id BIGINT
                    )
                ''')
    except Exception as e:
        logger.error(f"Database Initialization Error: {e}")

init_db()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    
    keyboard = [
        [InlineKeyboardButton("🎁 Join Loot Deals", url="https://t.me/loot_dells")],
        [InlineKeyboardButton("🤖 Join KB Bot Service", url="https://t.me/KbBotService")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"👋 Hello, **{html.escape(user_name)}**!\n\n"
        "Welcome to the **Movie Search Bot** 🎬.\n"
        "Just type the name of the movie you are looking for, and I will find it for you instantly.\n\n"
        "👇 **Please join our official channels below:**"
    )
    await update.message.reply_text(text=welcome_text, reply_markup=reply_markup, parse_mode="HTML")

async def save_movie_to_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.channel_post or update.effective_message
    if not message:
        return

    if message.text or message.caption:
        full_text = message.text or message.caption
        message_link = message.link if message.link else "No Link Available"

        try:
            with psycopg2.connect(DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO movies (file_name, file_id, chat_id) VALUES (%s, %s, %s)",
                        (full_text, message_link, message.chat_id)
                    )
            logger.info("New Post/Link saved successfully!")
        except Exception as e:
            logger.error(f"Database Save Error: {e}")

async def search_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    if not query or query.startswith("/"):
        return

    searching_msg = await update.message.reply_text("🔍 Searching for the movie...")

    try:
        # ডাটাবেজ থেকে সুরক্ষিতভাবে তথ্য খোঁজা
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT file_name, file_id FROM movies WHERE file_name ILIKE %s", (f"%{query}%",))
                results = cur.fetchall()

        try:
            await searching_msg.delete()
        except:
            pass

        if results:
            for full_text, message_link in results[:3]:
                # html.escape ব্যবহার করা হয়েছে যাতে কোনো স্পেশাল ক্যারেক্টার বটকে ক্রাশ না করায়
                title = html.escape(full_text.split('\n')[0][:50])
                safe_link = html.escape(message_link)
                
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"🎬 **Found:** {title}...\n\n📥 **Download / Watch Link:**\n{safe_link}\n\n🌟 *Provided by Movie Bot*",
                    parse_mode="HTML",
                    disable_web_page_preview=False 
                )
        else:
            encoded_query = urllib.parse.quote(query)
            google_search_url = f"https://www.google.com/search?q={encoded_query}"
            
            keyboard = [[InlineKeyboardButton("🌐 Search on Google (Check Spelling)", url=google_search_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"❌ Sorry, no movie found matching **'{html.escape(query)}'** in our database.\n\n"
                "Please check if the spelling is correct by clicking the button below:",
                reply_markup=reply_markup,
                parse_mode="HTML"
            )

    except Exception as e:
        logger.error(f"Search Error: {e}")
        try:
            await searching_msg.delete()
        except:
            pass
        
        encoded_query = urllib.parse.quote(query)
        google_search_url = f"https://www.google.com/search?q={encoded_query}"
        
        keyboard = [[InlineKeyboardButton("🌐 Search on Google", url=google_search_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # যদি কোনো এরর আসে, তবে ঠিক কী এরর হয়েছে তা মেসেজেই দেখিয়ে দেবে
        await update.message.reply_text(
            f"⚠️ **System Error:** `{html.escape(str(e))}`\n\n"
            "An internal error occurred. You can search for it on Google using the button below:",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.Chat(DB_CHANNEL_ID) & (filters.TEXT | filters.CAPTION), save_movie_to_db))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), search_movie))

    print("Movie Bot is running with Advanced Security...")
    application.run_polling()

if __name__ == "__main__":
    main()
