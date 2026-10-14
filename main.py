import os
import telebot
from telebot import types
from yt_dlp import YoutubeDL

# 1. Tokeningizni shu yerga yozing
BOT_TOKEN = "8876050592:AAFQGkAYEOX_pbURhp6x5VsbJD_0S4adafo"
ADMIN_ID = 123456789  # O'z Telegram ID raqamingizni yozishingiz mumkin

bot = telebot.TeleBot(BOT_TOKEN)

users_set = set()
user_urls = {}
user_languages = {}  # Foydalanuvchilarning tillari

# Har xil tillardagi matnlar
TEXTS = {
    'uz': {
        'welcome': "🔥 **Assalomu alaykum!** Botimizga xush kelibsiz.\n\n📥 YouTube, Instagram yoki boshqa platformalardan video yoki musiqa yuklab olish uchun menga havolani (linkni) yuboring.",
        'choose_lang': "🇺🇿 Iltimos, tilni tanlang:",
        'choose_dl': "📥 **Yuklab olish turini tanlang:**",
        'lang_changed': "✅ Til O'zbek tiliga o'zgartirildi!",
        'downloading': "⏳ Yuklab olinmoqda, iltimos kuting...",
        'error': "❌ Xatolik yuz berdi. Iltimos, havolani tekshirib qaytadan urinib ko'ring."
    },
    'ru': {
        'welcome': "🔥 **Здравствуйте!** Добро пожаловать.\n\n📥 Отправьте мне ссылку на видео или музыку для скачивания.",
        'choose_lang': "🇷🇺 Пожалуйста, выберите язык:",
        'choose_dl': "📥 **Выберите формат скачивания:**",
        'lang_changed': "✅ Язык изменен на Русский!",
        'downloading': "⏳ Загрузка, пожалуйста подождите...",
        'error': "❌ Произошла ошибка. Пожалуйста, проверьте ссылку."
    }
}

def get_lang(user_id):
    return user_languages.get(user_id, 'uz')

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    users_set.add(user_id)
    lang = get_lang(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_uz = types.InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data='lang_uz')
    btn_ru = types.InlineKeyboardButton("🇷🇺 Русский", callback_data='lang_ru')
    markup.add(btn_uz, btn_ru)
    
    bot.send_message(message.chat.id, TEXTS[lang]['welcome'], parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('lang_'))
def handle_language(call):
    user_id = call.from_user.id
    lang = call.data.split('_')[1]
    user_languages[user_id] = lang
    
    bot.answer_callback_query(call.id, TEXTS[lang]['lang_changed'])
    bot.edit_message_text(TEXTS[lang]['welcome'], call.message.chat.id, call.message.message_id, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text and message.text.startswith('http'))
def handle_url(message):
    user_id = message.from_user.id
    lang = get_lang(user_id)
    user_urls[user_id] = message.text
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_video = types.InlineKeyboardButton("🎥 Video yuklash", callback_data='dl_video')
    btn_audio = types.InlineKeyboardButton("🎵 Musiqa (MP3)", callback_data='dl_audio')
    markup.add(btn_video, btn_audio)
    
    bot.reply_to(message, TEXTS[lang]['choose_dl'], parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('dl_'))
def handle_download_type(call):
    user_id = call.from_user.id
    lang = get_lang(user_id)
    url = user_urls.get(user_id)
    
    if not url:
        bot.answer_callback_query(call.id, "Havola topilmadI!")
        return

    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, TEXTS[lang]['downloading'])

    try:
        if call.data == 'dl_video':
            ydl_opts = {'format': 'best', 'outtmpl': 'downloads/%(id)s.%(ext)s', 'max_filesize': 50*1024*1024}
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
            with open(filename, 'rb') as f:
                bot.send_video(call.message.chat.id, f)
            os.remove(filename)
            
        elif call.data == 'dl_audio':
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': 'downloads/%(id)s.%(ext)s',
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
                'max_filesize': 50*1024*1024
            }
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
            with open(filename, 'rb') as f:
                bot.send_audio(call.message.chat.id, f)
            os.remove(filename)
            
    except Exception as e:
        print(f"Xatolik: {e}")
        bot.send_message(call.message.chat.id, TEXTS[lang]['error'])

# 2. Flask va Botni parallel ishga tushirish qismi
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is running 24/7!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

if __name__ == "__main__":
    # Eski webhooklarni tozalash
    bot.remove_webhook()
    print("Bot va Flask serveri ishga tushmoqda...")
    
    # Avval Flask serverini fonda ishga tushiramiz
    keep_alive()
    
    # Keyin botni polling rejimida ishga qo'shamiz
    bot.infinity_polling(skip_pending=True)
