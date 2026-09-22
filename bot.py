import os
import logging
import threading
import re
import time
import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException
from flask import Flask, request as flask_request
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
# Flask keep-alive server
# ──────────────────────────────────────────
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot ishlayapti!", 200

@app.route('/ping')
def ping():
    return "pong", 200

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

# ──────────────────────────────────────────
# Bot initialization
# ──────────────────────────────────────────
if not config.BOT_TOKEN or config.BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
    log.critical("XATOLIK: Bot tokeni sozlanmagan!")
    exit(1)

bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode=None)

# Prevent session timeout on Render
import telebot.apihelper
telebot.apihelper.SESSION_TIME_TO_LIVE = 5 * 60

mapping_lock = threading.Lock()


# ══════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════

def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


def is_subscribed(user_id: int) -> bool:
    """Check if user has joined all required channels.
    TEMPORARILY DISABLED — always returns True.
    To re-enable: uncomment the code below and remove 'return True'.
    """
    return True  # ← vaqtincha o'chirilgan

    # --- QUYIDAGI KOD VAQTINCHA O'CHIRILGAN ---
    # if not config.REQUIRED_CHANNELS:
    #     return True
    # for channel in config.REQUIRED_CHANNELS:
    #     target = channel
    #     if target.startswith('-100') or target.lstrip('-').isdigit():
    #         try:
    #             target = int(target)
    #         except ValueError:
    #             pass
    #     try:
    #         member = bot.get_chat_member(target, user_id)
    #         if member.status not in ('member', 'administrator', 'creator'):
    #             return False
    #     except Exception as e:
    #         log.warning(f"Obuna tekshirishda xatolik ({channel}): {e}")
    #         return False
    # return True


def safe_edit(chat_id, message_id, text, reply_markup=None, parse_mode='HTML'):
    """Edit a message. Falls back to sending a new one on error."""
    try:
        bot.edit_message_text(
            text, chat_id, message_id,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except ApiTelegramException as e:
        err = str(e).lower()
        if "message is not modified" in err:
            pass  # Content identical — safe to ignore
        elif "message to edit not found" in err or "message can't be edited" in err:
            bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            log.error(f"safe_edit error: {e}")
            bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)


def send_materials(chat_id, call_id, topic_key):
    """Copy messages from source channel to user."""
    message_ids = storage.get_messages(topic_key)

    if not message_ids:
        bot.answer_callback_query(
            call_id,
            "⚠️ Ushbu mavzu bo'yicha manbalar hozircha yuklanmagan.",
            show_alert=True
        )
        return

    if not config.SOURCES_CHANNEL_ID:
        bot.answer_callback_query(
            call_id,
            "❌ Manbalar kanali sozlanmagan. Bot adminiga murojaat qiling.",
            show_alert=True
        )
        return

    bot.answer_callback_query(call_id, "⏳ Manbalar yuborilmoqda...", show_alert=False)

    success = 0
    for msg_id in message_ids:
        try:
            bot.copy_message(
                chat_id=chat_id,
                from_chat_id=config.SOURCES_CHANNEL_ID,
                message_id=msg_id
                # protect_content=True  ← vaqtincha o'chirilgan
            )
            success += 1
            time.sleep(0.05)  # Avoid flood
        except ApiTelegramException as e:
            if "429" in str(e):
                time.sleep(2)
                try:
                    bot.copy_message(chat_id, config.SOURCES_CHANNEL_ID, msg_id)
                    success += 1
                except Exception:
                    pass
            else:
                log.error(f"copy_message error (topic={topic_key}, msg_id={msg_id}): {e}")

    if success == 0:
        bot.send_message(chat_id, "❌ Manbalarni yuborishda xatolik. Iltimos, keyinroq urunib ko'ring.")
    else:
        is_oxta = topic_key.startswith("oxta")
        back_key = "subject_oxta" if is_oxta else "back_to_semester"
        back_markup = types.InlineKeyboardMarkup()
        back_markup.add(types.InlineKeyboardButton("🔙 Menyuga qaytish", callback_data=back_key))
        bot.send_message(
            chat_id,
            f"✅ <b>{success} ta</b> manba yuborildi. Boshqa mavzuni tanlash uchun:",
            reply_markup=back_markup,
            parse_mode='HTML'
        )


