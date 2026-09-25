import os
import re
import time
import logging
import threading
import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException
from flask import Flask
import config
import storage

# ──────────────────────────────────────────
# Logging
# ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
telebot.logger.setLevel(logging.WARNING)
log = logging.getLogger(__name__)

# ──────────────────────────────────────────
# Flask keep-alive server for Render
# ──────────────────────────────────────────
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ OXTA Bot ishlayapti!", 200

@app.route('/ping')
def ping():
    return "pong", 200

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

# ──────────────────────────────────────────
# Bot initialization
# ──────────────────────────────────────────
if not config.BOT_TOKEN:
    log.critical("XATOLIK: Bot tokeni sozlanmagan!")
    exit(1)

bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode=None)

# Prevent session timeout on Render
import telebot.apihelper
telebot.apihelper.SESSION_TIME_TO_LIVE = 5 * 60

mapping_lock = threading.Lock()
admin_states = {}


# ══════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════

def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


def strip_hashtags(text: str) -> str:
    """Remove hashtags and clean extra whitespace."""
    if not text:
        return ""
    cleaned = re.sub(r'#[\w_]+', '', text)
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    cleaned = re.sub(r'\n\s*\n+', '\n\n', cleaned)
    return cleaned.strip()


def safe_edit(chat_id, message_id, text, reply_markup=None, parse_mode='HTML'):
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=reply_markup, parse_mode=parse_mode)
    except ApiTelegramException as e:
        err = str(e).lower()
        if "message is not modified" in err:
            pass
        else:
            bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)


def send_materials_to_user(chat_id, mavzu: int, section: str, call_id=None):
    """Send materials of a specific section in a topic."""
    message_ids = storage.get_messages(mavzu, section)
    sec_info = config.SECTIONS.get(section, {})
    sec_title = sec_info.get("title", section.title())
    mavzu_title = config.OXTA_TOPICS.get(mavzu, f"{mavzu}-mavzu")

    if not message_ids:
        msg = f"⚠️ {mavzu}-mavzu bo'yicha <b>{sec_title}</b> hozircha yuklanmagan."
        if call_id:
            bot.answer_callback_query(call_id, "⚠️ Materiallar hozircha yuklanmagan.", show_alert=True)
        else:
            bot.send_message(chat_id, msg, parse_mode='HTML')
        return

    if not config.SOURCES_CHANNEL_ID:
        err_msg = "❌ Manbalar kanali sozlanmagan. Bot adminiga murojaat qiling."
        if call_id:
            bot.answer_callback_query(call_id, err_msg, show_alert=True)
        else:
            bot.send_message(chat_id, err_msg)
        return

    if call_id:
        bot.answer_callback_query(call_id, "⏳ Materiallar yuborilmoqda...", show_alert=False)

    success = 0
    for msg_id in message_ids:
        try:
            caption = storage.get_caption(msg_id)
            copy_kwargs = {}
            if caption is not None:
                copy_kwargs["caption"] = caption
                copy_kwargs["parse_mode"] = "HTML"

            bot.copy_message(
                chat_id=chat_id,
                from_chat_id=config.SOURCES_CHANNEL_ID,
                message_id=msg_id,
                **copy_kwargs
            )
            success += 1
            time.sleep(0.05)
        except ApiTelegramException as e:
            if "429" in str(e):
                time.sleep(2)
                try:
                    bot.copy_message(chat_id, config.SOURCES_CHANNEL_ID, msg_id, **copy_kwargs)
                    success += 1
                except Exception:
                    pass
            else:
                log.error(f"copy_message error (m={mavzu}, s={section}, id={msg_id}): {e}")

    if success == 0:
        bot.send_message(chat_id, "❌ Materiallarni yuborishda xatolik. Keyinroq urunib ko'ring.")
    else:
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("🔙 Bo'limlarga qaytish", callback_data=f"topic_{mavzu}"),
            types.InlineKeyboardButton("🏠 Asosiy menyu", callback_data="main_menu")
        )
        bot.send_message(
            chat_id,
            f"✅ <b>{mavzu}-mavzu: {sec_title}</b> bo'yicha <b>{success} ta</b> manba yuborildi.",
            reply_markup=markup,
            parse_mode='HTML'
        )


# ══════════════════════════════════════════
# KEYBOARDS
# ══════════════════════════════════════════

