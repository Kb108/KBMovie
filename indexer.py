import os
import re
import asyncio
import psycopg2

from pyrogram import Client


# =========================================================
# RAILWAY VARIABLES
# =========================================================

API_ID_RAW = (
    os.getenv("API_ID")
    or os.getenv("api_id")
    or os.getenv("App api_id")
    or ""
)

API_HASH = (
    os.getenv("API_HASH")
    or os.getenv("api_hash")
    or os.getenv("App api_hash")
    or ""
)

BOT_TOKEN = (
    os.getenv("BOT_TOKEN")
    or os.getenv("token")
    or os.getenv("TOKEN")
    or ""
)

DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("database_url")
    or ""
)


# =========================================================
# CHECK VARIABLES
# =========================================================

try:
    API_ID = int(str(API_ID_RAW).strip())
except (ValueError, TypeError):
    API_ID = 0


if API_ID <= 0:
    raise RuntimeError("API_ID is missing or invalid.")

if not API_HASH:
    raise RuntimeError("API_HASH is missing.")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing.")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing.")


# =========================================================
# SOURCE CHANNEL
# =========================================================

SOURCE_CHANNEL = "@demo_original"


# =========================================================
# TELEGRAM CLIENT
# =========================================================

app = Client(
    "kb_movie_indexer",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# =========================================================
# CREATE DATABASE TABLE
# =========================================================

def create_table():

    connection = None
    cursor = None

    try:

        connection = psycopg2.connect(
            DATABASE_URL,
            connect_timeout=10
        )

        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kb_movies_v2 (
                id SERIAL PRIMARY KEY,
                search_text TEXT NOT NULL,
                message_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                UNIQUE(channel_id, message_id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kb_movies_search
            ON kb_movies_v2(search_text)
        """)

        connection.commit()

        print("✅ Database table is ready.")

    except Exception as error:

        print(f"❌ Database Error: {error}")

        raise

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# =========================================================
# EXTRACT MOVIE NAME
# =========================================================

def extract_movie_name(caption):

    if not caption:
        return None

    lines = caption.splitlines()

    for line in lines:

        line = line.strip()

        if not line:
            continue

        # Remove emojis / symbols from beginning
        line = re.sub(
            r"^[^\w]+",
            "",
            line
        ).strip()

        if not line:
            continue

        lower_line = line.lower()

        # Ignore information lines
        ignored_words = [
            "language:",
            "quality:",
            "size:",
            "download",
            "link:",
            "format:",
            "audio:",
            "subtitle:",
            "year:",
            "genre:"
        ]

        if any(
            lower_line.startswith(word)
            for word in ignored_words
        ):
            continue

        # First useful line = Movie Name
        if len(line) >= 2:

            return line

    return None


# =========================================================
# SAVE MOVIE TO DATABASE
# =========================================================

def save_movie(movie_name, message_id, channel_id):

    connection = None
    cursor = None

    try:

        connection = psycopg2.connect(
            DATABASE_URL,
            connect_timeout=10
        )

        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO kb_movies_v2
            (
                search_text,
                message_id,
                channel_id
            )
            VALUES (%s, %s, %s)

            ON CONFLICT (channel_id, message_id)
            DO NOTHING
            """,
            (
                movie_name,
                int(message_id),
                int(channel_id)
            )
        )

        connection.commit()

        return cursor.rowcount

    except Exception as error:

        print(
            f"❌ Database Save Error: {error}"
        )

        if connection:
            connection.rollback()

        return 0

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# =========================================================
# INDEX CHANNEL
# =========================================================

async def index_movies():

    print("")
    print("==========================================")
    print("🎬 KB MOVIE INDEXER")
    print("==========================================")
    print("📢 Source Channel:", SOURCE_CHANNEL)
    print("==========================================")
    print("")

    # Create database table
    create_table()

    # Find channel
    try:

        channel = await app.get_chat(
            SOURCE_CHANNEL
        )

    except Exception as error:

        print(
            "❌ Could not access source channel."
        )

        print(
            f"Error: {error}"
        )

        return

    print(
        f"✅ Channel Found: {channel.title}"
    )

    print(
        f"🆔 Channel ID: {channel.id}"
    )

    print("")
    print("🔎 Starting old message scan...")
    print("")

    total = 0
    saved = 0
    skipped = 0
    duplicates = 0

    try:

        async for message in app.get_chat_history(
            channel.id
        ):

            total += 1

            # -----------------------------------------
            # Check for media
            # -----------------------------------------

            if not (
                message.document
                or message.video
                or message.audio
                or message.photo
            ):

                skipped += 1
                continue


            # -----------------------------------------
            # Get caption
            # -----------------------------------------

            caption = message.caption

            if not caption:

                skipped += 1
                continue


            # -----------------------------------------
            # Extract Movie Name
            # -----------------------------------------

            movie_name = extract_movie_name(
                caption
            )

            if not movie_name:

                skipped += 1
                continue


            # -----------------------------------------
            # Save to PostgreSQL
            # -----------------------------------------

            result = save_movie(
                movie_name,
                message.id,
                channel.id
            )


            if result == 1:

                saved += 1

                print(
                    f"✅ [{saved}] {movie_name}"
                )

            else:

                duplicates += 1

                print(
                    f"↩️ Already indexed: "
                    f"{movie_name}"
                )


            # -----------------------------------------
            # Small delay
            # -----------------------------------------

            await asyncio.sleep(0.15)


            # -----------------------------------------
            # Progress
            # -----------------------------------------

            if total % 100 == 0:

                print("")
                print(
                    "📊 Progress"
                )

                print(
                    f"Messages scanned : {total}"
                )

                print(
                    f"New movies saved : {saved}"
                )

                print(
                    f"Duplicates       : {duplicates}"
                )

                print(
                    f"Skipped          : {skipped}"
                )

                print("")


    except Exception as error:

        print("")
        print("❌ Indexing Error:")
        print(error)
        print("")


    print("")
    print("==========================================")
    print("🎉 INDEXING FINISHED")
    print("==========================================")
    print(
        f"📨 Total scanned : {total}"
    )
    print(
        f"💾 New movies    : {saved}"
    )
    print(
        f"↩️ Duplicates    : {duplicates}"
    )
    print(
        f"⏭️ Skipped       : {skipped}"
    )
    print("==========================================")
    print("")


# =========================================================
# MAIN
# =========================================================

async def main():

    async with app:

        await index_movies()


# =========================================================
# START
# =========================================================

asyncio.run(main())
