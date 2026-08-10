import os
import json
import re
import threading
import telebot
from telebot import types
from flask import Flask
import config

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


mapping_lock = threading.Lock()

# Initialize Bot
if not config.BOT_TOKEN or config.BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
    print("XATOLIK: Bot tokeni sozlanmagan! .env faylini to'ldiring.")
    exit(1)

bot = telebot.TeleBot(config.BOT_TOKEN)

# Load mapping from mapping.json
def load_mapping():
    try:
        if os.path.exists(config.MAPPING_FILE):
            with open(config.MAPPING_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Mapping faylini yuklashda xatolik: {e}")
    # Fallback to empty mapping
    return {str(i): [] for i in range(1, 23)}

# Save mapping to mapping.json
def save_mapping(mapping):
    try:
        with open(config.MAPPING_FILE, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Mapping faylini saqlashda xatolik: {e}")

# Check subscription status for all required channels
def is_subscribed(user_id):
    if not config.REQUIRED_CHANNELS:
        return True  # Skip check if not configured
    
    for channel in config.REQUIRED_CHANNELS:
        # Try resolving if it is username or ID
        target_channel = channel
        if target_channel.startswith('-100') or target_channel.isdigit():
            try:
                target_channel = int(target_channel)
            except ValueError:
                pass

        try:
            member = bot.get_chat_member(target_channel, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except Exception as e:
            print(f"Obuna tekshirishda xatolik ({channel} uchun, user: {user_id}): {e}")
            # Note: If the bot is not admin in the channel/group, this API call will fail.
            return False
    return True

# Main Start Message
def send_welcome(message):
    first_name = message.from_user.first_name or "Foydalanuvchi"
    
    # Greet user
    welcome_text = f"Assalomu alaykum, {first_name}.\n\n<b>Ravon Rivojlanish</b> loyihasiga xush kelibsiz!"
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🏠 Asosiy menyu"))
    
    bot.send_message(message.chat.id, welcome_text, parse_mode='HTML', reply_markup=markup)
    
    # Check subscription
    if is_subscribed(message.from_user.id):
        send_category_selection(message.chat.id)
    else:
        send_subscription_request(message.chat.id)

# Ask for subscription
def send_subscription_request(chat_id):
    markup = types.InlineKeyboardMarkup()
    
    # Add buttons for all required channels
    for idx, link in enumerate(config.REQUIRED_CHANNEL_LINKS):
        if len(config.REQUIRED_CHANNEL_LINKS) > 1:
            channel_name = f"📢 {idx+1}-kanalga a'zo bo'lish"
        else:
            channel_name = "📢 Kanalga a'zo bo'lish"
        btn_channel = types.InlineKeyboardButton(channel_name, url=link)
        markup.add(btn_channel)
        
    btn_verify = types.InlineKeyboardButton("Obunani tasdiqlash ✅", callback_data="verify_subscription")
    markup.add(btn_verify)
    
    if len(config.REQUIRED_CHANNEL_LINKS) > 1:
        text = "Botdan foydalanish uchun quyidagi kanallarimizga a'zo bo'ling, so'ngra pastdagi \"Obunani tasdiqlash ✅\" tugmasini bosing:"
    else:
        text = "Botdan foydalanish uchun kanalimizga a'zo bo'ling, so'ngra pastdagi \"Obunani tasdiqlash ✅\" tugmasini bosing:"
        
    bot.send_message(chat_id, text, reply_markup=markup)

# Send Category Selection Menu
def send_category_selection(chat_id, message_id=None):
    text = "Yo'nalishni tanlang:"
    markup = types.InlineKeyboardMarkup()
    btn_fundamental = types.InlineKeyboardButton("📚 Fundamental fanlar", callback_data="category_fundamental")
    btn_klinik = types.InlineKeyboardButton("🩺 Klinik fanlar", callback_data="category_klinik")
    markup.row(btn_fundamental, btn_klinik)
    
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
        except Exception:
            bot.send_message(chat_id, text, reply_markup=markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)

# Send Subject Selection Menu
def send_subject_selection(chat_id, message_id, category):
    markup = types.InlineKeyboardMarkup()
    
    if category == "fundamental":
        text = "Fanni tanlang:"
        btn_farma = types.InlineKeyboardButton("💊 Farmakologiya", callback_data="subject_farmakologiya")
        btn_oxta = types.InlineKeyboardButton("🔪 OXTA", callback_data="subject_oxta")
        markup.add(btn_farma)
        markup.add(btn_oxta)
    else:
        text = "Klinik fanlar bo'yicha ma'lumotlar tez kunda qo'shiladi."
        
    btn_back = types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_category")
    markup.add(btn_back)
    
    bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)

# Send Semester Selection Menu
def send_semester_selection(chat_id, message_id):
    text = "Bo'limni tanlang:"
    
    markup = types.InlineKeyboardMarkup()
    btn_ad = types.InlineKeyboardButton("📚 Adabiyotlar", callback_data="topic_ad")
    btn_sem1 = types.InlineKeyboardButton("📘 1-semestr", callback_data="semester_1")
    btn_sem2 = types.InlineKeyboardButton("📕 2-semestr", callback_data="semester_2")
    btn_back = types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_subject")
    
    markup.add(btn_ad)
    markup.row(btn_sem1, btn_sem2)
    markup.add(btn_back)
    
    bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)

# Send Topics Menu
def send_topics_menu(chat_id, message_id, semester):
    markup = types.InlineKeyboardMarkup()
    
    if semester == 1:
        text = config.SEMESTER_1_TEXT
        mt_topics = config.SEMESTER_1_MT
    else:
        text = config.SEMESTER_2_TEXT
        mt_topics = config.SEMESTER_2_MT
        
    # Add 1 to 9 numerical buttons in a 3x3 grid
    row = []
    for i in range(1, 10):
        btn = types.InlineKeyboardButton(str(i), callback_data=f"topic_s{semester}_{i}")
        row.append(btn)
        if len(row) == 3:
            markup.row(*row)
            row = []
    if row:
        markup.row(*row)
        
    # Add Independent Study (MT) buttons
    for topic in mt_topics:
        btn = types.InlineKeyboardButton(topic["title"], callback_data=f"topic_{topic['id']}")
        markup.add(btn)
        
    btn_back = types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_subject")
    markup.add(btn_back)
    
    bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='HTML')