def kb_topics():
    """15 topics keyboard grid (3 per row)."""
    markup = types.InlineKeyboardMarkup()
    row = []
    for i in range(1, 16):
        row.append(types.InlineKeyboardButton(str(i), callback_data=f"topic_{i}"))
        if len(row) == 3:
            markup.row(*row)
            row = []
    if row:
        markup.row(*row)
    return markup


def kb_sections(mavzu: int):
    """Dynamic section keyboard: only show available sections with materials!"""
    markup = types.InlineKeyboardMarkup()
    available = storage.get_available_sections(mavzu)

    # Order of sections
    order = ["video", "praktika", "slayd", "post", "konspekt", "savollar", "test"]
    present = [s for s in order if s in available]

    # If nothing uploaded yet, show info or empty
    if not present:
        # Show all sections if admin, or empty
        pass
    else:
        # Arrange in rows of 2
        row = []
        for sec in present:
            btn_title = config.SECTIONS[sec]["btn"]
            row.append(types.InlineKeyboardButton(btn_title, callback_data=f"sec_{mavzu}_{sec}"))
            if len(row) == 2:
                markup.row(*row)
                row = []
        if row:
            markup.row(*row)

    markup.add(types.InlineKeyboardButton("⬅️ Barcha mavzular", callback_data="main_menu"))
    return markup, present


# ══════════════════════════════════════════
# USER COMMANDS
# ══════════════════════════════════════════

@bot.message_handler(commands=['start'])
def start_handler(message):
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) > 1:
        # Deep link payload
        payload = parts[1].strip()
        # Format can be m3_video or m3
        if payload.startswith("m"):
            raw = payload[1:]
            if "_" in raw:
                try:
                    m_num, sec = raw.split("_", 1)
                    send_materials_to_user(message.chat.id, int(m_num), sec)
                    return
                except Exception:
                    pass
            elif raw.isdigit():
                show_topic_menu(message.chat.id, int(raw))
                return

    send_main_menu(message.chat.id, message.from_user.first_name)


def send_main_menu(chat_id, first_name="Foydalanuvchi"):
    text = (
        f"👋 Assalomu alaykum, <b>{first_name}</b>!\n\n"
        f"🔬 <b>OXTA (Topografik Anatomiya va Operativ Xirurgiya)</b> ta'lim botiga xush kelibsiz!\n\n"
        f"Kerakli mavzuni tanlang: 👇"
    )
    # Reply keyboard with Asosiy menyu button
    rk = types.ReplyKeyboardMarkup(resize_keyboard=True)
    rk.add(types.KeyboardButton("🏠 Asosiy menyu"))

    bot.send_message(chat_id, text, reply_markup=rk, parse_mode='HTML')
    bot.send_message(chat_id, "📚 <b>1–15 mavzular ro'yxati:</b>", reply_markup=kb_topics(), parse_mode='HTML')


@bot.message_handler(func=lambda m: m.text == "🏠 Asosiy menyu")
def main_menu_reply_btn(message):
    send_main_menu(message.chat.id, message.from_user.first_name)


@bot.message_handler(commands=['help'])
def help_handler(message):
    text = (
        "ℹ️ <b>OXTA Bot qo'llanmasi:</b>\n\n"
        "• /start — Barcha 15 ta mavzuni ko'rish\n"
        "• Mavzuni tanlab, kerakli bo'limni (Video, Slayd, Konspekt...) bosing\n\n"
        "<b>Tezkor buyruqlar:</b>\n"
        "Har bir mavzu bo'limlariga to'g'ridan-to'g'ri kirish mumkin:\n"
        "• <code>/video1</code>, <code>/video2</code> ... <code>/video15</code>\n"
        "• <code>/slayd1</code> ... <code>/slayd15</code>\n"
        "• <code>/konspekt1</code> ... <code>/konspekt15</code>\n"
        "• <code>/practice1</code> ... <code>/practice15</code>\n"
        "• <code>/test1</code> ... <code>/test15</code>\n\n"
        "Admin: @RavonRivojlanish"
    )
    bot.send_message(message.chat.id, text, parse_mode='HTML')


# ══════════════════════════════════════════
# DIRECT COMMANDS (/video1, /slayd1, /test1...)
# ══════════════════════════════════════════

