import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import psycopg2

# Retrieve environment variables from Railway
API_ID = int(os.getenv("API_ID", "12806494"))
API_HASH = os.getenv("API_HASH", "e0e7832c9d7b4150b3e9940aa3a9ee8c")
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

app = Client("kb_movie_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Function to search movies from the database
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

# Background function to automatically delete messages after a specific delay (default 10 minutes or 600 seconds)
async def schedule_message_deletion(message, delay_seconds=600):
    await asyncio.sleep(delay_seconds)
    try:
        await message.delete()
    except Exception as e:
        print(f"Auto-delete error: {e}")

# Start menu and homepage handler
@app.on_message(filters.command("start"))
async def start_handler(client, message):
    start_text = (
        "👋 **Welcome to our Movie Bot!**\n\n"
        "You can easily find your favorite movies through this bot. "
        "Please choose an option below:"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Search Movies", switch_inline_query_current_chat("")),
         InlineKeyboardButton("ℹ️ About", callback_data="about")],
        [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{client.me.username}?startgroup=true"),
         InlineKeyboardButton("🆘 Help", callback_data="help")]
    ])
    
    sent_msg = await message.reply_text(start_text, reply_markup=keyboard)

# Inline or regular text search handler for movies
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
            
            # Automatically delete both the movie file and the user's search message after 10 minutes (600 seconds)
            asyncio.create_task(schedule_message_deletion(sent_msg, 600))
            asyncio.create_task(schedule_message_deletion(message, 600))
            
        except Exception as e:
            print(f"Error copying message: {e}")

# Callback query handler for About & Help buttons
@app.on_callback_query()
async def callback_handler(client, callback_query):
    data = callback_query.data
    if data == "about":
        await callback_query.answer("This bot helps you find any movie easily.", show_alert=True)
    elif data == "help":
        await callback_query.answer("Simply send a movie name to get the file link.", show_alert=True)

print("🤖 Movie Bot has successfully started with the auto-delete system active!")
app.run()
