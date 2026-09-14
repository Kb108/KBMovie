import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import psycopg2

# Load environment variables from Railway
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

app = Client("kb_movie_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Function to query movies from the PostgreSQL database
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

# Background task to handle 10-minute (600 seconds) automatic deletion
async def schedule_message_deletion(message, delay_seconds=600):
    await asyncio.sleep(delay_seconds)
    try:
        await message.delete()
    except Exception as e:
        print(f"Auto-delete error: {e}")

# Start command handler
@app.on_message(filters.command("start"))
async def start_handler(client, message):
    start_text = (
        "👋 **Welcome to the Movie Bot!**\n\n"
        "Send any movie name to search and receive your files instantly.\n"
        "ℹ️ *Note: All queries and bot responses are automatically deleted after 10 minutes.*"
    )
    sent_msg = await message.reply_text(start_text)
    
    # Auto-delete the start greeting and user command after 10 minutes
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
        sent_msg = await message.reply_text("❌ Sorry, no movies found matching this name in our database.")
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
            
            # Exactly 10 minutes (600 seconds) auto-delete timer for both bot response and user query
            asyncio.create_task(schedule_message_deletion(sent_msg, 600))
            asyncio.create_task(schedule_message_deletion(message, 600))
            
        except Exception as e:
            print(f"Error copying message: {e}")

print("🤖 Movie Bot has successfully started with the 10-minute auto-delete system active!")
app.run()
