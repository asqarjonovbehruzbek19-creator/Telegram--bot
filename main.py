
import os
import asyncio
import logging
import tempfile
import shutil
from pathlib import Path
from urllib.parse import urlparse
from threading import Thread

import yt_dlp
from flask import Flask
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import (
    ReplyKeyboardBuilder,
    InlineKeyboardBuilder,
)

# TOKEN Render Environment Variables ichida bo'lishi kerak
TOKEN = os.getenv("BOT_TOKEN", "")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN kiritilmagan!")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN)
dp = Dispatcher()

app = Flask(__name__)

# Foydalanuvchining oxirgi havolasi
user_urls = {}

MAX_SIZE = 49 * 1024 * 1024


@app.route("/")
def home():
    return "Media bot ishlayapti!"


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    Thread(target=run_flask, daemon=True).start()


def valid_url(url):
    try:
        p = urlparse(url)
        host = (p.hostname or "").lower()

        instagram = (
            host == "instagram.com"
            or host.endswith(".instagram.com")
        )
        youtube = (
            host == "youtube.com"
            or host.endswith(".youtube.com")
            or host == "youtu.be"
        )

        return (
            p.scheme in ("https", "http")
            and (instagram or youtube)
        )
    except Exception:
        return False


def get_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="📥 Yuklab olish")
    kb.button(text="ℹ️ Bot haqida")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)


