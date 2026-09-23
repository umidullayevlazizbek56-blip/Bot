"""
Telegram Video Downloader Bot
Instagram, YouTube, TikTok, Snapchat va boshqa 1000+ saytdan video yuklab beradi.

O'RNATISH:
    pip install python-telegram-bot yt-dlp --upgrade

    yt-dlp uchun ffmpeg ham kerak (video+audio birlashtirish uchun):
    - Windows: https://ffmpeg.org/download.html dan yuklab, PATH ga qo'shing
    - Linux:   sudo apt install ffmpeg
    - Mac:     brew install ffmpeg

ISHGA TUSHIRISH:
    1. @BotFather orqali Telegram bot yarating va TOKEN oling
    2. Pastdagi BOT_TOKEN o'zgaruvchisiga tokeningizni qo'ying
    3. python video_downloader_bot.py

ESLATMA:
    - Faqat OMMAVIY (public) postlar/videolarni yuklab olish mumkin.
    - Ba'zi platformalar (masalan Instagram private akkauntlar) login talab qilishi mumkin.
    - Mualliflik huquqi bilan himoyalangan kontentni ruxsatsiz tarqatish noqonuniy
      bo'lishi mumkin — botdan faqat o'zingiz uchun / qonuniy maqsadlarda foydalaning.
"""

import asyncio
import html
import json
import logging
import os
import re
import uuid

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
import yt_dlp

# ============ SOZLAMALAR ============
BOT_TOKEN = "8522202095:AAGsaeux2PKg83yv8jtEnU9dLWwClNOMyWY"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
KINO_CODES_FILE = os.path.join(BASE_DIR, "kino_codes.json")
MAX_FILE_SIZE_MB = 5000
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# FFmpeg va Node.js yo'llarini sozlash
FFMPEG_PATH = r"C:\Users\DarkNight\AppData\Local\Programs\Python\Python313\Scripts\ffmpeg.exe"
if not os.path.exists(FFMPEG_PATH):
    try:
        import imageio_ffmpeg
        FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        FFMPEG_PATH = None

NODE_PATH = r"C:\Program Files\nodejs\node.exe"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

URL_REGEX = re.compile(r"https?://\S+")

# Asosiy menyu tugmalari
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🎬 Kino yuklash (MP4)")],
        [KeyboardButton("🎵 Musiqa yuklash (MP3)"), KeyboardButton("📥 Havoladan yuklash")],
        [KeyboardButton("ℹ️ Yordam / Qo'llanma")],
    ],
    resize_keyboard=True,
)