# ══════════════════════════════════════════
# KEYBOARDS
# ══════════════════════════════════════════

def kb_subscription():
    markup = types.InlineKeyboardMarkup()
    for idx, link in enumerate(config.REQUIRED_CHANNEL_LINKS):
        label = f"📢 {idx+1}-kanalga a'zo bo'lish" if len(config.REQUIRED_CHANNEL_LINKS) > 1 else "📢 Kanalga a'zo bo'lish"
        markup.add(types.InlineKeyboardButton(label, url=link))
    markup.add(types.InlineKeyboardButton("✅ Obunani tasdiqlash", callback_data="verify_subscription"))
    return markup


def kb_category():
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("📚 Fundamental fanlar", callback_data="category_fundamental"),
        types.InlineKeyboardButton("🩺 Klinik fanlar", callback_data="category_klinik")
    )
    return markup


def kb_fundamental():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💊 Farmakologiya", callback_data="subject_farmakologiya"))
    markup.add(types.InlineKeyboardButton("🔬 OXTA", callback_data="subject_oxta"))
    markup.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_category"))
    return markup


def kb_farmakologiya():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📖 Adabiyotlar", callback_data="topic_ad"))
    markup.row(
        types.InlineKeyboardButton("📘 1-semestr", callback_data="semester_1"),
        types.InlineKeyboardButton("📕 2-semestr", callback_data="semester_2")
    )
    markup.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_subject"))
    return markup


def kb_semester(semester: int):
    """Grid keyboard 1-9 + MT topics + back."""
    markup = types.InlineKeyboardMarkup()
    mt_topics = config.SEMESTER_1_MT if semester == 1 else config.SEMESTER_2_MT
    prefix = f"s{semester}"

    row = []
    for i in range(1, 10):
        row.append(types.InlineKeyboardButton(str(i), callback_data=f"topic_{prefix}_{i}"))
        if len(row) == 3:
            markup.row(*row)
            row = []
    if row:
        markup.row(*row)

    for topic in mt_topics:
        markup.add(types.InlineKeyboardButton(topic["title"], callback_data=f"topic_{topic['id']}"))

    markup.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_subject"))
    return markup


def kb_oxta():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🤖 OXTA botiga o'tish ➡️", url="https://t.me/Tibbiyot_Schoolbot"))
    markup.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_fundamental"))
    return markup


# ══════════════════════════════════════════
# SENDERS
# ══════════════════════════════════════════

def send_welcome(message):
    first_name = message.from_user.first_name or "Foydalanuvchi"
    welcome_text = (
        f"👋 Assalomu alaykum, <b>{first_name}</b>!\n\n"
        f"🎓 <b>Ravon Rivojlanish</b> ta'lim botiga xush kelibsiz!\n\n"
        f"Bu bot tibbiyot talabalari uchun Farmakologiya va OXTA fanlaridan "
        f"o'quv materiallarini taqdim etadi.\n\n"
        f"Pastdagi tugmalardan birini tanlang 👇"
    )
    reply_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    reply_markup.add(types.KeyboardButton("🏠 Asosiy menyu"))

    bot.send_message(message.chat.id, welcome_text, parse_mode='HTML', reply_markup=reply_markup)

    if is_subscribed(message.from_user.id):
        send_category_menu(message.chat.id)
    else:
        send_subscription_request(message.chat.id)


def send_subscription_request(chat_id):
    if len(config.REQUIRED_CHANNEL_LINKS) > 1:
        text = "⛔ Botdan foydalanish uchun quyidagi kanallarimizga a'zo bo'ling, so'ngra <b>\"Obunani tasdiqlash\"</b> tugmasini bosing:"
    else:
        text = "⛔ Botdan foydalanish uchun kanalimizga a'zo bo'ling, so'ngra <b>\"Obunani tasdiqlash\"</b> tugmasini bosing:"
    bot.send_message(chat_id, text, reply_markup=kb_subscription(), parse_mode='HTML')


