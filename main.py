import os
import re
import time
import asyncio
import logging
import sqlite3
import tempfile
from pathlib import Path

import aiohttp
from flask import Flask
from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter
from pdf2docx import Converter

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, KeyboardButton,
    ReplyKeyboardMarkup, InlineKeyboardButton,
    InlineKeyboardMarkup
)

# ========== SOZLAMALAR ==========
TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}
MAX_MB = int(os.getenv("MAX_FILE_MB", "40"))
MAX_BYTES = MAX_MB * 1024 * 1024
DB = os.getenv("DB_PATH", "bot_data.sqlite3")
WORK = Path("/tmp/pdf_center")
WORK.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("pdf-center")

app = Flask(__name__)

@app.get("/")
def home():
    return {"status": "ok", "bot": "PDF Markaz"}, 200

@app.get("/health")
def health():
    return "OK", 200

router = Router()
dp = Dispatcher()
dp.include_router(router)
bot = None

# ========== TUGMALAR ==========
MERGE = "📚 PDF birlashtirish"
SPLIT = "✂️ Sahifalarni ajratish"
COMPRESS = "🗜 PDF siqish"
IMAGE = "🖼 Rasm → PDF"
WORD = "📝 PDF → Word"
BOOKS = "📖 Kitob qidirish"
HELP = "ℹ️ Yordam"
ADMIN = "🛠 Admin panel"
CANCEL = "❌ Bekor qilish"
DONE = "✅ Tayyor"

MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=MERGE), KeyboardButton(text=SPLIT)],
        [KeyboardButton(text=COMPRESS), KeyboardButton(text=IMAGE)],
        [KeyboardButton(text=WORD), KeyboardButton(text=BOOKS)],
        [KeyboardButton(text=HELP)],
    ],
    resize_keyboard=True
)

CANCEL_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=CANCEL)],
    ],
    resize_keyboard=True
)

class Flow(StatesGroup):
    merge = State()
    split_file = State()
    split_range = State()
    compress = State()
    images = State()
    word = State()
    books = State()
    broadcast = State()