@bot.message_handler(regexp=r'^/(video|practice|praktika|slayd|slide|konspekt|post|savollar|test)(\d+)$')
def direct_section_command(message):
    match = re.match(r'^/(video|practice|praktika|slayd|slide|konspekt|post|savollar|test)(\d+)$', message.text.lower())
    if not match:
        return
    sec_alias = match.group(1)
    mavzu_num = int(match.group(2))

    if mavzu_num < 1 or mavzu_num > 15:
        bot.reply_to(message, "❌ Mavzu raqami 1–15 oralig'ida bo'lishi kerak.")
        return

    sec_key = config.SECTION_ALIASES.get(sec_alias)
    if not sec_key:
        return

    send_materials_to_user(message.chat.id, mavzu_num, sec_key)


# ══════════════════════════════════════════
# CALLBACK HANDLERS
# ══════════════════════════════════════════

def show_topic_menu(chat_id, mavzu: int, message_id=None):
    title = config.OXTA_TOPICS.get(mavzu, f"{mavzu}-mavzu")
    markup, present = kb_sections(mavzu)

    if present:
        text = f"🔬 <b>{mavzu}-mavzu: {title}</b>\n\nKerakli bo'limni tanlang: 👇"
    else:
        text = (
            f"🔬 <b>{mavzu}-mavzu: {title}</b>\n\n"
            f"⚠️ Ushbu mavzu bo'yicha materiallar hozircha yuklanmagan.\n"
            f"Tez kunda joylanadi!"
        )

    if message_id:
        safe_edit(chat_id, message_id, text, markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith("topic_"))
