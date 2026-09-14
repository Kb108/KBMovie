import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import psycopg2

# Railway থেকে যেকোনো ফরম্যাটের ভেরিয়েবল স্বয়ংক্রিয়ভাবে লুফে নেওয়ার ব্যবস্থা
API_ID_RAW = os.getenv("API_ID") or os.getenv("api_id") or os.getenv("App api_id") or "0"
API_ID = int(API_ID_RAW) if str(API_ID_RAW).isdigit() else 0

API_HASH = os.getenv("API_HASH") or os.getenv("api_hash") or os.getenv("App api_hash") or ""
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("token") or os.getenv("TOKEN") or ""
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("database_url") or ""

app = Client("kb_movie_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ডাটাবেজ থেকে মুভি খোঁজার ফাংশন
def search_movies_from_db(query):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            "SELECT search_text, message_id, channel_id FROM kb_movies_v2 WHERE search_text ILIKE %s LIMIT 10",
            (f"%{query}%",)
        )
        results = cur.fetchall()
        cur.close()
        conn.close()
        return results
    except Exception as e:
        print(f"Database Search Error: {e}")
        return []

# ১০ মিনিট (৬০০ সেকেন্ড) পর মেসেজ ডিলিট করার ব্যাকগ্রাউন্ড টাস্ক
async def schedule_message_deletion(message, delay_seconds=600):
    await asyncio.sleep(delay_seconds)
    try:
        await message.delete()
    except Exception as e:
        print(f"Auto-delete error: {e}")

# স্টার্ট কমান্ড হ্যান্ডলার
@app.on_message(filters.command("start"))
async def start_handler(client, message):
    start_text = (
        "👋 **স্বাগতম আমাদের মুভি বটে!**\n\n"
        "যেকোনো মুভির নাম লিখে পাঠান এবং মুহূর্তেই ফাইল পেয়ে যান।\n"
        "ℹ️ *নোট: ইউজার ও বটের পাঠানো সমস্ত মেসেজ ১০ মিনিট পর স্বয়ংক্রিয়ভাবে মুছে যাবে।*"
    )
    sent_msg = await message.reply_text(start_text)
    
    asyncio.create_task(schedule_message_deletion(sent_msg, 600))
    asyncio.create_task(schedule_message_deletion(message, 600))

# মুভি সার্চ এবং ফাইল পাঠানোর হ্যান্ডলার
@app.on_message(filters.text & ~filters.command(["start"]))
async def movie_search_handler(client, message):
    query = message.text.strip()
    if len(query) < 2:
        return

    results = search_movies_from_db(query)
    
    if not results:
        sent_msg = await message.reply_text("❌ দুঃখিত, এই নামের কোনো মুভি আমাদের ডাটাবেজে পাওয়া যায়নি।")
        asyncio.create_task(schedule_message_deletion(sent_msg, 600))
        asyncio.create_task(schedule_message_deletion(message, 600))
        return

    for text, msg_id, channel_id in results:
        try:
            sent_msg = await client.copy_message(
                chat_id=message.chat.id,
                from_chat_id=channel_id,
                message_id=msg_id
            )
            
            # ১০ মিনিট (৬০০ সেকেন্ড) পর মুভি ফাইল এবং ইউজারের সার্চ টেক্সট ডিলিট হবে
            asyncio.create_task(schedule_message_deletion(sent_msg, 600))
            asyncio.create_task(schedule_message_deletion(message, 600))
            
        except Exception as e:
            print(f"Error copying message: {e}")

print("🤖 মুভি বট সফলভাবে চালু হয়েছে এবং ১০ মিনিটের অটো-ডিলিট সিস্টেম সক্রিয় আছে!")
app.run()
