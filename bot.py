import os
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
video_links = {}  # To store user requests temporarily

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 Send a YouTube link to choose quality for download.")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    chat_id = str(update.effective_chat.id)

    await update.message.reply_text("🔍 Fetching available video qualities...")

    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = [
            f for f in info.get("formats", [])
            if f.get("vcodec") != "none" and f.get("acodec") != "none" and f.get("filesize") and f.get("filesize") < 50_000_000
        ]

        if not formats:
            await update.message.reply_text("❌ No small downloadable formats found under 50MB.")
            return

        buttons = []
        for fmt in formats:
            label = f"{fmt.get('format_note', '')} - {fmt.get('ext')} ({round(fmt['filesize'] / 1024 / 1024, 1)}MB)"
            fmt_id = fmt["format_id"]
            buttons.append([InlineKeyboardButton(label, callback_data=f"{chat_id}|{fmt_id}")])

        video_links[chat_id] = {"url": url, "info": info}
        reply_markup = InlineKeyboardMarkup(buttons)
        await update.message.reply_text("✅ Choose video quality:", reply_markup=reply_markup)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id, format_id = query.data.split("|")
    user_data = video_links.get(chat_id)

    if not user_data:
        await query.edit_message_text("⚠️ Session expired or data missing.")
        return

    url = user_data["url"]
    title = user_data["info"]["title"]

    await query.edit_message_text("⏬ Downloading selected quality...")

    ydl_opts = {
        'format': format_id,
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'quiet': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        await context.bot.send_video(
            chat_id=int(chat_id),
            video=open(filename, 'rb'),
            caption=title
        )
        os.remove(filename)

    except Exception as e:
        await context.bot.send_message(chat_id=int(chat_id), text=f"❌ Error downloading: {e}")

if __name__ == '__main__':
    if not BOT_TOKEN:
        print("❗ BOT_TOKEN not found.")
        exit(1)

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex(r'https?://.*'), handle_url))
    app.add_handler(CallbackQueryHandler(button_callback))

    os.makedirs("downloads", exist_ok=True)
    app.run_polling()
