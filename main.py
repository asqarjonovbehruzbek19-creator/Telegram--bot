import os
import asyncio
import logging
import aiohttp
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
    return "Bot is running fast!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()
# ---------------------------------

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="🇺🇿 O'zbek tili", callback_data="lang_uz")
    builder.adjust(1)
    
    await message.answer(
        "Assalomu alaykum! Botimizga xush kelibsiz.\nIltimos, tilni tanlang:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "lang_uz")
async def set_language(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🇺🇿 Til o'zbek tiliga o'zgartirildi!\n\n"
        "⚡ Menga **YouTube**, **Instagram** yoki **TikTok** havolasini yuboring, bir necha soniyada yuklab beraman!"
    )

@dp.message(F.text)
async def handle_text(message: types.Message):
    text = message.text.strip()
    
    if text.startswith("http"):
        if any(domain in text for domain in ["youtube.com", "youtu.be", "instagram.com", "tiktok.com"]):
            msg = await message.answer("⚡ Tezkor yuklab olinmoqda...")
            
            try:
                # Ochiq va bepul Cobalt API orqali tezkor yuklab olish
                api_url = "https://co.wuk.sh/api/json"
                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
                payload = {
                    "url": text,
                    "vQuality": "720"
                }

                async with aiohttp.ClientSession() as session:
                    async with session.post(api_url, json=payload, headers=headers) as resp:
                        res_data = await resp.json()

                if res_data.get("status") == "stream" or res_data.get("status") == "redirect":
                    download_url = res_data.get("url")
                    
                    builder = InlineKeyboardBuilder()
                    builder.button(text="📥 Videoni yuklab olish", url=download_url)
                    builder.adjust(1)
                    
                    await bot.edit_message_text(
                        "✅ Video muvaffaqiyatli tayyorlandi!",
                        chat_id=message.chat.id,
                        message_id=msg.message_id,
                        reply_markup=builder.as_markup()
                    )
                else:
                    await bot.edit_message_text(
                        "❌ Kechirasiz, bu havoladan video olib bo'lmadi. Boshqa havola yuborib ko'ring.",
                        chat_id=message.chat.id,
                        message_id=msg.message_id
                    )
            except Exception as e:
                await bot.edit_message_text(
                    f"❌ Xatolik yuz berdi: {e}",
                    chat_id=message.chat.id,
                    message_id=msg.message_id
                )
        else:
            await message.answer("⚠️ Iltimos, faqat YouTube, Instagram yoki TikTok havolasini yuboring! 🔗")
    else:
        await message.answer("⚠️ Iltimos, to'g'ridan-to'g'ri havola yuboring! 🔗")

async def main():
    keep_alive()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())



