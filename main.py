# main.py
import os
import io
import logging
from threading import Thread
from flask import Flask
from PIL import Image
import pypdf
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# Logging sozlamalari
logging.basicConfig(level=logging.INFO)

# Telegram Bot Token (Render Environment Variables orqali berish tavsiya etiladi)
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Flask Keep-Alive Server
app = Flask(__name__)

@app.route('/')
def home():
    return "PDF Converter Bot is Alive!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# FSM holatlari (States)
class BotStates(StatesGroup):
    choosing_language = State()
    main_menu = State()
    collecting_images = State()
    merging_pdfs = State()
    splitting_pdf = State()
    encrypt_pdf_file = State()
    encrypt_pdf_pass = State()
    decrypt_pdf_file = State()
    decrypt_pdf_pass = State()

# Matnlar lug'ati (Uzbek, Russian, English)
TEXTS = {
    'uz': {
        'welcome': "👋 <b>Assalomu alaykum!</b>\n\nMen yuqori darajadagi <b>PDF Pro Bot</b>man. Kerakli xizmatni tanlang:",
        'lang_saved': "✅ Til muvaffaqiyatli tanlandi!",
        'btn_img2pdf': "🖼️ Rasmlarni PDF qilish",
        'btn_merge': "📑 PDF-larni birlashtirish",
        'btn_split': "✂️ PDF-ni bo'lish",
        'btn_encrypt': "🔐 PDF-ga parol qo'yish",
        'btn_decrypt': "🔓 Parolni olib tashlash",
        'btn_lang': "🌐 Tilni o'zgartirish",
        'send_images': "🖼️ Menga PDF-ga aylantirmoqchi bo'lgan rasmlaringizni birma-bir yuboring.\n\nTugatgach, <b>'🏁 PDF yaratish'</b> tugmasini bosing.",
        'btn_make_pdf': "🏁 PDF yaratish",
        'btn_back': "⬅️ Orqaga",
        'no_images': "⚠️ Siz hali birorta ham rasm yubormadingiz!",
        'converting': "⏳ PDF fayl tayyorlanmoqda, kuting...",
        'send_pdfs_merge': "📑 Birlashtirmoqchi bo'lgan PDF fayllaringizni yuboring (kamida 2 ta).\n\nTugatgach, <b>'🏁 Birlashtirish'</b> tugmasini bosing.",
        'btn_start_merge': "🏁 Birlashtirish",
        'need_at_least_2': "⚠️ Birlashtirish uchun kamida 2 ta PDF fayl yuborishingiz kerak!",
        'send_pdf_split': "✂️ Bo'lmoqchi bo'lgan PDF faylingizni yuboring:",
        'send_pdf_encrypt': "🔐 Parol qo'ymoqchi bo me'morchilingiz bo'lgan PDF faylni yuboring:",
        'send_pass_encrypt': "🔑 Endi ushbu PDF uchun maxfiy parol kiriting:",
        'send_pdf_decrypt': "🔓 Parolini olib tashlamoqchi bo'lgan PDF faylni yuboring:",
        'send_pass_decrypt': "🔑 Faylning amaldagi parolini kiriting:",
        'success_pdf': "🎉 Barchasi tayyor! Hujjatingiz yuklandi.",
        'error': "❌ Xatolik yuz berdi. Fayl formati yoki parol to'g'riligini munosib tekshiring.",
    },
    'ru': {
        'welcome': "👋 <b>Здравствуйте!</b>\n\nЯ продвинутый <b>PDF Pro Bot</b>. Выберите нужную услугу:",
        'lang_saved': "✅ Язык успешно выбран!",
        'btn_img2pdf': "🖼️ Изображения в PDF",
        'btn_merge': "📑 Объединить PDF",
        'btn_split': "✂️ Разделить PDF",
        'btn_encrypt': "🔐 Защитить PDF паролем",
        'btn_decrypt': "🔓 Снять пароль с PDF",
        'btn_lang': "🌐 Сменить язык",
        'send_images': "🖼️ Отправляйте изображения по одному.\n\nКогда закончите, нажмите <b>'🏁 Создать PDF'</b>.",
        'btn_make_pdf': "🏁 Создать PDF",
        'btn_back': "⬅️ Назад",
        'no_images': "⚠️ Вы еще не отправили ни одного изображения!",
        'converting': "⏳ Генерируется PDF файл, подождите...",
        'send_pdfs_merge': "📑 Отправьте PDF файлы для объединения (минимум 2).\n\nЗатем нажмите <b>'🏁 Объединить'</b>.",
        'btn_start_merge': "🏁 Объединить",
        'need_at_least_2': "⚠️ Нужно отправить как минимум 2 PDF файла!",
        'send_pdf_split': "✂️ Отправьте PDF файл, который хотите разделить:",
        'send_pdf_encrypt': "🔐 Отправьте PDF файл для установки пароля:",
        'send_pass_encrypt': "🔑 Введите пароль для этого PDF:",
        'send_pdf_decrypt': "🔓 Отправьте защищенный PDF файл:",
        'send_pass_decrypt': "🔑 Введите текущий пароль от файла:",
        'success_pdf': "🎉 Готово! Ваш документ сгенерирован.",
        'error': "❌ Произошла ошибка. Проверьте формат файла или пароль.",
    },
    'en': {
        'welcome': "👋 <b>Hello!</b>\n\nI am advanced <b>PDF Pro Bot</b>. Choose a service:",
        'lang_saved': "✅ Language selected successfully!",
        'btn_img2pdf': "🖼️ Images to PDF",
        'btn_merge': "📑 Merge PDFs",
        'btn_split': "✂️ Split PDF",
        'btn_encrypt': "🔐 Encrypt PDF",
        'btn_decrypt': "🔓 Decrypt PDF",
        'btn_lang': "🌐 Change Language",
        'send_images': "🖼️ Send your images one by one.\n\nWhen finished, press <b>'🏁 Generate PDF'</b>.",
        'btn_make_pdf': "🏁 Generate PDF",
        'btn_back': "⬅️ Back",
        'no_images': "⚠️ You haven't sent any images yet!",
        'converting': "⏳ Generating PDF file, please wait...",
        'send_pdfs_merge': "📑 Send PDF files to merge (at least 2).\n\nThen press <b>'🏁 Merge'</b>.",
        'btn_start_merge': "🏁 Merge",
        'need_at_least_2': "⚠️ You need to send at least 2 PDF files!",
        'send_pdf_split': "✂️ Send the PDF file you want to split:",
        'send_pdf_encrypt': "🔐 Send the PDF file you want to password protect:",
        'send_pass_encrypt': "🔑 Enter the password for this PDF:",
        'send_pdf_decrypt': "🔓 Send the encrypted PDF file:",
        'send_pass_decrypt': "🔑 Enter the current password:",
        'success_pdf': "🎉 All done! Your document is ready.",
        'error': "❌ An error occurred. Check file format or password.",
    }
}