def send_category_menu(chat_id, message_id=None):
    text = "📂 <b>Yo'nalishni tanlang:</b>"
    if message_id:
        safe_edit(chat_id, message_id, text, kb_category())
    else:
        bot.send_message(chat_id, text, reply_markup=kb_category(), parse_mode='HTML')


# ══════════════════════════════════════════
# HANDLERS — Commands
# ══════════════════════════════════════════

@bot.message_handler(commands=['start'])
def start_handler(message):
    """Handle /start — with optional deep link payload."""
    parts = message.text.strip().split(maxsplit=1)

    if len(parts) > 1:
        # Deep link: /start <topic_key>
        topic_key = parts[1].strip()
        _handle_deeplink(message, topic_key)
    else:
        send_welcome(message)


def _handle_deeplink(message, topic_key: str):
    """Send topic materials directly when user comes from a channel deep link."""
    chat_id = message.chat.id
    first_name = message.from_user.first_name or "Foydalanuvchi"

    # Greet briefly
    bot.send_message(
        chat_id,
        f"👋 Salom, <b>{first_name}</b>! Materiallar yuklanmoqda...",
        parse_mode='HTML'
    )

    # Send materials directly
    message_ids = storage.get_messages(topic_key)

    if not message_ids:
        bot.send_message(
            chat_id,
            "⚠️ Bu mavzu bo'yicha materiallar hozircha yuklanmagan.\n\n"
            "Botning to'liq menyusini ko'rish uchun /start bosing.",
            parse_mode='HTML'
        )
        return

    if not config.SOURCES_CHANNEL_ID:
        bot.send_message(chat_id, "❌ Server xatoligi. /start bosib qayta urunib ko'ring.")
        return

    success = 0
    for msg_id in message_ids:
        try:
            bot.copy_message(
                chat_id=chat_id,
                from_chat_id=config.SOURCES_CHANNEL_ID,
                message_id=msg_id
            )
            success += 1
            time.sleep(0.05)
        except ApiTelegramException as e:
            if "429" in str(e):
                time.sleep(2)
                try:
                    bot.copy_message(chat_id, config.SOURCES_CHANNEL_ID, msg_id)
                    success += 1
                except Exception:
                    pass
            else:
                log.error(f"deeplink copy_message error (topic={topic_key}, msg_id={msg_id}): {e}")

    if success == 0:
        bot.send_message(chat_id, "❌ Manbalarni yuborishda xatolik yuz berdi. Qayta /start bosing.")
    else:
        is_oxta = topic_key.startswith("oxta")
        back_key = "subject_oxta" if is_oxta else "back_to_semester"
        back_markup = types.InlineKeyboardMarkup()
        back_markup.row(
            types.InlineKeyboardButton("🏠 Asosiy menyu", callback_data="back_to_category"),
            types.InlineKeyboardButton("🔙 Boshqa mavzular", callback_data=back_key)
        )
        bot.send_message(
            chat_id,
            f"✅ <b>{success} ta</b> manba yuborildi!\n\nBoshqa materiallarni ham ko'rmoqchimisiz?",
            reply_markup=back_markup,
            parse_mode='HTML'
        )




@bot.message_handler(func=lambda m: m.text == "🏠 Asosiy menyu")
def main_menu_btn(message):
    send_welcome(message)


@bot.message_handler(commands=['help'])
def help_handler(message):
    text = (
        "ℹ️ <b>Bot haqida:</b>\n\n"
        "Bu bot Farmakologiya va OXTA fanlaridan o'quv materiallarini yuboradi.\n\n"
        "<b>Foydalanish:</b>\n"
        "• /start — Asosiy menyuni ochish\n"
        "• Mavzuni tanlang → materiallar darhol yuboriladi\n\n"
        "<b>Muammo bo'lsa:</b>\n"
        "• Botni restart qilish uchun /start bosing\n"
        "• Admin: @RavonRivojlanish"
    )
    bot.send_message(message.chat.id, text, parse_mode='HTML')


