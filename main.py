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

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))  # <-- O'z ID raqamingiz

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")


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


# Foydalanuvchi holatlari va rasmlarni vaqtincha saqlash
user_images = {}


def get_main_keyboard():
  kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  kb.add(
      types.KeyboardButton("🖼️ Rasmlarni PDF qilish"),
      types.KeyboardButton("🌐 Til / Language"),
  )
  return kb


@bot.message_handler(commands=["start"])
def cmd_start(message):
  add_user(message.from_user.id)
  bot.send_message(
      message.chat.id,
      (
          "👋 <b>Assalomu alaykum!</b>\n\nMen <b>PDF Pro Bot</b>man. Kerakli"
          " xizmatni tanlang:"
      ),
      reply_markup=get_main_keyboard(),
  )


@bot.message_handler(commands=["stats"])
def cmd_stats(message):
  if message.from_user.id == ADMIN_ID:
    count = get_user_count()
    bot.send_message(
        message.chat.id, f"📊 <b>Botdagi jami obunachilar soni:</b> {count} ta"
    )
  else:
    bot.send_message(message.chat.id, "❌ Bu buyruq faqat admin uchun!")


@bot.message_handler(
    func=lambda message: message.text == "🖼️ Rasmlarni PDF qilish"
)
def start_img2pdf(message):
  user_images[message.from_user.id] = []
  kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
  kb.add(types.KeyboardButton("🏁 PDF yaratish"))
  kb.add(types.KeyboardButton("⬅️ Orqaga"))
  bot.send_message(
      message.chat.id,
      (
          "🖼️ Menga PDF-ga aylantirmoqchi bo'lgan rasmlaringizni birma-bir"
          " yuboring.\n\nTugatgach, <b>'🏁 PDF yaratish'</b> tugmasini bosing."
      ),
      reply_markup=kb,
  )


@bot.message_handler(func=lambda message: message.text == "⬅️ Orqaga")
def go_back(message):
  bot.send_message(
      message.chat.id, "Asosiy menyu:", reply_markup=get_main_keyboard()
  )


@bot.message_handler(content_types=["photo"])
def handle_photos(message):
  user_id = message.from_user.id
  if user_id not in user_images:
    user_images[user_id] = []

  file_info = bot.get_file(message.photo[-1].file_id)
  downloaded_file = bot.download_file(file_info.file_path)
  user_images[user_id].append(downloaded_file)
  bot.reply_to(message, f"📸 Rasm #{len(user_images[user_id])} saqlandi!")


@bot.message_handler(func=lambda message: message.text == "🏁 PDF yaratish")
def generate_pdf(message):
  user_id = message.from_user.id
  if user_id not in user_images or not user_images[user_id]:
    bot.send_message(message.chat.id, "⚠️ Siz hali birorta ham rasm yubormadingiz!")
    return

  bot.send_message(message.chat.id, "⏳ PDF fayl tayyorlanmoqda, kuting...")

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
      caption="🎉 Barchasi tayyor! Hujjatingiz yuklandi.",
      reply_markup=get_main_keyboard(),
  )
  user_images[user_id] = []


if __name__ == "__main__":
  # Flask serverni ishga tushirish
  server_thread = Thread(target=run_flask)
  server_thread.daemon = True
  server_thread.start()

  # Botni ishga tushirish
  bot.infinity_polling()










