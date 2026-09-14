# Movie search and delivery handler
@app.on_message(filters.text & ~filters.command(["start"]))
async def movie_search_handler(client, message):
    query = message.text.strip()

    if len(query) < 2:
        return

    results = search_movies_from_db(query)

    # Movie not found
    if not results:
        encoded_query = urllib.parse.quote_plus(f"{query} movie")
        google_url = f"https://www.google.com/search?q={encoded_query}"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔍 Search on Google",
                    url=google_url
                )
            ]
        ])

        sent_msg = await message.reply_text(
            f"❌ Movie not found for: **{query}**\n\n"
            "Please check the spelling on Google and try again.",
            reply_markup=keyboard
        )

        asyncio.create_task(
            schedule_message_deletion(sent_msg, 600)
        )

        asyncio.create_task(
            schedule_message_deletion(message, 600)
        )

        return

    # Movie found
    for text, msg_id, channel_id in results:
        try:
            sent_msg = await client.copy_message(
                chat_id=message.chat.id,
                from_chat_id=channel_id,
                message_id=msg_id
            )

            # Message below the movie
            warning_msg = await message.reply_text(
                "⚠️ **This file will be deleted after 10 minutes. "
                "Please save or forward it before it gets deleted!**"
            )

            # Delete movie after 10 minutes
            asyncio.create_task(
                schedule_message_deletion(sent_msg, 600)
            )

            # Delete warning after 10 minutes
            asyncio.create_task(
                schedule_message_deletion(warning_msg, 600)
            )

            # Delete user's search message after 10 minutes
            asyncio.create_task(
                schedule_message_deletion(message, 600)
            )

        except Exception as e:
            print(f"Error copying message: {e}")