def callback_topic(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    mavzu_num = int(call.data.replace("topic_", ""))
    show_topic_menu(call.message.chat.id, mavzu_num, call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("sec_"))
def callback_section(call):
    # format: sec_3_video
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    parts = call.data.split("_")
    mavzu_num = int(parts[1])
    section = parts[2]
    send_materials_to_user(call.message.chat.id, mavzu_num, section, call_id=call.id)


@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def callback_main_menu(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    safe_edit(
        call.message.chat.id, call.message.message_id,
        "📚 <b>OXTA — 1–15 mavzular ro'yxati:</b>\n\nKerakli mavzuni tanlang 👇",
        kb_topics()
    )


# ══════════════════════════════════════════
# ADMIN PANEL & COMMANDS
# ══════════════════════════════════════════

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if not is_admin(message.from_user.id):
        return
    text = (
        "⚙️ <b>OXTA Bot Admin Paneli</b>\n\n"
        "<b>Material qo'shish:</b>\n"
        "Manbalar kanalida xabarga <b>Reply</b> qilib yozing:\n"
        "<code>/add &lt;mavzu&gt; &lt;bo'lim&gt;</code>\n\n"
        "<b>Namunalar:</b>\n"
        "• <code>/add 1 video</code> — 1-mavzu videosi\n"
        "• <code>/add 3 slayd</code> — 3-mavzu slaydlari\n"
        "• <code>/add 4 praktika</code> — 4-mavzu praktikasi\n"
        "• <code>/add 1 test</code> — 1-mavzu testlari\n"
        "• <code>/add 2 konspekt</code> — 2-mavzu konspekti\n\n"
        "<b>Boshqaruv buyruqlari:</b>\n"
        "• <code>/list</code> — Barcha saqlangan materiallar ro'yxati\n"
        "• <code>/remove 1 video &lt;msg_id&gt;</code> — Bitta xabarni o'chirish\n"
        "• <code>/clear 1 video</code> — Bo'limni tozalash\n"
        "• <code>/post</code> — Kanal uchun interaktiv post yaratish\n"
        "• <code>/deeplink 1 video</code> — Tez havola olish\n"
        "• <code>/cancel</code> — Jarayonni bekor qilish"
    )
    bot.send_message(message.chat.id, text, parse_mode='HTML')


def handle_oxta_add(message, is_channel_post=False):
    if not is_channel_post:
        if not message.from_user or not is_admin(message.from_user.id):
            return

    text = message.text or message.caption or ""
    text = re.sub(r'^/add(@\w+)?', '/add', text.strip(), flags=re.IGNORECASE)

    # Patterns:
    # 1. /add 1 video [msg_id]
    # 2. /add_1_video_[msg_id]
    parts = text.split()
    mavzu = None
    sec_alias = None
    explicit_id = None

    if text.startswith("/add_"):
        sub_parts = text[5:].split("_")
        if len(sub_parts) >= 2 and sub_parts[0].isdigit():
            mavzu = int(sub_parts[0])
            sec_alias = sub_parts[1].lower()
            if len(sub_parts) >= 3 and sub_parts[2].isdigit():
                explicit_id = int(sub_parts[2])
    elif len(parts) >= 3:
        if parts[1].isdigit():
            mavzu = int(parts[1])
            sec_alias = parts[2].lower()
            if len(parts) >= 4 and parts[3].isdigit():
                explicit_id = int(parts[3])

    if not mavzu or not sec_alias:
        bot.reply_to(
            message,
            "❌ <b>Format noto'g'ri!</b>\n"
            "Format: <code>/add &lt;mavzu&gt; &lt;bo'lim&gt;</code>\n"
            "Misol: <code>/add 1 video</code> yoki <code>/add 3 slayd</code>\n"
            "<i>(Xabarga reply qiling yoki xabar ID sini qo'shing: /add 1 video 541)</i>",
            parse_mode='HTML'
        )
        return

    if mavzu < 1 or mavzu > 15:
        bot.reply_to(message, "❌ Mavzu raqami 1–15 oralig'ida bo'lishi kerak.")
        return

    sec_key = config.SECTION_ALIASES.get(sec_alias)
    if not sec_key:
        valid_secs = ", ".join(config.SECTIONS.keys())
        bot.reply_to(message, f"❌ Noma'lum bo'lim: <code>{sec_alias}</code>\nMavjud: {valid_secs}", parse_mode='HTML')
        return

    msg_id = None
    raw_text = ""

    if explicit_id:
        msg_id = explicit_id
    elif message.reply_to_message:
        reply = message.reply_to_message
        msg_id = getattr(reply, 'forward_from_message_id', None) or reply.message_id
        raw_text = reply.caption or reply.text or ""
    else:
        bot.reply_to(
            message,
            "❌ <b>Xabar aniqlanmadi!</b>\n"
            "Biror xabarga <b>Reply</b> qilib <code>/add 1 video</code> yozing\n"
            "yoki xabar ID sini qo'shib yozing: <code>/add 1 video 541</code>",
            parse_mode='HTML'
        )
        return

    cleaned_caption = strip_hashtags(raw_text)

    with mapping_lock:
        added = storage.add_message(mavzu, sec_key, msg_id, caption=cleaned_caption if cleaned_caption else None)

    sec_title = config.SECTIONS[sec_key]["btn"]
    if added:
        bot.reply_to(message, f"✅ Xabar <b>#{msg_id}</b> → <b>{mavzu}-mavzu ({sec_title})</b> ga saqlandi!", parse_mode='HTML')
    else:
        bot.reply_to(message, f"ℹ️ Xabar <b>#{msg_id}</b> allaqachon mavjud.", parse_mode='HTML')


@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith('/add'))
def admin_add(message):
    handle_oxta_add(message, is_channel_post=False)


@bot.channel_post_handler(content_types=['text', 'audio', 'document', 'photo', 'video', 'voice'], func=lambda m: m.text and m.text.lower().startswith('/add'))
def channel_add_handler(message):
    handle_oxta_add(message, is_channel_post=True)


@bot.message_handler(commands=['remove'])
def admin_remove(message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.strip().split()
    if len(parts) < 4 or not parts[1].isdigit() or not parts[3].isdigit():
        bot.reply_to(message, "Format: <code>/remove &lt;mavzu&gt; &lt;bo'lim&gt; &lt;msg_id&gt;</code>", parse_mode='HTML')
        return

    mavzu = int(parts[1])
    sec_key = config.SECTION_ALIASES.get(parts[2].lower())
    msg_id = int(parts[3])

    if not sec_key:
        bot.reply_to(message, "❌ Noma'lum bo'lim.")
        return

    removed = storage.remove_message(mavzu, sec_key, msg_id)
    if removed:
        bot.reply_to(message, f"🗑️ Xabar #{msg_id} o'chirildi.")
    else:
        bot.reply_to(message, "❌ Xabar topilmadi.")


@bot.message_handler(commands=['clear'])
def admin_clear(message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.strip().split()
    if len(parts) < 3 or not parts[1].isdigit():
        bot.reply_to(message, "Format: <code>/clear &lt;mavzu&gt; &lt;bo'lim&gt;</code>", parse_mode='HTML')
        return

    mavzu = int(parts[1])
    sec_key = config.SECTION_ALIASES.get(parts[2].lower())
    if not sec_key:
        bot.reply_to(message, "❌ Noma'lum bo'lim.")
        return

    storage.clear_section(mavzu, sec_key)
    bot.reply_to(message, f"🗑️ <b>{mavzu}-mavzu: {sec_key}</b> to'liq tozalandi.", parse_mode='HTML')


@bot.message_handler(commands=['list'])
def admin_list(message):
    if not is_admin(message.from_user.id):
        return
    data = storage.list_all()
    if not data:
        bot.reply_to(message, "📭 Hozircha hech qanday material yuklanmagan.")
        return

    lines = ["📋 <b>OXTA materiallari statistikasi:</b>\n"]
    for m in sorted(data.keys()):
        m_title = config.OXTA_TOPICS.get(m, "")
        lines.append(f"📌 <b>{m}-mavzu: {m_title}</b>")
        for sec, cnt in data[m].items():
            s_name = config.SECTIONS.get(sec, {}).get("btn", sec)
            lines.append(f"   • {s_name}: {cnt} ta")
        lines.append("")

    bot.reply_to(message, "\n".join(lines), parse_mode='HTML')


# ══════════════════════════════════════════
# /post & /deeplink — Kanal uchun postlar
# ══════════════════════════════════════════

@bot.message_handler(commands=['cancel'])
def cancel_handler(message):
    uid = message.from_user.id
    if uid in admin_states:
        del admin_states[uid]
        bot.reply_to(message, "❌ Jarayon bekor qilindi.")
    else:
        bot.reply_to(message, "ℹ️ Faol jarayon yo'q.")


@bot.message_handler(commands=['post'])
def post_builder_start(message):
    if not is_admin(message.from_user.id):
        return

    uid = message.from_user.id
    admin_states[uid] = {"step": "choose_mavzu"}

    markup = types.InlineKeyboardMarkup()
    row = []
    for i in range(1, 16):
        row.append(types.InlineKeyboardButton(str(i), callback_data=f"post_m_{i}"))
        if len(row) == 3:
            markup.row(*row)
            row = []
    if row:
        markup.row(*row)
    markup.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data="post_cancel"))

    bot.send_message(
        message.chat.id,
        "📝 <b>OXTA Post yaratuvchi</b>\n\n1-qadam: Mavzuni tanlang 👇",
        reply_markup=markup,
        parse_mode='HTML'
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("post_m_"))
def post_mavzu_picked(call):
    uid = call.from_user.id
    if not is_admin(uid) or uid not in admin_states:
        return
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    mavzu = int(call.data.replace("post_m_", ""))
    admin_states[uid]["mavzu"] = mavzu
    admin_states[uid]["step"] = "choose_sec"

    markup = types.InlineKeyboardMarkup()
    row = []
    for sec_key, sec_val in config.SECTIONS.items():
        row.append(types.InlineKeyboardButton(sec_val["btn"], callback_data=f"post_s_{sec_key}"))
        if len(row) == 2:
            markup.row(*row)
            row = []
    if row:
        markup.row(*row)
    markup.add(types.InlineKeyboardButton("📁 Butun mavzuni olish", callback_data="post_s_all"))
    markup.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data="post_cancel"))

    m_title = config.OXTA_TOPICS.get(mavzu, "")
    safe_edit(
        call.message.chat.id, call.message.message_id,
        f"📝 <b>Post yaratuvchi</b> — {mavzu}-mavzu ({m_title})\n\n2-qadam: Qaysi bo'lim uchun havola yaratamiz? 👇",
        markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("post_s_"))
