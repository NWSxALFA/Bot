import telebot
from telebot import types
import json, os, random, logging
from datetime import datetime, timedelta
import threading
import time
from flask import Flask
from threading import Thread



# =========================
# KEEP_ALIVE sozlamalari
# =========================
app = Flask('telegram-bot')

@app.route('/')
def home():
    return "Bot ishlayapti!"

def run():
    app.run(host='0.0.0.0', port=8000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# =========================
# Konfiguratsiya
# =========================
TOKEN = "7141972686:AAFgCSNltVZxji_M2NjuEYaOfdv5WJcqcv8"
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# Adminlar ro'yxati (asosiy admin + qo'shimcha adminlar)
ADMINS = {
    5996676608: {
        "username": "@NWSxALFA",
        "role": "superadmin"
    },
    # Qo'shimcha adminlar qo'shish mumkin: 123456789: {"username": "@admin", "role":"admin"}
}

# Kanallar (bot bu kanallarda admin bo'lishi kerak)
CHANNELS = [
    "@ALFA_BONUS_NEWS", "@NWS_ALFA_07", "@NWS_ALFA_UC"
]

# Foydalanuvchi ma'lumotlari
channels = ["https://t.me/ALFA_BONUS_NEWS", "https://t.me/NWS_ALFA_07", "https://t.me/NWS_ALFA_UC", 
           "https://t.me/ALFA_CHAT_007"]  # admin o'zgartiradi
posts = [
    "https://t.me/NWS_ALFA_07/1118",
    "https://t.me/NWS_ALFA_UC/17"
]

# To'lov tizimlari
PAYMENT_METHODS = {
    "humo": {
        "name": "📱 Humo",
        "number": "9860 1766 1304 0045"
    },
    "uzcard": {
        "name": "📱 Uzcard",
        "number": "5614 6848 3174 9591"
    },
    "visa": {
        "name": "📱 Visa",
        "number": "4023 0610 1846 9590"
    },
    "mastercard": {
        "name": "📱 Mastercard",
        "number": "5476 3801 4214 9343"
    },
    "uzumcard": {
        "name": "📱 Uzumcard",
        "number": "4916 9903 3210 8916"
    },
    "stars": {
        "name": "⭐ Stars orqali",
        "number": "Admin bilan bog'laning"
    }
}

# Fayllar
DATA_FILE = "users.json"
ORDERS_FILE = "orders.json"
ADMINS_FILE = "admins.json"
LOGS_FILE = "bot.log"
PROMO_FILE = "promo.json"

# Sozlamalar
REFERRAL_LEVELS = {1: 600, 2: 100, 3: 50}
MIN_WITHDRAWAL = 70000  # Minimal yechib olish miqdori
BACKUP_INTERVAL = 86400  # 24 soatda bir backup
DAILY_BONUS_RANGE = (0, 100)  # Kunlik bonus diapazoni
STARS_RATE = 350  # 1 star = 350 so'm

# =========================
# Logging sozlamalari
# =========================
logging.basicConfig(
    filename=LOGS_FILE,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    encoding='utf-8'
)

# =========================
# Yordamchi funksiyalar
# =========================
def is_admin(user_id: int) -> bool:
    """Foydalanuvchi admin ekanligini tekshirish"""
    return user_id in ADMINS

def main_menu(is_admin_flag: bool = False) -> types.ReplyKeyboardMarkup:
    """Asosiy menyuni yaratish"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        "💸 Pul ishlash", "🎁 Kunlik bonus", "📊 Hisobim", "🎟 Promokod", "➕ Hisobni to'ldirish",
        "💸 Pul yechish", "👥 Referal", "📈 Statistika", "🏆 Top referallar",
        "🛍 UC / Premium / Stars", "⚙️ Sozlamalar"
    ]
    if is_admin_flag:
        buttons.append("👨‍💻 Admin panel")
    markup.add(*buttons)
    return markup

def admin_menu() -> types.ReplyKeyboardMarkup:
    """Admin menyusi"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📢 Reklama yuborish", "👤 Foydalanuvchi boshqaruvi",
               "📦 Buyurtmalar boshqaruvi", "📊 Statistika", "⬅️ Asosiy menyu")
    return markup

def back_menu() -> types.ReplyKeyboardMarkup:
    """Orqaga qaytish tugmasi"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("⬅️ Ortga")
    return markup

def safe_username(u):
    """Username ni xavfsiz formatda qaytarish"""
    if not u or u == "Nomaʼlum": 
        return "Nomaʼlum"
    return u if u.startswith("@") else f"@{u}"

def check_subscription(user_id):
    """Foydalanuvchi barcha kanallarga obuna bo'lganligini tekshirish"""
    for channel in CHANNELS:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception as e:
            logging.error(f"Kanal a'zoligini tekshirishda xato: {e}")
            return False
    return True

def subscription_required(func):
    """Foydalanuvchi kanalga obuna bo'lishini tekshiruvchi dekorator"""
    def wrapped(message, *args, **kwargs):
        if not check_subscription(message.from_user.id):
            show_channel_sub(message)
            return
        return func(message, *args, **kwargs)
    return wrapped

# Ma'lumotlarni yuklash
def load_data():
    """Barcha ma'lumotlarni fayllardan yuklash"""
    data = {}
    files = {
        DATA_FILE: {},
        ORDERS_FILE: [],
        ADMINS_FILE: ADMINS,
        PROMO_FILE: {
            "REF100": 100,
            "KIDO500": 500,
            "ALFABONUS": 1500,
            "REF1000": 1000,
            "REF500": 500,
            "SPECIAL": 1000
        }
    }
    for file, default in files.items():
        try:
            if os.path.exists(file):
                with open(file, "r", encoding='utf-8') as f:
                    data[file] = json.load(f)
            else:
                data[file] = default
        except Exception as e:
            logging.error(f"{file} yuklashda xato: {e}")
            data[file] = default
    return data

# Ma'lumotlarni saqlash
def save_data():
    """Barcha ma'lumotlarni fayllarga saqlash"""
    global users, orders, admins, promo_codes
    files = {
        DATA_FILE: users,
        ORDERS_FILE: orders,
        ADMINS_FILE: admins,
        PROMO_FILE: promo_codes
    }
    for file, data_obj in files.items():
        try:
            with open(file, "w", encoding='utf-8') as f:
                json.dump(data_obj, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logging.error(f"{file} saqlashda xato: {e}")

# Dastlabki ma'lumotlarni yuklash
data = load_data()
users = data[DATA_FILE]
orders = data[ORDERS_FILE]
admins = data[ADMINS_FILE]
promo_codes = data[PROMO_FILE]

# Backup tizimi
def auto_backup():
    """Avtomatik backup tizimi"""
    while True:
        time.sleep(BACKUP_INTERVAL)
        save_data()
        logging.info("Avtomatik backup amalga oshirildi")

backup_thread = threading.Thread(target=auto_backup)
backup_thread.daemon = True
backup_thread.start()

# =========================
# 1. Bloklangan foydalanuvchilarni tekshirish
# =========================
@bot.message_handler(func=lambda m: str(m.from_user.id) in users and users[str(
    m.from_user.id)].get('blocked', False))
def handle_blocked_users(msg):
    """Bloklangan foydalanuvchilarga xabar berish"""
    bot.reply_to(msg, "❌ Sizning akkauntingiz bloklangan! Admin bilan bog'laning.")

# =========================
# 2. Kanal obunasi tekshirish
# =========================
def show_channel_sub(message):
    """Kanal obunasini tekshirish va bonus berish"""
    uid = str(message.from_user.id)
    
    # Agar allaqachon bonus olgan bo'lsa
    if uid in users and users[uid].get('channel_bonus_received', False):
        return True

    markup = types.InlineKeyboardMarkup()
    for ch in CHANNELS:
        markup.add(
            types.InlineKeyboardButton(f"➕ {ch}", url=f"https://t.me/{ch[1:]}")
        )
    markup.add(
        types.InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")
    )

    bot.send_message(
        message.chat.id,
        "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'lishingiz kerak:\n\n"
        + "\n".join(f"🔹 {ch}" for ch in CHANNELS) +
        "\n\nObuna bo'lgach, «✅ Tekshirish» tugmasini bosing",
        reply_markup=markup
    )
    return False

@bot.callback_query_handler(func=lambda c: c.data == "check_sub")
def check_sub_callback(call):
    """Obuna tekshirish callback"""
    try:
        uid = str(call.from_user.id)
        user_is_subscribed = check_subscription(call.from_user.id)

        if not user_is_subscribed:
            bot.answer_callback_query(
                call.id, "❌ Barcha kanallarga obuna bo'lishingiz kerak!")
            show_channel_sub(call.message)
            return

        # Agar obuna bo'lgan bo'lsa
        if uid not in users:
            users[uid] = {
                "balance": 100,
                "stars": 0,
                "channel_bonus_received": True,
                "refs": {"level1": 0, "level2": 0, "level3": 0},
                "join_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "games_played": 0,
                "games_won": 0,
                "username": safe_username(call.from_user.username)
            }
        elif not users[uid].get('channel_bonus_received', False):
            users[uid]['balance'] = users[uid].get('balance', 0) + 100
            users[uid]['channel_bonus_received'] = True

        save_data()
        bot.answer_callback_query(call.id, "✅ Obuna tekshirildi!")
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="✅ Barcha kanallarga obuna bo'lgansiz!\n\n🎉 Sizga 100 so'm bonus berildi!"
        )
        bot.send_message(
            call.message.chat.id,
            "Menyuni tanlang:",
            reply_markup=main_menu(is_admin_flag=is_admin(call.from_user.id))
        )
    except Exception as e:
        logging.error(f"check_sub da xato: {e}")
        bot.answer_callback_query(
            call.id, "❌ Xato yuz berdi. Iltimos, qayta urinib ko'ring.")