# ══════════════════════════════════════════
# HANDLERS — Admin Panel
# ══════════════════════════════════════════

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if not is_admin(message.from_user.id):
        return
    text = (
        "⚙️ <b>Admin paneli</b>\n\n"
        "<b>Material qo'shish:</b>\n"
        "Kanalda postga reply qilib yozing:\n"
        "<code>/add f1 3</code> — Farma 1-semestr, 3-mavzu\n"
        "<code>/add f2 5</code> — Farma 2-semestr, 5-mavzu\n"
        "<code>/add f1 mt1</code> — Farma 1-semestr, MT1\n"
        "<code>/add f2 ad</code> — Farma adabiyotlari\n"
        "<code>/add oxta 7</code> — OXTA 7-mavzu\n"
        "<code>/add oxta ad</code> — OXTA adabiyotlari\n\n"
        "<b>Boshqa buyruqlar:</b>\n"
        "<code>/list</code> — Barcha saqlangan mavzular\n"
        "<code>/remove f1 3 &lt;msg_id&gt;</code> — Bitta xabarni o'chirish\n"
        "<code>/clear oxta 7</code> — Mavzuni to'liq tozalash\n\n"
        "<b>Kanal uchun tugma yaratish:</b>\n"
        "<code>/deeplink f1 3</code> — Farma 1-sem, 3-mavzu tugmasi\n"
        "<code>/deeplink oxta 7</code> — OXTA 7-mavzu tugmasi"
    )
    bot.send_message(message.chat.id, text, parse_mode='HTML')


@bot.message_handler(commands=['deeplink'])
def admin_deeplink(message):
    """Generate a deep link button for channel posts."""
    if not is_admin(message.from_user.id):
        return

    parts = message.text.strip().split()
    if len(parts) < 3:
        bot.reply_to(
            message,
            "Format: <code>/deeplink &lt;fan&gt; &lt;mavzu&gt;</code>\n"
            "Misol: <code>/deeplink f1 3</code> yoki <code>/deeplink oxta 7</code>",
            parse_mode='HTML'
        )
        return

    fan = parts[1].lower()
    mavzu = parts[2].lower()

    alias = config.TOPIC_ALIASES.get(fan)
    if not alias:
        bot.reply_to(message, f"❌ Noma'lum fan: <code>{fan}</code>", parse_mode='HTML')
        return

    # Determine the key
    if mavzu == "ad":
        key = alias["ad_key"]
        label = "Adabiyotlar"
    elif mavzu.startswith("mt"):
        mt_num = mavzu[2:]
        mt_ids = alias.get("mt_ids", [])
        if not mt_num.isdigit() or int(mt_num) < 1 or int(mt_num) > len(mt_ids):
            bot.reply_to(message, f"❌ MT raqami noto'g'ri. Mavjud: mt1 — mt{len(mt_ids)}")
            return
        key = mt_ids[int(mt_num) - 1]
        label = f"MT {mt_num}-mavzu"
    elif mavzu.isdigit():
        num = int(mavzu)
        if num < 1 or num > alias["max"]:
            bot.reply_to(message, f"❌ Raqam 1–{alias['max']} oralig'ida bo'lishi kerak.")
            return
        key = f"{alias['prefix']}_{num}"
        label = f"{num}-mavzu"
    else:
        bot.reply_to(message, "❌ Mavzu noto'g'ri. Raqam, 'ad' yoki 'mt1' kabi yozing.")
        return

    # Get bot username
    try:
        me = bot.get_me()
        bot_username = me.username
    except Exception:
        bot_username = "RavonRivojlanishbot"

    deep_link = f"https://t.me/{bot_username}?start={key}"

    # Fan name for display
    fan_names = {
        "f1": "💊 Farmakologiya 1-semestr",
        "farma": "💊 Farmakologiya 1-semestr",
        "f2": "💊 Farmakologiya 2-semestr",
        "farma2": "💊 Farmakologiya 2-semestr",
        "oxta": "🔬 OXTA",
    }
    fan_name = fan_names.get(fan, fan.upper())

    # Send preview with the button
    preview_markup = types.InlineKeyboardMarkup()
    preview_markup.add(types.InlineKeyboardButton("📥 Mavzuni olish", url=deep_link))

    bot.send_message(
        message.chat.id,
        f"✅ <b>Tayyor!</b> Quyidagi tugmani kanalingizga post sifatida joylashtiring:\n\n"
        f"<b>Fan:</b> {fan_name}\n"
        f"<b>Mavzu:</b> {label}\n"
        f"<b>Kalit:</b> <code>{key}</code>\n\n"
        f"👇 Tugma namunasi:",
        reply_markup=preview_markup,
        parse_mode='HTML'
    )

    # Also send the raw URL for manual use
    bot.send_message(
        message.chat.id,
        f"🔗 To'g'ridan-to'g'ri havola:\n<code>{deep_link}</code>\n\n"
        f"<i>Bu havolani postga inline tugma sifatida qo'shing.</i>",
        parse_mode='HTML'
    )



