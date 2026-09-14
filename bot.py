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

# PostgreSQL ডাটাবেজ এবং টেবিল তৈরি করা (Text/Link সাপোর্টের জন্য আপডেট করা হয়েছে)
def init_db():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS movies (
                id SERIAL PRIMARY KEY,
                file_name TEXT,
                file_id TEXT,
                chat_id BIGINT,
                message_link TEXT
            )
        ''')
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Database Initialization Error: {e}")

init_db()

async def save_movie_to_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """প্রাইভেট চ্যানেলের নতুন পোস্ট (টেক্সট বা লিংক সহ) ডাটাবেজে সেভ করবে"""
    message = update.channel_post or update.effective_message
    if not message:
        return

    # নতুন নিয়ম: ভিডিওর বদলে যেকোনো টেক্সট মেসেজ বা ক্যাপশন চেক করবে
    if message.text or message.caption:
        # ফাইলের নাম হিসেবে মেসেজের প্রথম লাইন বা সম্পূর্ণ টেক্সট নেওয়া
        full_text = message.text or message.caption
        file_name = full_text.split('\n')[0]  # প্রথম লাইনকে টাইটেল হিসেবে ধরা
        
        # টেলিগ্রামের পার্মালিন্ক তৈরি করা (যাতে ইউজার ক্লিক করে সরাসরি চ্যানেলে যেতে পারে)
        message_link = message.link if message.link else "No Link"

        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            # ডাটাবেজে ফাইল_নাম, চ্যাট_আইডি এবং মেসেজ_লিংক সেভ করা (file_id এর বদলে লিংক ব্যবহার করা হবে)
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
    """গ্রুপে বা ইনবক্সে কেউ মুভি সার্চ করলে তা ডাটাবেজ থেকে খুঁজে বের করবে"""
    query = update.message.text
    if not query or query.startswith("/"):
        return

    searching_msg = await update.message.reply_text("🔍 Searching for the movie link...")

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        # ডাটাবেজে নামের সাথে মিলিয়ে খোঁজা
        cur.execute("SELECT file_name, message_link FROM movies WHERE file_name ILIKE %s", (f"%{query}%",))
        results = cur.fetchall()
        cur.close()
        conn.close()

        await searching_msg.delete()

        if results:
            # যদি মুভি পাওয়া যায়, তবে একে একে পাঠিয়ে দেওয়া (লিংক সহ)
            for file_name, message_link in results[:5]:  # একসঙ্গে সর্বোচ্চ ৫টি রেজルト
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"🎬 **Found: {file_name}**\n\n📥 Terabox Link:\n{message_link}\n\n🌟 Provided by Movie Bot",
                    parse_mode="Markdown",
                    disable_web_page_preview=False # লিংক প্রিভিউ চালু রাখা (যাতে Terabox থাম্বনেইল দেখা যায়)
                )
        else:
            # মুভি না পাওয়া গেলে গুগল সার্চের বাটন সহ মেসেজ
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

    # ১. প্রাইভেট চ্যানেলের নতুন টেক্সট/লিংক পোস্ট ট্র্যাক করার হ্যান্ডলার (ভিডিওর বদলে টেক্সট ফিল্টার)
    application.add_handler(MessageHandler(
        filters.Chat(DB_CHANNEL_ID) & (filters.TEXT | filters.CAPTION), 
        save_movie_to_db
    ))

    # ২. গ্রুপ বা ইনবক্সে মুভি সার্চ করার হ্যান্ডলার
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), search_movie))

    print("Text/Link Filter Movie Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
