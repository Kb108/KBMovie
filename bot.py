import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import psycopg2
import urllib.parse

# Automatically fetch environment variables regardless of case formatting in Railway
API_ID_RAW = os.getenv("API_ID") or os.getenv("api_id") or os.getenv("App api_id") or "0"
API_ID = int(API_ID_RAW) if str(API_ID_RAW).isdigit() else 0

API_HASH = os.getenv("API_HASH") or os.getenv("api_hash") or os.getenv("App api_hash") or ""
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("token") or os.getenv("TOKEN") or ""
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("database_url") or ""

app = Client("kb_movie_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Function to search movies from the PostgreSQL database
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

# Background task to handle 10-minute (600 seconds) automatic message deletion
async def schedule_message_deletion(message, delay_seconds=600):
    await asyncio.sleep(delay_seconds)
    try:
        await message.delete()
    except Exception as e:
        print(f"Auto-delete error: {e}")

# Start command handler with updated layout
@app.on_message(filters.command("start"))
async def start_handler(client, message):
    user_name = message.from_user.first_name if message.from_user else "User"
    start_text = (
        f"👋 Hello **{user_name}** 🌾,\n\n"
        "**I AM LATEST ADVANCED AND POWERFUL MOVIE DOWNLOADING BOT.. YOU CAN USE ME TO DOWNLOAD YOUR MOVIES...**\n\n"
        "👇 *Choose an option below or just type any movie name to search!*"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ ADD ME TO YOUR GROUP", url=f"https://t.me/{client.me.username}?startgroup=true")],
        [InlineKeyboardButton("🛍️ Loot Deals", url="https://t.me/loot_dells"), InlineKeyboardButton("📥 KB Downloader", url="https://t.me/KBDownloader_bot")],
        [InlineKeyboardButton("📂 Browse Files", switch_inline_query_current_chat(""))],
        [InlineKeyboardButton("✨ ABOUT", callback_data="about"), InlineKeyboardButton("✨ OWNER", url="https://t.me/KbBotService")]
    ])
    
    sent_msg = await message.reply_text(start_text, reply_markup=keyboard)
    
    asyncio.create_task(schedule_message_deletion(sent_msg, 600))
    asyncio.create_task(schedule_message_deletion(message, 600))

# Movie search and delivery handler
@app.on_message(filters.text & ~filters.command(["start"]))
async def movie_search_handler(client, message):
    query = message.text.strip()
    if len(query) < 2:
        return

    results = search_movies_from_db(query)
    
    if not results:
        encoded_query = urllib.parse.quote(query)
        google_url = f"https://www.google.com/search?q={encoded_query}+movie"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Search spelling on Google", url=google_url)]
        ])
        
        sent_msg = await message.reply_text(
            "❌ Sorry, no movies found matching this name in our database. Please check the spelling on Google:",
            reply_markup=keyboard
        )
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
            
            warning_msg = await message.reply_text(
                "⚠️ *Note: This file will be automatically deleted in 10 minutes. Please save or forward it!*"
            )
            
            asyncio.create_task(schedule_message_deletion(sent_msg, 600))
            asyncio.create_task(schedule_message_deletion(warning_msg, 600))
            asyncio.create_task(schedule_message_deletion(message, 600))
            
        except Exception as e:
            print(f"Error copying message: {e}")

# Callback query handler for interactive buttons like 'ABOUT'
@app.on_callback_query()
async def callback_handler(client, callback_query):
    if callback_query.data == "about":
        await callback_query.answer("This is an advanced movie downloading bot with 10-minute auto-delete features.", show_alert=True)

print("🤖 Movie Bot has successfully started with the 10-minute auto-delete system active!")
app.run()