@bot.message_handler(commands=['add'])
def admin_add(message):
    """Add a material. Must be a reply to the message in the source channel."""
    if not is_admin(message.from_user.id):
        return

    # Must be a reply
    if not message.reply_to_message:
        bot.reply_to(message,
            "❌ Bu buyruqni ishlating:\n"
            "Kanalda postga <b>reply</b> qilib <code>/add f1 3</code> yozing.",
            parse_mode='HTML'
        )
        return

    parts = message.text.strip().split()
    if len(parts) < 3:
        bot.reply_to(message, "❌ Format: <code>/add &lt;fan&gt; &lt;mavzu&gt;</code>\nMisol: <code>/add f1 3</code>", parse_mode='HTML')
        return

    fan = parts[1].lower()
    mavzu = parts[2].lower()

    alias = config.TOPIC_ALIASES.get(fan)
    if not alias:
        bot.reply_to(message, f"❌ Noma'lum fan: <code>{fan}</code>\nMavjud: {', '.join(config.TOPIC_ALIASES.keys())}", parse_mode='HTML')
        return

    # Determine the key
    if mavzu == "ad":
        key = alias["ad_key"]
    elif mavzu.startswith("mt"):
        mt_num = mavzu[2:]
        mt_ids = alias.get("mt_ids", [])
        if not mt_num.isdigit() or int(mt_num) < 1 or int(mt_num) > len(mt_ids):
            bot.reply_to(message, f"❌ MT raqami noto'g'ri. Mavjud: mt1 — mt{len(mt_ids)}")
            return
        key = mt_ids[int(mt_num) - 1]
    elif mavzu.isdigit():
        num = int(mavzu)
        if num < 1 or num > alias["max"]:
            bot.reply_to(message, f"❌ Mavzu raqami 1–{alias['max']} oralig'ida bo'lishi kerak.")
            return
        key = f"{alias['prefix']}_{num}"
    else:
        bot.reply_to(message, "❌ Mavzu noto'g'ri. Raqam, 'ad' yoki 'mt1' kabi yozing.")
        return

    msg_id = message.reply_to_message.message_id

    with mapping_lock:
        added = storage.add_message(key, msg_id)

    if added:
        bot.reply_to(message, f"✅ Xabar <b>#{msg_id}</b> → <code>{key}</code> ga saqlandi.", parse_mode='HTML')
    else:
        bot.reply_to(message, f"ℹ️ Xabar <b>#{msg_id}</b> allaqachon <code>{key}</code> da mavjud.", parse_mode='HTML')


@bot.message_handler(commands=['remove'])
def admin_remove(message):
    if not is_admin(message.from_user.id):
        return
    # Format: /remove <fan> <mavzu> <msg_id>
    parts = message.text.strip().split()
    if len(parts) < 4:
        bot.reply_to(message, "Format: <code>/remove &lt;fan&gt; &lt;mavzu&gt; &lt;msg_id&gt;</code>", parse_mode='HTML')
        return

    fan, mavzu, msg_id_str = parts[1].lower(), parts[2].lower(), parts[3]
    if not msg_id_str.isdigit():
        bot.reply_to(message, "❌ msg_id raqam bo'lishi kerak.")
        return

    alias = config.TOPIC_ALIASES.get(fan)
    if not alias:
        bot.reply_to(message, f"❌ Noma'lum fan: {fan}")
        return

    if mavzu == "ad":
        key = alias["ad_key"]
    elif mavzu.startswith("mt"):
        mt_num = mavzu[2:]
        mt_ids = alias.get("mt_ids", [])
        key = mt_ids[int(mt_num) - 1] if mt_num.isdigit() and 0 < int(mt_num) <= len(mt_ids) else None
    elif mavzu.isdigit():
        key = f"{alias['prefix']}_{mavzu}"
    else:
        key = None

    if not key:
        bot.reply_to(message, "❌ Kalit aniqlanmadi.")
        return

    with mapping_lock:
        removed = storage.remove_message(key, int(msg_id_str))

    if removed:
        bot.reply_to(message, f"🗑️ Xabar #{msg_id_str} <code>{key}</code> dan o'chirildi.", parse_mode='HTML')
    else:
        bot.reply_to(message, f"❌ Xabar #{msg_id_str} <code>{key}</code> da topilmadi.", parse_mode='HTML')