def post_sec_picked(call):
    uid = call.from_user.id
    if not is_admin(uid) or uid not in admin_states:
        return
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    sec = call.data.replace("post_s_", "")
    mavzu = admin_states[uid]["mavzu"]

    if sec == "all":
        key = f"m{mavzu}"
        sec_label = "Barcha materiallar"
    else:
        key = f"m{mavzu}_{sec}"
        sec_label = config.SECTIONS.get(sec, {}).get("btn", sec)

    admin_states[uid]["key"] = key
    admin_states[uid]["sec_label"] = sec_label
    admin_states[uid]["step"] = "ask_photo"

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("📷 Ha, rasm qo'shaman", callback_data="post_photo_yes"),
        types.InlineKeyboardButton("✏️ Yo'q, faqat matn", callback_data="post_photo_skip"),
    )
    markup.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data="post_cancel"))

    safe_edit(
        call.message.chat.id, call.message.message_id,
        f"📝 <b>Post yaratuvchi</b> — {mavzu}-mavzu ({sec_label})\n\n3-qadam: Post uchun rasm qo'shasizmi? 👇",
        markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "post_photo_yes")
def post_photo_yes(call):
    uid = call.from_user.id
    if not is_admin(uid) or uid not in admin_states:
        return
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    admin_states[uid]["step"] = "waiting_photo"
    safe_edit(call.message.chat.id, call.message.message_id, "📷 <b>Rasmni yuboring...</b>\n\n<i>Bekor qilish: /cancel</i>", None)


