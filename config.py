import os
from dotenv import load_dotenv

# Load environmental variables
load_dotenv()

# ──────────────────────────────────────────
# Bot Token from BotFather
# ──────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ──────────────────────────────────────────
# Admin Telegram user IDs (comma-separated)
# e.g. ADMIN_IDS=123456789,987654321
# ──────────────────────────────────────────
_admin_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _admin_raw.split(",") if x.strip().isdigit()]

# ──────────────────────────────────────────
# Required subscription channels
# ──────────────────────────────────────────
req_channels_raw = os.getenv("REQUIRED_CHANNELS", os.getenv("REQUIRED_CHANNEL", ""))
REQUIRED_CHANNELS = [c.strip() for c in req_channels_raw.split(",") if c.strip()]

req_links_raw = os.getenv("REQUIRED_CHANNEL_LINKS", os.getenv("REQUIRED_CHANNEL_LINK", "https://t.me/your_channel"))
REQUIRED_CHANNEL_LINKS = [l.strip() for l in req_links_raw.split(",") if l.strip()]

# ──────────────────────────────────────────
# Source (materials) channel ID
# ──────────────────────────────────────────
SOURCES_CHANNEL_ID = int(os.getenv("SOURCES_CHANNEL_ID", "0"))

# ──────────────────────────────────────────
# JSONBin.io persistent storage
# ──────────────────────────────────────────
JSONBIN_API_KEY = os.getenv("JSONBIN_API_KEY", "")
JSONBIN_BIN_ID = os.getenv("JSONBIN_BIN_ID", "")

# ──────────────────────────────────────────
# Local fallback mapping file
# ──────────────────────────────────────────
MAPPING_FILE = os.path.join(os.path.dirname(__file__), "mapping.json")

# ══════════════════════════════════════════
# FARMAKOLOGIYA — 1-semestr
# ══════════════════════════════════════════
SEMESTER_1_TEXT = """<b>💊 Farmakologiya — 1-semestr mavzulari:</b>

<b>1-mavzu:</b> Retsepturaning ahamiyati. Retsept tuzilishi. Qattiq va yumshoq dori shakllari.

<b>2-mavzu:</b> Enteral va parenteral suyuq dori shakllari va ularga retsept yozish.

<b>3-mavzu:</b> Umumiy farmakologiya. Farmakokinetika va farmakodinamika. Afferent nerv tizimi.

<b>4-mavzu:</b> M va M-N-xolinoretseptorlarga ta'sir etuvchi vositalar.

<b>5-mavzu:</b> N-xolinoretseptorlarga ta'sir etuvchi vositalar.

<b>6-mavzu:</b> Adrenoretseptorlarga ta'sir etuvchi vositalar.

<b>7-mavzu:</b> Uyqu chaqiruvchi vositalar. Neyroleptiklar. Anksiolitiklar.

<b>8-mavzu:</b> Psixostimulyatorlar. Depressiyaga qarshi vositalar.

<b>9-mavzu:</b> Nafas a'zolari faoliyatiga ta'sir etuvchi vositalar."""

SEMESTER_1_MT = [
    {"id": "s1_mt1", "title": "📝 MT: Analgetiklar"}
]

# ══════════════════════════════════════════
# FARMAKOLOGIYA — 2-semestr
# ══════════════════════════════════════════
SEMESTER_2_TEXT = """<b>💊 Farmakologiya — 2-semestr mavzulari:</b>

<b>1-mavzu:</b> Antianginal vositalar. Antiaritmik vositalar.

<b>2-mavzu:</b> Gipotenziv vositalar. Gipertenziv vositalar.

<b>3-mavzu:</b> Hazm a'zolari tizimiga ta'sir etuvchi vositalar.

<b>4-mavzu:</b> Diuretik vositalar.

<b>5-mavzu:</b> Qon tizimiga ta'sir etuvchi vositalar. Antiagregant. Antikoagulyant. Fibrinolitik.

<b>6-mavzu:</b> Gormonal preparatlar. Yallig'lanishga qarshi vositalar.

<b>7-mavzu:</b> Antiseptik va dezinfeksiyalovchi vositalar. Sintetik antibakterial vositalar.

<b>8-mavzu:</b> Antibiotiklar.

<b>9-mavzu:</b> Silga qarshi vositalar. Zamburug'larga qarshi vositalar."""

SEMESTER_2_MT = [
    {"id": "s2_mt1", "title": "📝 MT: Antiateroskleroz dorilar"},
    {"id": "s2_mt2", "title": "📝 MT: Vitaminlar"},
    {"id": "s2_mt3", "title": "📝 MT: O'smalarga qarshi vositalar"},
    {"id": "s2_mt4", "title": "📝 MT: Gijjalarga qarshi vositalar"}
]

# ══════════════════════════════════════════
# Admin panel: valid topic keys
# ══════════════════════════════════════════
# Maps short admin commands to internal keys
# Usage: /add <alias> <number>  OR  /add <alias> mt<number>  OR  /add <alias> ad
TOPIC_ALIASES = {
    # Farmakologiya 1-semestr
    "farma": {"prefix": "s1", "max": 9, "mt_ids": ["s1_mt1"], "ad_key": "ad"},
    "f1":    {"prefix": "s1", "max": 9, "mt_ids": ["s1_mt1"], "ad_key": "ad"},
    # Farmakologiya 2-semestr
    "farma2": {"prefix": "s2", "max": 9, "mt_ids": ["s2_mt1", "s2_mt2", "s2_mt3", "s2_mt4"], "ad_key": "ad"},
    "f2":     {"prefix": "s2", "max": 9, "mt_ids": ["s2_mt1", "s2_mt2", "s2_mt3", "s2_mt4"], "ad_key": "ad"},
}