# =========================
# 3. /start komandasi va referal tizimi
# =========================
@bot.message_handler(commands=['start'])
def start(message):
    """Start komandasi"""
    if not check_subscription(message.from_user.id):
        show_channel_sub(message)
        return

    uid = str(message.from_user.id)
    args = message.text.split()

    if uid not in users:
        users[uid] = {
            "username": safe_username(message.from_user.username),
            "balance": 0,
            "stars": 0,
            "refs": {"level1": 0, "level2": 0, "level3": 0},
            "bonus_date": "",
            "orders": [],
            "language": "uz",
            "referred_by": None,
            "join_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "channel_bonus_received": False,
            "used_promo": [],
            "blocked": False,
            "notifications": True,
            "games_played": 0,
            "games_won": 0,
            "first_name": message.from_user.first_name or "",
            "last_active": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_data()
    else:
        # username yangilab boriladi
        users[uid]["username"] = safe_username(message.from_user.username)
        users[uid]["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_data()

    # Referal tizimi - agar /start dan keyin referal kodi bo'lsa va foydalanuvchi yangi bo'lsa va o'zini referal qilmagan bo'lsa va referal kodi o'ziga tegishli bo'lsa va referal kodi haqiqiy bo'lsa referal egasiga ham habar bor sin taklif qilingan foydalanuvchi haqida va balansga ham bonus beriladi
    if len(args) > 1:
        ref_id = args[1]
        if (ref_id != uid and
            users[uid].get('referred_by') is None and
            ref_id in users):
            add_referral(ref_id, uid)
            

    bot.send_message(
        message.chat.id,
        f"👋 Assalomu alaykum! Botimizga xush kelibsiz!\n\n💰 Balans: {users[uid].get('balance', 0)} so'm\n⭐ Stars: {users[uid].get('stars', 0)}",
        reply_markup=main_menu(is_admin_flag=is_admin(message.from_user.id))
    )

def add_referral(ref_id, new_user_id):
    """Referal qo'shish"""
    # 1-daraja
    users[ref_id].setdefault('refs', {"level1": 0, "level2": 0, "level3": 0})
    users[ref_id]['refs']['level1'] = users[ref_id]['refs'].get('level1', 0) + 1
    users[ref_id]['balance'] = users[ref_id].get('balance', 0) + REFERRAL_LEVELS[1]

    # 2-daraja
    if users.get(ref_id, {}).get('referred_by'):
        level2_ref = users[ref_id]['referred_by']
        users[level2_ref].setdefault('refs', {"level1": 0, "level2": 0, "level3": 0})
        users[level2_ref]['refs']['level2'] = users[level2_ref]['refs'].get('level2', 0) + 1
        users[level2_ref]['balance'] = users[level2_ref].get('balance', 0) + REFERRAL_LEVELS[2]

        # 3-daraja
        if users.get(level2_ref, {}).get('referred_by'):
            level3_ref = users[level2_ref]['referred_by']
            users[level3_ref].setdefault('refs', {"level1": 0, "level2": 0, "level3": 0})
            users[level3_ref]['refs']['level3'] = users[level3_ref]['refs'].get('level3', 0) + 1
            users[level3_ref]['balance'] = users[level3_ref].get('balance', 0) + REFERRAL_LEVELS[3]

    users[new_user_id]['referred_by'] = ref_id
    save_data()

# =========================
# 4. Balans va profil
# =========================
@bot.message_handler(func=lambda m: m.text == "📊 Hisobim")
@subscription_required
def show_profile(msg):
    """Foydalanuvchi profilini ko'rsatish"""
    uid = str(msg.from_user.id)
    u = users.get(uid, {})
    text = (
        f"👤 <b>Profil</b>\n"
        f"👨‍💻 <b>ID:</b> {msg.from_user.id}\n"
        f"@{u.get('username','Nomaʼlum').replace('@','')}\n\n"
        f"💰 <b>Balans:</b> {u.get('balance', 0)} so'm\n"
        f"⭐ <b>Stars:</b> {u.get('stars', 0)}\n"
        f"🎮 <b>O'yinlar statistikasi:</b>\n"
        f"  • Umumiy: {u.get('games_played', 0)} ta\n"
        f"  • Yutuq: {u.get('games_won', 0)} ta\n\n"
        f"👥 <b>Referallar</b>:\n"
        f"  • Umumiy: {sum(u.get('refs', {}).values())} ta\n"
        f"  • 1-darajali: {u.get('refs', {}).get('level1', 0)} ta\n"
        f"  • 2-darajali: {u.get('refs', {}).get('level2', 0)} ta\n"
        f"  • 3-darajali: {u.get('refs', {}).get('level3', 0)} ta\n"
        f"📅 <b>Ro'yxatdan o'tgan:</b> {u.get('join_date', 'Nomaʼlum')}\n"
    )

    if u.get('referred_by'):
        text += f"👤 <b>Taklif qilgan:</b> {safe_username(users[u['referred_by']].get('username'))}"
    
    bot.send_message(msg.chat.id, text, parse_mode="HTML")

# =========================
# 5. Pul yechish - TO'LIQ QAYTA YOZILGAN
# =========================
@bot.message_handler(func=lambda m: m.text == "💸 Pul yechish")
@subscription_required
def withdraw(msg):
    """Pul yechish menyusi"""
    uid = str(msg.from_user.id)

    # Tekshirish: referal shartlari
    if users.get(uid, {}).get('refs', {}).get('level1', 0) < 15:
        bot.send_message(
            msg.chat.id,
            "❌ Pul yechish uchun kamida 15 ta 1-darajali referal kerak."
        )
        return
    if users.get(uid, {}).get('refs', {}).get('level2', 0) < 1:
        bot.send_message(
            msg.chat.id,
            "❌ Pul yechish uchun kamida 1 ta 2-darajali referal kerak."
        )
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for method in PAYMENT_METHODS.values():
        markup.add(method['name'])
    markup.add("⬅️ Ortga")

    bot.send_message(msg.chat.id, "💳 To'lov usulini tanlang:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_withdraw_method)

def process_withdraw_method(msg):
    """To'lov usulini qayta ishlash"""
    if msg.text == "⬅️ Ortga":
        bot.send_message(
            msg.chat.id,
            "🔙 Asosiy menyu",
            reply_markup=main_menu(is_admin_flag=is_admin(msg.from_user.id))
        )
        return

    method = next(
        (k for k, v in PAYMENT_METHODS.items() if v['name'] == msg.text), None
    )
    if not method:
        bot.send_message(
            msg.chat.id,
            "❌ Noto'g'ri tanlov! Iltimos, ro'yxatdagi usullardan birini tanlang."
        )
        bot.register_next_step_handler(msg, process_withdraw_method)
        return

    # Saqlaymiz qaysi usul tanlangan
    users[str(msg.from_user.id)]['withdraw_method'] = method

    # Miqdorni so'rash
    bot.send_message(
        msg.chat.id,
        f"💰 Yechib olish miqdorini kiriting (minimal {MIN_WITHDRAWAL} so'm):",
        reply_markup=back_menu()
    )
    bot.register_next_step_handler(msg, process_withdraw_amount)

def process_withdraw_amount(msg):
    """Yechish miqdorini qayta ishlash"""
    uid = str(msg.from_user.id)

    if msg.text == "⬅️ Ortga":
        bot.send_message(
            msg.chat.id,
            "🔙 Asosiy menyu",
            reply_markup=main_menu(is_admin_flag=is_admin(msg.from_user.id))
        )
        return

    try:
        amount = int(msg.text.strip())
    except ValueError:
        bot.send_message(msg.chat.id, "❗ Iltimos faqat raqam kiriting.")
        bot.register_next_step_handler(msg, process_withdraw_amount)
        return

    if amount < MIN_WITHDRAWAL:
        bot.send_message(
            msg.chat.id,
            f"❌ Minimal yechib olish miqdori {MIN_WITHDRAWAL} so'm"
        )
        bot.register_next_step_handler(msg, process_withdraw_amount)
        return

    if users[uid].get('balance', 0) < amount:
        bot.send_message(msg.chat.id, "❌ Balansingizda yetarli mablag' yo'q.")
        return

    # Miqdorni saqlaymiz
    users[uid]['pending_withdraw_amount'] = amount
    save_data()

    # Agar karta usuli tanlangan bo'lsa, karta raqamini so'raymiz
    if users[uid]['withdraw_method'] in ['humo', 'uzcard', 'visa', 'mastercard', 'uzumcard']:
        bot.send_message(
            msg.chat.id,
            "💳 Iltimos, karta raqamingizni kiriting (16-19 ta raqam):",
            reply_markup=back_menu()
        )
        bot.register_next_step_handler(msg, process_card_number)
    else:
        # Stars orqali yechish
        complete_withdraw_order(msg)

def process_card_number(msg):
    """Karta raqamini qayta ishlash"""
    uid = str(msg.from_user.id)

    if msg.text == "⬅️ Ortga":
        users[uid].pop('pending_withdraw_amount', None)
        users[uid].pop('withdraw_method', None)
        save_data()
        bot.send_message(
            msg.chat.id,
            "🔙 Asosiy menyu",
            reply_markup=main_menu(is_admin_flag=is_admin(msg.from_user.id))
        )
        return

    card_number = msg.text.strip().replace(" ", "")
    if not card_number.isdigit() or len(card_number) < 16 or len(card_number) > 19:
        bot.send_message(
            msg.chat.id,
            "❌ Noto'g'ri karta raqami formati. Iltimos, to'g'ri 16-19 xonali raqam kiriting."
        )
        bot.register_next_step_handler(msg, process_card_number)
        return

    # Karta raqamini saqlaymiz va buyurtma yaratamiz
    users[uid]['card_number'] = card_number
    complete_withdraw_order(msg)

def complete_withdraw_order(msg):
    """Yechish buyurtmasini yakunlash"""
    uid = str(msg.from_user.id)
    
    if 'pending_withdraw_amount' not in users[uid]:
        bot.send_message(msg.chat.id, "❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")
        return
    
    amount = users[uid]['pending_withdraw_amount']
    method_key = users[uid].get('withdraw_method')
    
    # Balansni kamaytiramiz
    users[uid]['balance'] -= amount
    
    # Buyurtma yaratish
    order = {
        "kind": "withdraw",
        "user_id": uid,
        "username": users[uid].get("username", msg.from_user.username),
        "amount": amount,
        "method": method_key,
        "status": "pending",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Agar karta raqami bo'lsa, qo'shamiz
    if users[uid].get('card_number'):
        order['card_number'] = users[uid]['card_number']
    
    orders.append(order)
    
    # Tozalash
    users[uid].pop('pending_withdraw_amount', None)
    users[uid].pop('card_number', None)
    users[uid].pop('withdraw_method', None)
    
    save_data()
    
    # Adminlarga xabar
    method = PAYMENT_METHODS.get(method_key, {"name": "Noma'lum"})
    admin_message = (
        f"🔄 <b>Yangi yechish so'rovi</b>\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"👤 Foydalanuvchi: {safe_username(order['username'])}\n"
        f"💳 Usul: {method['name']}\n"
        f"🚀 Miqdor: {amount} so'm\n"
    )
    
    if order.get('card_number'):
        admin_message += f"🔢 Karta raqami: {order['card_number']}\n"
    
    admin_message += (
        f"📅 Vaqt: {order['date']}\n\n"
        f"✅ Tasdiqlash: /approve_{len(orders)-1}\n"
        f"❌ Rad etish: /reject_{len(orders)-1}"
    )
    
    for admin_id in ADMINS:
        try:
            bot.send_message(admin_id, admin_message, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Admin {admin_id} ga xabar yuborishda xato: {e}")
    
    # Foydalanuvchiga xabar
    bot.send_message(
        uid,
        "✅ So'rov muvaffaqiyatli yuborildi. Adminlar tez orada ko'rib chiqishadi.",
        reply_markup=main_menu(is_admin_flag=is_admin(msg.from_user.id))
    )

# =========================
# 6. Balans to'ldirish
# =========================
@bot.message_handler(func=lambda m: m.text == "➕ Hisobni to'ldirish")
@subscription_required
def fill_balance(msg):
    """Balans to'ldirish menyusi"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for method in PAYMENT_METHODS.values():
        markup.add(method['name'])
    markup.add("👨‍💻 Admin orqali", "⬅️ Ortga")

    bot.send_message(msg.chat.id, "💳 To'lov usulini tanlang:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_payment_method)

def process_payment_method(msg):
    """To'lov usulini tanlash"""
    if msg.text == "⬅️ Ortga":
        return bot.send_message(
            msg.chat.id,
            "🔙 Asosiy menyu",
            reply_markup=main_menu(is_admin_flag=is_admin(msg.from_user.id))
        )

    if msg.text == "👨‍💻 Admin orqali":
        admin_contact = next((admin for admin in ADMINS.values()), None)
        return bot.send_message(
            msg.chat.id,
            f"👨‍💻 Admin bilan bog'laning: {admin_contact['username']}"
            if admin_contact else "❌ Admin topilmadi."
        )

    method = next(
        (k for k, v in PAYMENT_METHODS.items() if v['name'] == msg.text), None
    )
    if not method:
        bot.send_message(msg.chat.id, "❌ Noto'g'ri tanlov!")
        return bot.register_next_step_handler(msg, process_payment_method)

    users[str(msg.from_user.id)]['payment_method'] = method

    if method == "stars":
        bot.send_message(
            msg.chat.id,
            f"⭐ Stars miqdorini kiriting (1 star = {STARS_RATE} so'm):",
            reply_markup=back_menu()
        )
        bot.register_next_step_handler(msg, process_stars_amount)
    else:
        bot.send_message(
            msg.chat.id,
            f"💰 To'lov miqdorini kiriting (minimal 5000 so'm):",
            reply_markup=back_menu()
        )
        bot.register_next_step_handler(msg, process_payment_amount)

def process_stars_amount(msg):
    """Stars miqdorini qayta ishlash"""
    uid = str(msg.from_user.id)

    if msg.text == "⬅️ Ortga":
        return bot.send_message(
            msg.chat.id,
            "🔙 Asosiy menyu",
            reply_markup=main_menu(is_admin_flag=is_admin(msg.from_user.id))
        )

    try:
        stars = int(msg.text.strip())
    except ValueError:
        bot.send_message(msg.chat.id, "❗ Faqat raqam kiriting.")
        return bot.register_next_step_handler(msg, process_stars_amount)

    if stars <= 0:
        bot.send_message(msg.chat.id, "❗ Musbat son kiriting.")
        return bot.register_next_step_handler(msg, process_stars_amount)

    current_stars = users[uid].get('stars', 0)
    if current_stars < stars:
        return bot.send_message(
            msg.chat.id,
            f"❌ Sizda yetarli star yo'q.\nSizda: {current_stars} star bor.",
            reply_markup=back_menu()
        )

    amount = stars * STARS_RATE
    users[uid]['stars'] -= stars
    users[uid]['balance'] = users[uid].get('balance', 0) + amount
    users[uid].setdefault('payment_history', []).append({
        "type": "stars",
        "stars": stars,
        "amount": amount,
        "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    save_data()

    # Adminlarga xabar
    for admin_id in ADMINS:
        try:
            bot.send_message(
                admin_id,
                f"⭐ <b>Stars orqali balans to'ldirish</b>\n"
                f"👤 Foydalanuvchi: {safe_username(users[uid].get('username', msg.from_user.username))}\n"
                f"🆔 ID: {uid}\n"
                f"⭐ Stars: {stars} (1 star = {STARS_RATE} so'm)\n"
                f"💰 Miqdor: {amount} so'm\n"
                f"📅 Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Admin {admin_id} ga xabar yuborishda xato: {e}")

    bot.send_message(
        uid,
        f"✅ {stars} star hisobingizdan yechildi va balansga {amount} so'm qo'shildi!\n"
        f"💰 Yangi balans: {users[uid]['balance']} so'm\n"
        f"⭐ Qolgan stars: {users[uid]['stars']}",
        reply_markup=main_menu(is_admin_flag=is_admin(msg.from_user.id))
    )

def process_payment_amount(msg):
    """To'lov miqdorini qayta ishlash"""
    uid = str(msg.from_user.id)

    if msg.text == "⬅️ Ortga":
        return bot.send_message(
            msg.chat.id,
            "🔙 Asosiy menyu",
            reply_markup=main_menu(is_admin_flag=is_admin(msg.from_user.id))
        )

    try:
        amount = int(msg.text.strip())
    except ValueError:
        bot.send_message(msg.chat.id, "❗ Faqat raqam kiriting.")
        return bot.register_next_step_handler(msg, process_payment_amount)

    if amount < 5000:
        bot.send_message(msg.chat.id, "❌ Minimal to'lov miqdori 5000 so'm")
        return bot.register_next_step_handler(msg, process_payment_amount)

    method_key = users[uid]['payment_method']
    method = PAYMENT_METHODS[method_key]
    
    bot.send_message(
        msg.chat.id,
        f"ℹ️ <b>To'lov ma'lumotlari</b>\n\n"
        f"💳 Usul: {method['name']}\n"
        f"📱 Raqam: {method['number']}\n"
        f"💰 Miqdor: {amount} so'm\n\n"
        f"📸 To'lov qilganingizdan so'ng <b>chek rasmini</b> yuboring.",
        reply_markup=back_menu(),
        parse_mode="HTML"
    )

    users[uid]['payment_amount'] = amount
    save_data()
    bot.register_next_step_handler(msg, process_payment_receipt)

def process_payment_receipt(msg):
    """To'lov chekini qayta ishlash"""
    uid = str(msg.from_user.id)

    if msg.text == "⬅️ Ortga":
        return bot.send_message(
            msg.chat.id,
            "🔙 Asosiy menyu",
            reply_markup=main_menu(is_admin_flag=is_admin(msg.from_user.id))
        )

    if not msg.photo:
        bot.send_message(msg.chat.id, "❗ To'lov cheki rasmini yuboring.")
        return bot.register_next_step_handler(msg, process_payment_receipt)

    photo = msg.photo[-1].file_id
    amount = users[uid]['payment_amount']
    method = users[uid]['payment_method']

    payment = {
        "kind": "topup",
        "user_id": uid,
        "username": users[uid].get("username", msg.from_user.username),
        "amount": amount,
        "method": method,
        "status": "pending",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "photo_id": photo
    }
    
    order_id = len(orders)
    orders.append(payment)
    save_data()

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_pay_{order_id}"),
        types.InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_pay_{order_id}")
    )

    for admin_id in ADMINS:
        try:
            bot.send_photo(
                admin_id,
                photo,
                caption=(
                    f"🔄 <b>Yangi to'lov so'rovi</b>\n"
                    f"🆔 ID: <code>{uid}</code>\n"
                    f"👤 Foydalanuvchi: {safe_username(payment['username'])}\n"
                    f"💳 Usul: {PAYMENT_METHODS[method]['name']}\n"
                    f"💰 Miqdor: {amount} so'm\n"
                    f"📅 Vaqt: {payment['date']}"
                ),
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Admin {admin_id} ga xabar yuborishda xato: {e}")

    bot.send_message(
        uid,
        "✅ To'lov cheki qabul qilindi. Adminlar tez orada ko'rib chiqishadi.",
        reply_markup=main_menu(is_admin_flag=is_admin(msg.from_user.id))
    )

# =========================
# 7. Admin to'lov tasdiqlash/rad etish
# =========================
@bot.callback_query_handler(
    func=lambda call: call.data.startswith(('approve_pay_', 'reject_pay_'))
)
def handle_admin_payment_action(call):
    """Admin tomonidan to'lovni tasdiqlash/rad etish"""
    try:
        action, order_id = call.data.split('_pay_')
        order_id = int(order_id)

        if order_id < 0 or order_id >= len(orders):
            return bot.answer_callback_query(call.id, "❌ Noto'g'ri buyurtma ID!")

        order = orders[order_id]
        uid = order['user_id']

        if order['status'] != 'pending':
            return bot.answer_callback_query(
                call.id, "ℹ️ Bu to'lov allaqachon ko'rib chiqilgan."
            )

        if action == "approve":
            orders[order_id]['status'] = 'approved'
            users[uid]['balance'] = users[uid].get('balance', 0) + order['amount']
            
            bot.send_message(
                uid,
                f"✅ To'lovingiz tasdiqlandi!\n"
                f"💰 Miqdor: {order['amount']} so'm\n"
                f"💳 Usul: {PAYMENT_METHODS[order['method']]['name']}\n"
                f"📅 Vaqt: {order['date']}\n\n"
                f"💳 Yangi balans: {users[uid]['balance']} so'm"
            )
            bot.answer_callback_query(call.id, f"✅ To'lov #{order_id} tasdiqlandi.")
        else:
            orders[order_id]['status'] = 'rejected'
            bot.send_message(
                uid,
                "❌ To'lovingiz rad etildi! Sabab: Admin tomonidan rad etildi."
            )
            bot.answer_callback_query(call.id, f"❌ To'lov #{order_id} rad etildi.")

        save_data()
    except Exception as e:
        logging.error(f"Admin to'lov boshqaruvida xato: {e}")
        bot.answer_callback_query(call.id, "❌ Xato yuz berdi.")

# =========================
# 8. PUL ISHLASH - TO'LIQ QAYTA YOZILGAN
# =========================
@bot.message_handler(func=lambda m: m.text == "💸 Pul ishlash")
@subscription_required
def pul_ishlash(msg):
    """Pul ishlash menyusi"""
    user_id = str(msg.from_user.id)
    
    # Agar foydalanuvchi bazada yo'q bo'lsa, qo'shamiz
    if user_id not in users:
        users[user_id] = {
            "balance": 0,
            "completed_channels": [],
            "completed_posts": [],
            "username": safe_username(msg.from_user.username)
        }
        save_data()

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📢 Obuna bo'lish", "👁 Post ko'rish")
    markup.add("⬅️ Ortga")
    
    bot.send_message(msg.chat.id, "💸 Pul ishlash bo'limi:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📢 Obuna bo'lish")
@subscription_required
def subscribe_task(msg):
    """Obuna bo'lish topshirig'i"""
    user_id = str(msg.from_user.id)
    
    # Bajarilmagan birinchi kanalni topish
    available_channel = None
    for i, channel in enumerate(channels):
        if i not in users[user_id].get("completed_channels", []):
            available_channel = (i, channel)
            break

    if available_channel is None:
        bot.send_message(
            msg.chat.id, 
            "📭 Hozircha barcha obuna topshiriqlari tugadi. Keyinroq qayta teking!"
        )
        return

    step, link = available_channel
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("➕ Obuna bo'lish", url=link))
    markup.add(
        types.InlineKeyboardButton("✅ Tekshirish", callback_data=f"check_sub_{step}"),
        types.InlineKeyboardButton("⏭ Keyingisi", callback_data=f"next_sub_{step}")
    )
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_earn"))

    bot.send_message(
        msg.chat.id, 
        f"📢 {step+1}-kanalga obuna bo'ling:\n\nKanal: {link}", 
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text == "👁 Post ko'rish")
@subscription_required
def view_post_task(msg):
    """Post ko'rish topshirig'i"""
    user_id = str(msg.from_user.id)
    
    # Bajarilmagan birinchi postni topish
    available_post = None
    for i, post in enumerate(posts):
        if i not in users[user_id].get("completed_posts", []):
            available_post = (i, post)
            break

    if available_post is None:
        bot.send_message(
            msg.chat.id, 
            "📭 Hozircha barcha post ko'rish topshiriqlari tugadi. Keyinroq qayta teking!"
        )
        return

    step, link = available_post
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("👁 Postni ko'rish", url=link))
    markup.add(
        types.InlineKeyboardButton("✅ Tekshirish", callback_data=f"check_post_{step}"),
        types.InlineKeyboardButton("⏭ Keyingisi", callback_data=f"next_post_{step}")
    )
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_earn"))

    bot.send_message(
        msg.chat.id, 
        f"👁 {step+1}-postni ko'ring:\n\nPost: {link}", 
        reply_markup=markup
    )

# Obuna tekshirish callback
@bot.callback_query_handler(func=lambda call: call.data.startswith("check_sub_"))
def check_subscription_callback(call):
    """Obunani tekshirish"""
    user_id = str(call.from_user.id)
    step = int(call.data.split("_")[2])

    # Agar bu kanal allaqachon bajarilgan bo'lsa
    if step in users[user_id].get("completed_channels", []):
        bot.answer_callback_query(call.id, "❌ Bu topshiriq allaqachon bajarilgan!")
        return

    # Bu yerda haqiqiy obuna tekshiruvini qo'shing
    # Hozircha avtomatik tasdiqlaymiz
    users[user_id]["balance"] = users[user_id].get("balance", 0) + 100
    if "completed_channels" not in users[user_id]:
        users[user_id]["completed_channels"] = []
    users[user_id]["completed_channels"].append(step)
    save_data()

    bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi! +100 so'm")
    show_next_available_sub_task(call.message, user_id)

# Keyingi obuna topshirig'i
@bot.callback_query_handler(func=lambda call: call.data.startswith("next_sub_"))
def next_subscription_callback(call):
    """Keyingi obuna topshirig'iga o'tish"""
    user_id = str(call.from_user.id)
    step = int(call.data.split("_")[2])

    # Agar bu kanal allaqachon bajarilgan bo'lsa
    if step in users[user_id].get("completed_channels", []):
        bot.answer_callback_query(call.id, "❌ Bu topshiriq allaqachon bajarilgan!")
        return

    show_next_available_sub_task(call.message, user_id)

def show_next_available_sub_task(message, user_id):
    """Keyingi bajarilmagan kanalni ko'rsatish"""
    available_channel = None
    for i, channel in enumerate(channels):
        if i not in users[user_id].get("completed_channels", []):
            available_channel = (i, channel)
            break

    if available_channel is None:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_earn"))
        bot.edit_message_text(
            "📭 Hozircha barcha obuna topshiriqlari tugadi. Keyinroq qayta teking! ✅", 
            message.chat.id, 
            message.message_id,
            reply_markup=markup
        )
        return

    step, link = available_channel
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("➕ Obuna bo'lish", url=link))
    markup.add(
        types.InlineKeyboardButton("✅ Tekshirish", callback_data=f"check_sub_{step}"),
        types.InlineKeyboardButton("⏭ Keyingisi", callback_data=f"next_sub_{step}")
    )
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_earn"))

    bot.edit_message_text(
        f"📢 {step+1}-kanalga obuna bo'ling:\n\nKanal: {link}", 
        message.chat.id, 
        message.message_id,
        reply_markup=markup
    )

# Post tekshirish callback
@bot.callback_query_handler(func=lambda call: call.data.startswith("check_post_"))
def check_post_callback(call):
    """Post ko'rishni tekshirish"""
    user_id = str(call.from_user.id)
    step = int(call.data.split("_")[2])

    # Agar bu post allaqachon bajarilgan bo'lsa
    if step in users[user_id].get("completed_posts", []):
        bot.answer_callback_query(call.id, "❌ Bu topshiriq allaqachon bajarilgan!")
        return

    users[user_id]["balance"] = users[user_id].get("balance", 0) + 20
    if "completed_posts" not in users[user_id]:
        users[user_id]["completed_posts"] = []
    users[user_id]["completed_posts"].append(step)
    save_data()

    bot.answer_callback_query(call.id, "✅ Post ko'rildi! +20 so'm")
    show_next_available_post_task(call.message, user_id)

# Keyingi post topshirig'i
@bot.callback_query_handler(func=lambda call: call.data.startswith("next_post_"))
def next_post_callback(call):
    """Keyingi post topshirig'iga o'tish"""
    user_id = str(call.from_user.id)
    step = int(call.data.split("_")[2])

    # Agar bu post allaqachon bajarilgan bo'lsa
    if step in users[user_id].get("completed_posts", []):
        bot.answer_callback_query(call.id, "❌ Bu topshiriq allaqachon bajarilgan!")
        return

    show_next_available_post_task(call.message, user_id)

def show_next_available_post_task(message, user_id):
    """Keyingi bajarilmagan postni ko'rsatish"""
    available_post = None
    for i, post in enumerate(posts):
        if i not in users[user_id].get("completed_posts", []):
            available_post = (i, post)
            break

    if available_post is None:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_earn"))
        bot.edit_message_text(
            "📭 Hozircha barcha post ko'rish topshiriqlari tugadi. Keyinroq qayta teking! ✅", 
            message.chat.id, 
            message.message_id,
            reply_markup=markup
        )
        return

    step, link = available_post
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("👁 Postni ko'rish", url=link))
    markup.add(
        types.InlineKeyboardButton("✅ Tekshirish", callback_data=f"check_post_{step}"),
        types.InlineKeyboardButton("⏭ Keyingisi", callback_data=f"next_post_{step}")
    )
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_earn"))

    bot.edit_message_text(
        f"👁 {step+1}-postni ko'ring:\n\nPost: {link}", 
        message.chat.id, 
        message.message_id,
        reply_markup=markup
    )

# Orqaga qaytish
@bot.callback_query_handler(func=lambda call: call.data == "back_to_earn")
def back_to_earn_callback(call):
    """Pul ishlash bo'limiga qaytish"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📢 Obuna bo'lish", "👁 Post ko'rish")
    markup.add("⬅️ Ortga")

    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "💸 Pul ishlash bo'limi:", reply_markup=markup)

# =========================
# 9. Kunlik bonus
# =========================
@bot.message_handler(func=lambda m: m.text == "🎁 Kunlik bonus")
@subscription_required
def daily_bonus(msg):
    """Kunlik bonus berish"""
    uid = str(msg.from_user.id)
    today = datetime.now().strftime("%Y-%m-%d")

    # Foydalanuvchi ma'lumotlari yo'q bo'lsa, yaratib qo'yamiz
    if uid not in users:
        users[uid] = {
            "balance": 0,
            "stars": 0,
            "bonus_date": "",
            "username": safe_username(msg.from_user.username),
            "refs": {"level1": 0, "level2": 0, "level3": 0},
            "join_date": today,
            "games_played": 0,
            "games_won": 0,
            "first_name": msg.from_user.first_name or ""
        }

    # Bugun bonus olinganligini tekshirish
    if users[uid].get("bonus_date") == today:
        bot.send_message(
            msg.chat.id,
            "❌ Siz bugungi bonusingizni oldingiz.\nErtaga qayta urinib ko'ring 😊"
        )
        return

    # Bonus oralig'i
    bonus = random.randint(*DAILY_BONUS_RANGE)
    users[uid]["balance"] = users[uid].get("balance", 0) + bonus
    users[uid]["bonus_date"] = today
    save_data()

    bot.send_message(
        msg.chat.id,
        f"🎉 Tabriklaymiz! Siz bugungi bonusingizni oldingiz!\n\n"
        f"💰 Bonus: <b>{bonus:,} so'm</b>\n"
        f"⚖️ Balansingiz: <b>{users[uid]['balance']:,} so'm</b>",
        parse_mode="HTML"
    )

# =========================
# 10. Referal tizimi
# =========================
@bot.message_handler(func=lambda m: m.text == "👥 Referal")
@subscription_required
def referral_info(msg):
    """Referal ma'lumotlari"""
    uid = str(msg.from_user.id)
    bot_username = bot.get_me().username
    ref_link = f"https://t.me/{bot_username}?start={uid}"

    text = f"""
📢 Do'stlaringizni taklif qiling va bonus oling!

🔗 Sizning referal havolangiz:
{ref_link}

📊 Sizning referal statistikangiz:
👥 1-darajali: {users[uid].get('refs', {}).get('level1', 0)} ta
👥 2-darajali: {users[uid].get('refs', {}).get('level2', 0)} ta
👥 3-darajali: {users[uid].get('refs', {}).get('level3', 0)} ta

💰 Har bir 1-darajali referal uchun: {REFERRAL_LEVELS[1]} so'm
💰 Har bir 2-darajali referal uchun: {REFERRAL_LEVELS[2]} so'm
💰 Har bir 3-darajali referal uchun: {REFERRAL_LEVELS[3]} so'm

💡 Sizning havolangiz orqali ro'yxatdan o'tgan har bir foydalanuvchi sizga daromad keltiradi!
    """
    bot.send_message(msg.chat.id, text)

# =========================
# 11. Statistika
# =========================
@bot.message_handler(func=lambda m: m.text == "📈 Statistika")
@subscription_required
def stats(msg):
    """Bot statistikasi"""
    total_users = len(users)
    active_today = sum(1 for u in users.values() if u.get(
        'last_active', '').startswith(datetime.now().strftime('%Y-%m-%d')))
    new_today = sum(1 for u in users.values() if u.get(
        'join_date', '').startswith(datetime.now().strftime('%Y-%m-%d')))
    total_balance = sum(u.get('balance', 0) for u in users.values())
    total_refs = sum(
        u.get('refs', {}).get('level1', 0) for u in users.values())
    total_games = sum(u.get('games_played', 0) for u in users.values())

    text = (
        "📊 <b>Bot statistikasi</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users}</b>\n"
        f"🆕 Bugun qo'shilganlar: <b>{new_today}</b>\n"
        f"⚡ Bugun faol bo'lganlar: <b>{active_today}</b>\n\n"
        f"💰 Jami balans: <b>{total_balance:,} so'm</b>\n"
        f"🤝 Jami referallar: <b>{total_refs}</b>\n"
        f"🎮 Jami o'yinlar: <b>{total_games}</b>\n\n"
        f"📅 Sana: <b>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"
        f"⏱️ Statistika har 5 daqiqada yangilanadi"
    )

    bot.send_message(msg.chat.id, text, parse_mode="HTML")

# =========================
# 12. UC/Premium/Stars bo'limi
# =========================
@bot.message_handler(func=lambda m: m.text == "🛍 UC / Premium / Stars")
@subscription_required
def shop_menu(msg):
    """Do'kon menyusi"""
    markup = types.InlineKeyboardMarkup(row_width=1)

    # UC paketlari
    markup.add(
        types.InlineKeyboardButton("💎 UC Paketlar 💎", callback_data="none"))

    uc_packages = [
        ("60 UC - 12,000 so'm", 12000, 60),
        ("120 UC - 24,000 so'm", 24000, 120),
        ("180 UC - 36,000 so'm", 36000, 180),
        ("325 UC - 60,000 so'm", 60000, 325),
        ("385 UC - 72,000 so'm", 72000, 385),
        ("660 UC - 118,000 so'm", 118000, 660),
        ("720 UC - 127,000 so'm", 127000, 720),
        ("1800 UC - 300,000 so'm", 300000, 1800),
        ("3850 UC - 590,000 so'm", 590000, 3850),
        ("8100 UC - 1,170,000 so'm", 1310000, 8100),
        ("16200 UC - 2,350,000 so'm", 2350000, 16200)
    ]
    
    for label, price, amount in uc_packages:
        markup.add(
            types.InlineKeyboardButton(
                label, callback_data=f"shop_uc_{price}_{amount}"
            )
        )

    # Premium paketlari
    markup.add(
        types.InlineKeyboardButton("🚀 Premium Paketlar 🚀", callback_data="none")
    )
    
    premium_packages = [
        ("Premium 3 oy - 176,000 so'm", 176000, 3),
        ("Premium 6 oy - 230,000 so'm", 230000, 6),
        ("Premium 12 oy - 399,000 so'm", 399000, 12)
    ]
    
    for label, price, months in premium_packages:
        markup.add(
            types.InlineKeyboardButton(
                label, callback_data=f"shop_premium_{price}_{months}"
            )
        )

    # Stars paketlari
    markup.add(
        types.InlineKeyboardButton("⭐ Stars Paketlar ⭐", callback_data="none")
    )
    
    stars_packages = [
        ("100 Stars - 35,000 so'm", 35000, 100),
        ("250 Stars - 70,000 so'm", 70000, 250),
        ("500 Stars - 130,000 so'm", 130000, 500),
        ("1000 Stars - 250,000 so'm", 250000, 1000),
        ("2500 Stars - 600,000 so'm", 600000, 2500),
        ("5000 Stars - 1,200,000 so'm", 1200000, 5000)
    ]
    
    for label, price, amount in stars_packages:
        markup.add(
            types.InlineKeyboardButton(
                label, callback_data=f"shop_stars_{price}_{amount}"
            )
        )

    markup.add(
        types.InlineKeyboardButton("⬅️ Ortga", callback_data="shop_back")
    )
    
    bot.send_message(
        msg.chat.id,
        "🛒 Quyidagi paketlardan birini tanlang:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("shop_"))
def handle_shop_callback(call):
    """Do'kon callbacklarini boshqarish"""
    data = call.data
    uid = str(call.from_user.id)

    if data == "shop_back":
        bot.edit_message_text(
            "🔙 Asosiy menyu",
            call.message.chat.id,
            call.message.message_id
        )
        bot.send_message(
            call.message.chat.id,
            "🔙 Asosiy menyu",
            reply_markup=main_menu(is_admin_flag=is_admin(call.from_user.id))
        )
        return

    if data.startswith("shop_uc_"):
        _, _, price, amount = data.split("_")
        item_type = "UC"
        item_amount = f"{amount} UC"
    elif data.startswith("shop_premium_"):
        _, _, price, months = data.split("_")
        item_type = "Premium"
        item_amount = f"{months} oy"
    elif data.startswith("shop_stars_"):
        _, _, price, amount = data.split("_")
        item_type = "Stars"
        item_amount = f"{amount} Stars"
    else:
        bot.answer_callback_query(call.id, "❌ Noto'g'ri tanlov!")
        return

    price = int(price)

    if users[uid].get('balance', 0) < price:
        bot.answer_callback_query(call.id, "❌ Balansingizda yetarli mablag' yo'q!")
        return

    bot.answer_callback_query(call.id, f"✅ {item_type} paketi tanlandi!")
    bot.send_message(
        call.message.chat.id,
        f"🆔 {item_type} yetkazib berish uchun o'yin ID raqamingizni yuboring:"
    )

    users[uid]['pending_order'] = {
        "type": item_type,
        "amount": item_amount,
        "price": price
    }
    save_data()

    bot.register_next_step_handler(call.message, process_game_id)

def process_game_id(msg):
    """O'yin ID raqamini qayta ishlash"""
    uid = str(msg.from_user.id)
    game_id = msg.text.strip()

    if not users[uid].get('pending_order'):
        bot.send_message(
            msg.chat.id,
            "❌ Xato yuz berdi. Iltimos, qayta urinib ko'ring.",
            reply_markup=main_menu(is_admin_flag=is_admin(msg.from_user.id))
        )
        return

    order = users[uid]['pending_order']
    del users[uid]['pending_order']

    users[uid]['balance'] = users[uid].get('balance', 0) - order['price']

    new_order = {
        "kind": "shop",
        "user_id": uid,
        "username": users[uid].get("username", msg.from_user.username),
        "type": order['type'],
        "amount": order['amount'],
        "price": order['price'],
        "game_id": game_id,
        "status": "pending",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    orders.append(new_order)
    save_data()

    # Adminlarga xabar
    for admin_id in ADMINS:
        try:
            bot.send_message(
                admin_id,
                f"🛒 <b>Yangi buyurtma</b>\n"
                f"👤 Foydalanuvchi: {safe_username(new_order['username'])}\n"
                f"📦 Turi: {new_order['type']}\n"
                f"💰 Miqdor: {new_order['amount']}\n"
                f"💵 Narxi: {new_order['price']} so'm\n"
                f"🆔 ID: {new_order['game_id']}\n"
                f"📅 Vaqt: {new_order['date']}\n\n"
                f"✅ Tasdiqlash: /approve_order_{len(orders)-1}\n"
                f"❌ Rad etish: /reject_order_{len(orders)-1}",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Admin {admin_id} ga xabar yuborishda xato: {e}")

    bot.send_message(
        msg.chat.id,
        f"✅ Buyurtma qabul qilindi! Adminlar tez orada ko'rib chiqishadi.\n\n"
        f"📦 Buyurtma: {order['type']} {order['amount']}\n"
        f"💰 Narxi: {order['price']} so'm\n"
        f"🆔 ID: {game_id}",
        reply_markup=main_menu(is_admin_flag=is_admin(msg.from_user.id))
    )

# =========================
# 13. Admin buyurtma tasdiqlash/rad etish
# =========================
@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and (m.text.startswith(
        '/approve_order_') or m.text.startswith('/reject_order_'))
)
def handle_admin_shop_action(msg):
    """Admin tomonidan do'kon buyurtmasini boshqarish"""
    try:
        action, order_id = msg.text.split('_order_')
        order_id = int(order_id)

        if order_id < 0 or order_id >= len(orders):
            bot.send_message(msg.chat.id, "❌ Noto'g'ri buyurtma IDsi!")
            return

        order = orders[order_id]
        if order.get("kind") != "shop":
            bot.send_message(msg.chat.id, "ℹ️ Bu buyruq faqat do'kon buyurtmalari uchun.")
            return

        uid = order['user_id']

        if action == '/approve':
            orders[order_id]['status'] = 'approved'
            bot.send_message(
                uid,
                f"✅ Buyurtmangiz tasdiqlandi!\n"
                f"📦 Buyurtma: {order['type']} {order['amount']}\n"
                f"💰 Narxi: {order['price']} so'm\n"
                f"🆔 ID: {order['game_id']}\n\n"
                f"ℹ️ Mahsulot 12 soat ichida yetkazib beriladi."
            )
            bot.send_message(msg.chat.id, f"✅ Buyurtma #{order_id} tasdiqlandi.")
        else:
            orders[order_id]['status'] = 'rejected'
            users[uid]['balance'] = users[uid].get('balance', 0) + order['price']
            bot.send_message(
                uid,
                f"❌ Buyurtmangiz rad etildi!\n"
                f"📦 Buyurtma: {order['type']} {order['amount']}\n"
                f"💰 Miqdor: {order['price']} so'm qaytarildi.\n"
                f"ℹ️ Sabab: Admin tomonidan rad etildi."
            )
            bot.send_message(msg.chat.id, f"❌ Buyurtma #{order_id} rad etildi.")

        save_data()
    except Exception as e:
        logging.error(f"Admin buyurtma boshqaruvida xato: {e}")
        bot.send_message(msg.chat.id, "❌ Xato yuz berdi. Iltimos, qayta urinib ko'ring.")

# =========================
# 14. Sozlamalar
# =========================
@bot.message_handler(func=lambda m: m.text == "⚙️ Sozlamalar")
@subscription_required
def settings_menu(msg):
    """Sozlamalar menyusi"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🔔 Bildirishnomalar", "📜 Buyurtmalar tarixi",
               "💳 To'lovlar tarixi", "📩 Adminga murojaat", "⬅️ Ortga")
    bot.send_message(msg.chat.id, "⚙️ Sozlamalar menyusi:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🔔 Bildirishnomalar")
@subscription_required
def toggle_notifications(msg):
    """Bildirishnomalarni yoqish/o'chirish"""
    uid = str(msg.from_user.id)
    
    if uid not in users:
        users[uid] = {"notifications": True}

    current = users[uid].get("notifications", True)
    users[uid]["notifications"] = not current
    save_data()

    status = "yoqilgan" if users[uid]["notifications"] else "o'chirilgan"
    bot.send_message(
        msg.chat.id,
        f"🔔 Bildirishnomalar {status}!",
        reply_markup=main_menu(is_admin_flag=is_admin(msg.from_user.id))
    )

@bot.message_handler(func=lambda m: m.text == "📜 Buyurtmalar tarixi")
@subscription_required
def order_history(msg):
    """Buyurtmalar tarixi"""
    uid = str(msg.from_user.id)
    user_orders = [
        o for o in orders
        if o.get('user_id') == uid and o.get('kind') == 'shop'
    ]

    if not user_orders:
        bot.send_message(msg.chat.id, "📜 Sizda hali buyurtmalar mavjud emas.")
        return

    text = "📜 <b>Buyurtmalar tarixi</b>:\n\n"
    for i, order in enumerate(user_orders[-5:], 1):  # Oxirgi 5 ta buyurtma
        text += (f"{i}. {order['type']} {order['amount']}\n"
                 f"💰 Narxi: {order['price']} so'm\n"
                 f"📅 Sana: {order['date']}\n"
                 f"🔄 Holati: {order['status']}\n\n")

    bot.send_message(msg.chat.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "💳 To'lovlar tarixi")
@subscription_required
def payment_history(msg):
    """To'lovlar tarixi"""
    uid = str(msg.from_user.id)
    user_payments = [
        o for o in orders
        if o.get('user_id') == uid and o.get('kind') in ['topup', 'withdraw']
    ]

    if not user_payments:
        bot.send_message(msg.chat.id, "💳 Sizda hali to'lovlar mavjud emas.")
        return

    text = "💳 <b>To'lovlar tarixi</b>:\n\n"
    for i, payment in enumerate(user_payments[-5:], 1):  # Oxirgi 5 ta to'lov
        if payment['kind'] == 'topup':
            kind = "➕ Hisob to'ldirish"
        else:
            kind = "💸 Pul yechish"

        text += (f"{i}. {kind}\n"
                 f"💰 Miqdor: {payment['amount']} so'm\n"
                 f"📅 Sana: {payment['date']}\n"
                 f"🔄 Holati: {payment['status']}\n\n")

    bot.send_message(msg.chat.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "📩 Adminga murojaat")
@subscription_required
def contact_admin(msg):
    """Adminga murojaat qilish"""
    bot.send_message(msg.chat.id, "✏️ Adminga yubormoqchi bo'lgan xabaringizni kiriting:")
    bot.register_next_step_handler(msg, send_to_admin)

def send_to_admin(msg):
    """Xabarni adminlarga yuborish"""
    text = msg.text
    uid = msg.from_user.id
    username = f"@{msg.from_user.username}" if msg.from_user.username else msg.from_user.first_name

    # Adminlarga yuborish
    for admin_id in ADMINS:
        try:
            bot.send_message(
                admin_id,
                f"📩 <b>Yangi murojaat</b>\n"
                f"👤 Foydalanuvchi: {username} (ID: {uid})\n"
                f"💬 Xabar:\n{text}",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Admin {admin_id} ga xabar yuborishda xato: {e}")

    bot.send_message(
        uid,
        "✅ Xabaringiz adminlarga yuborildi.",
        reply_markup=main_menu(is_admin_flag=is_admin(uid))
    )

# =========================
# 15. Admin paneli - TO'LIQ QAYTA YOZILGAN
# =========================
@bot.message_handler(
    func=lambda m: m.text == "👨‍💻 Admin panel" and is_admin(m.from_user.id)
)
def admin_panel(msg):
    """Admin paneli"""
    bot.send_message(msg.chat.id, "👨‍💻 Admin panel:", reply_markup=admin_menu())

@bot.message_handler(
    func=lambda m: m.text == "📢 Reklama yuborish" and is_admin(m.from_user.id)
)
def admin_advert(msg):
    """Reklama yuborish"""
    bot.send_message(
        msg.chat.id,
        "📢 Reklama matnini (yoki media bilan) yuboring yoki ⬅️ Ortga:",
        reply_markup=back_menu()
    )
    bot.register_next_step_handler(msg, process_advert)

def process_advert(msg):
    """Reklamani qayta ishlash va yuborish"""
    if msg.text == "⬅️ Ortga":
        bot.send_message(msg.chat.id, "🔙 Admin panel", reply_markup=admin_menu())
        return

    sent = 0
    failed = 0
    total = len(users)

    progress_msg = bot.send_message(msg.chat.id, f"📤 Reklama yuborilmoqda... 0/{total}")

    for uid in list(users.keys()):
        try:
            if msg.content_type == 'photo':
                bot.send_photo(uid, msg.photo[-1].file_id, caption=msg.caption)
            elif msg.content_type == 'video':
                bot.send_video(uid, msg.video.file_id, caption=msg.caption)
            elif msg.content_type == 'document':
                bot.send_document(uid, msg.document.file_id, caption=msg.caption)
            elif msg.content_type == 'audio':
                bot.send_audio(uid, msg.audio.file_id, caption=msg.caption)
            elif msg.content_type == 'voice':
                bot.send_voice(uid, msg.voice.file_id, caption=msg.caption)
            else:
                bot.send_message(uid, msg.text)
            sent += 1
        except Exception as e:
            failed += 1
            logging.error(f"Reklamani {uid} ga yuborishda xato: {e}")

        if (sent + failed) % 10 == 0 or (sent + failed) == total:
            try:
                bot.edit_message_text(
                    f"📤 Reklama yuborilmoqda... {sent + failed}/{total}\n✅ Yuborildi: {sent}\n❌ Xato: {failed}",
                    msg.chat.id, progress_msg.message_id
                )
            except Exception:
                pass

    try:
        bot.edit_message_text(
            f"✅ Reklama yuborish yakunlandi!\n\nJami: {total}\n✅ Yuborildi: {sent}\n❌ Xato: {failed}",
            msg.chat.id, progress_msg.message_id
        )
    except Exception:
        bot.send_message(
            msg.chat.id,
            f"✅ Reklama yakunlandi.\nJami: {total}\n✅: {sent}\n❌: {failed}"
        )

    bot.send_message(msg.chat.id, "🔙 Admin panel", reply_markup=admin_menu())

@bot.message_handler(
    func=lambda m: m.text == "👤 Foydalanuvchi boshqaruvi" and is_admin(m.from_user.id)
)
def user_management(msg):
    """Foydalanuvchi boshqaruvi"""
    bot.send_message(
        msg.chat.id,
        "👤 Foydalanuvchi ID yoki username yuboring:",
        reply_markup=back_menu()
    )
    bot.register_next_step_handler(msg, find_user)

def find_user(msg):
    """Foydalanuvchini topish"""
    if msg.text == "⬅️ Ortga":
        bot.send_message(msg.chat.id, "🔙 Admin panel", reply_markup=admin_menu())
        return

    query = msg.text.strip()
    target_uid = None
    target_username = None

    # ID bo'yicha
    if query.isdigit():
        if query in users:
            target_uid = query
            target_username = users[query].get('username', 'Nomaʼlum')
    else:
        q = query.lower().replace("@", "")
        for uid, user in users.items():
            if 'username' in user and user['username'].lower().replace("@", "") == q:
                target_uid = uid
                target_username = user['username']
                break

    if not target_uid:
        bot.send_message(msg.chat.id, "❌ Foydalanuvchi topilmadi.")
        bot.register_next_step_handler(msg, find_user)
        return

    u = users[target_uid]

    # Referal statistikasi
    refs = u.get('refs', {})
    total_refs = sum(refs.values())

    text = (
        f"👤 <b>Foydalanuvchi ma'lumotlari</b>\n\n"
        f"🆔 ID: <code>{target_uid}</code>\n"
        f"📛 Username: {safe_username(target_username)}\n"
        f"👤 Ism: {u.get('first_name', 'Nomaʼlum')}\n"
        f"📅 Ro'yxatdan o'tgan sana: {u.get('join_date', 'Nomaʼlum')}\n"
        f"🕐 Oxirgi faollik: {u.get('last_active', 'Nomaʼlum')}\n\n"
        f"💰 Balans: {u.get('balance', 0):,} so'm\n"
        f"⭐ Stars: {u.get('stars', 0)}\n\n"
        f"🎮 O'yinlar: {u.get('games_played', 0)} ta\n"
        f"🏆 Yutuqlar: {u.get('games_won', 0)} ta\n"
        f"👥 Referallar: {total_refs} ta\n\n"
        f"🔒 Holati: {'❌ Bloklangan' if u.get('blocked') else '✅ Faol'}\n"
        f"🔔 Bildirishnomalar: {'✅ Yoqilgan' if u.get('notifications', True) else '❌ Oʻchirilgan'}"
    )

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    if u.get('blocked'):
        markup.add("🔓 Blokdan chiqarish", "💰 Balans o'zgartirish",
                  "⭐ Stars o'zgartirish", "📝 Xabar yuborish", "⬅️ Ortga")
    else:
        markup.add("💰 Balans o'zgartirish", "⭐ Stars o'zgartirish",
                  "🔒 Bloklash", "📝 Xabar yuborish", "⬅️ Ortga")

    bot.send_message(msg.chat.id, text, reply_markup=markup, parse_mode="HTML")
    bot.register_next_step_handler(msg, lambda m, u=target_uid: manage_user(m, u))

def manage_user(msg, uid):
    """Foydalanuvchini boshqarish"""
    if msg.text == "⬅️ Ortga":
        bot.send_message(msg.chat.id, "🔙 Admin panel", reply_markup=admin_menu())
        return

    if msg.text == "💰 Balans o'zgartirish":
        bot.send_message(
            msg.chat.id,
            "💰 Yangi balans miqdorini kiriting:",
            reply_markup=back_menu()
        )
        bot.register_next_step_handler(msg, lambda m, u=uid: change_balance(m, u))
    elif msg.text == "⭐ Stars o'zgartirish":
        bot.send_message(
            msg.chat.id,
            "⭐ Yangi stars miqdorini kiriting:",
            reply_markup=back_menu()
        )
        bot.register_next_step_handler(msg, lambda m, u=uid: change_stars(m, u))
    elif msg.text == "🔒 Bloklash":
        users[uid]['blocked'] = True
        save_data()
        try:
            bot.send_message(
                uid, "❌ Sizning akkauntingiz admin tomonidan bloklangan!"
            )
        except Exception:
            pass
        bot.send_message(msg.chat.id, f"✅ {uid} foydalanuvchi bloklandi!", reply_markup=admin_menu())
    elif msg.text == "🔓 Blokdan chiqarish":
        users[uid]['blocked'] = False
        save_data()
        try:
            bot.send_message(uid, "✅ Sizning akkauntingiz blokdan chiqarildi!")
        except Exception:
            pass
        bot.send_message(msg.chat.id, f"✅ {uid} foydalanuvchi blokdan chiqarildi!", reply_markup=admin_menu())
    elif msg.text == "📝 Xabar yuborish":
        bot.send_message(
            msg.chat.id,
            "📝 Xabar matnini yuboring:",
            reply_markup=back_menu()
        )
        bot.register_next_step_handler(msg, lambda m, u=uid: send_user_message(m, u))
    else:
        bot.send_message(msg.chat.id, "❌ Noto'g'ri tanlov!")
        bot.register_next_step_handler(msg, lambda m, u=uid: manage_user(m, u))

def change_balance(msg, uid):
    """Balansni o'zgartirish"""
    if msg.text == "⬅️ Ortga":
        bot.send_message(msg.chat.id, "🔙 Admin panel", reply_markup=admin_menu())
        return

    try:
        new_balance = int(msg.text.strip())
    except ValueError:
        bot.send_message(msg.chat.id, "❗ Iltimos faqat raqam kiriting.")
        bot.register_next_step_handler(msg, lambda m, u=uid: change_balance(m, u))
        return

    old_balance = users[uid].get('balance', 0)
    users[uid]['balance'] = new_balance
    save_data()

    try:
        bot.send_message(
            uid,
            f"💰 Balansingiz o'zgartirildi:\nEski: {old_balance:,} so'm\nYangi: {new_balance:,} so'm"
        )
    except Exception:
        pass

    bot.send_message(
        msg.chat.id,
        f"✅ Foydalanuvchi balansi o'zgartirildi.\nEski: {old_balance:,}\nYangi: {new_balance:,}",
        reply_markup=admin_menu()
    )

def change_stars(msg, uid):
    """Stars miqdorini o'zgartirish"""
    if msg.text == "⬅️ Ortga":
        bot.send_message(msg.chat.id, "🔙 Admin panel", reply_markup=admin_menu())
        return

    try:
        new_stars = int(msg.text.strip())
    except ValueError:
        bot.send_message(msg.chat.id, "❗ Iltimos faqat raqam kiriting.")
        bot.register_next_step_handler(msg, lambda m, u=uid: change_stars(m, u))
        return

    old_stars = users[uid].get('stars', 0)
    users[uid]['stars'] = new_stars
    save_data()

    try:
        bot.send_message(
            uid,
            f"⭐ Stars miqdoringiz o'zgartirildi:\nEski: {old_stars}\nYangi: {new_stars}"
        )
    except Exception:
        pass

    bot.send_message(
        msg.chat.id,
        f"✅ Foydalanuvchi stars miqdori o'zgartirildi.\nEski: {old_stars}\nYangi: {new_stars}",
        reply_markup=admin_menu()
    )

def send_user_message(msg, uid):
    """Foydalanuvchiga xabar yuborish"""
    if msg.text == "⬅️ Ortga":
        bot.send_message(msg.chat.id, "🔙 Admin panel", reply_markup=admin_menu())
        return

    try:
        if msg.content_type == 'photo':
            bot.send_photo(uid, msg.photo[-1].file_id, caption=msg.caption)
        elif msg.content_type == 'video':
            bot.send_video(uid, msg.video.file_id, caption=msg.caption)
        elif msg.content_type == 'document':
            bot.send_document(uid, msg.document.file_id, caption=msg.caption)
        elif msg.content_type == 'audio':
            bot.send_audio(uid, msg.audio.file_id, caption=msg.caption)
        elif msg.content_type == 'voice':
            bot.send_voice(uid, msg.voice.file_id, caption=msg.caption)
        else:
            bot.send_message(uid, msg.text)

        bot.send_message(msg.chat.id, "✅ Xabar muvaffaqiyatli yuborildi.", reply_markup=admin_menu())
    except Exception as e:
        logging.error(f"Xabarni {uid} ga yuborishda xato: {e}")
        bot.send_message(msg.chat.id, f"❌ Xabar yuborishda xato: {e}")

@bot.message_handler(
    func=lambda m: m.text == "📦 Buyurtmalar boshqaruvi" and is_admin(m.from_user.id)
)
def order_management(msg):
    """Buyurtmalar boshqaruvi"""
    pending_orders = [o for o in orders if o.get('status') == 'pending']

    if not pending_orders:
        bot.send_message(
            msg.chat.id,
            "✅ Hozircha kutilayotgan buyurtmalar mavjud emas.",
            reply_markup=admin_menu()
        )
        return

    text = "📦 <b>Kutilayotgan buyurtmalar</b>:\n\n"
    for i, order in enumerate(pending_orders[:10], 1):
        user_info = users.get(order.get('user_id', ''), {})
        username = user_info.get('username', 'Nomaʼlum')

        if order.get('kind') == 'withdraw':
            order_type = "💸 Pul yechish"
            details = f"Miqdor: {order.get('amount', 0):,} so'm"
        elif order.get('kind') == 'topup':
            order_type = "➕ Hisob to'ldirish"
            details = f"Miqdor: {order.get('amount', 0):,} so'm"
        else:
            order_type = "🛒 Do'kon buyurtmasi"
            details = f"Mahsulot: {order.get('type', 'Nomaʼlum')}"

        text += (f"{i}. {order_type}\n"
                 f"👤 {safe_username(username)} (ID: {order.get('user_id')})\n"
                 f"{details}\n"
                 f"📅 {order.get('date', 'Nomaʼlum')}\n"
                 f"✅ /approve_{orders.index(order)}\n"
                 f"❌ /reject_{orders.index(order)}\n\n")

    bot.send_message(msg.chat.id, text, parse_mode="HTML")

# =========================
# 16. Admin buyruqlari (/approve_, /reject_)
# =========================
@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and (
        m.text.startswith('/approve_') or m.text.startswith('/reject_')
    )
)
def handle_admin_order_action(msg):
    """Admin tomonidan buyurtmani tasdiqlash/rad etish"""
    try:
        if msg.text.startswith('/approve_'):
            action = 'approve'
            order_id = int(msg.text.split('_')[1])
        elif msg.text.startswith('/reject_'):
            action = 'reject'
            order_id = int(msg.text.split('_')[1])
        else:
            return

        if order_id < 0 or order_id >= len(orders):
            bot.send_message(msg.chat.id, "❌ Noto'g'ri buyurtma ID!")
            return

        order = orders[order_id]
        uid = order['user_id']

        if order['status'] != 'pending':
            bot.send_message(msg.chat.id, "ℹ️ Bu buyurtma allaqachon ko'rib chiqilgan.")
            return

        if action == 'approve':
            orders[order_id]['status'] = 'approved'
            
            if order['kind'] == 'withdraw':
                bot.send_message(
                    uid,
                    f"✅ Pul yechish so'rovingiz tasdiqlandi!\n"
                    f"💰 Miqdor: {order['amount']} so'm\n"
                    f"📅 Vaqt: {order['date']}\n\n"
                    f"💸 Pul 1-3 ish kunida hisobingizga o'tkaziladi."
                )
            elif order['kind'] == 'topup':
                # Topup uchun balans allaqachon oshirilgan
                bot.send_message(
                    uid,
                    f"✅ To'lovingiz tasdiqlandi!\n"
                    f"💰 Miqdor: {order['amount']} so'm\n"
                    f"📅 Vaqt: {order['date']}"
                )
            
            bot.send_message(msg.chat.id, f"✅ Buyurtma #{order_id} tasdiqlandi.")
        
        else:  # reject
            orders[order_id]['status'] = 'rejected'
            
            if order['kind'] == 'withdraw':
                users[uid]['balance'] = users[uid].get('balance', 0) + order['amount']
                bot.send_message(
                    uid,
                    f"❌ Pul yechish so'rovingiz rad etildi!\n"
                    f"💰 Miqdor: {order['amount']} so'm balansingizga qaytarildi.\n"
                    f"ℹ️ Sabab: Admin tomonidan rad etildi."
                )
            elif order['kind'] == 'topup':
                bot.send_message(
                    uid,
                    f"❌ To'lovingiz rad etildi!\n"
                    f"ℹ️ Sabab: Admin tomonidan rad etildi."
                )
            
            bot.send_message(msg.chat.id, f"❌ Buyurtma #{order_id} rad etildi.")

        save_data()
    except Exception as e:
        logging.error(f"Admin buyurtma boshqaruvida xato: {e}")
        bot.send_message(msg.chat.id, "❌ Xato yuz berdi. Iltimos, qayta urinib ko'ring.")

@bot.message_handler(
    func=lambda m: m.text == "📊 Statistika" and is_admin(m.from_user.id)
)
def admin_stats(msg):
    """Admin statistikasi"""
    total_users = len(users)
    active_today = sum(1 for u in users.values() if u.get(
        'last_active', '').startswith(datetime.now().strftime('%Y-%m-%d')))
    new_today = sum(1 for u in users.values() if u.get(
        'join_date', '').startswith(datetime.now().strftime('%Y-%m-%d')))
    total_balance = sum(u.get('balance', 0) for u in users.values())
    total_stars = sum(u.get('stars', 0) for u in users.values())
    total_refs = sum(
        u.get('refs', {}).get('level1', 0) for u in users.values())

    total_games = sum(u.get('games_played', 0) for u in users.values())
    total_wins = sum(u.get('games_won', 0) for u in users.values())
    win_rate = round(
        (total_wins / total_games * 100), 2) if total_games > 0 else 0

    text = (
        "📊 <b>Admin statistikasi</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users:,}</b>\n"
        f"🆕 Bugun qo'shilganlar: <b>{new_today}</b>\n"
        f"⚡ Bugun faol bo'lganlar: <b>{active_today}</b>\n\n"
        f"💰 Jami balans: <b>{total_balance:,} so'm</b>\n"
        f"⭐ Jami stars: <b>{total_stars:,}</b>\n"
        f"🤝 Jami referallar: <b>{total_refs:,}</b>\n\n"
        f"📅 Sana: <b>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>"
    )

    bot.send_message(msg.chat.id, text, parse_mode="HTML")

@bot.message_handler(
    func=lambda m: m.text == "⬅️ Asosiy menyu" and is_admin(m.from_user.id)
)
def back_to_main_from_admin(msg):
    """Admin panelidan asosiy menyuga qaytish"""
    bot.send_message(
        msg.chat.id,
        "🔙 Asosiy menyu",
        reply_markup=main_menu(is_admin_flag=True)
    )

# =========================
# 17. Promokodlar
# =========================
@bot.message_handler(func=lambda m: m.text == "🎟 Promokod")
@subscription_required
def promo_code_menu(msg):
    """Promokod menyusi"""
    bot.send_message(msg.chat.id, "🎟 Promokodni kiriting:", reply_markup=back_menu())
    bot.register_next_step_handler(msg, check_promo_code)

def check_promo_code(msg):
    """Promokodni tekshirish"""
    uid = str(msg.from_user.id)

    if msg.text == "⬅️ Ortga":
        bot.send_message(
            msg.chat.id,
            "🔙 Asosiy menyu",
            reply_markup=main_menu(is_admin_flag=is_admin(msg.from_user.id))
        )
        return

    code = msg.text.upper().strip()
    if code in promo_codes:
        if 'used_promo' not in users[uid]:
            users[uid]['used_promo'] = []

        if code not in users[uid]['used_promo']:
            bonus = int(promo_codes[code])
            users[uid]['balance'] = users[uid].get('balance', 0) + bonus
            users[uid]['used_promo'].append(code)
            save_data()
            
            bot.send_message(
                msg.chat.id,
                f"🎉 Promokod muvaffaqiyatli qo'llandi!\n💰 Balansingizga +{bonus} so'm qo'shildi.",
                reply_markup=main_menu(is_admin_flag=is_admin(msg.from_user.id))
            )
        else:
            bot.send_message(
                msg.chat.id,
                "❌ Siz bu promokoddan allaqachon foydalangansiz!",
                reply_markup=main_menu(is_admin_flag=is_admin(msg.from_user.id))
            )
    else:
        bot.send_message(
            msg.chat.id,
            "❌ Noto'g'ri promokod!",
            reply_markup=main_menu(is_admin_flag=is_admin(msg.from_user.id))
        )

# =========================
# 18. Top referallar
# =========================
@bot.message_handler(func=lambda m: m.text == "🏆 Top referallar")
@subscription_required
def top_referrals(msg):
    """Top referallar menyusi"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🥇 1-daraja TOP", "🥈 2-daraja TOP", "🥉 3-daraja TOP",
               "⭐ Umumiy TOP", "🏆 Mening referallarim", "⬅️ Ortga")
    
    bot.send_message(
        msg.chat.id,
        "🏆 Qaysi top referallar ro'yxatini ko'rmoqchisiz?",
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text in [
    "🥇 1-daraja TOP", "🥈 2-daraja TOP", "🥉 3-daraja TOP", "⭐ Umumiy TOP",
    "🏆 Mening referallarim", "⬅️ Ortga"
])
@subscription_required
def show_top_referrals(msg):
    """Top referallarni ko'rsatish"""
    uid = str(msg.from_user.id)

    # 🔙 Ortga
    if msg.text == "⬅️ Ortga":
        bot.send_message(
            msg.chat.id,
            "🔙 Asosiy menyu",
            reply_markup=main_menu(is_admin_flag=is_admin(msg.from_user.id))
        )
        return

    # 🏆 Mening referallarim
    if msg.text == "🏆 Mening referallarim":
        u = users.get(uid, {}).get("refs", {})
        text = (
            f"👤 <b>Sizning referallaringiz</b>\n\n"
            f"🥇 1-daraja: {u.get('level1',0)} ta\n"
            f"🥈 2-daraja: {u.get('level2',0)} ta\n"
            f"🥉 3-daraja: {u.get('level3',0)} ta\n"
            f"⭐ Umumiy: {sum(u.values())} ta"
        )
        bot.send_message(msg.chat.id, text, parse_mode="HTML")
        return

    # Funksiya: TOP list chiqarish
    def format_top(top_users, title, level_key=None):
        text = f"{title}\n\n"
        medals = ["🥇", "🥈", "🥉"]

        for i, (uid, user) in enumerate(top_users, 1):
            if level_key:
                count = user['refs'].get(level_key, 0)
            else:
                count = sum(user.get('refs', {}).values())

            username = safe_username(user.get('username', 'Nomaʼlum'))
            prefix = medals[i - 1] if i <= 3 else f"{i}."
            if level_key:
                text += f"{prefix} {username} — {count} ta referal\n"
            else:
                l1 = user['refs'].get('level1', 0)
                l2 = user['refs'].get('level2', 0)
                l3 = user['refs'].get('level3', 0)
                text += f"{prefix} {username} — {count} ta (1: {l1}, 2: {l2}, 3: {l3})\n"

        return text

    # 🥇 1-daraja TOP
    if msg.text == "🥇 1-daraja TOP":
        top_users = sorted([(uid, u) for uid, u in users.items()
                           if u.get('refs', {}).get('level1', 0) > 0],
                          key=lambda x: x[1]['refs']['level1'],
                          reverse=True)[:10]
        if not top_users:
            bot.send_message(
                msg.chat.id,
                "🥇 Hali 1-darajali top referallar mavjud emas."
            )
            return
        text = format_top(top_users, "🥇 <b>TOP 10 - 1-darajali referallar</b>", "level1")
        bot.send_message(msg.chat.id, text, parse_mode="HTML")

    # 🥈 2-daraja TOP
    elif msg.text == "🥈 2-daraja TOP":
        top_users = sorted([(uid, u) for uid, u in users.items()
                           if u.get('refs', {}).get('level2', 0) > 0],
                          key=lambda x: x[1]['refs']['level2'],
                          reverse=True)[:10]
        if not top_users:
            bot.send_message(
                msg.chat.id,
                "🥈 Hali 2-darajali top referallar mavjud emas."
            )
            return
        text = format_top(top_users, "🥈 <b>TOP 10 - 2-darajali referallar</b>", "level2")
        bot.send_message(msg.chat.id, text, parse_mode="HTML")

    # 🥉 3-daraja TOP
    elif msg.text == "🥉 3-daraja TOP":
        top_users = sorted([(uid, u) for uid, u in users.items()
                           if u.get('refs', {}).get('level3', 0) > 0],
                          key=lambda x: x[1]['refs']['level3'],
                          reverse=True)[:10]
        if not top_users:
            bot.send_message(
                msg.chat.id,
                "🥉 Hali 3-darajali top referallar mavjud emas."
            )
            return
        text = format_top(top_users, "🥉 <b>TOP 10 - 3-darajali referallar</b>", "level3")
        bot.send_message(msg.chat.id, text, parse_mode="HTML")

    # ⭐ Umumiy TOP
    elif msg.text == "⭐ Umumiy TOP":
        def total_refs(u):
            return sum(u.get('refs', {}).values())

        top_users = sorted([(uid, u)
                           for uid, u in users.items() if total_refs(u) > 0],
                          key=lambda x: total_refs(x[1]),
                          reverse=True)[:10]
        if not top_users:
            bot.send_message(
                msg.chat.id,
                "⭐ Hali umumiy top referallar mavjud emas."
            )
            return
        text = format_top(top_users, "⭐ <b>TOP 10 - Umumiy referallar</b>")
        bot.send_message(msg.chat.id, text, parse_mode="HTML")

# =========================
# 19. Admin buyruqlari (/addbal, /block, /unblock, /addpromo)
# =========================
@bot.message_handler(commands=['addbal'])
def add_balance_command(msg):
    """Admin tomonidan balans qo'shish"""
    if not is_admin(msg.from_user.id):
        return

    try:
        _, user_id, amount = msg.text.split()
        amount = int(amount)

        if user_id not in users:
            bot.reply_to(msg, "❌ Foydalanuvchi topilmadi!")
            return

        users[user_id]['balance'] = users[user_id].get('balance', 0) + amount
        save_data()

        bot.reply_to(msg, f"✅ {user_id} foydalanuvchisiga {amount} so'm qo'shildi!")
        try:
            bot.send_message(
                user_id,
                f"💰 Admin sizning balansingizga {amount} so'm qo'shdi!\n"
                f"Yangi balans: {users[user_id]['balance']} so'm"
            )
        except Exception:
            pass
    except Exception:
        bot.reply_to(msg, "❗ Foydalanish: /addbal <user_id> <amount>")

@bot.message_handler(commands=['addstars'])
def add_stars_command(msg):
    """Admin tomonidan stars qo'shish"""
    if not is_admin(msg.from_user.id):
        return

    try:
        _, user_id, amount = msg.text.split()
        amount = int(amount)

        if user_id not in users:
            bot.reply_to(msg, "❌ Foydalanuvchi topilmadi!")
            return

        users[user_id]['stars'] = users[user_id].get('stars', 0) + amount
        save_data()

        bot.reply_to(msg, f"✅ {user_id} foydalanuvchisiga {amount} stars qo'shildi!")
        try:
            bot.send_message(
                user_id,
                f"⭐ Admin sizning stars hisobingizga {amount} stars qo'shdi!\n"
                f"Yangi stars: {users[user_id]['stars']}"
            )
        except Exception:
            pass
    except Exception:
        bot.reply_to(msg, "❗ Foydalanish: /addstars <user_id> <amount>")

@bot.message_handler(commands=['block'])
def block_user_command(msg):
    """Admin tomonidan foydalanuvchini bloklash"""
    if not is_admin(msg.from_user.id):
        return

    try:
        _, user_id = msg.text.split()

        if user_id not in users:
            bot.reply_to(msg, "❌ Foydalanuvchi topilmadi!")
            return

        users[user_id]['blocked'] = True
        save_data()
        bot.reply_to(msg, f"✅ {user_id} foydalanuvchi bloklandi!")
        try:
            bot.send_message(
                user_id,
                "❌ Sizning akkauntingiz admin tomonidan bloklangan!"
            )
        except Exception:
            pass
    except Exception:
        bot.reply_to(msg, "❗ Foydalanish: /block <user_id>")

@bot.message_handler(commands=['unblock'])
def unblock_user_command(msg):
    """Admin tomonidan foydalanuvchini blokdan chiqarish"""
    if not is_admin(msg.from_user.id):
        return

    try:
        _, user_id = msg.text.split()

        if user_id not in users:
            bot.reply_to(msg, "❌ Foydalanuvchi topilmadi!")
            return

        users[user_id]['blocked'] = False
        save_data()
        bot.reply_to(msg, f"✅ {user_id} foydalanuvchi blokdan chiqarildi!")
        try:
            bot.send_message(user_id, "✅ Sizning akkauntingiz blokdan chiqarildi!")
        except Exception:
            pass
    except Exception:
        bot.reply_to(msg, "❗ Foydalanish: /unblock <user_id>")

@bot.message_handler(commands=['addpromo'])
def add_promo(msg):
    """Admin tomonidan promokod qo'shish"""
    if not is_admin(msg.from_user.id):
        return

    try:
        _, code, amount = msg.text.split()
        amount = int(amount)
        promo_codes[code.upper()] = amount
        save_data()
        bot.reply_to(msg, f"✅ Promokod qo'shildi: {code.upper()} - {amount} so'm")
    except Exception:
        bot.reply_to(msg, "❗ Foydalanish: /addpromo <kod> <miqdor>")

@bot.message_handler(commands=['reply'])
def admin_reply(msg):
    """Admin tomonidan foydalanuvchiga javob"""
    if not is_admin(msg.from_user.id):
        bot.reply_to(msg, "⛔ Siz admin emassiz!")
        return

    try:
        parts = msg.text.split(" ", 2)  # /reply user_id xabar
        if len(parts) < 3:
            bot.reply_to(msg, "❌ Foydalanish: /reply <user_id> <xabar>")
            return

        user_id = parts[1]  # foydalanuvchi ID
        text = parts[2]  # admin yozgan matn

        # Foydalanuvchi mavjudligini tekshirish
        if user_id not in users:
            bot.reply_to(msg, "❌ Foydalanuvchi topilmadi!")
            return

        # Foydalanuvchiga xabar yuborish
        try:
            bot.send_message(
                user_id,
                f"📩 <b>Admin javobi:</b>\n{text}",
                parse_mode="HTML"
            )
            bot.reply_to(
                msg,
                f"✅ Xabar foydalanuvchiga yuborildi (ID: {user_id})"
            )

            # Xabarni adminlar logiga yozish
            admin_id = msg.from_user.id
            admin_name = ADMINS.get(admin_id, {}).get("username", "Noma'lum admin")
            logging.info(
                f"Admin {admin_name} ({admin_id}) foydalanuvchi {user_id} ga javob yubordi: {text}"
            )

        except Exception as e:
            bot.reply_to(msg, f"❌ Xabar yuborishda xato: {e}")
            logging.error(f"Foydalanuvchiga javob yuborishda xato: {e}")

    except Exception as e:
        bot.reply_to(msg, f"❌ Xato yuz berdi: {e}")
        logging.error(f"Admin reply commandida xato: {e}")

# =========================
# 20. Boshqa xabarlarni qayta ishlash
# =========================
@bot.message_handler(func=lambda m: True,
                     content_types=[
                         'text', 'photo', 'video', 'document', 'sticker',
                         'audio', 'voice'
                     ])
def catch_all(msg):
    """Barcha xabarlarni qayta ishlash"""
    # username ni doimiy yangilash
    uid = str(msg.from_user.id)
    if uid in users:
        users[uid]["username"] = safe_username(msg.from_user.username)
        users[uid]["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_data()

    # Global "⬅️ Ortga" tugmasi
    if msg.text == "⬅️ Ortga":
        bot.send_message(
            msg.chat.id,
            "🔙 Asosiy menyu",
            reply_markup=main_menu(is_admin_flag=is_admin(msg.from_user.id))
        )
        return

    # Agar noma'lum matn bo'lsa, menyuni ko'rsatamiz
    if msg.text and msg.text not in [
            "📊 Hisobim", "💸 Pul yechish", "➕ Hisobni to'ldirish", "💸 Pul ishlash",
            "🎁 Kunlik bonus", "👥 Referal", "📈 Statistika",
            "🛍 UC / Premium / Stars", "⚙️ Sozlamalar", "🎟 Promokod",
            "🏆 Top referallar", "👨‍💻 Admin panel"
    ]:
        bot.send_message(
            msg.chat.id,
            "🔽 Quyidagi menyulardan birini tanlang:",
            reply_markup=main_menu(is_admin_flag=is_admin(msg.from_user.id))
        )

# =========================
# Botni ishga tushirish
# =========================
if __name__ == "__main__":
    keep_alive()  # KEEP_ALIVE ni ishga tushirish
    logging.info("Bot ishga tushdi")

    try:
        print(f"Bot ishga tushdi. {len(users)} ta foydalanuvchi, {len(orders)} ta buyurtma yuklandi.")
        logging.info(
            f"Bot ishga tushdi - Foydalanuvchilar: {len(users)}, Buyurtmalar: {len(orders)}"
        )

        bot.infinity_polling(timeout=60, long_polling_timeout=60)

    except Exception as e:
        logging.error(f"Botda kritik xato: {e}", exc_info=True)
        print(f"Xato yuz berdi: {e}")

    finally:
        # Dastur tugaganda ma'lumotlarni saqlash
        save_data()
        logging.info("Bot to'xtatildi. Ma'lumotlar saqlandi.")