@bot.callback_query_handler(func=lambda call: call.data == "post_photo_skip")
def post_photo_skip(call):
    uid = call.from_user.id
    if not is_admin(uid) or uid not in admin_states:
        return
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    admin_states[uid]["photo_id"] = None
    admin_states[uid]["step"] = "waiting_text"
    safe_edit(call.message.chat.id, call.message.message_id, "✏️ <b>Post matnini yozing:</b>\n\n<i>Bekor qilish: /cancel</i>", None)


@bot.callback_query_handler(func=lambda call: call.data == "post_cancel")
def post_cancel(call):
    uid = call.from_user.id
    admin_states.pop(uid, None)
    try:
        bot.answer_callback_query(call.id, "❌ Bekor qilindi")
    except Exception:
        pass
    safe_edit(call.message.chat.id, call.message.message_id, "❌ Post yaratish bekor qilindi.", None)


@bot.message_handler(content_types=['photo'], func=lambda m: m.from_user.id in admin_states and admin_states.get(m.from_user.id, {}).get("step") == "waiting_photo")
def post_receive_photo(message):
    uid = message.from_user.id
    admin_states[uid]["photo_id"] = message.photo[-1].file_id
    admin_states[uid]["step"] = "waiting_text"
    bot.send_message(message.chat.id, "✅ Rasm qabul qilindi!\n\n✏️ <b>Endi post matnini yozing:</b>", parse_mode='HTML')


@bot.message_handler(func=lambda m: m.from_user.id in admin_states and admin_states.get(m.from_user.id, {}).get("step") == "waiting_text" and m.content_type == "text" and not m.text.startswith("/"))
def post_receive_text(message):
    uid = message.from_user.id
    admin_states[uid]["text"] = message.text
    admin_states[uid]["step"] = "waiting_btn"
    bot.send_message(message.chat.id, "✅ Matn qabul qilindi!\n\n🔘 <b>Tugmada nima yozilsin?</b>\nMasalan: <i>📥 Mavzuni olish</i>, <i>📹 Videoni ko'rish</i>", parse_mode='HTML')


@bot.message_handler(func=lambda m: m.from_user.id in admin_states and admin_states.get(m.from_user.id, {}).get("step") == "waiting_btn" and m.content_type == "text" and not m.text.startswith("/"))
def post_receive_btn(message):
    uid = message.from_user.id
    state = admin_states[uid]
    btn_text = message.text.strip()
    key = state["key"]

    try:
        me = bot.get_me()
        bot_user = me.username
    except Exception:
        bot_user = "Tibbiyot_Schoolbot"

    deep_link = f"https://t.me/{bot_user}?start={key}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(btn_text, url=deep_link))

    state["markup"] = markup
    state["deep_link"] = deep_link

    # Preview
    bot.send_message(message.chat.id, "👁 <b>Post namunasi:</b>", parse_mode='HTML')
    if state.get("photo_id"):
        bot.send_photo(message.chat.id, state["photo_id"], caption=state["text"], reply_markup=markup, parse_mode='HTML')
    else:
        bot.send_message(message.chat.id, state["text"], reply_markup=markup, parse_mode='HTML')

    action_kb = types.InlineKeyboardMarkup()
    if config.PUBLIC_CHANNEL:
        action_kb.add(types.InlineKeyboardButton(f"🚀 {config.PUBLIC_CHANNEL} ga chop etish", callback_data="post_pub_default"))
    action_kb.add(types.InlineKeyboardButton("✏️ Kanalga chop etish", callback_data="post_pub_custom"))
    action_kb.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data="post_cancel"))

    bot.send_message(
        message.chat.id,
        "👇 <b>Postni to'g'ridan-to'g'ri kanalga chiqaring:</b>\n"
        "<i>(Bot kanal nomidan chop etadi, tugmasi yo'qolmaydi!)</i>",
        reply_markup=action_kb,
        parse_mode='HTML'
    )