# Send OXTA Menu
def send_oxta_menu(chat_id, message_id):
    text = config.OXTA_TEXT
    markup = types.InlineKeyboardMarkup()
    
    # Adabiyotlar at the top
    btn_adabiyotlar = types.InlineKeyboardButton("📚 Adabiyotlar", callback_data="topic_oxta_adabiyotlar")
    markup.add(btn_adabiyotlar)
    
    # Add OXTA topics (1 to 15) in a 3x5 grid
    row = []
    for i in range(1, 16):
        btn = types.InlineKeyboardButton(str(i), callback_data=f"topic_oxta_mavzu{i}")
        row.append(btn)
        if len(row) == 3:
            markup.row(*row)
            row = []
    if row:
        markup.row(*row)
        
    btn_back = types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_fundamental")
    markup.add(btn_back)
    
    bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='HTML')

# /start command handler
@bot.message_handler(commands=['start'])
def start_handler(message):
    send_welcome(message)

# Main menu button handler
@bot.message_handler(func=lambda message: message.text == "🏠 Asosiy menyu")
def main_menu_btn(message):
    send_welcome(message)

# Callback queries handler
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    # 1. Verify subscription
    if call.data == "verify_subscription":
        if is_subscribed(user_id):
            bot.answer_callback_query(call.id, "Rahmat! Obuna tasdiqlandi ✅", show_alert=False)
            # Remove subscription request message and show subjects
            try:
                bot.delete_message(chat_id, message_id)
            except Exception:
                pass
            send_category_selection(chat_id)
        else:
            bot.answer_callback_query(
                call.id, 
                "Siz hali kanalga a'zo bo'lmadingiz! Iltimos, a'zo bo'ling va qayta urunib ko'ring.", 
                show_alert=True
            )
            
    # 2. Main menu (Category)
    elif call.data == "back_to_category":
        if not is_subscribed(user_id):
            send_subscription_request(chat_id)
            return
        send_category_selection(chat_id, message_id)
        
    # 3. Category -> Fundamental
    elif call.data == "category_fundamental" or call.data == "back_to_fundamental":
        if not is_subscribed(user_id):
            send_subscription_request(chat_id)
            return
        send_subject_selection(chat_id, message_id, "fundamental")
        
    # 4. Category -> Klinik
    elif call.data == "category_klinik":
        if not is_subscribed(user_id):
            send_subscription_request(chat_id)
            return
        send_subject_selection(chat_id, message_id, "klinik")

    # 5. Back to Subject (Farmakologiya uses this)
    elif call.data == "back_to_subject":
        if not is_subscribed(user_id):
            send_subscription_request(chat_id)
            return
        send_subject_selection(chat_id, message_id, "fundamental")
        
    # 6. Subject -> Farmakologiya
    elif call.data == "subject_farmakologiya":
        if not is_subscribed(user_id):
            send_subscription_request(chat_id)
            return
        send_semester_selection(chat_id, message_id)
        
    # 7. Subject -> OXTA
    elif call.data == "subject_oxta":
        if not is_subscribed(user_id):
            send_subscription_request(chat_id)
            return
        send_oxta_menu(chat_id, message_id)
        
    # Back to Semesters
    elif call.data == "back_to_semester":
        if not is_subscribed(user_id):
            send_subscription_request(chat_id)
            return
        send_semester_selection(chat_id, message_id)
        
    # Semester 1 selected
    elif call.data == "semester_1":
        if not is_subscribed(user_id):
            send_subscription_request(chat_id)
            return
        send_topics_menu(chat_id, message_id, semester=1)
        
    # Semester 2 selected
    elif call.data == "semester_2":
        if not is_subscribed(user_id):
            send_subscription_request(chat_id)
            return
        send_topics_menu(chat_id, message_id, semester=2)
        
    # 7. Topic selected
    elif call.data.startswith("topic_"):
        if not is_subscribed(user_id):
            send_subscription_request(chat_id)
            return
            
        topic_id = call.data.split("_", 1)[1]
        
        # Load mapping database
        mapping = load_mapping()
        message_ids = mapping.get(topic_id, [])
        
        if not message_ids:
            bot.answer_callback_query(
                call.id, 
                "Ushbu mavzu bo'yicha manbalar hozircha yuklanmagan ⚠️", 
                show_alert=True
            )
            return
            
        if not config.SOURCES_CHANNEL_ID:
            bot.answer_callback_query(
                call.id,
                "Xatolik: Manbalar kanali IDsi sozlanmagan! Bot adminiga murojaat qiling.",
                show_alert=True
            )
            return

        bot.answer_callback_query(call.id, "Manbalar yuborilmoqda... 📤", show_alert=False)
        
        # Send messages from the source channel securely
        success_count = 0
        for msg_id in message_ids:
            try:
                # copy_message creates a clean copy of the message with sharing restrictions if protect_content=True
                bot.copy_message(
                    chat_id=chat_id,
                    from_chat_id=config.SOURCES_CHANNEL_ID,
                    message_id=msg_id,
                    protect_content=True
                )
                success_count += 1
            except Exception as e:
                print(f"Xabarni ko'chirishda xatolik (Topic {topic_id}, Msg ID {msg_id}): {e}")
                
        if success_count == 0:
            bot.send_message(chat_id, "Manbalarni yuborishda xatolik yuz berdi. Iltimos, keyinroq urunib ko'ring.")
        else:
            back_markup = types.InlineKeyboardMarkup()
            if topic_id.startswith("oxta"):
                back_markup.add(types.InlineKeyboardButton("🔙 Menyuga qaytish", callback_data="subject_oxta"))
            else:
                back_markup.add(types.InlineKeyboardButton("🔙 Menyuga qaytish", callback_data="back_to_semester"))
            bot.send_message(chat_id, "Boshqa mavzuni tanlash uchun menyuga qayting:", reply_markup=back_markup)

