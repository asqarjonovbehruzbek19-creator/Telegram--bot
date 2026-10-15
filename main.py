import io
import logging
import os
import sqlite3
from threading import Thread
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from flask import Flask
from PIL import Image

# Logging sozlamalari
logging.basicConfig(level=logging.INFO)

# Tokenlar va Admin ID
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(
    os.getenv("ADMIN_ID", "123456789")
)  # <-- O'zingizning Telegram ID raqamingizni yozing

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


# --- BAZA BILAN ISHLASH (SQLite) ---
def init_db():
  conn = sqlite3.connect("bot_users.db")
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY
        )
    """)
  conn.commit()
  conn.close()


def add_user(user_id):
  conn = sqlite3.connect("bot_users.db")
  cursor = conn.cursor()
  cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
  conn.commit()
  conn.close()


def get_user_count():
  conn = sqlite3.connect("bot_users.db")
  cursor = conn.cursor()
  cursor.execute("SELECT COUNT(*) FROM users")
  count = cursor.fetchone()[0]
  conn.close()
  return count


# Bazani ishga tushirish
init_db()

# Flask Keep-Alive Server (Render uchun)
app = Flask(__name__)


@app.route("/")
def home():
  return "PDF Converter Bot is Alive!"


def run_flask():
  port = int(os.environ.get("PORT", 8080))
  app.run(host="0.0.0.0", port=port)


# FSM holatlari
class BotStates(StatesGroup):
  main_menu = State()
  collecting_images = State()


# Matnlar lug'ati
TEXTS = {
    "uz": {
        "welcome": (
            "👋 <b>Assalomu alaykum!</b>\n\nMen yuqori darajadagi <b>PDF Pro"
            " Bot</b>man. Kerakli xizmatni tanlang:"
        ),
        "btn_img2pdf": "🖼️ Rasmlarni PDF qilish",
        "btn_lang": "🌐 Tilni o'zgartirish",
        "send_images": (
            "🖼️ Menga PDF-ga aylantirmoqchi bo'lgan rasmlaringizni birma-bir"
            " yuboring.\n\nTugatgach, <b>'🏁 PDF yaratish'</b> tugmasini"
            " bosing."
        ),
        "btn_make_pdf": "🏁 PDF yaratish",
        "btn_back": "⬅️ Orqaga",
        "no_images": "⚠️ Siz hali birorta ham rasm yubormadingiz!",
        "converting": "⏳ PDF fayl tayyorlanmoqda, kuting...",
        "success_pdf": "🎉 Barchasi tayyor! Hujjatingiz yuklandi.",
    },
    "ru": {
        "welcome": (
            "👋 <b>Здравствуйте!</b>\n\nЯ продвинутый <b>PDF Pro Bot</b>."
            " Выберите нужную услугу:"
        ),
        "btn_img2pdf": "🖼️ Изображения в PDF",
        "btn_lang": "🌐 Сменить язык",
        "send_images": (
            "🖼️ Отправляйте изображения по одному.\n\nКогда закончите, нажмите"
            " <b>'🏁 Создать PDF'</b>."
        ),
        "btn_make_pdf": "🏁 Создать PDF",
        "btn_back": "⬅️ Назад",
        "no_images": "⚠️ Вы еще не отправили ни одного изображения!",
        "converting": "⏳ Генерируется PDF файл, подождите...",
        "success_pdf": "🎉 Готово! Ваш документ сгенерирован.",
    },
    "en": {
        "welcome": (
            "👋 <b>Hello!</b>\n\nI am advanced <b>PDF Pro Bot</b>. Choose a"
            " service:"
        ),
        "btn_img2pdf": "🖼️ Images to PDF",
        "btn_lang": "🌐 Change Language",
        "send_images": (
            "🖼️ Send your images one by one.\n\nWhen finished, press <b>'🏁"
            " Generate PDF'</b>."
        ),
        "btn_make_pdf": "🏁 Generate PDF",
        "btn_back": "⬅️ Back",
        "no_images": "⚠️ You haven't sent any images yet!",
        "converting": "⏳ Generating PDF file, please wait...",
        "success_pdf": "🎉 All done! Your document is ready.",
    },
}


def get_main_keyboard(lang):
  t = TEXTS[lang]
  kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  kb.add(types.KeyboardButton(t["btn_img2pdf"]), types.KeyboardButton(t["btn_lang"]))
  return kb


# Start buyrug'i
@dp.message_handler(commands=["start"], state="*")
async def cmd_start(message: types.Message, state: FSMContext):
  add_user(message.from_user.id)  # Foydalanuvchini bazaga qo'shish
  await state.finish()

  kb = types.InlineKeyboardMarkup(row_width=3)
  kb.add(
      types.InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="lang_uz"),
      types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
      types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
  )
  await message.answer(
      "🌐 Select Language / Tilni tanlang / Выберите язык:", reply_markup=kb
  )


# Statistika buyrug'i (Faqat admin uchun)
@dp.message_handler(commands=["stats"])
async def cmd_stats(message: types.Message):
  if message.from_user.id == ADMIN_ID:
    count = get_user_count()
    await message.answer(f"📊 <b>Botdagi jami obunachilar soni:</b> {count} ta")
  else:
    await message.answer("❌ Bu buyruq faqat admin uchun!")


# Tilni tanlash
@dp.callback_query_handler(lambda c: c.data.startswith("lang_"), state="*")
async def process_language(callback: types.CallbackQuery, state: FSMContext):
  lang = callback.data.split("_")[1]
  await state.update_data(lang=lang)
  await callback.message.delete()
  await callback.message.answer(
      TEXTS[lang]["welcome"],
      reply_markup=get_main_keyboard(lang),
      parse_mode="HTML",
  )
  await BotStates.main_menu.set()


# Rasmni PDF qilishni boshlash
@dp.message_handler(
    lambda m: any(m.text == TEXTS[l]["btn_img2pdf"] for l in TEXTS),
    state=BotStates.main_menu,
)
async def start_img2pdf(message: types.Message, state: FSMContext):
  data = await state.get_data()
  lang = data.get("lang", "uz")
  await state.update_data(images=[])

  kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
  kb.add(types.KeyboardButton(TEXTS[lang]["btn_make_pdf"]))
  kb.add(types.KeyboardButton(TEXTS[lang]["btn_back"]))

  await message.answer(
      TEXTS[lang]["send_images"], reply_markup=kb, parse_mode="HTML"
  )
  await BotStates.collecting_images.set()


# Rasmlarni qabul qilish
@dp.message_handler(content_types=["photo"], state=BotStates.collecting_images)
async def process_image(message: types.Message, state: FSMContext):
  data = await state.get_data()
  images = data.get("images", [])
  photo = message.photo[-1]
  file_info = await bot.get_file(photo.file_id)
  downloaded_file = await bot.download_file(file_info.file_path)
  images.append(downloaded_file.read())
  await state.update_data(images=images)
  await message.reply(f"📸 Image #{len(images)} saved!")


# PDF yaratish va yuborish
@dp.message_handler(
    lambda m: any(m.text == TEXTS[l]["btn_make_pdf"] for l in TEXTS),
    state=BotStates.collecting_images,
)
async def generate_pdf_from_imgs(message: types.Message, state: FSMContext):
  data = await state.get_data()
  lang = data.get("lang", "uz")
  images = data.get("images", [])

  if not images:
    await message.answer(TEXTS[lang]["no_images"])
    return

  await message.answer(TEXTS[lang]["converting"])

  pil_images = []
  for img_bytes in images:
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    pil_images.append(img)

  output = io.BytesIO()
  pil_images[0].save(
      output, format="PDF", save_all=True, append_images=pil_images[1:]
  )
  output.seek(0)

  await message.answer_document(
      types.InputFile(output, filename="converted_document.pdf"),
      caption=TEXTS[lang]["success_pdf"],
  )
  await message.answer(
      TEXTS[lang]["welcome"],
      reply_markup=get_main_keyboard(lang),
      parse_mode="HTML",
  )
  await BotStates.main_menu.set()


# Orqaga qaytish
@dp.message_handler(
    lambda m: any(
        m.text in [TEXTS[l]["btn_back"], TEXTS[l]["btn_lang"]] for l in TEXTS
    ),
    state="*",
)
async def go_back(message: types.Message, state: FSMContext):
  await cmd_start(message, state)


if __name__ == "__main__":
  # Flask serverni ishga tushirish (Render uchun)
  server_thread = Thread(target=run_flask)
  server_thread.daemon = True
  server_thread.start()

  # Botni ishga tushirish
  executor.start_polling(dp, skip_updates=True)