# Mashhur kinolar bazasi (Kino kodlari)
DEFAULT_KINO_CODES = {
    "1": {
        "title": "Forsaj 10 (Fast X)",
        "year": "2023",
        "genre": "Jangari, Triller",
        "desc": "Dominik Toretto va uning oilasi bu safar eng shafqatsiz dushmani Dante bilan to'qnash keladi.",
        "poster": "https://m.media-amazon.com/images/M/MV5BNzZmOTU1ZTEtYzVhNi00NzQxLWI5ZjAtNWNhNjEwY2E3YmZjXkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg",
        "url": "https://www.youtube.com/results?search_query=forsaj+10+uzbek+tilida",
    },
    "2": {
        "title": "Avatar 2: Suv yo'li",
        "year": "2022",
        "genre": "Fantastika, Sarguzasht",
        "desc": "Jeyk Salli va Neytiri Pandorada yangi xavf-xatarlarga qarshi kurashadilar.",
        "poster": "https://m.media-amazon.com/images/M/MV5BYjhiNjBlODctY2ZiOC00YjVlLWFlNzAtNTVhNzM1YjI1NzMxXkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg",
        "url": "https://www.youtube.com/results?search_query=avatar+2+suv+yoli+uzbek+tilida",
    },
    "3": {
        "title": "Qasoskorlar: Intiho",
        "year": "2019",
        "genre": "Fantastika, Jangari",
        "desc": "Qasoskorlar Tanos yetkazgan zararni tuzatish va koinotni qutqarish uchun oxirgi jangga kirishadi.",
        "poster": "https://m.media-amazon.com/images/M/MV5BMTc5MDE2ODcwNV5BMl5BanBnXkFtZTgwMzI2NzQ2NzM@._V1_FMjpg_UX1000_.jpg",
        "url": "https://www.youtube.com/results?search_query=qasoskorlar+intiho+uzbek+tilida",
    },
    "4": {
        "title": "O'rgimchak odam: Uyga yo'l yo'q",
        "year": "2021",
        "genre": "Fantastika, Jangari",
        "desc": "Piter Parker shaxsi fosh bo'lgach, Doktor Strenjdan yordam so'raydi, biroq multikoinot xavfi yuzaga keladi.",
        "poster": "https://m.media-amazon.com/images/M/MV5BMmFiZGZjMmEtMTA0Ni00MzA2LTljMTYtZGI2MGJmZWYzZTQ2XkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg",
        "url": "https://www.youtube.com/results?search_query=orgimchak+odam+uyga+yol+yoq+uzbek+tilida",
    },
    "5": {
        "title": "Jentlmenlar (The Gentlemen)",
        "year": "2020",
        "genre": "Kriminal, Komediya",
        "desc": "London nufuzli narkobaroni o'z biznesini sotmoqchi bo'ladi, lekin buni bilgan to'dalar o'yin boshlashadi.",
        "poster": "https://m.media-amazon.com/images/M/MV5BMTlkMmVhNzctZDRkNS00N2E5LTk2YTAtODAwYTkyODMwOTZhXkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg",
        "url": "https://www.youtube.com/results?search_query=jentlmenlar+uzbek+tilida",
    },
    "6": {
        "title": "Interstellar (Yulduzlararo)",
        "year": "2014",
        "genre": "Fantastika, Drama",
        "desc": "Insoniyat Yer yuzida halokatga yuz tutganda, fazogirlar yangi sayyora izlashga jo'naydi.",
        "poster": "https://m.media-amazon.com/images/M/MV5BYzdjMDAxZGItMjI2My00ODA1LTlkNzItOWFjMDU5ZDJlYWY3XkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg",
        "url": "https://www.youtube.com/results?search_query=interstellar+uzbek+tilida",
    },
    "7": {
        "title": "Titanik (Titanic)",
        "year": "1997",
        "genre": "Drama, Romantika",
        "desc": "Tarixdagi eng ulkan kemada ikki yoshning muhabbat hikoyasi va fojia.",
        "poster": "https://m.media-amazon.com/images/M/MV5BYzYyN2FiZmUtYWYzMy00MzViLWJkZTMtOGY1ZjgzNWMwN2YxXkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg",
        "url": "https://www.youtube.com/results?search_query=titanik+uzbek+tilida",
    },
    "8": {
        "title": "Jon Uik 4 (John Wick 4)",
        "year": "2023",
        "genre": "Jangari, Triller",
        "desc": "Jon Uik Oliy Kengashga qarshi so'nggi va eng xavfli jangga kirishadi.",
        "poster": "https://m.media-amazon.com/images/M/MV5BNmU4M2E1YmYtYzI5Yy00OGJkLTkyZTctMTYyMzliNDAxM2VlXkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg",
        "url": "https://www.youtube.com/results?search_query=jon+uik+4+uzbek+tilida",
    },
    "9": {
        "title": "Mahallada duv-duv gap",
        "year": "1960",
        "genre": "Klassika, Komediya",
        "desc": "O'zbek kinosining nodir durdonasi, sevimli qahramonlar va unutilmas dialoglar.",
        "poster": "https://upload.wikimedia.org/wikipedia/uz/thumb/b/b3/Mahallada_duv-duv_gap.jpg/800px-Mahallada_duv-duv_gap.jpg",
        "url": "https://www.youtube.com/results?search_query=mahallada+duv-duv+gap+uzbekfilm",
    },
    "10": {
        "title": "Shum bola",
        "year": "1977",
        "genre": "Klassika, Sarguzasht",
        "desc": "G'afur G'ulom qissasi asosidagi mashhur o'zbek kinosi.",
        "poster": "https://i.ytimg.com/vi/qEGgJzugfNE/hqdefault.jpg",
        "url": "https://www.youtube.com/results?search_query=shum+bola+uzbekfilm",
    },
    "11": {
        "title": "Astral 5: Qizil eshik (Insidious)",
        "year": "2023",
        "genre": "Qo'rqinchli, Triller, Ujas",
        "desc": "Lambertlar oilasi dahshatli iblislarni butunlay daf qilish uchun narigi dunyo tubiga tushadilar.",
        "poster": "https://m.media-amazon.com/images/M/MV5BMmM0NzM4ZGUtODJjYS00MzRkLWE5NWYtMjFmYTQwMzE3MmM5XkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg",
        "url": "https://www.youtube.com/results?search_query=astral+qizil+eshik+uzbek+tilida",
    },
    "12": {
        "title": "La'nat (The Conjuring)",
        "year": "2013",
        "genre": "Qo'rqinchli, Detektiv, Ujas",
        "desc": "Ed va Lorreyn Uorren sirli va xavfli qora kuchlar bilan to'qnash kelishadi.",
        "poster": "https://m.media-amazon.com/images/M/MV5BMTM3NjA1NDMyMV5BMl5BanBnXkFtZTcwMDQzNDMzOQ@@._V1_FMjpg_UX1000_.jpg",
        "url": "https://www.youtube.com/results?search_query=lanat+conjuring+uzbek+tilida",
    },
    "13": {
        "title": "Monaxinya 2 (The Nun 2)",
        "year": "2023",
        "genre": "Qo'rqinchli, Ujas, Sirli",
        "desc": "Iblis Valak yana qaytadi va Yevropa monastirlarida qonli hodisalar boshlanadi.",
        "poster": "https://m.media-amazon.com/images/M/MV5BN2E3NjY0YjQtY2FjYi00YzM1LWFjNzQtMGQ3YjZlNDU4YmUzXkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg",
        "url": "https://www.youtube.com/results?search_query=monaxinya+2+uzbek+tilida",
    },
    "14": {
        "title": "U (IT / Оно)",
        "year": "2017",
        "genre": "Qo'rqinchli, Drama, Ujas",
        "desc": "Derri shahrida bolalar g'oyib bo'la boshlaydi. Bolalar yovuz masxaraboz Pennivaysga qarshi chiqadilar.",
        "poster": "https://m.media-amazon.com/images/M/MV5BYzg1ZDYxNmQtOWNhNi00MTc4LTg4YjQtMDRmM2ZlOWE3MmRmXkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg",
        "url": "https://www.youtube.com/results?search_query=it+ono+uzbek+tilida",
    },
    "15": {
        "title": "Sinister (Qabihlik)",
        "year": "2012",
        "genre": "Qo'rqinchli, Detektiv, Ujas",
        "desc": "Yozuvchi yangi uy chortog'idan topilgan videotasmalardagi dahshatli sirlarni fosh qiladi.",
        "poster": "https://m.media-amazon.com/images/M/MV5BMjI5MTg1Njg0Ml5BMl5BanBnXkFtZTcwNzg2Mjc4OA@@._V1_FMjpg_UX1000_.jpg",
        "url": "https://www.youtube.com/results?search_query=sinister+uzbek+tilida",
    },
    "16": {
        "title": "Jipers Kripers (Jeepers Creepers)",
        "year": "2001",
        "genre": "Qo'rqinchli, Triller, Ujas",
        "desc": "Har 23 yilda 23 kunga uyg'onadigan qonxo'r maxluq.",
        "poster": "https://m.media-amazon.com/images/M/MV5BZGQ1OWJmNDMtYzZiYi00NzI2LTgyZDUtOTljYzA1Y2VjNTFhXkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg",
        "url": "https://www.youtube.com/results?search_query=jipers+kripers+uzbek+tilida",
    },
    "17": {
        "title": "O'liklar tirilishi (Evil Dead Rise)",
        "year": "2023",
        "genre": "Qo'rqinchli, Qonli, Ujas",
        "desc": "Qadimgi kitob o'qilgach, binoga qonxo'r iblislar bostirib kiradi.",
        "poster": "https://m.media-amazon.com/images/M/MV5BMmZiN2VmMjktZDE5OC00ZWRmLWFlMmEtYWViMTY4NjM3ZmNkXkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg",
        "url": "https://www.youtube.com/results?search_query=evil+dead+rise+uzbek+tilida",
    },
    "18": {
        "title": "Qo'g'irchoq Anabel (Annabelle)",
        "year": "2014",
        "genre": "Qo'rqinchli, Ujas",
        "desc": "La'nati qo'g'irchoq oilaning uyiga kirib olib, dahshatli hodisalarni boshlaydi.",
        "poster": "https://m.media-amazon.com/images/M/MV5BOTQwZmQyYzEtODk5ZC00OTY3LWExMjAtYzRjNWFhNGM3MzBlXkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg",
        "url": "https://www.youtube.com/results?search_query=annabelle+uzbek+tilida",
    },
    "19": {
        "title": "Jimjitlik joyi (A Quiet Place)",
        "year": "2018",
        "genre": "Qo'rqinchli, Fantastika, Drama",
        "desc": "Ovozga qarab hujum qiladigan dahshatli yirtqichlar hukmron dunyo.",
        "poster": "https://m.media-amazon.com/images/M/MV5BMjI0MDMzNTQ0M15BMl5BanBnXkFtZTgwMTM5NzM3NDM@._V1_FMjpg_UX1000_.jpg",
        "url": "https://www.youtube.com/results?search_query=jimjitlik+joyi+uzbek+tilida",
    },
    "20": {
        "title": "Iblisga o'lja (Prey for the Devil)",
        "year": "2022",
        "genre": "Qo'rqinchli, Ujas",
        "desc": "Yosh rohiba birinchi bor shayton haydash marosimida eng qudratli iblis bilan yuzlashadi.",
        "poster": "https://m.media-amazon.com/images/M/MV5BZDUxMGM4OWQtYTM3YS00MzI0LTk4MTYtZTBkMjliNDg0M2Q3XkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg",
        "url": "https://www.youtube.com/results?search_query=iblisga+olja+tarjima+kino+uzbek+tilida",
    },
}