# Channel post listener (runs in background for automatic mapping)
# It handles new and edited posts/messages in the SOURCES_CHANNEL_ID
# We specify content_types to receive documents (PDFs), photos, videos, voice, and text.
@bot.channel_post_handler(content_types=['text', 'audio', 'document', 'photo', 'video', 'voice'], func=lambda message: True)
@bot.message_handler(content_types=['text', 'audio', 'document', 'photo', 'video', 'voice'], func=lambda message: message.chat.id == config.SOURCES_CHANNEL_ID)
@bot.edited_channel_post_handler(content_types=['text', 'audio', 'document', 'photo', 'video', 'voice'], func=lambda message: True)
@bot.edited_message_handler(content_types=['text', 'audio', 'document', 'photo', 'video', 'voice'], func=lambda message: message.chat.id == config.SOURCES_CHANNEL_ID)
def source_material_handler(message):
    chat_id = message.chat.id
    text = message.text or message.caption or ""
    print(f"[DEBUG] Kanaldan yangi/tahrirlangan xabar keldi. Chat ID: {chat_id}, Matn: {text[:40]}...")
    
    # Verify that this is indeed from the sources channel
    if chat_id != config.SOURCES_CHANNEL_ID:
        print(f"[DEBUG] Chat ID mos kelmadi ({chat_id} != {config.SOURCES_CHANNEL_ID}). E'tiborga olinmadi.")
        return
        
    text = message.text or message.caption or ""
    
    # Search for hashtags: #farma_(\w+), #mavzu(\d+), #oxta_(\w+)
    match_farma = re.search(r'#farma_(\w+)', text, re.IGNORECASE)
    match_mavzu = re.search(r'#mavzu(\d+)', text, re.IGNORECASE)
    match_oxta = re.search(r'#oxta_(\w+)', text, re.IGNORECASE)
    
    key = None
    if match_farma:
        key = match_farma.group(1).lower()
    elif match_mavzu:
        key = match_mavzu.group(1)
    elif match_oxta:
        key = f"oxta_{match_oxta.group(1).lower()}"
        
    if key:
        with mapping_lock:
            mapping = load_mapping()
            
            if key not in mapping:
                mapping[key] = []
                
            msg_id = message.message_id
            
            # Save if not already exists
            if msg_id not in mapping[key]:
                mapping[key].append(msg_id)
                save_mapping(mapping)
                print(f"[SUCCESS] {msg_id}-xabar {key}-kalitiga avtomatik bog'landi.")

if __name__ == "__main__":
    print("Veb-server fon rejimida ishga tushirilmoqda...")
    t = threading.Thread(target=run_web)
    t.start()
    
    print("Farmakologiya Bot ishga tushmoqda...")
    try:
        me = bot.get_me()
        print(f"Ishlayotgan bot: @{me.username} ({me.first_name})")
    except Exception as e:
        print(f"Bot ma'lumotlarini olishda xatolik (Token noto'g'ri bo'lishi mumkin!): {e}")
    print(f"Manbalar kanali ID: {config.SOURCES_CHANNEL_ID}")
    print(f"Obuna talab qilinadigan kanallar: {config.REQUIRED_CHANNELS}")
    
    try:
        # 1-ideya: Set bot commands (☰ Menu)
        bot.set_my_commands([
            types.BotCommand("/start", "Asosiy menyu")
        ])
        bot.infinity_polling()
    except Exception as e:
        print(f"Bot to'xtab qoldi: {e}")
