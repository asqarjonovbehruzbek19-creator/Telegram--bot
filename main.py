import io
import logging
import os
import sqlite3
from threading import Thread
from flask import Flask
from PIL import Image
import telebot
from telebot import types

# Logging sozlamalari
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8820793134:AAFqXcnF5Xk_KxHK-3qPx3-y59amLGeUAGQ")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Foydalanuvchilar tili va yuklanayotgan rasmlarni saqlash uchun lug'atlar
user_languages = {}
user_images = {}

# --- BAZA (SQLite) ---
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

init_db()

# Flask Server (Render uchun)
app = Flask(__name__)

@app.route("/")
def home():
  return "PDF Converter Bot is Alive!"

def run_flask():
  port = int(os.environ.get("PORT", 8080))
  app.run(host="0.0.0.0", port=port)

# Matnlar lug'ati
TEXTS = {
    "uz": {
        "welcome": "👋 <b>Assalomu alaykum!</b>\n\nMen <b>PDF Pro Bot</b>man. Kerakli xizmatni tanlang:",
        "btn_img2pdf": "🖼️ Rasmlarni PDF qilish",
        "btn_lang": "🌐 Til / Language",
        "send_images": "🖼️ Menga PDF-ga aylantirmoqchi bo'lgan rasmlaringizni birma-bir yuboring.\n\nTugatgach, <b>'🏁 PDF yaratish'</b> tugmasini bosing.",
        "btn_make_pdf": "🏁 PDF yaratish",
        "btn_back": "⬅️ Orqaga",
        "no_images": "⚠️ Siz hali birorta ham rasm yubormadingiz!",
        "converting": "⏳ PDF fayl tayyorlanmoqda, kuting...",
        "success_pdf": "🎉 Barchasi tayyor! Hujjatingiz yuklandi.",
        "lang_changed": "✅ Til O'zbek tiliga o'zgartirildi!"
    },
    "ru": {
        "welcome": "👋 <b>Здравствуйте!</b>\n\nЯ <b>PDF Pro Bot</b>. Выберите нужную услугу:",
        "btn_img2pdf": "🖼️ Изображения в PDF",
        "btn_lang": "🌐 Til / Language",
        "send_images": "🖼️ Отправляйте изображения по одному.\n\nКогда закончите, нажмите <b>'🏁 Создать PDF'</b>.",
        "btn_make_pdf": "🏁 Создать PDF",
        "btn_back": "⬅️ Назад",
        "no_images": "⚠️ Вы еще не отправили ни одного изображения!",
        "converting": "⏳ Генерируется PDF файл, подождите...",
        "success_pdf": "🎉 Готово! Ваш документ сгенерирован.",
        "lang_changed": "✅ Язык изменен на русский!"
    },
    "en": {
        "welcome": "👋 <b>Hello!</b>\n\nI am <b>PDF Pro Bot</b>. Choose a service:",
        "btn_img2pdf": "🖼️ Images to PDF",
        "btn_lang": "🌐 Til / Language",
        "send_images": "🖼️ Send your images one by one.\n\nWhen finished, press <b>'🏁 Generate PDF'</b>.",
        "btn_make_pdf": "🏁 Generate PDF",
        "btn_back": "⬅️ Back",
        "no_images": "⚠️ You haven't sent any images yet!",
        "converting": "⏳ Generating PDF file, please wait...",
        "success_pdf": "🎉 All done! Your document is ready.",
        "lang_changed": "✅ Language changed to English!"
    }
}

def get_main_keyboard(lang):
  t = TEXTS.get(lang, TEXTS["uz"])
  kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  kb.add(
      types.KeyboardButton(t["btn_img2pdf"]),
      types.KeyboardButton(t["btn_lang"])
  )
  return kb

def get_language_inline():
  kb = types.InlineKeyboardMarkup(row_width=3)
  kb.add(
      types.InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="lang_uz"),
      types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
      types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
  )
  return kb