def load_kino_codes() -> dict:
    """Kino kodlarini fayldan yuklash."""
    if os.path.exists(KINO_CODES_FILE):
        try:
            with open(KINO_CODES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_KINO_CODES.copy()


def save_kino_codes(data: dict):
    """Kino kodlarini faylga saqlash."""
    try:
        with open(KINO_CODES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Kino kodlarini saqlashda xatolik: %s", e)


SUPPORTED_HINT = (
    "🤖 <b>Bot imkoniyatlari:</b>\n\n"
    "1️⃣ <b>🎬 Kino yuklash (MP4):</b>\n"
    "   Shunchaki kino nomini yozing (masalan: <code>Shum bola</code>, <code>Forsaj</code>, <code>Qorqimchi</code>, <code>Avatar</code>).\n"
    "   Bot kinoni internet va YouTube dan qidirib topib, to'g'ridan-to'g'ri <b>MP4 formatida</b> yuklab beradi!\n\n"
    "2️⃣ <b>🎵 Musiqa yuklash (MP3):</b>\n"
    "   Qo'shiq nomi yoki ijrochini yozing (masalan: <code>Konsta Odamlar nima deydi</code>).\n\n"
    "3️⃣ <b>📥 Havoladan yuklash:</b>\n"
    "   YouTube, Instagram, TikTok yoki boshqa tarmoq linkini yuboring!\n"
)


def format_duration(seconds: int | float | None) -> str:
    """Soniyalarni mm:ss yoki hh:mm:ss formatga o'tkazish."""
    if not seconds:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def format_movie_duration(seconds: int | float | None) -> str:
    """Kinolar davomiyligini chiroyli formatda chiqarish."""
    if not seconds:
        return "Noma'lum"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h} soat {m} daqiqa"
    return f"{m} daqiqa"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name if update.effective_user else "Foydalanuvchi"
    await update.message.reply_text(
        f"Salom, {html.escape(user_name)}! 👋\n\n"
        "Men musiqa qidiruvchi va video yuklovchi botman.\n\n"
        + SUPPORTED_HINT +
        "\n👇 Kerakli bo'limni tanlang yoki to'g'ridan-to'g'ri yozing:",
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_KEYBOARD,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        SUPPORTED_HINT,
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_KEYBOARD,
    )


def build_ydl_opts(out_template: str) -> dict:
    """yt-dlp sozlamalari."""
    opts = {
        "outtmpl": out_template,
        "format": (
            "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/"
            "bestvideo[height<=1080]+bestaudio/"
            "best[ext=mp4][height<=1080]/"
            "best[height<=720]/"
            "best"
        ),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "socket_timeout": 30,
    }
    if FFMPEG_PATH and os.path.exists(FFMPEG_PATH):
        opts["ffmpeg_location"] = FFMPEG_PATH
    if os.path.exists(NODE_PATH):
        opts["js_runtimes"] = {"node": {}}
    return opts


def _extract_and_download(url: str, out_template: str):
    """Sinxron yuklash funksiyasi (thread ichida ishlatiladi)."""
    ydl_opts = build_ydl_opts(out_template)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=True)


async def download_media(url: str, file_id: str) -> tuple[str, str]:
    """Videoni yuklab, (fayl_yo'li, sarlavha) ni qaytaradi."""
    out_template = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")

    # asyncio.to_thread orqali botni qotirmasdan yuklab olish
    info = await asyncio.to_thread(_extract_and_download, url, out_template)

    title = ""
    if info:
        if "entries" in info and info["entries"]:
            first = next((e for e in info["entries"] if e), None)
            if first:
                title = first.get("title", "")
        else:
            title = info.get("title", "")

    matching_files = [
        os.path.join(DOWNLOAD_DIR, f)
        for f in os.listdir(DOWNLOAD_DIR)
        if f.startswith(file_id) and not f.endswith((".part", ".ytdl"))
    ]

    if not matching_files:
        raise FileNotFoundError("Yuklangan fayl topilmadi.")

    mp4_candidates = [f for f in matching_files if f.lower().endswith(".mp4")]
    if mp4_candidates:
        chosen_file = mp4_candidates[0]
    else:
        chosen_file = max(matching_files, key=os.path.getsize)

    return chosen_file, title


def build_audio_ydl_opts(out_template: str) -> dict:
    """yt-dlp musiqa yuklash va MP3 ga aylantirish sozlamalari."""
    opts = {
        "outtmpl": out_template,
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "socket_timeout": 30,
    }
    if FFMPEG_PATH and os.path.exists(FFMPEG_PATH):
        opts["ffmpeg_location"] = FFMPEG_PATH
    if os.path.exists(NODE_PATH):
        opts["js_runtimes"] = {"node": {}}
    return opts


def _search_youtube_task(query: str, limit: int = 5) -> list[dict]:
    """YouTube dan musiqa qidirish (tezkor flat extract)."""
    search_query = f"ytsearch{limit}:{query}"
    opts = {
        "extract_flat": True,
        "quiet": True,
        "no_warnings": True,
    }
    if os.path.exists(NODE_PATH):
        opts["js_runtimes"] = {"node": {}}
    with yt_dlp.YoutubeDL(opts) as ydl:
        res = ydl.extract_info(search_query, download=False)
        entries = res.get("entries", []) if res else []
        results = []
        for e in entries:
            if not e:
                continue
            results.append(
                {
                    "id": e.get("id"),
                    "title": e.get("title", "Nomsiz musiqa"),
                    "duration": e.get("duration"),
                    "uploader": e.get("uploader") or e.get("channel") or "",
                }
            )
        return results


async def search_music(query: str, limit: int = 5) -> list[dict]:
    """Musiqalarni qidirish (asinxron)."""
    return await asyncio.to_thread(_search_youtube_task, query, limit)


def _search_movie_task(query: str, limit: int = 5) -> list[dict]:
    """Kinoni YouTube dan qidirish."""
    clean_query = query.strip()
    if not any(k in clean_query.lower() for k in ["kino", "film", "tarjima"]):
        search_query = f"ytsearch{limit}:{clean_query} tarjima kino to'liq"
    else:
        search_query = f"ytsearch{limit}:{clean_query}"

    opts = {
        "extract_flat": True,
        "quiet": True,
        "no_warnings": True,
    }
    if os.path.exists(NODE_PATH):
        opts["js_runtimes"] = {"node": {}}

    with yt_dlp.YoutubeDL(opts) as ydl:
        res = ydl.extract_info(search_query, download=False)
        entries = res.get("entries", []) if res else []
        results = []
        for e in entries:
            if not e:
                continue
            thumb = ""
            thumbnails = e.get("thumbnails")
            if thumbnails and isinstance(thumbnails, list):
                thumb = thumbnails[-1].get("url", "")
            results.append(
                {
                    "id": e.get("id"),
                    "title": e.get("title", "Nomsiz kino"),
                    "duration": e.get("duration"),
                    "uploader": e.get("uploader") or e.get("channel") or "",
                    "thumbnail": thumb,
                }
            )
        return results


async def search_movies(query: str, limit: int = 5) -> list[dict]:
    """Kinoni qidirish (asinxron)."""
    return await asyncio.to_thread(_search_movie_task, query, limit)