def download_media(url, mode, folder):
    """
    mode:
      video = Instagram video
      audio = Instagram audio yoki YouTube MP3
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    opts = {
        "outtmpl": str(folder / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "restrictfilenames": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "socket_timeout": 30,
        "max_filesize": MAX_SIZE,
    }

    if mode == "video":
        opts["format"] = (
            "best[ext=mp4]/best"
        )
        opts["merge_output_format"] = "mp4"
    else:
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]

    # Faqat ruxsatli, ochiq kontent.
    # Login/parol yoki cheklovni aylanib o'tish yo'q.
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

    if not info:
        raise RuntimeError("Media topilmadi.")

    if mode == "audio":
        files = list(folder.glob("*.mp3"))
    else:
        files = [
            p for p in folder.iterdir()
            if p.is_file()
            and p.suffix.lower() in (
                ".mp4", ".m4v", ".mov", ".webm"
            )
        ]

    files = sorted(files, key=lambda p: p.stat().st_mtime)

    if not files:
        raise RuntimeError(
            "Yuklangan fayl topilmadi. Havola yoki formatni tekshiring."
        )

    return files, info.get("title", "Media")


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "👋 Assalomu alaykum!\n\n"
        "📸 Instagram videosi va audiosi\n"
        "🎵 YouTube qo'shiqlarini MP3 yuklash\n\n"
        "Havolani yuboring, keyin kerakli formatni tanlang.",
        reply_markup=get_menu(),
    )


@dp.message(F.text == "ℹ️ Bot haqida")
async def about(message: types.Message):
    await message.answer(
        "📥 Instagram video: MP4\n"
        "🎧 Instagram audio: MP3\n"
        "🎵 YouTube audio: MP3\n\n"
        "Eslatma: FFmpeg o'rnatilgan bo'lishi kerak.",
        reply_markup=get_menu(),
    )


@dp.message(F.text == "📥 Yuklab olish")
async def ask_link(message: types.Message):
    await message.answer(
        "Instagram yoki YouTube havolasini yuboring."
    )


@dp.message(F.text)
async def receive_link(message: types.Message):
    url = message.text.strip()

    if not valid_url(url):
        await message.answer(
            "❌ To'g'ri Instagram yoki YouTube havolasini yuboring."
        )
        return

    host = (urlparse(url).hostname or "").lower()
    is_instagram = (
        host == "instagram.com"
        or host.endswith(".instagram.com")
    )
    is_youtube = (
        host == "youtube.com"
        or host.endswith(".youtube.com")
        or host == "youtu.be"
    )

    if is_instagram:
        # Instagram uchun odatiy post/Reels havolalari
        if not any(x in url for x in (
            "/reel/", "/reels/", "/p/", "/tv/"
        )):
            await message.answer(
                "❌ Instagram post yoki Reels havolasini yuboring."
            )
            return

        kb = InlineKeyboardBuilder()
        kb.button(
            text="🎬 Video MP4",
            callback_data="ig_video",
        )
        kb.button(
            text="🎧 Audio MP3",
            callback_data="ig_audio",
        )
        kb.adjust(1)

        user_urls[message.from_user.id] = url

        await message.answer(
            "Instagram havolasi qabul qilindi. Formatni tanlang:",
            reply_markup=kb.as_markup(),
        )

    elif is_youtube:
        kb = InlineKeyboardBuilder()
        kb.button(
            text="🎵 Qo'shiq MP3",
            callback_data="yt_audio",
        )

        user_urls[message.from_user.id] = url

        await message.answer(
            "YouTube havolasi qabul qilindi:",
            reply_markup=kb.as_markup(),
        )


async def process_job(
    callback: types.CallbackQuery,
    mode: str,
):
    url = user_urls.get(callback.from_user.id)

    if not url:
        await callback.answer(
            "Havola topilmadi. Uni qayta yuboring.",
            show_alert=True,
        )
        return

    await callback.answer()

    status = await callback.message.answer(
        "⏳ Yuklanmoqda, iltimos kuting..."
    )

    folder = tempfile.mkdtemp(prefix="media_")
    files = []

    try:
        files, title = await asyncio.to_thread(
            download_media, url, mode, folder
        )

        sent = 0

        for path in files:
            if path.stat().st_size > MAX_SIZE:
                continue

            with path.open("rb") as f:
                if mode == "video":
                    await callback.message.answer_video(
                        f,
                        caption=f"🎬 {title[:900]}",
                        supports_streaming=True,
                    )
                else:
                    await callback.message.answer_audio(
                        f,
                        title=title[:900],
                        caption="🎵 MP3",
                    )

            sent += 1

        if sent:
            await status.edit_text(
                f"✅ Tayyor! {sent} ta fayl yuborildi."
            )
        else:
            await status.edit_text(
                "❌ Fayl juda katta yoki Telegram yubora olmadi."
            )

    except Exception as e:
        logger.exception("Yuklash xatosi: %s", e)
        await status.edit_text(
            "❌ Yuklab bo'lmadi.\n\n"
            "Havola ochiq ekanini tekshiring. "
            "Instagram cheklovi, eski yt-dlp yoki "
            "FFmpeg yo'qligi sabab bo'lishi mumkin."
        )

    finally:
        shutil.rmtree(folder, ignore_errors=True)


@dp.callback_query(F.data == "ig_video")
async def instagram_video(callback: types.CallbackQuery):
    url = user_urls.get(callback.from_user.id, "")
    if not url or "instagram.com" not in url:
        await callback.answer(
            "Instagram havolasini qayta yuboring.",
            show_alert=True,
        )
        return

    await process_job(callback, "video")


@dp.callback_query(F.data == "ig_audio")
async def instagram_audio(callback: types.CallbackQuery):
    url = user_urls.get(callback.from_user.id, "")
    if not url or "instagram.com" not in url:
        await callback.answer(
            "Instagram havolasini qayta yuboring.",
            show_alert=True,
        )
        return

    await process_job(callback, "audio")


@dp.callback_query(F.data == "yt_audio")
async def youtube_audio(callback: types.CallbackQuery):
    url = user_urls.get(callback.from_user.id, "")
    host = (urlparse(url).hostname or "").lower()

    if not url or not (
        host == "youtube.com"
        or host.endswith(".youtube.com")
        or host == "youtu.be"
    ):
        await callback.answer(
            "YouTube havolasini qayta yuboring.",
            show_alert=True,
        )
        return

    await process_job(callback, "audio")


async def main():
    keep_alive()
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())


