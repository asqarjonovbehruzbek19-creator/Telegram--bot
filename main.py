import os
import asyncio
import logging
import yt_dlp
import aiohttp
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

TOKEN = "8876050592:AAFItuCq50hD9kf6vUFXDOP-VHQvapHRZuE"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- RENDER UCHUN FLASK SERVER ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running perfectly and ready!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()
# ---------------------------------

def download_video(url):
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'restrictfilenames': True,
    }
    os.makedirs('downloads', exist_ok=True)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename, info.get('title', 'Video')

def download_audio(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'restrictfilenames': True,
    }
    os.makedirs('downloads', exist_ok=True)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        audio_file = os.path.splitext(filename)[0] + '.mp3'
        return audio_file, info.get('title', 'Musiqa')

def get_main_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text="📥 Yuklab olish")
    builder.button(text="ℹ️ Bot haqida")
    builder.button(text="🇺🇿 Til: O'zbekcha")
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    welcome_text = (
        "🌟 **Assalomu alaykum va rahmatulloh!**\n\n"
        "Xush kelibsiz! Bu bot orqali siz **YouTube** (video va MP3) hamda **Instagram** (reels, video) havolalarini mutlaqo bepul yuklab olishingiz mumkin. 🎬🎵\n\n"
        "👇 Boshlash uchun quyidagi tugmani bosing yoki to'g'ridan-to'g'ri havola yuboring!"
    )
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=get_main_menu())

@dp.message(F.text == "ℹ️ Bot haqida")
async def about_bot(message: types.Message):
    await message.answer(
        "ℹ️ **Bot haqida ma'lumot:**\n\n"
        "• YouTube va Instagram tarmoqlaridan kontentlarni tezkor yuklaydi.\n"
        "• 24/7 rejimida uzluksiz ishlaydi.",
        parse_mode="Markdown",
        reply_markup=get_main_menu()
    )

@dp.message(F.text == "🇺🇿 Til: O'zbekcha")
async def lang_settings(message: types.Message):
    await message.answer(
        "🇺🇿 Siz allaqachon mukammal **O'zbek tilidasiz!** Barcha xizmatlar o'zbek tilida ko'rsatiladi.",
        reply_markup=get_main_menu()
    )

@dp.message(F.text == "📥 Yuklab olish")
async def ask_link(message: types.Message):
    await message.answer(
        "🔗 Marhamat, menga **YouTube** yoki **Instagram** havolasini yuboring:",
        reply_markup=get_main_menu()
    )

@dp.message(F.text)
async def handle_text(message: types.Message):
    text = message.text.strip()
    
    if text.startswith("http"):
        if "youtube.com" in text or "youtu.be" in text:
            builder = InlineKeyboardBuilder()
            builder.button(text="🎬 Videoni yuklash (MP4)", callback_data=f"vid|{text}")
            builder.button(text="🎵 Musiqani yuklash (MP3)", callback_data=f"aud|{text}")
            builder.adjust(1)
            
            await message.answer(
                "🎯 **YouTube havolasi qabul qilindi!**\nQaysi formatda yuklab olmoqchisiz?",
                parse_mode="Markdown",
                reply_markup=builder.as_markup()
            )
        elif "instagram.com" in text:
            status_msg = await message.answer("⏳ **Instagram videosi yuklab olinmoqda...**", parse_mode="Markdown")
            try:
                # Instagram uchun barqaror API orqali to'g'ridan-to'g'ri video linkini olish
                api_url = f"https://api.vkrp.xyz/api/v1/insta?url={text}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(api_url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            video_url = data.get("data") or data.get("url")
                            if video_url:
                                await message.answer_video(video_url, caption="🎬 **Instagram'dan yuklab olindi!**", parse_mode="Markdown")
                                await status_msg.delete()
                                return
                
                # Zaxira usul: agar birinchi API ishlamasa, ikkinchi usul orqali urinib ko'ramiz
                fallback_opts = {'format': 'best', 'outtmpl': 'downloads/%(id)s.%(ext)s', 'restrictfilenames': True}
                os.makedirs('downloads', exist_ok=True)
                with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                    info = ydl.extract_info(text, download=True)
                    f_path = ydl.prepare_filename(info)
                    with open(f_path, 'rb') as v_file:
                        await message.answer_video(v_file, caption="🎬 **Instagram'dan yuklab olindi!**", parse_mode="Markdown")
                    await status_msg.delete()
                    if os.path.exists(f_path):
                        os.remove(f_path)
            except Exception as e:
                await status_msg.edit_text(f"❌ **Instagram videosini yuklab bo'lmadiki:** Havola noto'g'ri yoki yopiq sahifaga tegishli bo'lishi mumkin.", parse_mode="Markdown")
        else:
            await message.answer(
                "⚠️ Hozircha faqat **YouTube** va **Instagram** havolalari qo'llab-quvvatlanadi! 🔗",
                reply_markup=get_main_menu()
            )
    else:
        await message.answer(
            "⚠️ Iltimos, to'g'ri havola yuboring yoki pastdagi menyulardan foydalaning! 🔗",
            reply_markup=get_main_menu()
        )

@dp.callback_query(F.data.startswith("vid|") | F.data.startswith("aud|"))
async def process_download(callback: types.CallbackQuery):
    data_parts = callback.data.split("|", 1)
    action = data_parts[0]
    target = data_parts[1]
    
    status_msg = await callback.message.edit_text("⚡ **Yuklab olinmoqda, iltimos biroz kuting...** ⏳", parse_mode="Markdown")

    try:
        if action == "vid":
            file_path, title = await asyncio.to_thread(download_video, target)
            with open(file_path, 'rb') as video:
                await callback.message.answer_video(video, caption=f"🎬 <b>{title}</b>", parse_mode="HTML")
            await status_msg.delete()
            if os.path.exists(file_path):
                os.remove(file_path)
                
        elif action == "aud":
            file_path, title = await asyncio.to_thread(download_audio, target)
            with open(file_path, 'rb') as audio:
                await callback.message.answer_audio(audio, caption=f"🎧 <b>{title}</b>", parse_mode="HTML")
            await status_msg.delete()
            if os.path.exists(file_path):
                os.remove(file_path)
                
    except Exception as e:
        await status_msg.edit_text(f"❌ **Xatolik yuz berdi:** {e}", parse_mode="Markdown")

async def main():
    keep_alive()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())