async def process_kino_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """Kinoni qidirish va natijalarni chiqarish."""
    clean_q = query.strip().lstrip("#")
    kino_codes = load_kino_codes()
    if clean_q in kino_codes:
        kino = kino_codes[clean_q]
        caption = (
            f"🎬 <b>Kino kodi: #{clean_q}</b>\n\n"
            f"🎞 <b>Nomi:</b> {kino['title']} ({kino.get('year', '')})\n"
            f"🎭 <b>Janri:</b> {kino.get('genre', '')}\n"
            f"📝 <b>Tavsif:</b> {kino.get('desc', '')}\n\n"
            "👇 <i>Kinoni tomosha qilish uchun quyidagi tugmani bosing:</i>"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ Onlayn tomosha qilish", url=kino.get("url", "https://youtube.com"))]
        ])
        poster = kino.get("poster")
        if poster:
            try:
                await update.message.reply_photo(
                    photo=poster,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb,
                )
                return
            except Exception:
                pass
        await update.message.reply_text(
            caption,
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
        )
        return

    status_msg = await update.message.reply_text(
        f"🔍 <i>\"{html.escape(query)}\"</i> bo'yicha kinolar qidirilmoqda...",
        parse_mode=ParseMode.HTML,
    )
    try:
        results = await search_movies(query, limit=5)
        if not results:
            await status_msg.edit_text(
                f"❌ <b>\"{html.escape(query)}\"</b> bo'yicha kino topilmadi.\n\n"
                "💡 Boshqa nom bilan qidirib ko'ring yoki kino kodini kiriting.",
                parse_mode=ParseMode.HTML,
            )
            return

        buttons = []
        text_lines = [f"🎬 <b>\"{html.escape(query)}\" bo'yicha topilgan kinolar:</b>\n"]

        for idx, movie in enumerate(results, 1):
            m_id = movie["id"]
            m_title = movie["title"]
            dur_str = format_movie_duration(movie.get("duration"))
            text_lines.append(f"{idx}. <b>{html.escape(m_title)}</b> ({dur_str})")

            btn_text = f"{idx}. {m_title[:35]}"
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"kino_view_{m_id}")])

        buttons.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_search")])

        keyboard = InlineKeyboardMarkup(buttons)
        await status_msg.edit_text(
            "\n".join(text_lines)
            + "\n\n<i>Tomosha qilish yoki tanlash uchun quyidagi tugmalardan birini bosing:</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.exception("Kino qidirishda xatolik: %s", e)
        await status_msg.edit_text(f"❌ Kino qidirishda xatolik yuz berdi: {e}")


HORROR_CODES = ["11", "12", "13", "14", "15", "16", "17", "18", "19", "20"]


def is_horror_text(text: str) -> bool:
    """Foydalanuvchi qo'rqinchli kino so'raganini aniqlash."""
    clean = text.lower().replace("'", "").replace("`", "").replace("’", "").replace("ʻ", "").strip()
    return any(w in clean for w in ["qorqimchi", "qorqinchli", "qorqinli", "ujas", "horror", "daxshat", "dahshatli", "qorqinch", "strashno"])


async def show_horror_movies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Qo'rqinchli kinolar (Ujas) to'plamini chiqarish."""
    kino_codes = load_kino_codes()
    text_lines = [
        "😱 <b>Qo'rqinchli kinolar (Ujas filmlar) to'plami:</b>\n"
    ]
    buttons = []
    row = []

    for code in HORROR_CODES:
        kino = kino_codes.get(code)
        if not kino:
            continue
        title = kino["title"]
        year = kino.get("year", "")
        text_lines.append(f"• <b>#{code}</b>: {html.escape(title)} ({year})")

        btn_text = f"#{code} {title[:18]}"
        row.append(InlineKeyboardButton(btn_text, callback_data=f"kino_code_{code}"))
        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton("🔎 YouTube'dan ko'proq ujas kino qidirish", callback_data="search_kino_qorqinchli tarjima kino toliq")])
    buttons.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_search")])

    msg_text = "\n".join(text_lines) + "\n\n<i>Tomosha qilish uchun kinoni tanlang yoki kodini yuboring:</i>"
    kb = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        await update.callback_query.message.reply_text(msg_text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.message.reply_text(msg_text, parse_mode=ParseMode.HTML, reply_markup=kb)


def build_kino_ydl_opts(out_template: str) -> dict:
    """Kino yuklash uchun yt-dlp sozlamalari — tezlashtirilgan."""
    opts = {
        "outtmpl": out_template,
        # To'g'ridan 360p yoki 240p so'raymiz — kichik fayl = tez yuklanadi
        "format": (
            "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/"
            "bestvideo[height<=360]+bestaudio/"
            "best[height<=360][ext=mp4]/"
            "best[height<=360]/"
            "best[height<=480]/"
            "best"
        ),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "socket_timeout": 60,
        "retries": 5,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 4,   # 4 ta bo'lakni parallel yuklab → 4x tez
        "http_chunk_size": 5242880,            # 5 MB bo'laklar — tezroq boshlanadi
        "continuedl": True,
    }
    if FFMPEG_PATH and os.path.exists(FFMPEG_PATH):
        opts["ffmpeg_location"] = FFMPEG_PATH
    if os.path.exists(NODE_PATH):
        opts["js_runtimes"] = {"node": {}}
    return opts


async def download_and_send_kino(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """Kinoni qidirib, MP4 formatida yuklab foydalanuvchiga yuborish."""
    clean_q = query.strip()
    for prefix in ["/kino ", "kino "]:
        if clean_q.lower().startswith(prefix):
            clean_q = clean_q[len(prefix):].strip()

    msg = update.effective_message
    status_msg = await msg.reply_text(
        f"🔍 <i>\"{html.escape(clean_q)}\"</i> kinosi qidirilmoqda...",
        parse_mode=ParseMode.HTML,
    )
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VIDEO
    )

    clean_lower = clean_q.lower()

    # ---- Kontent turini aniqlash ----
    is_horror  = is_horror_text(clean_q)
    is_cartoon = any(w in clean_lower for w in [
        "multfilm", "multik", "cartoon", "anime", "animatsiya",
        "shrek", "tom va jerry", "masha", "luntik", "peppa"
    ])
    is_serial  = any(w in clean_lower for w in [
        "serial", "series", "season", "mavsum", "qism", "episode"
    ])
    is_uzbek   = any(w in clean_lower for w in [
        "o'zbek", "uzbek", "o'zbekcha", "shum bola", "mahallada",
        "uzbekfilm", "milliy", "o'zbek kino"
    ])
    has_kino_kw = any(w in clean_lower for w in [
        "kino", "film", "tarjima", "toliq", "full"
    ])

    # ---- Qidiruv so'rovlari ketma-ketligi (eng aniqdan umumiygacha) ----
    if is_cartoon:
        search_queries = [
            f"ytsearch5:{clean_q} multfilm uzbek tilida toliq",
            f"ytsearch5:{clean_q} cartoon full uzbek",
            f"ytsearch5:{clean_q} multfilm toliq",
            f"ytsearch5:{clean_q}",
        ]
    elif is_serial:
        search_queries = [
            f"ytsearch5:{clean_q} serial uzbek tilida",
            f"ytsearch5:{clean_q} series full uzbek",
            f"ytsearch5:{clean_q} full season",
            f"ytsearch5:{clean_q}",
        ]
    elif is_horror:
        search_queries = [
            f"ytsearch5:{clean_q} qorqinchli kino toliq uzbek tilida",
            f"ytsearch5:{clean_q} horror full movie uzbek",
            f"ytsearch5:{clean_q} horror full movie",
            f"ytsearch5:{clean_q}",
        ]
    elif is_uzbek or not has_kino_kw:
        # O'zbek kino yoki oddiy nom
        search_queries = [
            f"ytsearch5:{clean_q} toliq kino uzbek tilida",
            f"ytsearch5:{clean_q} full movie uzbek",
            f"ytsearch5:{clean_q} tarjima kino",
            f"ytsearch5:{clean_q} full movie",
            f"ytsearch5:{clean_q}",
        ]
    else:
        search_queries = [
            f"ytsearch5:{clean_q}",
            f"ytsearch5:{clean_q} full movie",
            f"ytsearch5:{clean_q} uzbek tilida",
        ]

    file_id = str(uuid.uuid4())
    out_template = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")

    # Multfilm va seriallar qisqaroq bo'lishi mumkin
    if is_cartoon or is_serial:
        MIN_MOVIE_DURATION = 15 * 60   # 15 daqiqa
    else:
        MIN_MOVIE_DURATION = 40 * 60   # 40 daqiqa

    def _search_and_download():
        ydl_opts_search = {
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
        }
        if os.path.exists(NODE_PATH):
            ydl_opts_search["js_runtimes"] = {"node": {}}

        def _pick_best(entries):
            if not entries:
                return None
            def dur(e):
                try:
                    return int(e.get("duration") or 0)
                except Exception:
                    return 0
            long_vids = [e for e in entries if dur(e) >= MIN_MOVIE_DURATION]
            if long_vids:
                ideal = [e for e in long_vids if dur(e) <= 180 * 60]
                return max(ideal, key=dur) if ideal else max(long_vids, key=dur)
            return max(entries, key=dur) if entries else None

        with yt_dlp.YoutubeDL(ydl_opts_search) as ydl_s:
            best_entry = None
            for sq in search_queries:
                try:
                    res = ydl_s.extract_info(sq, download=False)
                    entries = [e for e in (res.get("entries") or []) if e and e.get("id")]
                    candidate = _pick_best(entries)
                    if candidate and int(candidate.get("duration") or 0) >= MIN_MOVIE_DURATION:
                        best_entry = candidate
                        break
                    if best_entry is None and candidate:
                        best_entry = candidate
                except Exception:
                    continue

            if not best_entry:
                return None, None

            video_url = f"https://www.youtube.com/watch?v={best_entry['id']}"

        opts = build_kino_ydl_opts(out_template)
        # Internet uzilsa avtomatik qayta urinish
        import time as _time
        last_exc = None
        for attempt in range(1, 4):
            try:
                with yt_dlp.YoutubeDL(opts) as ydl_d:
                    info = ydl_d.extract_info(video_url, download=True)
                return best_entry, info
            except Exception as dl_exc:
                last_exc = dl_exc
                err_msg = str(dl_exc).lower()
                is_net = any(k in err_msg for k in [
                    "read", "connect", "timeout", "reset", "broken",
                    "eof", "connection", "network", "ssl", "errno"
                ])
                if is_net and attempt < 3:
                    _time.sleep(2 * attempt)
                    continue
                raise last_exc

    try:
        top_entry, info = await asyncio.to_thread(_search_and_download)
        if not top_entry:
            await status_msg.edit_text(
                f"❌ <b>\"{html.escape(clean_q)}\"</b> bo'yicha kino topilmadi.\nBoshqa nom bilan urinib ko'ring.",
                parse_mode=ParseMode.HTML,
            )
            return

        title = top_entry.get("title") or (info.get("title") if info else "Kino")
        video_id = top_entry.get("id", "")
        yt_link = f"https://youtu.be/{video_id}" if video_id else ""

        await status_msg.edit_text(
            f"🎬 <b>{html.escape(title)}</b> topildi!\n"
            "⏳ MP4 formatida tayyorlanmoqda, kuting...",
            parse_mode=ParseMode.HTML,
        )

        matching_files = [
            os.path.join(DOWNLOAD_DIR, f)
            for f in os.listdir(DOWNLOAD_DIR)
            if f.startswith(file_id) and not f.endswith((".part", ".ytdl"))
        ]

        if not matching_files:
            raise FileNotFoundError("Yuklangan video fayli topilmadi.")

        mp4_candidates = [f for f in matching_files if f.lower().endswith(".mp4")]
        if mp4_candidates:
            chosen_file = mp4_candidates[0]
        else:
            chosen_file = max(matching_files, key=os.path.getsize)

        size_bytes = os.path.getsize(chosen_file)
        size_mb = size_bytes / (1024 * 1024)

        if size_mb > MAX_FILE_SIZE_MB:
            await status_msg.edit_text(
                f"🎬 <b>{html.escape(title)}</b>\n\n"
                f"⚠️ Kino to'liq film bo'lgani sababli hajmi katta ({size_mb:.1f} MB).\n"
                f"Telegram bot faqat {MAX_FILE_SIZE_MB} MB gacha bo'lgan videolarni to'g'ridan-to'g'ri yubora oladi.\n\n"
                f"📥 Kinoni to'liq MP4 formatda tomosha qilish yoki yuklab olish uchun quyidagi tugmani bosing:",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("▶️ Onlayn ko'rish / Yuklab olish", url=yt_link)]
                ]) if yt_link else None
            )
            return

        await status_msg.edit_text("📤 Video yuborilmoqda...")
        safe_title = html.escape(title[:300].strip())
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username or "bot"
        caption = f"🎬 <b>{safe_title}</b>\n\n🤖 @{bot_username} orqali MP4 formatda yuklandi"

        with open(chosen_file, "rb") as vf:
            await msg.reply_video(
                video=vf,
                caption=caption,
                parse_mode=ParseMode.HTML,
                supports_streaming=True,
                read_timeout=180,
                write_timeout=180,
            )

        await status_msg.delete()

        # Video yuborilgandan keyin YouTube havolasini ham yubor
        if yt_link:
            await msg.reply_text(
                f"🔗 <b>YouTube havolasi:</b>\n{yt_link}",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("▶️ YouTube da tomosha qilish", url=yt_link)]
                ])
            )

    except Exception as e:
        logger.exception("Kino yuklashda xatolik: %s", e)
        # video_id ni olishga harakat
        _vid_id = ""
        try:
            _vid_id = top_entry.get("id", "") if top_entry else ""
        except Exception:
            pass

        if _vid_id:
            await status_msg.edit_text(
                f"⚠️ Kino yuklanayotganda xato yuz berdi.\n\n"
                f"📺 Kinoni quyidagi tugma orqali YouTube da to'liq tomosha qilishingiz mumkin:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("▶️ YouTube da tomosha qilish", url=f"https://youtu.be/{_vid_id}")]
                ])
            )
        else:
            await status_msg.edit_text(
                "❌ Kinoni yuklab bo'lmadi.\n\n"
                "Iltimos, boshqa kino nomini yozib ko'ring yoki biroz kutib qayta urinib ko'ring."
            )
    finally:
        if file_id:
            for fname in os.listdir(DOWNLOAD_DIR):
                if fname.startswith(file_id):
                    try:
                        os.remove(os.path.join(DOWNLOAD_DIR, fname))
                    except OSError:
                        pass



def _download_audio_task(url: str, out_template: str):
    opts = build_audio_ydl_opts(out_template)
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=True)


async def download_music(video_id: str, file_id: str) -> tuple[str, dict]:
    """Musiqani MP3 qilib yuklab olish."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    out_template = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")

    info = await asyncio.to_thread(_download_audio_task, url, out_template)

    expected_mp3 = os.path.join(DOWNLOAD_DIR, f"{file_id}.mp3")
    if os.path.exists(expected_mp3):
        return expected_mp3, info or {}

    for fname in os.listdir(DOWNLOAD_DIR):
        if fname.startswith(file_id) and not fname.endswith((".part", ".ytdl")):
            return os.path.join(DOWNLOAD_DIR, fname), info or {}

    raise FileNotFoundError("Musiqa fayli topilmadi.")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline tugmalar bosilganda ishlovchi funksiya."""
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    if data == "cancel_search":
        await query.edit_message_text("❌ Qidiruv bekor qilindi.")
        return

    # To'g'ridan-to'g'ri kino MP4 yuklash tugmasi bosilganda
    if data.startswith("kino_direct_dl_"):
        kino_query = data.replace("kino_direct_dl_", "").strip()
        await download_and_send_kino(update, context, kino_query)
        return

    # Barcha mavjud kino kodlari
    if data == "show_all_codes":
        kino_codes = load_kino_codes()
        lines = ["⭐ <b>Barcha mavjud kino kodlari (Top 20):</b>\n"]
        for c in sorted(kino_codes.keys(), key=lambda x: int(x) if x.isdigit() else 999):
            k = kino_codes[c]
            lines.append(f"• <b>#{c}</b>: {html.escape(k['title'])} ({k.get('year', '')}) - <i>{k.get('genre', '')}</i>")
        lines.append("\n💡 <i>Istalgan kino kodini yozib yuborsangiz (masalan: <code>11</code> yoki <code>7</code>), bot kinoni chiqarib beradi!</i>")
        await query.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
        return

    # Qo'rqinchli kinolar to'plami tugmasi
    if data == "genre_horror":
        await show_horror_movies(update, context)
        return

    # Kino kodi orqali ochish
    if data.startswith("kino_code_"):
        code = data.replace("kino_code_", "")
        kino_codes = load_kino_codes()
        if code in kino_codes:
            kino = kino_codes[code]
            caption = (
                f"🎬 <b>Kino kodi: #{code}</b>\n\n"
                f"🎞 <b>Nomi:</b> {html.escape(kino['title'])} ({kino.get('year', '')})\n"
                f"🎭 <b>Janri:</b> {kino.get('genre', '')}\n"
                f"📝 <b>Tavsif:</b> {html.escape(kino.get('desc', ''))}\n\n"
                "👇 <i>Kinoni tomosha qilish uchun quyidagi tugmani bosing:</i>"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("▶️ Onlayn tomosha qilish", url=kino.get("url", "https://youtube.com"))]
            ])
            poster = kino.get("poster")
            if poster:
                try:
                    await query.message.reply_photo(photo=poster, caption=caption, parse_mode=ParseMode.HTML, reply_markup=kb)
                    return
                except Exception:
                    pass
            await query.message.reply_text(caption, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    # Musiqa yuklab berish
    if data.startswith("song_"):
        video_id = data.replace("song_", "")
        status_msg = await query.message.reply_text("⏳ Musiqa yuklanmoqda va tayyorlanmoqda...")
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VOICE
        )

        file_id = str(uuid.uuid4())
        try:
            filepath, info = await download_music(video_id, file_id)
            title = info.get("title") or "Musiqa"
            uploader = info.get("uploader") or info.get("channel") or ""
            duration = int(info.get("duration") or 0)

            safe_title = html.escape(title[:300].strip())
            safe_artist = html.escape(uploader[:100].strip()) if uploader else ""
            bot_info = await context.bot.get_me()
            bot_username = bot_info.username or "bot"

            caption = f"🎵 <b>{safe_title}</b>"
            if safe_artist:
                caption += f"\n👤 <i>{safe_artist}</i>"
            caption += f"\n\n🤖 @{bot_username} orqali yuklandi"

            await status_msg.edit_text("📤 Musiqa yuborilmoqda...")
            with open(filepath, "rb") as audio_file:
                await query.message.reply_audio(
                    audio=audio_file,
                    title=title,
                    performer=uploader,
                    duration=duration,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    read_timeout=120,
                    write_timeout=120,
                )
            await status_msg.delete()

        except Exception as e:
            logger.exception("Musiqa yuklashda xatolik: %s", e)
            await status_msg.edit_text(f"❌ Musiqani yuklab bo'lmadi: {e}")
        finally:
            if file_id:
                for fname in os.listdir(DOWNLOAD_DIR):
                    if fname.startswith(file_id):
                        try:
                            os.remove(os.path.join(DOWNLOAD_DIR, fname))
                        except OSError:
                            pass
        return

    # Shu nomdagi kinolarni qidirish tugmasi
    if data.startswith("search_kino_"):
        query_text = data.replace("search_kino_", "").strip()
        status_msg = await query.message.reply_text(
            f"🔍 <i>\"{html.escape(query_text)}\"</i> bo'yicha kinolar qidirilmoqda...",
            parse_mode=ParseMode.HTML,
        )
        try:
            results = await search_movies(query_text, limit=5)
            if not results:
                await status_msg.edit_text(f"❌ \"{html.escape(query_text)}\" bo'yicha kino topilmadi.")
                return

            buttons = []
            text_lines = [f"🎬 <b>\"{html.escape(query_text)}\" bo'yicha topilgan kinolar:</b>\n"]
            for idx, movie in enumerate(results, 1):
                m_id = movie["id"]
                m_title = movie["title"]
                dur_str = format_movie_duration(movie.get("duration"))
                text_lines.append(f"{idx}. <b>{html.escape(m_title)}</b> ({dur_str})")
                btn_text = f"{idx}. {m_title[:35]}"
                buttons.append([InlineKeyboardButton(btn_text, callback_data=f"kino_view_{m_id}")])

            buttons.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_search")])
            await status_msg.edit_text(
                "\n".join(text_lines) + "\n\n<i>Kinoni tanlang:</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        except Exception as e:
            await status_msg.edit_text(f"❌ Qidiruvda xatolik yuz berdi: {e}")
        return

    # Tanlangan kinoning batafsil kartasi
    if data.startswith("kino_view_"):
        video_id = data.replace("kino_view_", "")
        url = f"https://www.youtube.com/watch?v={video_id}"

        def _get_info():
            with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True}) as ydl:
                return ydl.extract_info(url, download=False)

        info = await asyncio.to_thread(_get_info)
        title = info.get("title", "Kino") if info else "Kino"
        duration = format_movie_duration(info.get("duration") if info else 0)
        channel = info.get("uploader") or info.get("channel") or "" if info else ""
        thumb = ""
        if info and info.get("thumbnails"):
            thumb = info["thumbnails"][-1].get("url", "")

        card_caption = (
            f"🎬 <b>{html.escape(title)}</b>\n\n"
            f"⏱ <b>Davomiyligi:</b> {duration}\n"
        )
        if channel:
            card_caption += f"📺 <b>Kanal:</b> {html.escape(channel)}\n"
        card_caption += (
            f"\n🔗 <b>Havola:</b> https://youtu.be/{video_id}\n\n"
            "👇 <i>Kinoni tomosha qilish uchun quyidagi tugmani bosing:</i>"
        )

        buttons = [
            [InlineKeyboardButton("▶️ Onlayn tomosha qilish", url=f"https://youtu.be/{video_id}")],
            [InlineKeyboardButton("📥 Telegramga yuklash (agar <50MB)", callback_data=f"kino_dl_{video_id}")],
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        if thumb:
            try:
                await query.message.reply_photo(
                    photo=thumb,
                    caption=card_caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                )
                return
            except Exception:
                pass
        await query.message.reply_text(
            card_caption,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
        return

    # Kinoni yuklash (agar 50MB dan kichik bo'lsa)
    if data.startswith("kino_dl_"):
        video_id = data.replace("kino_dl_", "")
        url = f"https://www.youtube.com/watch?v={video_id}"
        status_msg = await query.message.reply_text("⏳ Kino tekshirilmoqda va yuklanmoqda...")

        file_id = str(uuid.uuid4())
        try:
            filepath, title = await download_media(url, file_id)
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            if size_mb > MAX_FILE_SIZE_MB:
                await status_msg.edit_text(
                    f"⚠️ Ushbu kinoning hajmi juda katta ({size_mb:.1f} MB).\n"
                    f"Telegram bot faqat {MAX_FILE_SIZE_MB} MB gacha bo'lgan fayllarni yubora oladi.\n\n"
                    f"▶️ Kinoni quyidagi tugma orqali to'liq tomosha qilishingiz mumkin:",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("▶️ Onlayn tomosha qilish", url=f"https://youtu.be/{video_id}")]
                    ])
                )
                return

            await status_msg.edit_text("📤 Yuborilmoqda...")
            safe_title = html.escape(title[:300].strip()) if title else "Kino"
            caption = f"🎬 <b>{safe_title}</b>\n\n🤖 @muzikchapbot orqali yuklandi"
            with open(filepath, "rb") as vf:
                await query.message.reply_video(
                    video=vf,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    supports_streaming=True,
                    read_timeout=120,
                    write_timeout=120,
                )
            await status_msg.delete()
        except Exception as e:
            logger.exception("Kino yuklashda xatolik: %s", e)
            await status_msg.edit_text(
                f"⚠️ Kinoni to'g'ridan-to'g'ri Telegramga yuklab bo'lmadi (hajmi kattaligi yoki format sababli).\n\n"
                f"▶️ Quyidagi tugma orqali bemalol tomosha qilishingiz mumkin:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("▶️ Onlayn tomosha qilish", url=f"https://youtu.be/{video_id}")]
                ])
            )
        finally:
            if file_id:
                for fname in os.listdir(DOWNLOAD_DIR):
                    if fname.startswith(file_id):
                        try:
                            os.remove(os.path.join(DOWNLOAD_DIR, fname))
                        except OSError:
                            pass
        return


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        return

    # Menyu tugmalarini tekshirish
    if text in ["🎬 Kino yuklash (MP4)", "🎬 Kino qidirish"]:
        context.user_data["mode"] = "kino"
        await update.message.reply_text(
            "🎬 <b>Kino yuklash (MP4) bo'limi:</b>\n\n"
            "Qidirayotgan kino nomini yozib yuboring (masalan: <i>Shum bola</i>, <i>Mahallada duv-duv gap</i>, <i>Qorqimchi</i>, <i>Forsaj</i>):\n\n"
            "Men uni Google va YouTube dan qidirib topib, to'g'ridan-to'g'ri <b>MP4 formatida</b> yuklab beraman!",
            parse_mode=ParseMode.HTML,
            reply_markup=MAIN_KEYBOARD,
        )
        return

    if text in ["🎵 Musiqa yuklash (MP3)", "🎵 Musiqa qidirish"]:
        context.user_data["mode"] = "music"
        await update.message.reply_text(
            "🎵 <b>Musiqa yuklash (MP3) bo'limi:</b>\n\n"
            "Qo'shiq nomi yoki ijrochini yozib yuboring (masalan: <code>Konsta Odamlar nima deydi</code>):\n\n"
            "Men uni <b>MP3 formatida</b> yuklab beraman!",
            parse_mode=ParseMode.HTML,
            reply_markup=MAIN_KEYBOARD,
        )
        return

    if text in ["📥 Havoladan yuklash", "📥 Video yuklash"]:
        context.user_data["mode"] = None
        await update.message.reply_text(
            "📥 <b>Havoladan yuklash</b>\n\n"
            "Menga YouTube, Instagram, TikTok yoki boshqa tarmoqlardan video linkini yuboring.\n"
            "Men uni avtomatik yuklab beraman!",
            parse_mode=ParseMode.HTML,
            reply_markup=MAIN_KEYBOARD,
        )
        return

    if text in ["ℹ️ Yordam / Qo'llanma", "ℹ️ Yordam"]:
        await help_command(update, context)
        return

    # Foydalanuvchi kino rejimida bo'lsa yoki qo'rqinchli/kino so'zlarini yozgan bo'lsa
    user_mode = context.user_data.get("mode")
    text_lower = text.lower()
    has_kino_intent = (
        user_mode == "kino"
        or is_horror_text(text)
        or any(w in text_lower for w in ["kino", "film", "serial", "multfilm", "multik", "tarjima", "uzbekfilm"])
        or text_lower.startswith("/kino")
    )

    if has_kino_intent:
        await download_and_send_kino(update, context, text)
        return

    # Kino kodi kiritilgan bo'lsa (masalan: "1", "#7")
    is_code = False
    cleaned_code = ""
    if text.isdigit():
        is_code = True
        cleaned_code = text
    elif text.startswith("#") and text[1:].isdigit():
        is_code = True
        cleaned_code = text[1:]

    if is_code:
        await process_kino_search(update, context, cleaned_code)
        return

    match = URL_REGEX.search(text)

    # Agar havola (URL) bo'lmasa:
    if not match:
        # Agar musiqa rejimida bo'lsa yoki default bo'lsa
        status_msg = await update.message.reply_text(
            f"🔍 <i>\"{html.escape(text)}\"</i> qidirilmoqda...",
            parse_mode=ParseMode.HTML,
        )
        try:
            results = await search_music(text, limit=5)
            if not results:
                await status_msg.edit_text(
                    "❌ Hech qanday natija topilmadi. Boshqa nom bilan qidirib ko'ring."
                )
                return

            buttons = []
            text_lines = [f"🎵 <b>\"{html.escape(text)}\" bo'yicha musiqalar:</b>\n"]

            for idx, song in enumerate(results, 1):
                song_id = song["id"]
                stitle = song["title"]
                dur_str = format_duration(song.get("duration"))
                text_lines.append(f"{idx}. <b>{html.escape(stitle)}</b> ({dur_str})")

                btn_text = f"{idx}. {stitle[:35]}"
                buttons.append([InlineKeyboardButton(btn_text, callback_data=f"song_{song_id}")])

            # Kinoni to'g'ridan-to'g'ri MP4 yuklash tugmasi
            buttons.append([InlineKeyboardButton(f"🎬 \"{text[:20]}\" kinosini MP4 yuklash", callback_data=f"kino_direct_dl_{text[:30]}")])
            buttons.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_search")])

            keyboard = InlineKeyboardMarkup(buttons)
            await status_msg.edit_text(
                "\n".join(text_lines)
                + "\n\n<i>Musiqa yuklash uchun raqamni yoki kinoni MP4 yuklash tugmasini bosing:</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )
        except Exception as e:
            logger.exception("Qidiruvda xatolik: %s", e)
            await status_msg.edit_text(f"❌ Qidiruvda xatolik yuz berdi: {e}")
        return

    # Havola oxiridagi keraksiz belgilarni tozalash
    url = match.group(0).rstrip(".,!?\")>]}'")
    status_msg = await update.message.reply_text("⏳ Video yuklanmoqda, kuting...")
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VIDEO
    )

    file_id = str(uuid.uuid4())
    filepath = None
    try:
        filepath, title = await download_media(url, file_id)

        size_bytes = os.path.getsize(filepath)
        size_mb = size_bytes / (1024 * 1024)

        if size_mb > MAX_FILE_SIZE_MB:
            await status_msg.edit_text(
                f"⚠️ Video juda katta ({size_mb:.1f} MB).\n"
                f"Telegram bot faqat {MAX_FILE_SIZE_MB} MB gacha bo'lgan fayllarni yubora oladi."
            )
            return

        await status_msg.edit_text("📤 Yuborilmoqda...")

        safe_title = html.escape(title[:300].strip()) if title else "Video"
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username or "bot"
        caption = f"🎬 <b>{safe_title}</b>\n\n🤖 @{bot_username} orqali yuklandi"

        ext = os.path.splitext(filepath)[1].lower()

        if ext in [".jpg", ".jpeg", ".png", ".webp"]:
            with open(filepath, "rb") as f:
                await update.message.reply_photo(
                    photo=f,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    read_timeout=60,
                    write_timeout=60,
                )
        elif ext in [".mp3", ".m4a", ".ogg", ".opus", ".wav"]:
            with open(filepath, "rb") as f:
                await update.message.reply_audio(
                    audio=f,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    read_timeout=120,
                    write_timeout=120,
                )
        else:
            try:
                with open(filepath, "rb") as f:
                    await update.message.reply_video(
                        video=f,
                        caption=caption,
                        supports_streaming=True,
                        parse_mode=ParseMode.HTML,
                        read_timeout=120,
                        write_timeout=120,
                    )
            except Exception as video_err:
                logger.warning(
                    "reply_video orqali yuborilmadi (%s), fayl (document) sifatida yuborilmoqda...",
                    video_err,
                )
                with open(filepath, "rb") as f:
                    await update.message.reply_document(
                        document=f,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                        read_timeout=120,
                        write_timeout=120,
                    )

        await status_msg.delete()

    except yt_dlp.utils.DownloadError as e:
        logger.error("Download error: %s", e)
        err_str = str(e).lower()
        if "larger than max-filesize" in err_str:
            msg = "⚠️ Fayl hajmi 50MB dan katta bo'lgani uchun yuklab olinmadi."
        elif "private" in err_str or "login" in err_str:
            msg = "🔒 Bu post yoki akkaunt yopiq (private). Faqat ommaviy (public) videolarni yuklab olish mumkin."
        elif "unavailable" in err_str or "not found" in err_str:
            msg = "❌ Ushbu video topilmadi yoki o'chirilgan."
        else:
            msg = (
                "❌ Videoni yuklab bo'lmadi.\n"
                "Sabablari:\n"
                "• Link noto'g'ri yoki video o'chirilgan\n"
                "• Akkaunt/post yopiq (private)\n"
                "• Platforma yuklashni cheklagan\n\n"
                "Boshqa havola bilan urinib ko'ring."
            )
        await status_msg.edit_text(msg)

    except Exception as e:
        logger.exception("Kutilmagan xatolik")
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {e}")

    finally:
        # Temp fayllarni tozalash
        for fname in os.listdir(DOWNLOAD_DIR):
            if fname.startswith(file_id):
                try:
                    os.remove(os.path.join(DOWNLOAD_DIR, fname))
                except OSError:
                    pass


async def kino_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/kino buyrug'i."""
    if not context.args:
        context.user_data["mode"] = "kino"
        await update.message.reply_text(
            "🎬 <b>Kino qidirish bo'limi</b>\n\n"
            "Kino nomi yoki kodini yozing (masalan: <code>/kino Forsaj</code> yoki <code>/kino 1</code>):",
            parse_mode=ParseMode.HTML,
            reply_markup=MAIN_KEYBOARD,
        )
        return
    query = " ".join(context.args)
    await process_kino_search(update, context, query)


