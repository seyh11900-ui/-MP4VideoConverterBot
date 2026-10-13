import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import ffmpeg

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Retrieve environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when /start command is issued."""
    welcome_text = (
        "👋 **Welcome to the Video Converter Bot!**\n\n"
        "Send me any video file (e.g., .mov, .avi, .mkv, .webm) and I will convert it to **MP4** for you."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def convert_video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle video or document upload and convert to MP4 format."""
    message = update.message
    
    # Determine input video file source
    file_obj = None
    if message.video:
        file_obj = message.video
    elif message.document and message.document.mime_type and "video" in message.document.mime_type:
        file_obj = message.document
    else:
        await message.reply_text("Please send a valid video file.")
        return

    status_msg = await message.reply_text("📥 Downloading your video...")

    # Define temporary file paths
    input_file_path = f"temp_input_{file_obj.file_id}"
    output_file_path = f"temp_output_{file_obj.file_id}.mp4"

    try:
        # Download video from Telegram
        tg_file = await context.bot.get_file(file_obj.file_id)
        await tg_file.download_to_drive(input_file_path)

        await status_msg.edit_text("⚙️ Converting video to MP4 format...")

        # Run FFmpeg conversion asynchronously in a separate thread
        loop = asyncio.get_running_loop()
        def process_conversion():
            (
                ffmpeg
                .input(input_file_path)
                .output(output_file_path, vcodec='libx264', acodec='aac', strict='experimental')
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )

        await loop.run_in_executor(None, process_conversion)

        await status_msg.edit_text("📤 Uploading converted MP4 video back to you...")

        # Send back converted video
        with open(output_file_path, "rb") as video_file:
            await message.reply_video(
                video=video_file,
                caption="✅ Conversion completed! Here is your MP4 video.",
                supports_streaming=True
            )

    except ffmpeg.Error as e:
        logger.error(f"FFmpeg Error: {e.stderr.decode('utf-8') if e.stderr else str(e)}")
        await message.reply_text("❌ An error occurred during video conversion.")
    except Exception as e:
        logger.error(f"Error handling video conversion: {e}")
        await message.reply_text("❌ An unexpected error occurred.")
    finally:
        # Clean up temporary files
        await status_msg.delete()
        if os.path.exists(input_file_path):
            os.remove(input_file_path)
        if os.path.exists(output_file_path):
            os.remove(output_file_path)

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is not set!")
        return

    # Build Telegram Bot application
    app = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, convert_video_handler))

    # Start Polling
    logger.info("Bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