@bot.message_handler(commands=["start"])
def cmd_start(message):
  user_id = message.from_user.id
  add_user(user_id)
  
  if user_id not in user_languages:
    bot.send_message(
        message.chat.id,
        "🌐 Select Language / Tilni tanlang / Выберите язык:",
        reply_markup=get_language_inline()
    )
  else:
    lang = user_languages[user_id]
    bot.send_message(
        message.chat.id,
        TEXTS[lang]["welcome"],
        reply_markup=get_main_keyboard(lang)
    )

@bot.message_handler(commands=["stats"])
def cmd_stats(message):
  if message.from_user.id == ADMIN_ID:
    count = get_user_count()
    bot.send_message(message.chat.id, f"📊 <b>Botdagi jami obunachilar soni:</b> {count} ta")
  else:
    bot.send_message(message.chat.id, "❌ Bu buyruq faqat admin uchun!")

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def callback_language(call):
  user_id = call.from_user.id
  lang = call.data.split("_")[1]
  user_languages[user_id] = lang
  
  bot.answer_callback_query(call.id)
  bot.delete_message(call.message.chat.id, call.message.message_id)
  
  t = TEXTS[lang]
  bot.send_message(
      call.message.chat.id,
      f"{t['lang_changed']}\n\n{t['welcome']}",
      reply_markup=get_main_keyboard(lang)
  )

@bot.message_handler(func=lambda message: any(message.text == TEXTS[l]["btn_lang"] for l in TEXTS))
def change_language_btn(message):
  bot.send_message(
      message.chat.id,
      "🌐 Select Language / Tilni tanlang / Выберите язык:",
      reply_markup=get_language_inline()
  )

@bot.message_handler(func=lambda message: any(message.text == TEXTS[l]["btn_img2pdf"] for l in TEXTS))
def start_img2pdf(message):
  user_id = message.from_user.id
  lang = user_languages.get(user_id, "uz")
  user_images[user_id] = []
  
  t = TEXTS[lang]
  kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
  kb.add(types.KeyboardButton(t["btn_make_pdf"]))
  kb.add(types.KeyboardButton(t["btn_back"]))
  
  bot.send_message(message.chat.id, t["send_images"], reply_markup=kb)

@bot.message_handler(func=lambda message: any(message.text == TEXTS[l]["btn_back"] for l in TEXTS))
def go_back(message):
  user_id = message.from_user.id
  lang = user_languages.get(user_id, "uz")
  bot.send_message(
      message.chat.id,
      TEXTS[lang]["welcome"],
      reply_markup=get_main_keyboard(lang)
  )

@bot.message_handler(content_types=["photo"])
def handle_photos(message):
  user_id = message.from_user.id
  lang = user_languages.get(user_id, "uz")
  
  if user_id not in user_images:
    user_images[user_id] = []

  # telebot uchun sinxron usul (await olib tashlandi)
  file_info = bot.get_file(message.photo[-1].file_id)
  downloaded_file = bot.download_file(file_info.file_path)
  user_images[user_id].append(downloaded_file)
  
  msg = "📸 Rasm saqlandi!" if lang == "uz" else ("📸 Изображение сохранено!" if lang == "ru" else "📸 Image saved!")
  bot.reply_to(message, f"{msg} (#{len(user_images[user_id])})")

@bot.message_handler(func=lambda message: any(message.text == TEXTS[l]["btn_make_pdf"] for l in TEXTS))
def generate_pdf(message):
  user_id = message.from_user.id
  lang = user_languages.get(user_id, "uz")
  t = TEXTS[lang]
  
  if user_id not in user_images or not user_images[user_id]:
    bot.send_message(message.chat.id, t["no_images"])
    return

  bot.send_message(message.chat.id, t["converting"])

  pil_images = []
  for img_bytes in user_images[user_id]:
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    pil_images.append(img)

  output = io.BytesIO()
  pil_images[0].save(
      output, format="PDF", save_all=True, append_images=pil_images[1:]
  )
  output.seek(0)

  bot.send_document(
      message.chat.id,
      types.InputFile(output, "converted_document.pdf"),
      caption=t["success_pdf"],
      reply_markup=get_main_keyboard(lang)
  )
  user_images[user_id] = []

if __name__ == "__main__":
  server_thread = Thread(target=run_flask)
  server_thread.daemon = True
  server_thread.start()

  bot.infinity_polling()















