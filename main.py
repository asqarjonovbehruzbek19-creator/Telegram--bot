import os
import asyncio
import logging
import yt_dlp
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

TOKEN = "8876050592:AAFItuCq50hD9kf6vUFXDOP-VHQvapHRZuE"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- RENDER UCHUN FLASK SERVER ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()
# ---------------------------------

def download_media(url):
    ydl_opts = {
        'format': 'best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'restrictfilenames': True,
    }
    os.makedirs('downloads', exist_ok=True)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename, info.get('title', 'Media')

def download_audio(url):
    ydl_opts = {
        'format': 'bestaudio',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'restrictfilenames': True,
    }
    os.makedirs('downloads', exist_ok=True)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename, info.get('title', 'Musiqa')

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="🇺🇿 O'zbek tili", callback_data="lang_uz")
    builder.adjust(1)
    
    await message.answer(
        "Assalomu alaykum! Botimizga xush kelibsiz.\nIltimos, tilni tanlang:\n\n"
        "Здравствуйте! Добро пожаловать.\nПожалуйста, выберите язык:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "lang_uz")
async def set_language(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🇺🇿 Til o'zbek tiliga o'zgartirildi!\n\n"
        "Menga **YouTube**, **Instagram** yoki **TikTok** havolasini yuboring, men uni darhol yuklab beraman! 🎬📥"
    )

@dp.message(F.text)
async def handle_text(message: types.Message):
    text = message.text.strip()
    
    if text.startswith("http"):
        if "instagram.com" in text or "tiktok.com" in text:
            # Instagram yoki TikTok bo'sh to'g'ridan-to'g'ri yuklash tugmasi
            builder = InlineKeyboardBuilder()
            builder.button(text="📥 Yuklab olish", callback_data=f"instatiktok|{text}")
            builder.adjust(1)
            await message.answer("📥 Videoni yuklab olish uchun bosing:", reply_markup=builder.as_markup())
        else:
            # YouTube uchun video va audio tanlash
            builder = InlineKeyboardBuilder()
            builder.button(text="🎬 Videoni yuklash", callback_data=f"vid|{text}")
            builder.button(text="🎵 Musiqani yuklash", callback_data=f"aud|{text}")
            builder.adjust(1)
            await message.answer("📥 Yuklab olish turini tanlang:", reply_markup=builder.as_markup())
    else:
        await message.answer("⚠️ Iltimos, to'g'ridan-to'g'ri havola (link) yuboring! 🔗")

@dp.callback_query(F.data.startswith("vid|") | F.data.startswith("aud|") | F.data.startswith("instatiktok|"))
async def process_download(callback: types.CallbackQuery):
    data_parts = callback.data.split("|", 1)
    action = data_parts[0]
    target = data_parts[1]
    
    await callback.message.edit_text("⏳ Yuklab olinmoqda, iltimos kuting...")

    try:
        if action == "vid" or action == "instatiktok":
            file_path, title = download_media(target)
            with open(file_path, 'rb') as video:
                await callback.message.answer_video(video, caption=f"🎬 {title}")
            await callback.message.delete()
            if os.path.exists(file_path):
                os.remove(file_path)
                
        elif action == "aud":
            file_path, title = download_audio(target)
            with open(file_path, 'rb') as audio:
                await callback.message.answer_audio(audio, caption=f"🎧 {title}")
            await callback.message.delete()
            if os.path.exists(file_path):
                os.remove(file_path)
                
    except Exception as e:
        await callback.message.edit_text(f"❌ Xatolik yuz berdi: {e}")

async def main():
    keep_alive()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


