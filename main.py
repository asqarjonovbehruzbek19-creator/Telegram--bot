import os
import asyncio
import logging
import tempfile
import shutil
from pathlib import Path
from threading import Thread

import aiohttp
from flask import Flask
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from PIL import Image

TOKEN = "8820793134:AAFqXcnF5Xk_KxHK-3qPx3-y59amLGeUAGQ"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN)
dp = Dispatcher()

app = Flask(__name__)

# Foydalanuvchi ma'lumotlari: tili va rasmlari
user_languages = {}
user_images = {}

# --- LUG'ATLAR (Tarjimalar) ---
LANGS = {
    "uz": {
        "welcome": "👋 Assalomu alaykum!\n\n📸 Men yuborgan rasmlaringizni bitta **PDF** hujjatiga jamlab beruvchi botman.\n\nTilni tanlang:",
        "about": "📄 **PDF Maker Bot**\n\nBir nechta rasmlarni yuborib, ulardan tezda sifatli PDF fayl hosil qiling.",
        "btn_create": "📄 PDF yaratish",
        "btn_lang": "🌍 Tilni o'zgartirish",
        "btn_about": "ℹ️ Bot haqida",
        "ask_lang": "Tilni tanlang / Выберите язык / Choose language:",
        "lang_changed": "✅ Til O'zbek tiliga o'zgartirildi!",
        "start_pdf": "📷 Rasmlarni birma-bir yoki guruhlab yuboring.\n\nBarcha rasmlarni yuborib bo'lgach, tugmani bosing:",
        "btn_finish": "✅ PDF yaratishni yakunlash",
        "photo_saved": "✅ Rasm qabul qilindi! Jami rasmlar: {count} ta.\n\nYana rasm yuborishingiz yoki tugmani bosishingiz mumkin:",
        "no_photos": "❌ Hali hech qanday rasm yubormadingiz!",
        "processing": "⏳ Rasmlar PDF formatiga o'tkazilmoqda, iltimos kuting...",
        "success": "📄 Mana sizning PDF hujjatingiz!",
        "error": "❌ PDF yaratishda xatolik yuz berdi. Qaytadan urinib ko'ring."
    },
    "ru": {
        "welcome": "👋 Здравствуйте!\n\n📸 Я бот, который объединяет ваши фотографии в один документ **PDF**.\n\nВыберите язык:",
        "about": "📄 **PDF Maker Bot**\n\nОтправляйте фотографии и быстро создавайте качественные PDF файлы.",
        "btn_create": "📄 Создать PDF",
        "btn_lang": "🌍 Изменить язык",
        "btn_about": "ℹ️ О боте",
        "ask_lang": "Выберите язык / Choose language / Tilni tanlang:",
        "lang_changed": "✅ Язык изменен на русский!",
        "start_pdf": "📷 Отправляйте фотографии по одной или альбомом.\n\nПосле отправки всех фото нажмите кнопку:",
        "btn_finish": "✅ Завершить создание PDF",
        "photo_saved": "✅ Фото принято! Всего фото: {count}.\n\nМожете отправить еще или нажать кнопку:",
        "no_photos": "❌ Вы еще не отправили ни одной фотографии!",
        "processing": "⏳ Фотографии конвертируются в PDF, пожалуйста, подождите...",
        "success": "📄 Вот ваш PDF документ!",
        "error": "❌ Произошла ошибка при создании PDF. Попробуйте еще раз."
    },
    "en": {
        "welcome": "👋 Hello!\n\n📸 I am a bot that converts your sent images into a single **PDF** document.\n\nChoose your language:",
        "about": "📄 **PDF Maker Bot**\n\nSend multiple images and quickly generate high-quality PDF files.",
        "btn_create": "📄 Create PDF",
        "btn_lang": "🌍 Change Language",
        "btn_about": "ℹ️ About Bot",
        "ask_lang": "Choose language / Tilni tanlang / Выберите язык:",
        "lang_changed": "✅ Language changed to English!",
        "start_pdf": "📷 Send photos one by one or as an album.\n\nAfter sending all photos, click the button below:",
        "btn_finish": "✅ Finish and Create PDF",
        "photo_saved": "✅ Photo accepted! Total photos: {count}.\n\nYou can send more or click the button:",
        "no_photos": "❌ You haven't sent any photos yet!",
        "processing": "⏳ Converting images to PDF, please wait...",
        "success": "📄 Here is your PDF document!",
        "error": "❌ An error occurred while creating PDF. Please try again."
    }
}

def get_text(user_id, key, **kwargs):
    lang = user_languages.get(user_id, "uz")
    text = LANGS.get(lang, LANGS["uz"]).get(key, key)
    return text.format(**kwargs)

