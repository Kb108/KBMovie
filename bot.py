import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import psycopg2

# Railway বা পরিবেশ থেকে ভেরিয়েবলগুলো নেওয়া
API_ID = int(os.getenv("API_ID", "12806494"))
API_HASH = os.getenv("API_HASH", "e0e7832c9d7b4150b3e9940aa3a9ee8c")
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

app = Client("kb_movie_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ডাটাবেজ থেকে মুভি খোঁজার ফাংশন
def search_movies_from_db(query):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        # ডাটাবেজ থেকে ম্যাচিং মুভিগুলো খুঁজবে (সর্বোচ্চ ১০টি)
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

# নির্দিষ্ট সময় পর মেসেজ স্বয়ংক্রিয়ভাবে ডিলিট করার ব্যাকগ্রাউন্ড ফাংশন (ডিফল্ট ১০ মিনিট বা ৬০০ সেকেন্ড)
async def schedule_message_deletion(message, delay_seconds=600):
    await asyncio.sleep(delay_seconds)
    try:
        await message.delete()
    except Exception as e:
        print(f"Auto-delete error: {e}")

# স্টার্ট মেনু এবং হোমপেজ হ্যান্ডলার
@app.on_message(filters.command("start"))
async def start_handler(client, message):
    start_text = (
        "👋 **স্বাগতম আমাদের মুভি বটে!**\n\n"
        "আপনি এই বট থেকে খুব সহজেই আপনার পছন্দের মুভি খুঁজে পেতে পারেন। "
        "নিচের অপশনগুলো থেকে আপনার প্রয়োজনীয় সেবা বেছে নিন:"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 মুভি সার্চ করুন", switch_inline_query_current_chat("")),
         InlineKeyboardButton("ℹ️ আমাদের সম্পর্কে", callback_data="about")],
        [InlineKeyboardButton("➕ গ্রুপে অ্যাড করুন", url=f"https://t.me/{client.me.username}?startgroup=true"),
         InlineKeyboardButton("🆘 সাহায্য", callback_data="help")]
    ])
    
    sent_msg = await message.reply_text(start_text, reply_markup=keyboard)
    
    # স্টার্ট মেসেজটি এবং ইউজারের কমান্ড মেসেজটিও ১০ মিনিট পর ডিলিট করতে চাইলে নিচের লাইনগুলো চালু রাখতে পারেন:
    # asyncio.create_task(schedule_message_deletion(sent_msg, 600))
    # asyncio.create_task(schedule_message_deletion(message, 600))

# ইনলাইন বা সাধারণ টেক্সট সার্চ হ্যান্ডলার (মুভি খোঁজার জন্য)
@app.on_message(filters.text & ~filters.command(["start"]))
async def movie_search_handler(client, message):
    query = message.text.strip()
    if len(query) < 2:
        return

    results = search_movies_from_db(query)
    
    if not results:
        sent_msg = await message.reply_text("❌ দুঃখিত, এই নামের কোনো মুভি আমাদের ডাটাবেজে পাওয়া যায়নি।")
        # ১০ মিনিট পর ইউজার ও বটের মেসেজ ডিলিট করার শিডিউল
        asyncio.create_task(schedule_message_deletion(sent_msg, 600))
        asyncio.create_task(schedule_message_deletion(message, 600))
        return

    for text, msg_id, channel_id in results:
        try:
            # চ্যানেল থেকে মুভিটি ইউজারের চ্যাটে ফরোয়ার্ড/কপি করে পাঠানো
            sent_msg = await client.copy_message(
                chat_id=message.chat.id,
                from_chat_id=channel_id,
                message_id=msg_id
            )
            
            # ⏰ নিখুঁতভাবে ১০ মিনিট (৬০০ সেকেন্ড) পর মুভি ফাইল এবং ইউজারের সার্চ মেসেজটি অটো-ডিলিট হবে
            asyncio.create_task(schedule_message_deletion(sent_msg, 600))
            asyncio.create_task(schedule_message_deletion(message, 600))
            
        except Exception as e:
            print(f"Error copying message: {e}")

# কলব্যাক কুয়েরি (About & Help বাটন হ্যান্ডেল করার জন্য)
@app.on_callback_query()
async def callback_handler(client, callback_query):
    data = callback_query.data
    if data == "about":
        await callback_query.answer("এই বটটি দিয়ে আপনি যেকোনো মুভি খুব সহজেই খুঁজে পেতে পারেন।", show_alert=True)
    elif data == "help":
        await callback_query.answer("মুভির নাম লিখে সেন্ড করলেই বট আপনাকে মুভি ফাইল দিয়ে দেবে।", show_alert=True)

print("🤖 মুভি বট সফলভাবে চালু হয়েছে এবং অটো-ডিলিট সিস্টেম সক্রিয় আছে!")
app.run()