def get_main_keyboard(lang):
    t = TEXTS[lang]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton(t['btn_img2pdf']),
        types.KeyboardButton(t['btn_merge']),
        types.KeyboardButton(t['btn_split']),
        types.KeyboardButton(t['btn_encrypt']),
        types.KeyboardButton(t['btn_decrypt']),
        types.KeyboardButton(t['btn_lang'])
    )
    return kb

@dp.message_handler(commands=['start'], state='*')
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="lang_uz"),
        types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    )
    await message.answer("🌐 Select Language / Tilni tanlang / Выберите язык:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('lang_'), state='*')
async def process_language(callback: types.CallbackQuery, state: FSMContext):
    lang = callback.data.split('_')[1]
    await state.update_data(lang=lang)
    await callback.message.delete()
    await callback.message.answer(TEXTS[lang]['welcome'], reply_markup=get_main_keyboard(lang), parse_mode="HTML")
    await BotStates.main_menu.set()

# 🖼️ Images to PDF
@dp.message_handler(lambda m: any(m.text == TEXTS[l]['btn_img2pdf'] for l in TEXTS), state=BotStates.main_menu)
async def start_img2pdf(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'uz')
    await state.update_data(images=[])
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton(TEXTS[lang]['btn_make_pdf']))
    kb.add(types.KeyboardButton(TEXTS[lang]['btn_back']))
    
    await message.answer(TEXTS[lang]['send_images'], reply_markup=kb, parse_mode="HTML")
    await BotStates.collecting_images.set()

@dp.message_handler(content_types=['photo'], state=BotStates.collecting_images)
async def process_image(message: types.Message, state: FSMContext):
    data = await state.get_data()
    images = data.get('images', [])
    photo = message.photo[-1]
    file_info = await bot.get_file(photo.file_id)
    downloaded_file = await bot.download_file(file_info.file_path)
    images.append(downloaded_file.read())
    await state.update_data(images=images)
    await message.reply(f"📸 Image #{len(images)} saved!")

@dp.message_handler(lambda m: any(m.text == TEXTS[l]['btn_make_pdf'] for l in TEXTS), state=BotStates.collecting_images)
async def generate_pdf_from_imgs(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'uz')
    images = data.get('images', [])
    
    if not images:
        await message.answer(TEXTS[lang]['no_images'])
        return
        
    await message.answer(TEXTS[lang]['converting'])
    
    pil_images = []
    for img_bytes in images:
        img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        pil_images.append(img)
        
    output = io.BytesIO()
    pil_images[0].save(output, format='PDF', save_all=True, append_images=pil_images[1:])
    output.seek(0)
    
    await message.answer_document(types.InputFile(output, filename="images_document.pdf"), caption=TEXTS[lang]['success_pdf'])
    await message.answer(TEXTS[lang]['welcome'], reply_markup=get_main_keyboard(lang), parse_mode="HTML")
    await BotStates.main_menu.set()

# Back Button Handler
@dp.message_handler(lambda m: any(m.text == TEXTS[l]['btn_back'] for l in TEXTS), state='*')
async def go_back(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'uz')
    await message.answer(TEXTS[lang]['welcome'], reply_markup=get_main_keyboard(lang), parse_mode="HTML")
    await BotStates.main_menu.set()

if __name__ == '__main__':
    # Flask serverni parallel tarmoqda ishga tushirish
    server_thread = Thread(target=run_flask)
    server_thread.daemon = True
    server_thread.start()
    
    # Telegram Bot Polling
    executor.start_polling(dp, skip_updates=True)