# ========== MA'LUMOTLAR BAZASI ==========
def db_init():
    with sqlite3.connect(DB) as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users(
                user_id INTEGER PRIMARY KEY,
                joined INTEGER
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS actions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                created INTEGER
            )
        """)

def register(uid):
    with sqlite3.connect(DB) as c:
        c.execute(
            "INSERT OR IGNORE INTO users VALUES(?,?)",
            (uid, int(time.time()))
        )

def log_action(uid, action):
    with sqlite3.connect(DB) as c:
        c.execute(
            "INSERT INTO actions(user_id,action,created) VALUES(?,?,?)",
            (uid, action, int(time.time()))
        )

def all_users():
    with sqlite3.connect(DB) as c:
        return [r[0] for r in c.execute("SELECT user_id FROM users")]

def stats():
    with sqlite3.connect(DB) as c:
        users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        actions = c.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
        active = c.execute(
            "SELECT COUNT(DISTINCT user_id) FROM actions WHERE created>?",
            (int(time.time()) - 86400,)
        ).fetchone()[0]
    return users, actions, active

def is_admin(uid):
    return uid in ADMIN_IDS

def folder(uid):
    p = WORK / str(uid)
    p.mkdir(parents=True, exist_ok=True)
    return p

def check_size(size):
    if size and size > MAX_BYTES:
        raise ValueError(f"Fayl katta. Limit: {MAX_MB} MB.")

def safe_name(name):
    name = Path(name or "file").name
    return re.sub(r"[^\w.-]", "_", name)[:80]

async def download_doc(message, dest):
    doc = message.document
    if not doc:
        raise ValueError("Faylni hujjat sifatida yuboring.")
    check_size(doc.file_size)
    f = await bot.get_file(doc.file_id)
    await bot.download_file(f.file_path, destination=dest)
    return dest

def get_pdf(path):
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise ValueError("Parol bilan himoyalangan PDF ochilmadi.")
        if not reader.pages:
            raise ValueError("PDF ichida sahifa yo‘q.")
        return reader
    except ValueError:
        raise
    except Exception as e:
        raise ValueError("PDF fayl buzilgan yoki noto‘g‘ri.") from e

async def send_file(message, path, caption="✅ Tayyor!"):
    if not path.exists() or path.stat().st_size == 0:
        raise ValueError("Natija fayli yaratilmadi.")
    if path.stat().st_size > 49 * 1024 * 1024:
        raise ValueError("Natija 49 MB dan katta. Kichikroq fayl bilan urinib ko‘ring.")
    with path.open("rb") as f:
        await message.answer_document(f, caption=caption)

async def end_flow(message, state):
    await state.clear()
    await message.answer("Bosh menyu:", reply_markup=MENU)

# ========== START / YORDAM ==========
@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    register(message.from_user.id)
    await message.answer(
        f"Assalomu alaykum, {message.from_user.first_name or 'do‘st'}! 👋\n\n"
        "📚 *PDF MARKAZ*\n"
        "PDF fayllar bilan ishlash va kitob qidirish boti.\n\n"
        f"📦 Fayl limiti: {MAX_MB} MB\n"
        "Kerakli xizmatni tanlang:",
        reply_markup=MENU
    )

@router.message(Command("help"))
@router.message(F.text == HELP)
async def help_cmd(message: Message):
    await message.answer(
        "ℹ️ *Yordam*\n\n"
        "• PDF birlashtirish — 2 yoki undan ko‘p PDF yuboring.\n"
        "• Sahifa ajratish — PDF va sahifa raqamlarini kiriting.\n"
        "• Siqish — PDF ichidagi ma’lumotlarni optimallashtirish.\n"
        "• Rasm → PDF — rasmlarni yuborib, Tayyor tugmasini bosing.\n"
        "• PDF → Word — PDF fayl yuboring.\n"
        "• Kitob qidirish — kitob nomi yoki muallifini yozing.\n\n"
        "Bekor qilish: /cancel",
        reply_markup=MENU
    )

@router.message(Command("cancel"))
@router.message(F.text == CANCEL)
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Amal bekor qilindi.", reply_markup=MENU)

# ========== PDF BIRLASHTIRISH ==========
@router.message(F.text == MERGE)
async def merge_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Flow.merge)
    await state.update_data(files=[])
    await message.answer(
        "📚 Kamida 2 ta PDF yuboring. Tugatgach «✅ Tayyor» ni bosing.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=DONE)],
                [KeyboardButton(text=CANCEL)]
            ],
            resize_keyboard=True
        )
    )

@router.message(Flow.merge, F.document)
async def merge_add(message: Message, state: FSMContext):
    doc = message.document
    if not ((doc.file_name or "").lower().endswith(".pdf")
            or doc.mime_type == "application/pdf"):
        await message.answer("PDF fayl yuboring.")
        return
    try:
        data = await state.get_data()
        files = data.get("files", [])
        path = folder(message.from_user.id) / f"merge_{len(files)}_{safe_name(doc.file_name)}"
        await download_doc(message, path)
        get_pdf(path)
        files.append(str(path))
        await state.update_data(files=files)
        await message.answer(f"Qabul qilindi: {len(files)} ta PDF.")
    except Exception as e:
        await message.answer(f"❌ {e}")

@router.message(Flow.merge, F.text == DONE)
async def merge_done(message: Message, state: FSMContext):
    files = (await state.get_data()).get("files", [])
    if len(files) < 2:
        await message.answer("Kamida 2 ta PDF kerak.")
        return
    try:
        writer = PdfWriter()
        for name in files:
            for page in get_pdf(Path(name)).pages:
                writer.add_page(page)
        out = folder(message.from_user.id) / f"merged_{int(time.time())}.pdf"
        with out.open("wb") as f:
            writer.write(f)
        log_action(message.from_user.id, "merge")
        await send_file(message, out, "✅ PDF fayllar birlashtirildi.")
    except Exception as e:
        await message.answer(f"❌ Birlashtirishda xato: {e}")
    await end_flow(message, state)

# ========== SAHIFA AJRATISH ==========
@router.message(F.text == SPLIT)
async def split_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Flow.split_file)
    await message.answer("Ajratish uchun PDF fayl yuboring.", reply_markup=CANCEL_MENU)

@router.message(Flow.split_file, F.document)
async def split_receive(message: Message, state: FSMContext):
    doc = message.document
    if not ((doc.file_name or "").lower().endswith(".pdf")
            or doc.mime_type == "application/pdf"):
        await message.answer("PDF fayl yuboring.")
        return
    try:
        path = folder(message.from_user.id) / f"split_{int(time.time())}.pdf"
        await download_doc(message, path)
        reader = get_pdf(path)
        await state.update_data(path=str(path), pages=len(reader.pages))
        await state.set_state(Flow.split_range)
        await message.answer(
            f"PDF’da {len(reader.pages)} ta sahifa bor.\n"
            "Kerakli sahifalarni kiriting: `1-3` yoki `1,3,5-7`."
        )
    except Exception as e:
        await message.answer(f"❌ {e}")

def parse_pages(spec, total):
    result = []
    for part in spec.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            start, end = int(a), int(b)
            if start > end:
                raise ValueError("Oraliq noto‘g‘ri.")
            result.extend(range(start, end + 1))
        else:
            result.append(int(part))
    if not result or min(result) < 1 or max(result) > total:
        raise ValueError(f"Sahifa raqami 1 dan {total} gacha bo‘lishi kerak.")
    return sorted(set(result))

@router.message(Flow.split_range, F.text)
async def split_do(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        reader = get_pdf(Path(data["path"]))
        pages = parse_pages(message.text, len(reader.pages))
        writer = PdfWriter()
        for p in pages:
            writer.add_page(reader.pages[p - 1])
        out = folder(message.from_user.id) / f"pages_{int(time.time())}.pdf"
        with out.open("wb") as f:
            writer.write(f)
        log_action(message.from_user.id, "split")
        await send_file(message, out, f"✅ {len(pages)} ta sahifa ajratildi.")
    except Exception as e:
        await message.answer(f"❌ Sahifalarni ajratib bo‘lmadi: {e}")
        return
    await end_flow(message, state)

# ========== PDF SIQISH ==========
@router.message(F.text == COMPRESS)
async def compress_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Flow.compress)
    await message.answer("Siqish uchun PDF fayl yuboring.", reply_markup=CANCEL_MENU)

@router.message(Flow.compress, F.document)
async def compress_do(message: Message, state: FSMContext):
    doc = message.document
    if not ((doc.file_name or "").lower().endswith(".pdf")
            or doc.mime_type == "application/pdf"):
        await message.answer("PDF fayl yuboring.")
        return
    try:
        src = folder(message.from_user.id) / f"compress_in_{int(time.time())}.pdf"
        out = folder(message.from_user.id) / f"compressed_{int(time.time())}.pdf"
        await download_doc(message, src)
        reader = get_pdf(src)
        writer = PdfWriter()
        for page in reader.pages:
            try:
                page.compress_content_streams()
            except Exception:
                pass
            writer.add_page(page)
        with out.open("wb") as f:
            writer.write(f)
        before, after = src.stat().st_size, out.stat().st_size
        log_action(message.from_user.id, "compress")
        note = "PDF optimallashtirildi."
        if after < before:
            note += f" Hajmi: {before // 1024} KB → {after // 1024} KB."
        else:
            note += " Hajmi kamaymadi; PDF allaqachon optimallashgan bo‘lishi mumkin."
        await send_file(message, out, "✅ " + note)
    except Exception as e:
        await message.answer(f"❌ Siqishda xato: {e}")
    await end_flow(message, state)

# ========== RASM -> PDF ==========
@router.message(F.text == IMAGE)
async def image_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Flow.images)
    await state.update_data(images=[])
    await message.answer(
        "JPG yoki PNG rasmlarni yuboring. Tugatgach «✅ Tayyor» ni bosing.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=DONE)],
                [KeyboardButton(text=CANCEL)]
            ],
            resize_keyboard=True
        )
    )

@router.message(Flow.images, F.photo)
async def image_add_photo(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        images = data.get("images", [])
        path = folder(message.from_user.id) / f"image_{len(images)}_{int(time.time())}.jpg"
        f = await bot.get_file(message.photo[-1].file_id)
        await bot.download_file(f.file_path, destination=path)
        images.append(str(path))
        await state.update_data(images=images)
        await message.answer(f"Rasm olindi. Jami: {len(images)} ta.")
    except Exception as e:
        await message.answer(f"❌ {e}")

@router.message(Flow.images, F.document)
async def image_add_doc(message: Message, state: FSMContext):
    doc = message.document
    if not (doc.mime_type or "").startswith("image/"):
        await message.answer("Rasm fayl yuboring.")
        return
    try:
        data = await state.get_data()
        images = data.get("images", [])
        path = folder(message.from_user.id) / f"image_{len(images)}_{safe_name(doc.file_name)}"
        await download_doc(message, path)
        with Image.open(path) as im:
            im.verify()
        images.append(str(path))
        await state.update_data(images=images)
        await message.answer(f"Rasm olindi. Jami: {len(images)} ta.")
    except Exception as e:
        await message.answer(f"❌ Rasmni o‘qib bo‘lmadi: {e}")

@router.message(Flow.images, F.text == DONE)
async def image_done(message: Message, state: FSMContext):
    images = (await state.get_data()).get("images", [])
    if not images:
        await message.answer("Avval rasm yuboring.")
        return
    try:
        converted = []
        for name in images:
            with Image.open(name) as im:
                converted.append(ImageOps.exif_transpose(im).convert("RGB"))
        out = folder(message.from_user.id) / f"images_{int(time.time())}.pdf"
        converted[0].save(
            out, save_all=True, append_images=converted[1:],
            resolution=150.0
        )
        for im in converted:
            im.close()
        log_action(message.from_user.id, "image_to_pdf")
        await send_file(message, out, f"✅ {len(images)} ta rasm PDF qilindi.")
    except Exception as e:
        await message.answer(f"❌ PDF yaratilmadi: {e}")
    await end_flow(message, state)

# ========== PDF -> WORD ==========
@router.message(F.text == WORD)
async def word_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Flow.word)
    await message.answer("Word’ga aylantirish uchun PDF yuboring.", reply_markup=CANCEL_MENU)

@router.message(Flow.word, F.document)
async def word_do(message: Message, state: FSMContext):
    doc = message.document
    if not ((doc.file_name or "").lower().endswith(".pdf")
            or doc.mime_type == "application/pdf"):
        await message.answer("PDF fayl yuboring.")
        return
    try:
        src = folder(message.from_user.id) / f"word_{int(time.time())}.pdf"
        out = folder(message.from_user.id) / f"word_{int(time.time())}.docx"
        await download_doc(message, src)
        get_pdf(src)
        await message.answer("⏳ Word fayli tayyorlanmoqda...")
        def convert():
            cv = Converter(str(src))
            try:
                cv.convert(str(out))
            finally:
                cv.close()
        await asyncio.to_thread(convert)
        log_action(message.from_user.id, "pdf_to_word")
        await send_file(message, out, "✅ Word tayyor. Skanerlangan PDF’da natija farq qilishi mumkin.")
    except Exception as e:
        log.exception("PDF to Word error")
        await message.answer(f"❌ Word’ga aylantirishda xato: {e}")
    await end_flow(message, state)

# ========== KITOB QIDIRISH ==========
@router.message(F.text == BOOKS)
async def books_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Flow.books)
    await message.answer("Kitob nomi yoki muallifini yozing.", reply_markup=CANCEL_MENU)

@router.message(Flow.books, F.text)
async def books_search(message: Message, state: FSMContext):
    query = message.text.strip()
    if len(query) < 2:
        await message.answer("Kamida 2 ta harf yozing.")
        return
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                "https://openlibrary.org/search.json",
                params={"q": query, "limit": 5}
            ) as response:
                if response.status != 200:
                    raise RuntimeError("Kitob katalogi ho
