@bot.callback_query_handler(func=lambda call: call.data == "post_pub_default")
def post_pub_default(call):
    uid = call.from_user.id
    if not is_admin(uid) or uid not in admin_states:
        return
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    _publish_to_channel(call.message.chat.id, uid, config.PUBLIC_CHANNEL)


@bot.callback_query_handler(func=lambda call: call.data == "post_pub_custom")
def post_pub_custom(call):
    uid = call.from_user.id
    if not is_admin(uid) or uid not in admin_states:
        return
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    admin_states[uid]["step"] = "waiting_target_channel"
    safe_edit(call.message.chat.id, call.message.message_id, "📢 <b>Kanal username yoki ID sini yuboring:</b>\n\nMasalan: <code>@KanalNomi</code>\n\n<i>(Bot o'sha kanalda admin bo'lishi kerak!)</i>", None)


@bot.message_handler(func=lambda m: m.from_user.id in admin_states and admin_states.get(m.from_user.id, {}).get("step") == "waiting_target_channel" and m.content_type == "text" and not m.text.startswith("/"))
def post_target_chan_received(message):
    uid = message.from_user.id
    chan = message.text.strip()
    _publish_to_channel(message.chat.id, uid, chan)


def _publish_to_channel(notify_chat_id, uid, channel):
    if uid not in admin_states:
        return
    state = admin_states[uid]
    try:
        if state.get("photo_id"):
            bot.send_photo(channel, state["photo_id"], caption=state["text"], reply_markup=state["markup"], parse_mode='HTML')
        else:
            bot.send_message(channel, state["text"], reply_markup=state["markup"], parse_mode='HTML')

        bot.send_message(notify_chat_id, f"🎉 <b>Post {channel} kanaliga muvaffaqiyatli chop etildi!</b>", parse_mode='HTML')
        del admin_states[uid]
    except Exception as e:
        bot.send_message(notify_chat_id, f"❌ <b>Xatolik:</b>\n<code>{e}</code>\n\nBot ushbu kanalda Administrator bo'lishi shart!", parse_mode='HTML')


@bot.message_handler(commands=['deeplink'])
def admin_deeplink(message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.strip().split()
    if len(parts) < 3 or not parts[1].isdigit():
        bot.reply_to(message, "Format: <code>/deeplink &lt;mavzu&gt; &lt;bo'lim&gt;</code>\nMisol: <code>/deeplink 3 video</code>", parse_mode='HTML')
        return

    mavzu = int(parts[1])
    sec_key = config.SECTION_ALIASES.get(parts[2].lower())
    if not sec_key:
        bot.reply_to(message, "❌ Noma'lum bo'lim.")
        return

    try:
        me = bot.get_me()
        bot_user = me.username
    except Exception:
        bot_user = "Tibbiyot_Schoolbot"

    link = f"https://t.me/{bot_user}?start=m{mavzu}_{sec_key}"
    sec_btn = config.SECTIONS[sec_key]["btn"]

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(f"📥 {sec_btn}ni olish", url=link))

    bot.send_message(
        message.chat.id,
        f"🔗 <b>Tayyor havola:</b>\n<code>{link}</code>\n\n<b>Tugma namunasi:</b>",
        reply_markup=markup,
        parse_mode='HTML'
    )


# ══════════════════════════════════════════
# MAIN RUNNER
# ══════════════════════════════════════════

if __name__ == "__main__":
    log.info("OXTA veb-serveri ishga tushmoqda...")
    threading.Thread(target=run_web, daemon=True).start()

    log.info("OXTA Bot ishga tushmoqda...")
    try:
        me = bot.get_me()
        log.info(f"Bot: @{me.username} ({me.first_name})")
    except Exception as e:
        log.error(f"Bot ma'lumotlarini olishda xatolik: {e}")

    try:
        bot.set_my_commands([
            types.BotCommand("/start", "Asosiy menyu (1–15 mavzular)"),
            types.BotCommand("/help", "Qo'llanma va buyruqlar"),
        ])
    except Exception:
        pass

    log.info("OXTA Polling boshlandi...")
    bot.infinity_polling(
        timeout=10,
        long_polling_timeout=5,
        logger_level=logging.ERROR,
        restart_on_change=False
    )
