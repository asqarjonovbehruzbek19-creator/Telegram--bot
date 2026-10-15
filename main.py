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

# --- RENDER UCHUN FLASK SERVER (PORT MUAMMOSINI HAL QILADI) ---
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
# -------------------------------------------------------------

def download_video(url):
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'restrictfilenames': True,
    }
    os.makedirs('downloads', exist_ok=True)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename, info.get('title', 'Video')

def download_audio(url_or_query):
    if not url_or_query.startswith("http"):
        search_query = f"ytsearch1:{url_or_query}"
    else:
        search_query = url_or_query

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'restrictfilenames': True,
        'default_search': 'auto',
    }
    os.makedirs('downloads', exist_ok=True)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(search_query, download=True)
        if 'entries' in info:
            info = info['entries'][0]
        filename = ydl.prepare_filename(info)
        audio_file = os.path.splitext(filename)[0] + '.mp3'
        return audio_file, info.get('title', 'Musiqa')

def search_songs(query):
    ydl_opts = {
        'extract_flat': True,
        'default_search': 'ytsearch10',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        return info.get('entries', [])

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        "Salom! Menga YouTube havolasini yuboring yoki shunchaki qo'shiq nomini yozing. 🎵"
    )

@dp.message(F.text)
async def handle_text(message: types.Message):
    text = message.text.strip()
    
    if text.startswith("http"):
        builder = InlineKeyboardBuilder()
        builder.button(text="🎬 Videoni yuklash", callback_data=f"vid|{text}")
        builder.button(text="🎵 Qo'shiqni yuklash", callback_data=f"aud|{text}")
        builder.adjust(1)
        await message.answer("Yuklab olish turini tanlang:", reply_markup=builder.as_markup())
    else:
        status_msg = await message.answer("Qidirilmoqda...")
        try:
            results = search_songs(f"ytsearch10:{text}")
            if not results:
                await bot.edit_message_text("Hech narsa topilmadi.", chat_id=message.chat.id, message_id=status_msg.message_id)
                return

            response_text = f"'{text}' bo'yicha topilgan variantlar:\n\n"
            builder = InlineKeyboardBuilder()

            for idx, entry in enumerate(results, start=1):
                title = entry.get('title', 'Nomaʼlum')
                video_id = entry.get('id')
                response_text += f"{idx}. {title}\n"
                builder.button(text=str(idx), callback_data=f"dl|{video_id}")

            builder.adjust(5, 5)
            await bot.edit_message_text(
                response_text,
                chat_id=message.chat.id,
                message_id=status_msg.message_id,
                reply_markup=builder.as_markup()
            )
        except Exception as e:
            await bot.edit_message_text(f"Xatolik: {e}", chat_id=message.chat.id, message_id=status_msg.message_id)

@dp.callback_query(F.data.startswith("vid|") | F.data.startswith("aud|") | F.data.startswith("dl|"))
async def process_download(callback: types.CallbackQuery):
    data_parts = callback.data.split("|", 1)
    action = data_parts[0]
    target = data_parts[1]
    
    await callback.message.edit_text("Yuklab olinmoqda...")

    try:
        if action == "vid":
            file_path, title = download_video(target)
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
                
        elif action == "dl":
            url = f"https://www.youtube.com/watch?v={target}"
            file_path, title = download_audio(url)
            with open(file_path, 'rb') as audio:
                await callback.message.answer_audio(audio, caption=f"🎧 {title}")
            await callback.message.delete()
            if os.path.exists(file_path):
                os.remove(file_path)
                
    except Exception as e:
        await callback.message.edit_text(f"Xatolik yuz berdi: {e}")

async def main():
    keep_alive()  # Flask serverni ishga tushiradi
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

