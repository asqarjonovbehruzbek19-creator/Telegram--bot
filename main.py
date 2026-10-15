import os
import asyncio
import logging
import tempfile
import shutil
from pathlib import Path
from urllib.parse import urlparse
from threading import Thread

import yt_dlp
import aiohttp
from flask import Flask
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import (
    ReplyKeyboardBuilder,
    InlineKeyboardBuilder,
)

TOKEN = "8876050592:AAGm3o9VuHG58deU0nmyhCwABSdV4-XlTMc"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN)
dp = Dispatcher()

app = Flask(__name__)

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
        instagram = host == "instagram.com" or host.endswith(".instagram.com")
        youtube = host == "youtube.com" or host.endswith(".youtube.com") or host == "youtu.be"
        return p.scheme in ("https", "http") and (instagram or youtube)
    except Exception:
        return False


def get_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="📥 Yuklab olish")
    kb.button(text="ℹ️ Bot haqida")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)


def download_youtube(url, mode, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    opts = {
        "outtmpl": str(folder / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "restrictfilenames": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 5,
        "socket_timeout": 60,
        "max_filesize": MAX_SIZE,
    }

    if mode == "video":
        opts["format"] = "best[ext=mp4]/best"
    else:
        opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

    if not info:
        raise RuntimeError("Media topilmadi.")

    files = [p for p in folder.iterdir() if p.is_file()]
    files = sorted(files, key=lambda p: p.stat().st_mtime)

    if not files:
        raise RuntimeError("Yuklangan fayl topilmadi.")

    return files, info.get("title", "YouTube Video")


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "👋 Assalomu alaykum!\n\n"
        "📸 Instagram videosi va audiosi\n"
        "🎵 YouTube videolari va qo'shiqlarini yuklash\n\n"
        "Havolani yuboring, keyin kerakli formatni tanlang.",
        reply_markup=get_menu(),
    )


@dp.message(F.text == "ℹ️ Bot haqida")
async def about(message: types.Message):
    await message.answer(
        "📥 Instagram va YouTube media fayllarini yuklab beruvchi tezkor bot.\n\n"
        "Bot 24/7 rejimida ishlaydi.",
        reply_markup=get_menu(),
    )


@dp.message(F.text == "📥 Yuklab olish")
async def ask_link(message: types.Message):
    await message.answer("Instagram yoki YouTube havolasini yuboring.")


@dp.message(F.text)
async def receive_link(message: types.Message):
    url = message.text.strip()

    if not valid_url(url):
        await message.answer("❌ To'g'ri Instagram yoki YouTube havolasini yuboring.")
        return

    host = (urlparse(url).hostname or "").lower()
    is_instagram = host == "instagram.com" or host.endswith(".instagram.com")
    is_youtube = host == "youtube.com" or host.endswith(".youtube.com") or host == "youtu.be"

    user_urls[message.from_user.id] = url

    if is_instagram:
        kb = InlineKeyboardBuilder()
        kb.button(text="🎬 Video MP4", callback_data="ig_video")
        kb.button(text="🎧 Audio", callback_data="ig_audio")
        kb.adjust(1)
        await message.answer("Instagram havolasi qabul qilindi. Formatni tanlang:", reply_markup=kb.as_markup())

    elif is_youtube:
        kb = InlineKeyboardBuilder()
        kb.button(text="🎬 Video MP4", callback_data="yt_video")
        kb.button(text="🎵 Qo'shiq / Audio", callback_data="yt_audio")
        kb.adjust(1)
        await message.answer("YouTube havolasi qabul qilindi. Formatni tanlang:", reply_markup=kb.as_markup())


async def process_instagram(callback: types.CallbackQuery, mode: str):
    url = user_urls.get(callback.from_user.id)
    if not url:
        await callback.answer("Havola topilmadi. Uni qayta yuboring.", show_alert=True)
        return

    await callback.answer()
    status = await callback.message.answer("⏳ Instagram'dan yuklanmoqda, iltimos kuting...")

    try:
        # Cobalt API orqali Instagram havolasini to'g'ridan-to'g'ri olish
        api_url = "https://co.wuk.sh/api/json"
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        payload = {"url": url, "vQuality": "720"}

        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, headers=headers) as resp:
                res_data = await resp.json()

        if res_data.get("status") in ("stream", "redirect", "picker"):
            if res_data.get("status") == "picker":
                download_url = res_data.get("picker")[0].get("url")
            else:
                download_url = res_data.get("url")

            if download_url:
                if mode == "video":
                    await callback.message.answer_video(download_url, caption="🎬 Instagram videosi")
                else:
                    await callback.message.answer_audio(download_url, caption="🎵 Instagram audiosi")
                await status.delete()
                return

        raise RuntimeError("API orqali olinmadi")

    except Exception:
        folder = tempfile.mkdtemp(prefix="insta_")
        try:
            opts = {
                "outtmpl": str(folder / "%(id)s.%(ext)s"),
                "noplaylist": True,
                "format": "best[ext=mp4]/best" if mode == "video" else "bestaudio/best",
                "quiet": True,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
            
            with open(filename, "rb") as f:
                if mode == "video":
                    await callback.message.answer_video(f, caption="🎬 Instagram videosi")
                else:
                    await callback.message.answer_audio(f, caption="🎵 Instagram audiosi")
            await status.delete()
            shutil.rmtree(folder, ignore_errors=True)
        except Exception as e:
            logger.exception("Instagram yuklash xatosi: %s", e)
            await status.edit_text("❌ Instagram videosini yuklab bo'lmadi. Havola ochiqligini tekshiring.")


async def process_youtube(callback: types.CallbackQuery, mode: str):
    url = user_urls.get(callback.from_user.id)
    if not url:
        await callback.answer("Havola topilmadi. Uni qayta yuboring.", show_alert=True)
        return

    await callback.answer()
    status = await callback.message.answer("⏳ YouTube'dan yuklanmoqda, iltimos kuting...")

    folder = tempfile.mkdtemp(prefix="youtube_")
    try:
        files, title = await asyncio.to_thread(download_youtube, url, mode, folder)
        for path in files:
            with path.open("rb") as f:
                if mode == "video":
                    await callback.message.answer_video(f, caption=f"🎬 {title[:900]}", supports_streaming=True)
                else:
                    await callback.message.answer_audio(f, title=title[:900], caption="🎵 YouTube Audio")
        await status.delete()
    except Exception as e:
        logger.exception("YouTube yuklash xatosi: %s", e)
        await status.edit_text("❌ YouTube'dan yuklab bo'lmadi.")
    finally:
        shutil.rmtree(folder, ignore_errors=True)


@dp.callback_query(F.data == "ig_video")
async def ig_vid(callback: types.CallbackQuery):
    await process_instagram(callback, "video")


@dp.callback_query(F.data == "ig_audio")
async def ig_aud(callback: types.CallbackQuery):
    await process_instagram(callback, "audio")


@dp.callback_query(F.data == "yt_video")
async def yt_vid(callback: types.CallbackQuery):
    await process_youtube(callback, "video")


@dp.callback_query(F.data == "yt_audio")
async def yt_aud(callback: types.CallbackQuery):
    await process_youtube(callback, "audio")


async def main():
    keep_alive()
    # Webhookni o'chirib tashlash (Xatolikni oldini olish uchun)
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())





