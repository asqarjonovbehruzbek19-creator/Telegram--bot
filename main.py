import os
import re
import uuid
import asyncio
import sqlite3
import tempfile
import threading
from html import escape

import aiohttp
from flask import Flask
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pdf2docx import Converter

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    FSInputFile,
    CallbackQuery,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode


# =====================================
# SOZLAMALAR
# =====================================

TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "40"))

BASE_DIR = tempfile.gettempdir()
DB_NAME = "users.db"

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()

app = Flask(__name__)


# =====================================
# WEB SERVER — RENDER UCHUN
# =====================================

@app.route("/")
def home():
    return "PDF Center Bot ishlayapti!"


@app.route("/health")
def health():
    return {"status": "ok"}


def run_web():
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)


# =====================================
# MA'LUMOTLAR BAZASI
# =====================================

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY
            )
        """)


async def add_user(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users(user_id) VALUES (?)",
            (user_id,)
        )


def get_users():
    with sqlite3.connect(DB_NAME) as conn:
        return [
            row[0]
            for row in conn.execute("SELECT user_id FROM users")
        ]


def is_admin(user_id):
    return user_id in ADMIN_IDS


# =====================================
# MENYU
# =====================================

def main_menu(admin=False):
    buttons = [
        [KeyboardButton(text="📎 PDF birlashtirish"),
         KeyboardButton(text="✂️ PDF ajratish")],
        [KeyboardButton(text="🗜 PDF siqish"),
         KeyboardButton(text="🖼 Rasm → PDF")],
        [KeyboardButton(text="📝 PDF → Word"),
         KeyboardButton(text="📚 Kitob qidirish")],
        [KeyboardButton(text="❌ Bekor qilish")],
    ]

    if admin:
        buttons.append([KeyboardButton(text="⚙️ Admin panel")])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )


# =====================================
# HOLATLAR
# =====================================

class Flow(StatesGroup):
    merge = State()
    split_upload = State()
    split_pages = State()
    compress = State()
    images = State()
    word = State()
    book = State()
    broadcast = State()


# =====================================
# YORDAMCHI FUNKSIYALAR
# =====================================

async def download_file(file_id, destination):
    tg_file = await bot.get_file(file_id)
    await bot.download_file(
        tg_file.file_path,
        destination=destination
    )
    return destination


def temp_path(extension):
    return os.path.join(
        BASE_DIR,
        f"{uuid.uuid4().hex}.{extension}"
    )


def remove_file(path):
    try:
        if path and os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


def check_pdf(path):
    reader = PdfReader(path)
    if reader.is_encrypted:
        raise ValueError("Parol bilan himoyalangan PDF.")
    return reader


def parse_pages(text, total):
    pages = set()

    for part in text.replace(" ", "").split(","):
        if not part:
            continue

        if "-" in part:
            a, b = part.split("-", 1)
            start, end = int(a), int(b)

            if start > end:
                raise ValueError("Sahifa oralig'i noto'g'ri.")

            if start < 1 or end > total:
                raise ValueError(
                    f"Sahifalar 1 dan {total} gacha bo'lishi kerak."
                )

            pages.update(range(start, end + 1))
        else:
            number = int(part)

            if number < 1 or number > total:
                raise ValueError(
                    f"Sahifalar 1 dan {total} gacha bo'lishi kerak."
                )

            pages.add(number)

    if not pages:
        raise ValueError("Sahifa raqamlarini kiriting.")

    return sorted(pages)


def get_document(message):
    return message.document


async def validate_pdf(message, document):
    if not (document.file_name or "").lower().endswith(".pdf"):
        await message.answer("❌ PDF fayl yuboring.")
        return False

    if (
        document.file_size
        and document.file_size > MAX_FILE_MB * 1024 * 1024
    ):
        await message.answer(
            f"❌ Fayl hajmi {MAX_FILE_MB} MB dan oshmasin."
        )
        return False

    return True


# =====================================
# START
# =====================================

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()

    if message.from_user:
        await add_user(message.from_user.id)

    await message.answer(
        "📚 <b>PDF Center botiga xush kelibsiz!</b>\n\n"
        "Quyidagi xizmatlardan foydalaning.",
        reply_markup=main_menu(
            is_admin(message.from_user.id)
            if message.from_user else False
        )
    )


@dp.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "📎 PDF birlashtirish\n"
        "✂️ PDF sahifalarini ajratish\n"
        "🗜 PDF siqish\n"
        "🖼 Rasmlardan PDF yaratish\n"
        "📝 PDFni Wordga aylantirish\n"
        "📚 Kitob qidirish\n\n"
        "Bekor qilish uchun /cancel yuboring."
    )


@dp.message(Command("cancel"))
@dp.message(F.text == "❌ Bekor qilish")
async def cancel(message: Message, state: FSMContext):
    data = await state.get_data()

    for key in ("pdf_paths", "image_paths"):
        for path in data.get(key, []):
            remove_file(path)

    for key in ("pdf_path",):
        remove_file(data.get(key))

    await state.clear()

    await message.answer(
        "❌ Amal bekor qilindi.",
        reply_markup=main_menu(
            is_admin(message.from_user.id)
            if message.from_user else False
        )
    )


# =====================================
# PDF BIRLASHTIRISH
# =====================================

@dp.message(F.text == "📎 PDF birlashtirish")
async def merge_start(message: Message, state: FSMContext):
    await state.set_state(Flow.merge)
    await state.update_data(pdf_paths=[])

    await message.answer(
        "Birlashtiriladigan PDF fayllarni birma-bir yuboring.\n"
        "Tugatgach, TAYYOR deb yozing."
    )


@dp.message(Flow.merge, F.document)
async def merge_receive(
    message: Message,
    state: FSMContext
):
    document = message.document

    if not await validate_pdf(message, document):
        return

    path = temp_path("pdf")

    try:
        await download_file(document.file_id, path)
        check_pdf(path)

        data = await state.get_data()
        paths = data.get("pdf_paths", [])
        paths.append(path)

        await state.update_data(pdf_paths=paths)

        await message.answer(
            f"✅ Fayl qabul qilindi. Jami: {len(paths)} ta.\n"
            "Yana PDF yuboring yoki TAYYOR deb yozing."
        )
    except Exception:
        remove_file(path)
        await message.answer("❌ PDF faylni o'qib bo'lmadi.")


@dp.message(Flow.merge, F.text)
async def merge_finish(message: Message, state: FSMContext):
    if (message.text or "").strip().upper() != "TAYYOR":
        await message.answer("PDF yuboring yoki TAYYOR deb yozing.")
        return

    data = await state.get_data()
    paths = data.get("pdf_paths", [])

    if len(paths) < 2:
        await message.answer("Kamida 2 ta PDF kerak.")
        return

    output = temp_path("pdf")

    try:
        writer = PdfWriter()

        for path in paths:
            reader = check_pdf(path)
            for page in reader.pages:
                writer.add_page(page)

        with open(output, "wb") as file:
            writer.write(file)

        await message.answer_document(
            FSInputFile(output, filename="birlashtirilgan.pdf"),
            caption="✅ PDF fayllar birlashtirildi."
        )

    except Exception:
        await message.answer("❌ Birlashtirishda xatolik.")

    finally:
        for path in paths:
            remove_file(path)
        remove_file(output)
        await state.clear()


# =====================================
# PDF SAHIFALARINI AJRATISH
# =====================================

@dp.message(F.text == "✂️ PDF ajratish")
async def split_start(message: Message, state: FSMContext):
    await state.set_state(Flow.split_upload)

    await message.answer("Sahifalarini ajratmoqchi bo'lgan PDFni yuboring.")


@dp.message(Flow.split_upload, F.document)
async def split_receive(
    message: Message,
    state: FSMContext
):
    document = message.document

    if not await validate_pdf(message, document):
        return

    path = temp_path("pdf")

    try:
        await download_file(document.file_id, path)
        reader = check_pdf(path)

        await state.update_data(
            pdf_path=path,
            total_pages=len(reader.pages)
        )
        await state.set_state(Flow.split_pages)

        await message.answer(
            f"PDFda {len(reader.pages)} ta sahifa bor.\n\n"
            "Kerakli sahifalarni yozing.\n"
            "Misol: <code>1-3,5,7</code>"
        )

    except Exception:
        remove_file(path)
        await message.answer("❌ PDFni o'qib bo'lmadi.")


@dp.message(Flow.split_pages, F.text)
async def split_process(message: Message, state: FSMContext):
    data = await state.get_data()
    source = data.get("pdf_path")
    total = data.get("total_pages", 0)

    if not source or not os.path.exists(source):
        await message.answer("PDF topilmadi. Qaytadan yuboring.")
        await state.clear()
        return

    output = None

    try:
        pages = parse_pages(message.text or "", total)

        reader = check_pdf(source)
        writer = PdfWriter()

        for number in pages:
            writer.add_page(reader.pages[number - 1])

        output = temp_path("pdf")

        with open(output, "wb") as file:
            writer.write(file)

        await message.answer_document(
            FSInputFile(output, filename="ajratilgan.pdf"),
            caption="✅ Sahifalar ajratildi."
        )

        remove_file(source)
        await state.clear()

    except ValueError as error:
        await message.answer(
            f"❌ {escape(str(error))}\n"
            "Masalan: <code>1-3,5</code>"
        )

    except Exception:
        await message.answer("❌ Sahifalarni ajratib bo'lmadi.")

    finally:
        remove_file(output)


# =====================================
# PDF SIQISH
# =====================================

@dp.message(F.text == "🗜 PDF siqish")
async def compress_start(message: Message, state: FSMContext):
    await state.set_state(Flow.compress)
    await message.answer("Siqmoqchi bo'lgan PDF faylni yuboring.")


@dp.message(Flow.compress, F.document)
async def compress_pdf(
    message: Message,
    state: FSMContext
):
    document = message.document

    if not await validate_pdf(message, document):
        return

    source = temp_path("pdf")
    output = temp_path("pdf")

    try:
        await download_file(document.file_id, source)
        reader = check_pdf(source)
        writer = PdfWriter()

        for page in reader.pages:
            page.compress_content_streams()
            writer.add_page(page)

        with open(output, "wb") as file:
            writer.write(file)

        old_size = os.path.getsize(source) / 1024
        new_size = os.path.getsize(output) / 1024

        await message.answer_document(
            FSInputFile(output, filename="siqilgan.pdf"),
            caption=(
                "✅ PDF qayta saqlandi.\n"
                f"Oldingi hajm: {old_size:.1f} KB\n"
                f"Yangi hajm: {new_size:.1f} KB\n\n"
                "Eslatma: rasmlarni kuchli siqish bu usulda mavjud emas."
            )
        )

    except Exception:
        await message.answer("❌ PDFni siqib bo'lmadi.")

    finally:
        remove_file(source)
        remove_file(output)
        await state.clear()


# =====================================
# RASMLARNI PDF QILISH
# =====================================

@dp.message(F.text == "🖼 Rasm → PDF")
async def images_start(message: Message, state: FSMContext):
    await state.set_state(Flow.images)
    await state.update_data(image_paths=[])

    await message.answer(
        "Rasmlarni birma-bir yuboring.\n"
        "Tugatgach, TAYYOR deb yozing."
    )


@dp.message(Flow.images, F.photo)
async def image_receive_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    path = temp_path("jpg")

    try:
        await download_file(photo.file_id, path)

        data = await state.get_data()
        paths = data.get("image_paths", [])
        paths.append(path)

        await state.update_data(image_paths=paths)
        await message.answer(
            f"✅ Rasm qabul qilindi. Jami: {len(paths)} ta."
        )
    except Exception:
        remove_file(path)
        await message.answer("❌ Rasmni yuklab bo'lmadi.")


@dp.message(Flow.images, F.document)
async def image_receive_document(
    message: Message,
    state: FSMContext
):
    document = message.document

    if not document:
        return

    name = (document.file_name or "").lower()

    if not name.endswith((".jpg", ".jpeg", ".png", ".webp")):
        await message.answer("JPG, PNG yoki WEBP rasm yuboring.")
        return

    if (
        document.file_size
        and document.file_size > MAX_FILE_MB * 1024 * 1024
    ):
        await message.answer("❌ Rasm juda katta.")
        return

    path = temp_path("img")

    try:
        await download_file(document.file_id, path)

        # Fayl haqiqatan rasm ekanini tekshirish.
        with Image.open(path) as image:
            image.verify()

        data = await state.get_data()
        paths = data.get("image_paths", [])
        paths.append(path)

        await state.update_data(image_paths=paths)
        await message.answer(
            f"✅ Rasm qabul qilindi. Jami: {len(paths)} ta."
        )
    except Exception:
        remove_file(path)
        await message.answer("❌ Rasmni o'qib bo'lmadi.")


@dp.message(Flow.images, F.text)
async def images_finish(message: Message, state: FSMContext):
    if (message.text or "").strip().upper() != "TAYYOR":
        await message.answer("Rasm yuboring yoki TAYYOR deb yozing.")
        return

    data = await state.get_data()
    paths = data.get("image_paths", [])

    if not paths:
        await message.answer("Avval kamida bitta rasm yuboring.")
        return

    output = temp_path("pdf")

    try:
        converted = []

        for path in paths:
            with Image.open(path) as image:
                converted.append(image.convert("RGB").copy())

        converted[0].save(
            output,
            save_all=True,
            append_images=converted[1:]
        )

        for image in converted:
            image.close()

        await message.answer_document(
            FSInputFile(output, filename="rasmlardan.pdf"),
            caption="✅ Rasmlar PDFga aylantirildi."
        )

    except Exception:
        await message.answer("❌ Rasmlardan PDF yaratilmadi.")

    finally:
        for path in paths:
            remove_file(path)
        remove_file(output)
        await state.clear()


# =====================================
# PDF → WORD
# =====================================

@dp.message(F.text == "📝 PDF → Word")
async def word_start(message: Message, state: FSMContext):
    await state.set_state(Flow.word)
    await message.answer("Wordga aylantirish uchun PDF yuboring.")


@dp.message(Flow.word, F.document)
async def word_convert(message: Message, state: FSMContext):
    document = message.document

    if not await validate_pdf(message, document):
        return

    source = temp_path("pdf")
    output = temp_path("docx")

    try:
        await download_file(document.file_id, source)
        check_pdf(source)

        def convert():
            converter = Converter(source)
            try:
                converter.convert(output)
            finally:
                converter.close()

        await asyncio.to_thread(convert)

        await message.answer_document(
            FSInputFile(output, filename="word_hujjat.docx"),
            caption="✅ Word fayli tayyor."
        )

    except Exception:
        await message.answer(
            "❌ Konvertatsiya amalga oshmadi. "
            "Ayrim skanerlangan PDFlar to'g'ri o'girilmasligi mumkin."
        )

    finally:
        remove_file(source)
        remove_file(output)
        await state.clear()


# =====================================
# KITOB QIDIRISH
# =====================================

@dp.message(F.text == "📚 Kitob qidirish")
async def book_start(message: Message, state: FSMContext):
    await state.set_state(Flow.book)
    await message.answer("Kitob nomini yozing.")


@dp.message(Flow.book, F.text)
async def book_search(message: Message, state: FSMContext):
    query = (message.text or "").strip()

    if len(query) < 2:
        await message.answer("Kitob nomini to'liqroq yozing.")
        return

    url = "https://openlibrary.org/search.json"

    try:
        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                url,
                params={"title": query, "limit": 5}
            ) as response:
                if response.status != 200:
                    await message.answer("Qidiruv xizmati vaqtincha ishlamayapti.")
                    return

                data = await response.json()

        books = data.get("docs", [])

        if not books:
            await message.answer("📚 Kitob topilmadi.")
            return

        results = []

        for book in books[:5]:
            title = escape(book.get("title", "Nomsiz"))
            authors = book.get("author_name", ["Noma'lum muallif"])
            author = escape(", ".join(authors[:2]))
            year = book.get("first_publish_year", "Noma'lum")

            key = book.get("key", "")
            link = (
                "https://openlibrary.org" + key
                if key.startswith("/works/")
                else "https://openlibrary.org"
            )

            results.append(
                f"📖 <b>{title}</b>\n"
                f"✍️ {author}\n"
                f"📅 {year}\n"
                f"🔗 {link}"
            )

        await message.answer("\n\n".join(results))

    except Exception:
        await message.answer("❌ Kitob qidirishda xatolik yuz berdi.")

    finally:
        await state.clear()


# =====================================
# ADMIN PANEL
# =====================================

@dp.message(Command("admin"))
@dp.message(F.text == "⚙️ Admin panel")
async def admin_panel(message: Message):
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer("⛔ Siz admin emassiz.")
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Statistika", callback_data="admin_stats")
    builder.button(text="📢 Xabar yuborish", callback_data="admin_broadcast")
    builder.adjust(1)

    await message.answer(
        "⚙️ <b>Admin panel</b>\nKerakli amalni tanlang:",
        reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return

    users = get_users()

    await callback.message.answer(
        f"📊 <b>Bot statistikasi</b>\n\n"
        f"👥 Foydalanuvchilar: {len(users)}"
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(
    callback: CallbackQuery,
    state: FSMContext
):
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return

    await state.set_state(Flow.broadcast)

    await callback.message.answer(
        "📢 Barcha foydalanuvchilarga yuboriladigan matnni yozing.\n"
        "Bekor qilish uchun /cancel yuboring."
    )
    await callback.answer()


@dp.message(Flow.broadcast, F.text)
async def admin_broadcast_send(
    message: Message,
    state: FSMContext
):
    if not message.from_user or not is_admin(message.from_user.id):
        await state.clear()
        return

    text = (message.text or "").strip()

    if not text:
        await message.answer("Xabar bo'sh bo'lmasin.")
        return

    sent = 0
    failed = 0

    for user_id in get_users():
        try:
            await bot.send_message(user_id, escape(text))
            sent += 1
        except Exception:
            failed += 1

        await asyncio.sleep(0.04)

    await state.clear()

    await message.answer(
        "📢 Yuborish yakunlandi.\n\n"
        f"✅ Yuborildi: {sent}\n"
        f"❌ Yuborilmadi: {failed}"
    )


# =====================================
# XATOLIKLAR
# =====================================

@dp.message()
async def unknown_message(message: Message):
    await message.answer(
        "Menyudan xizmatni tanlang yoki /help buyrug'ini yuboring.",
        reply_markup=main_menu(
            is_admin(message.from_user.id)
            if message.from_user else False
        )
    )


# =====================================
# BOTNI ISHGA TUSHIRISH
# =====================================

async def run_bot():
    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN topilmadi. Render Environment bo'limiga qo'shing."
        )

    init_db()

    # Webhook yoqilgan bo'lsa, polling bilan to'qnashmasligi uchun o'chirish.
    await bot.delete_webhook(drop_pending_updates=False)

    await dp.start_polling(bot)


if __name__ == "__main__":
    threading.Thread(
        target=run_web,
        daemon=True
    ).start()

    asyncio.run(run_bot())