async def add_kino_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/addkino kod Kino nomi | link - yangi kino kodi qo'shish."""
    if not context.args:
        await update.message.reply_text(
            "ℹ️ <b>Yangi kino kodi qo'shish formati:</b>\n"
            "<code>/addkino kod Kino nomi | havola</code>\n\n"
            "<i>Misol:</i>\n"
            "<code>/addkino 11 Forsaj 1 | https://youtu.be/xyz</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    raw = " ".join(context.args)
    parts = raw.split("|")
    first_part = parts[0].strip().split(maxsplit=1)
    if len(first_part) < 2:
        await update.message.reply_text(
            "❌ Noto'g'ri format. Misol: <code>/addkino 11 Forsaj 1 | https://link</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    code = first_part[0]
    title = first_part[1]
    url = parts[1].strip() if len(parts) > 1 else f"https://www.youtube.com/results?search_query={title}"

    kino_codes = load_kino_codes()
    kino_codes[code] = {
        "title": title,
        "year": "2026",
        "genre": "Kino",
        "desc": f"{title} filmi",
        "url": url,
    }
    save_kino_codes(kino_codes)
    await update.message.reply_text(
        f"✅ #{code} kod bilan <b>{html.escape(title)}</b> muvaffaqiyatli saqlandi!",
        parse_mode=ParseMode.HTML,
    )


def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or not BOT_TOKEN:
        raise SystemExit(
            "Iltimos, BOT_TOKEN o'zgaruvchisiga @BotFather bergan tokeningizni qo'ying."
        )

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .read_timeout(60)
        .write_timeout(120)
        .connect_timeout(30)
        .pool_timeout(30)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("kino", kino_command))
    app.add_handler(CommandHandler("addkino", add_kino_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