@bot.message_handler(commands=['clear'])
def admin_clear(message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.strip().split()
    if len(parts) < 3:
        bot.reply_to(message, "Format: <code>/clear &lt;fan&gt; &lt;mavzu&gt;</code>", parse_mode='HTML')
        return

    fan, mavzu = parts[1].lower(), parts[2].lower()
    alias = config.TOPIC_ALIASES.get(fan)
    if not alias:
        bot.reply_to(message, f"❌ Noma'lum fan: {fan}")
        return

    if mavzu == "ad":
        key = alias["ad_key"]
    elif mavzu.startswith("mt"):
        mt_num = mavzu[2:]
        mt_ids = alias.get("mt_ids", [])
        key = mt_ids[int(mt_num) - 1] if mt_num.isdigit() and 0 < int(mt_num) <= len(mt_ids) else None
    elif mavzu.isdigit():
        key = f"{alias['prefix']}_{mavzu}"
    else:
        key = None

    if not key:
        bot.reply_to(message, "❌ Kalit aniqlanmadi.")
        return

    with mapping_lock:
        cleared = storage.clear_topic(key)

    if cleared:
        bot.reply_to(message, f"🗑️ <code>{key}</code> mavzusi to'liq tozalandi.", parse_mode='HTML')
    else:
        bot.reply_to(message, f"ℹ️ <code>{key}</code> da materiallar yo'q edi.", parse_mode='HTML')


@bot.message_handler(commands=['list'])
def admin_list(message):
    if not is_admin(message.from_user.id):
        return
    storage.invalidate_cache()
    topics = storage.list_topics()
    if not topics:
        bot.reply_to(message, "📭 Hech qanday material saqlanmagan.")
        return
    lines = [f"📋 <b>Saqlangan mavzular ({len(topics)} ta):</b>\n"]
    for key, count in sorted(topics):
        lines.append(f"• <code>{key}</code> — {count} ta xabar")
    bot.reply_to(message, "\n".join(lines), parse_mode='HTML')


# ══════════════════════════════════════════
# HANDLERS — Callback Queries
# ══════════════════════════════════════════

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    # Always answer immediately to stop spinner
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    data = call.data

    # ── Subscription verify ──
    if data == "verify_subscription":
        if is_subscribed(user_id):
            try:
                bot.delete_message(chat_id, message_id)
            except Exception:
                pass
            send_category_menu(chat_id)
        else:
            bot.answer_callback_query(
                call.id,
                "⛔ Siz hali kanalga a'zo bo'lmadingiz!\nA'zo bo'lib, qayta bosing.",
                show_alert=True
            )
        return

    # ── All other callbacks require subscription ──
    if not is_subscribed(user_id):
        try:
            bot.delete_message(chat_id, message_id)
        except Exception:
            pass
        send_subscription_request(chat_id)
        return

    # ── Navigation ──
    if data == "back_to_category":
        send_category_menu(chat_id, message_id)

    elif data in ("category_fundamental", "back_to_fundamental"):
        safe_edit(chat_id, message_id, "📂 <b>Fanni tanlang:</b>", kb_fundamental())

    elif data == "category_klinik":
        safe_edit(
            chat_id, message_id,
            "🩺 <b>Klinik fanlar</b>\n\nBu bo'lim tez kunda qo'shiladi. Kuzatib boring!",
            types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_category")
            )
        )

    elif data in ("back_to_subject", "subject_farmakologiya"):
        safe_edit(chat_id, message_id, "💊 <b>Farmakologiya — bo'limni tanlang:</b>", kb_farmakologiya())

    elif data == "subject_oxta":
        text = (
            "🔬 <b>OXTA (Topografik Anatomiya va Operativ Xirurgiya)</b>\n\n"
            "Ushbu fan bo'yicha barcha video darslar, taqdimotlar (slaydlar), konspektlar va darsliklar "
            "tizimli ravishda maxsus alohida botimizga joylangan.\n\n"
            "Barcha materiallardan qulay va to'liq foydalanish uchun quyidagi tugma orqali "
            "maxsus botimizga o'ting: 👇"
        )
        safe_edit(chat_id, message_id, text, kb_oxta())

    elif data == "semester_1":
        safe_edit(chat_id, message_id, config.SEMESTER_1_TEXT, kb_semester(1))

    elif data == "semester_2":
        safe_edit(chat_id, message_id, config.SEMESTER_2_TEXT, kb_semester(2))

    elif data == "back_to_semester":
        safe_edit(chat_id, message_id, "💊 <b>Farmakologiya — bo'limni tanlang:</b>", kb_farmakologiya())

    # ── Topic: materials ──
    elif data.startswith("topic_"):
        topic_key = data[len("topic_"):]
        send_materials(chat_id, call.id, topic_key)

    else:
        log.warning(f"Noma'lum callback: {data}")


