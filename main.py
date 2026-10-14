import os
import telebot
from telebot import types
from yt_dlp import YoutubeDL

BOT_TOKEN = "8876050592:AAFQGkAYEOX_pbURhp6x5VsbJD_0S4adafo"
ADMIN_ID = 123456789  # <-- O'z Telegram ID raqamingizni yozing

bot = telebot.TeleBot(BOT_TOKEN)

users_set = set()
user_urls = {}
user_languages = {} # Foydalanuvchilarning tillarini saqlash uchun

# Har xil tillardagi matnlar
TEXTS = {
    'uz': {
        'welcome': "🔥 **Assalomu alaykum. Botga Xush kelibsiz.**\nBot orqali Instagram, YouTube va TikTok'dan video va audio yuklab olishingiz mumkin.\n\n🚀 **Yuklab olmoqchi bo'lgan havolani yuboring!**",
        'choose_lang': "🇺🇿 Iltimos, tilni tanlang:",
        'choose_dl': "📥 **Yuklab olish turini tanlang:**",
        'lang_changed': "✅ Til O'zbek tiliga o'zgartirildi!"
    },
    'ru': {
        'welcome': "🔥 **Здравствуйте. Добро пожаловать в бот.**\nЗдесь вы можете скачивать видео и аудио из Instagram, YouTube и TikTok.\n\n🚀 **Отправьте ссылку для скачивания!**",
        'choose_lang': "🇷🇺 Пожалуйста, выберите язык:",
        'choose_dl': "📥 **Выберите тип скачивания:**",
        'lang_changed': "✅ Язык изменен на русский!"
    },
    'en': {
        'welcome': "🔥 **Hello. Welcome to the bot.**\nYou can download video and audio from Instagram, YouTube, and TikTok.\n\n🚀 **Send the link to download!**",
        'choose_lang': "🇬🇧 Please choose your language:",
        'choose_dl': "📥 **Choose download type:**",
        'lang_changed': "✅ Language changed to English!"
    }
}

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    users_set.add(message.chat.id)
    
    # Tilni tanlash uchun tugmalar
    markup = types.InlineKeyboardMarkup(row_width=3)
    btn_uz = types.InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="lang_uz")
    btn_ru = types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")
    btn_en = types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    markup.add(btn_uz, btn_ru, btn_en)
    
    bot.reply_to(message, "🌍 Iltimos, tilni tanlang / Пожалуйста, выберите язык / Please select language:", reply_markup=markup)

# --- ADMIN PANEL ---
@bot.message_handler(commands=['stat'])
def show_stats(message):
    if message.chat.id == ADMIN_ID:
        bot.reply_to(message, f"📊 **Jami foydalanuvchilar:** {len(users_set)} ta", parse_mode="Markdown")
    else:
        bot.reply_to(message, "Bu buyruq faqat admin uchun!")

@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    if message.chat.id == ADMIN_ID:
        text_to_send = message.text.replace('/broadcast', '').strip()
        if not text_to_send:
            bot.reply_to(message, "Xabar matnini kiriting.")
            return
        success = 0
        for uid in users_set:
            try:
                bot.send_message(uid, text_to_send)
                success += 1
            except:
                pass
        bot.reply_to(message, f"✅ Xabar tarqatildi: {success} ta foydalanuvchiga.")
    else:
        bot.reply_to(message, "Bu buyruq faqat admin uchun!")

# --- Til tanlash va havolalarni qabul qilish ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('lang_') or call.data.startswith('dl_'))
def callback_handler(call):
    chat_id = call.message.chat.id
    
    # Til o'zgartirish tugmalari bosilganda
    if call.data.startswith('lang_'):
        lang = call.data.split('_')[1]
        user_languages[chat_id] = lang
        bot.answer_callback_query(call.id, TEXTS[lang]['lang_changed'])
        bot.send_message(chat_id, TEXTS[lang]['welcome'], parse_mode="Markdown")
        return

    # Yuklab olish turini tanlash tugmalari bosilganda
    url = user_urls.get(chat_id)
    lang = user_languages.get(chat_id, 'uz') # Standart til O'zbekcha

    if not url:
        bot.answer_callback_query(call.id, "Havola topilmadi. Qaytadan yuboring.")
        return

    action = call.data
    bot.answer_callback_query(call.id, "Yuklab olish boshlandi...")
    msg = bot.send_message(chat_id, "⏳ Kuting...")

    ydl_video_opts = {'format': 'b', 'outtmpl': 'downloads/%(id)s_video.%(ext)s', 'quiet': True, 'no_warnings': True}
    ydl_audio_opts = {'format': 'ba', 'outtmpl': 'downloads/%(id)s_audio.%(ext)s', 'quiet': True, 'no_warnings': True}

    video_filename = None
    audio_filename = None

    try:
        if action == 'dl_video':
            with YoutubeDL(ydl_video_opts) as ydl:
                v_info = ydl.extract_info(url, download=True)
                video_filename = ydl.prepare_filename(v_info)
            with open(video_filename, 'rb') as vf:
                bot.send_video(chat_id, vf, caption=v_info.get('title', 'Video'))

        elif action == 'dl_audio':
            with YoutubeDL(ydl_audio_opts) as ydl:
                a_info = ydl.extract_info(url, download=True)
                audio_filename = ydl.prepare_filename(a_info)
            with open(audio_filename, 'rb') as af:
                bot.send_audio(chat_id, af, title=a_info.get('title', 'Audio'))

        elif action == 'dl_both':
            with YoutubeDL(ydl_video_opts) as ydl:
                v_info = ydl.extract_info(url, download=True)
                video_filename = ydl.prepare_filename(v_info)
            with YoutubeDL(ydl_audio_opts) as ydl:
                a_info = ydl.extract_info(url, download=True)
                audio_filename = ydl.prepare_filename(a_info)
            with open(video_filename, 'rb') as vf:
                bot.send_video(chat_id, vf, caption=v_info.get('title', 'Video'))
            with open(audio_filename, 'rb') as af:
                bot.send_audio(chat_id, af, title=a_info.get('title', 'Audio'))

        if video_filename and os.path.exists(video_filename):
            os.remove(video_filename)
        if audio_filename and os.path.exists(audio_filename):
            os.remove(audio_filename)

        bot.delete_message(chat_id, msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"❌ Xatolik: {e}", chat_id, msg.message_id)

@bot.message_handler(func=lambda message: True)
def handle_link(message):
    users_set.add(message.chat.id)
    chat_id = message.chat.id
    url = message.text.strip()
    lang = user_languages.get(chat_id, 'uz')
    
    if not (url.startswith("http://") or url.startswith("https://")):
        bot.reply_to(message, "Iltimos, to'g'ri havola yuboring!" if lang == 'uz' else "Please send a valid link!")
        return

    user_urls[chat_id] = url

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_video = types.InlineKeyboardButton("🎥 Video" if lang == 'uz' else "🎥 Video", callback_data="dl_video")
    btn_audio = types.InlineKeyboardButton("🎵 Audio" if lang == 'uz' else "🎵 Audio", callback_data="dl_audio")
    btn_both = types.InlineKeyboardButton("📦 Ikkalasi / Both" if lang != 'ru' else "📦 И то и другое", callback_data="dl_both")
    markup.add(btn_video, btn_audio, btn_both)

    bot.reply_to(message, TEXTS[lang]['choose_dl'], reply_markup=markup, parse_mode="Markdown")

bot.remove_webhook()
print("Bot ishga tushdi...")
bot.infinity_polling()
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

if __name__ == "__main__":
    keep_alive()