def get_menu(user_id):
    kb = ReplyKeyboardBuilder()
    kb.button(text=get_text(user_id, "btn_create"))
    kb.button(text=get_text(user_id, "btn_lang"))
    kb.button(text=get_text(user_id, "btn_about"))
    kb.adjust(2, 1)
    return kb.as_markup(resize_keyboard=True)

def get_lang_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="🇺🇿 O'zbekcha", callback_data="lang_uz")
    kb.button(text="🇷🇺 Русский", callback_data="lang_ru")
    kb.button(text="🇬🇧 English", callback_data="lang_en")
    kb.adjust(3)
    return kb.as_markup()


@app.route("/")
def home():
    return "Multilingual PDF Bot ishlayapti!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    Thread(target=run_flask, daemon=True).start()


@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_languages:
        user_languages[user_id] = "uz" # Standart til
    
    await message.answer(
        get_text(user_id, "welcome"),
        reply_markup=get_lang_keyboard()
    )
    await message.answer("Menu:", reply_markup=get_menu(user_id))


@dp.callback_query(F.data.startswith("lang_"))
async def change_language(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    new_lang = callback.data.split("_")[1]
    user_languages[user_id] = new_lang
    
    await callback.answer(get_text(user_id, "lang_changed"), show_alert=True)
    await callback.message.edit_text(
        get_text(user_id, "welcome"),
        reply_markup=get_lang_keyboard()
    )
    # Menuni yangi tilda yangilash uchun xabar yuboramiz
    await callback.message.answer("Menu:", reply_markup=get_menu(user_id))


@dp.message(F.text.in_(["🌍 Tilni o'zgartirish", "🌍 Изменить язык", "🌍 Change Language"]))
async def ask_language_cmd(message: types.Message):
    user_id = message.from_user.id
    await message.answer(get_text(user_id, "ask_lang"), reply_markup=get_lang_keyboard())


@dp.message(F.text.in_(["ℹ️ Bot haqida", "ℹ️ О боте", "ℹ️ About Bot"]))
async def about(message: types.Message):
    user_id = message.from_user.id
    await message.answer(get_text(user_id, "about"), reply_markup=get_menu(user_id))


@dp.message(F.text.in_(["📄 PDF yaratish", "📄 Создать PDF", "📄 Create PDF"]))
async def start_pdf_process(message: types.Message):
    user_id = message.from_user.id
    user_images[user_id] = []
    
    kb = InlineKeyboardBuilder()
    kb.button(text=get_text(user_id, "btn_finish"), callback_data="generate_pdf")
    kb.adjust(1)
    
    await message.answer(
        get_text(user_id, "start_pdf"),
        reply_markup=kb.as_markup()
    )


@dp.message(F.photo)
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_images:
        user_images[user_id] = []

    photo = message.photo[-1]
    file_info = await bot.get_file(photo.file_id)
    
    folder = Path(tempfile.gettempdir()) / f"pdf_bot_{user_id}"
    folder.mkdir(parents=True, exist_ok=True)
    
    file_path = folder / f"{photo.file_unique_id}.jpg"
    await bot.download_file(file_info.file_path, destination=file_path)
    
    user_images[user_id].append(str(file_path))

    kb = InlineKeyboardBuilder()
    kb.button(text=get_text(user_id, "btn_finish"), callback_data="generate_pdf")
    kb.adjust(1)

    count = len(user_images[user_id])
    await message.answer(
        get_text(user_id, "photo_saved", count=count),
        reply_markup=kb.as_markup()
    )


@dp.callback_query(F.data == "generate_pdf")
async def generate_pdf(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    images = user_images.get(user_id, [])

    if not images:
        await callback.answer(get_text(user_id, "no_photos"), show_alert=True)
        return

    await callback.answer()
    status_msg = await callback.message.answer(get_text(user_id, "processing"))

    try:
        pdf_path = Path(tempfile.gettempdir()) / f"document_{user_id}.pdf"
        
        pil_images = []
        for img_path in images:
            img = Image.open(img_path)
            if img.mode != "RGB":
                img = img.convert("RGB")
            pil_images.append(img)

        if pil_images:
            pil_images[0].save(
                pdf_path,
                "PDF",
                save_all=True,
                append_images=pil_images[1:]
            )

        document = types.FSInputFile(pdf_path, filename="Document.pdf")
        await callback.message.answer_document(document, caption=get_text(user_id, "success"))
        await status_msg.delete()

    except Exception as e:
        logger.exception("PDF yaratishda xatolik: %s", e)
        await status_msg.edit_text(get_text(user_id, "error"))
    finally:
        user_images[user_id] = []
        shutil.rmtree(Path(tempfile.gettempdir()) / f"pdf_bot_{user_id}", ignore_errors=True)


async def main():
    keep_alive()
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass
    
    await asyncio.sleep(2)
    
    try:
        await dp.start_polling(bot, handle_signals=False)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")








