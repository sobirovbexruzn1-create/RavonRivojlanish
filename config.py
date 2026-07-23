import os
from dotenv import load_dotenv

# Load environmental variables
load_dotenv()

# Bot Token from BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# The channels or groups that users MUST subscribe to (comma-separated list, e.g., @chan1,@chan2)
req_channels_raw = os.getenv("REQUIRED_CHANNELS", os.getenv("REQUIRED_CHANNEL", ""))
REQUIRED_CHANNELS = [c.strip() for c in req_channels_raw.split(",") if c.strip()]

# Corresponding invite links (comma-separated list, e.g., link1,link2)
req_links_raw = os.getenv("REQUIRED_CHANNEL_LINKS", os.getenv("REQUIRED_CHANNEL_LINK", "https://t.me/your_channel"))
REQUIRED_CHANNEL_LINKS = [l.strip() for l in req_links_raw.split(",") if l.strip()]

# The private channel/group where materials are stored (e.g. -100xxxxxxxx)
SOURCES_CHANNEL_ID = int(os.getenv("SOURCES_CHANNEL_ID", "0"))

# Path to the mapping database
MAPPING_FILE = os.path.join(os.path.dirname(__file__), "mapping.json")

# Define topics for semesters
SEMESTER_1_TEXT = """<b>1-semestr mavzulari:</b>

💊 <b>1-mavzu:</b> Retsepturaning Oila shifokori tayyorlashdagi ahamiyati. Retsept va uning tuzilishi. Qattiq va yumshoq dori shakllari va ularga retsept yozish qoidalari.

💊 <b>2-mavzu:</b> Enteral qo‘llaniluvchi suyuq dori shakllari va ularga retsept yozish qoidalari. Parenteral va sirtga qo‘llaniluvchi suyuq dori shakllari va ularga retsept yozish qoidalari.

💊 <b>3-mavzu:</b> Umumiy farmakologiya. Dori moddalarning farmakokinetikasi va farmakodinamikasi. Afferent nerv tizimiga ta’sir etuvchi vositalar.

💊 <b>4-mavzu:</b> M va M-N-xolinoretseptorlarga ta’sir etuvchi vositalar.

💊 <b>5-mavzu:</b> N-xolinoretseptorlarga ta’sir etuvchi vositalar.

💊 <b>6-mavzu:</b> Adrenoretseptorlarga ta’sir etuvchi vositalar.

💊 <b>7-mavzu:</b> Uyqu chaqiruvchi vositalar. Neyroleptiklar. Anksiolitiklar.

💊 <b>8-mavzu:</b> Psixostimulyatorlar. Depressiyaga qarshi vositalar.

💊 <b>9-mavzu:</b> Nafas a’zolari faoliyatiga ta’sir etuvchi vositalar."""

SEMESTER_1_MT = [
    {"id": "s1_mt1", "title": "Analgetiklar"}
]

SEMESTER_2_TEXT = """<b>2-semestr mavzulari:</b>

💊 <b>1-mavzu:</b> Antianginal vositalar. Antiaritmik vositalar.

💊 <b>2-mavzu:</b> Gipotenziv vositalar. Gipertenziv vositalar.

💊 <b>3-mavzu:</b> Hazm a’zolari tizimiga ta’sir etuvchi vositalar.

💊 <b>4-mavzu:</b> Diuretik vositalar.

💊 <b>5-mavzu:</b> Qon tizimiga ta’sir etuvchi vositalar. Antiagregant. Antikogulyant. Fibrinolitik vositalar.

💊 <b>6-mavzu:</b> Oqsil va polipeptid tuzilishga ega bo‘lgan gormonal preparatlar. Yallig‘lanishga qarshi vositalar.

💊 <b>7-mavzu:</b> Antiseptik va dezinfeksiyalovchi vositalar. Sintetik antibakterial vositalar.

💊 <b>8-mavzu:</b> Antibiotiklar.

💊 <b>9-mavzu:</b> Silga qarshi vositalar. Zamburug‘larga qarshi vositalar."""

SEMESTER_2_MT = [
    {"id": "s2_mt1", "title": "Antiateroskleroz dorilar"},
    {"id": "s2_mt2", "title": "Vitaminlar"},
    {"id": "s2_mt3", "title": "O'smalarga qarshi vositalar"},
    {"id": "s2_mt4", "title": "Gijjalarga qarshi vositalar"}
]