# ══════════════════════════════════════════
# HANDLERS — Channel posts (hashtag, backward compat)
# ══════════════════════════════════════════

@bot.channel_post_handler(
    content_types=['text', 'audio', 'document', 'photo', 'video', 'voice'],
    func=lambda m: True
)
@bot.edited_channel_post_handler(
    content_types=['text', 'audio', 'document', 'photo', 'video', 'voice'],
    func=lambda m: True
)
def source_material_handler(message):
    if message.chat.id != config.SOURCES_CHANNEL_ID:
        return

    text = message.text or message.caption or ""
    key = None

    # Hashtag patterns (backward compatibility)
    m_farma = re.search(r'#farma_([\w]+)', text, re.IGNORECASE)
    m_mavzu = re.search(r'#mavzu(\d+)', text, re.IGNORECASE)
    m_oxta  = re.search(r'#oxta_([\w]+)', text, re.IGNORECASE)

    if m_farma:
        key = m_farma.group(1).lower()
    elif m_mavzu:
        key = m_mavzu.group(1)
    elif m_oxta:
        key = f"oxta_{m_oxta.group(1).lower()}"

    if key:
        with mapping_lock:
            added = storage.add_message(key, message.message_id)
        if added:
            log.info(f"[HASHTAG] Xabar {message.message_id} → '{key}' ga saqlandi.")


# ══════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════

if __name__ == "__main__":
    # Start Flask web server in background
    log.info("Veb-server fon rejimida ishga tushirilmoqda...")
    threading.Thread(target=run_web, daemon=True).start()

    # Print startup info
    log.info("Bot ishga tushmoqda...")
    try:
        me = bot.get_me()
        log.info(f"Bot: @{me.username} ({me.first_name})")
    except Exception as e:
        log.error(f"Bot ma'lumotlarini olishda xatolik: {e}")

    log.info(f"Manbalar kanali: {config.SOURCES_CHANNEL_ID}")
    log.info(f"Adminlar: {config.ADMIN_IDS}")
    log.info(f"Obuna kanallari: {config.REQUIRED_CHANNELS}")

    # Set bot commands
    try:
        bot.set_my_commands([
            types.BotCommand("/start", "Asosiy menyu"),
            types.BotCommand("/help",  "Yordam"),
        ])
    except Exception as e:
        log.warning(f"Komandalari o'rnatishda xatolik: {e}")

    # Pre-load mapping cache
    log.info("Ma'lumotlar yuklanmoqda...")
    storage.load_mapping()

    log.info("✅ Bot tayyor. Polling boshlandi.")
    bot.infinity_polling(
        timeout=10,
        long_polling_timeout=5,
        logger_level=logging.ERROR,
        restart_on_change=False
    )
