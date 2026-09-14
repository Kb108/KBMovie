import os
import logging
import urllib.parse
import html
import asyncio
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
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS kb_movies_v2 (
                        id SERIAL PRIMARY KEY,
                        search_text TEXT,
                        message_id INTEGER,
                        channel_id BIGINT
                    )
                ''')
    except Exception as e:
        logger.error(f"Database Initialization Error: {e}")

init_db()

# ১০ মিনিট পর মেসেজ ডিলিট করার ফাংশন
async def auto_delete_message(bot, chat_id, message_id, delay):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"Message {message_id} auto-deleted after {delay} seconds.")
    except Exception as e:
        logger.error(f"Auto-delete Failed: {e}")

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
        msg_id = message.message_id
        chat_id = message.chat_id

        try:
            with psycopg2.connect(DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO kb_movies_v2 (search_text, message_id, channel_id) VALUES (%s, %s, %s)",
                        (full_text, msg_id, chat_id)
                    )
            logger.info(f"Exact Post saved successfully! (Message ID: {msg_id})")
        except Exception as e:
            logger.error(f"Database Save Error: {e}")

async def search_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    if not query or query.startswith("/"):
        return

    searching_msg = await update.message.reply_text("🔍 Searching for the movie...")

    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT message_id, channel_id FROM kb_movies_v2 WHERE search_text ILIKE %s", (f"%{query}%",))
                results = cur.fetchall()

        try:
            await searching_msg.delete()
        except:
            pass

        if results:
            for msg_id, channel_id in results[:3]:  
                try:
                    # প্রাইভেট চ্যানেলের মেসেজটি হুবহু কপি করে পাঠানো
                    sent_msg = await context.bot.copy_message(
                        chat_id=update.effective_chat.id,
                        from_chat_id=channel_id,
                        message_id=msg_id
                    )
                    
                    # 600 সেকেন্ড (১০ মিনিট) পর মুভি ডিলিট করার টাইমার সেট করা
                    asyncio.create_task(auto_delete_message(context.bot, update.effective_chat.id, sent_msg.message_id, 600))
                    
                except Exception as copy_err:
                    logger.error(f"Copy Message Error: {copy_err}")
            
            # ইউজারকে ওয়ার্নিং মেসেজ দেওয়া (ইংলিশে আপডেট করা হয়েছে)
            warning_msg = await update.message.reply_text("⚠️ *This movie will be automatically deleted in 10 minutes!*", parse_mode="HTML")
            
            # এই ওয়ার্নিং মেসেজটিও ১০ মিনিট পর ডিলিট হবে
            asyncio.create_task(auto_delete_message(context.bot, update.effective_chat.id, warning_msg.message_id, 600))

        else:
            encoded_query = urllib.parse.quote(query)
            google_search_url = f"https://www.google.com/search?q={encoded_query}"
            
            keyboard = [[InlineKeyboardButton("🌐 Search on Google (Check Spelling)", url=google_search_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            not_found_msg = await update.message.reply_text(
                f"❌ Sorry, no movie found matching **'{html.escape(query)}'** in our database.\n\n"
                "Please check if the spelling is correct by clicking the button below:",
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            # মুভি না পাওয়ার মেসেজটিও ২ মিনিট পর ডিলিট হয়ে যাবে
            asyncio.create_task(auto_delete_message(context.bot, update.effective_chat.id, not_found_msg.message_id, 120))

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

        error_msg = await update.message.reply_text(
            f"⚠️ **System Error:** `{html.escape(str(e))}`\n\n"
            "An internal error occurred. You can search for it on Google using the button below:",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        asyncio.create_task(auto_delete_message(context.bot, update.effective_chat.id, error_msg.message_id, 120))

def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.Chat(DB_CHANNEL_ID) & (filters.TEXT | filters.CAPTION), save_movie_to_db))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), search_movie))

    print("Movie Bot is running with Auto-Delete Feature...")
    application.run_polling()

if __name__ == "__main__":
    main()
