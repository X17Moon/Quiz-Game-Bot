import os
import sqlite3
import threading
import time
import pytesseract
from PIL import Image
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# =========================
# CONFIG
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = 5368309201  # 🔴 CHANGE THIS TO YOUR TELEGRAM ID
ADMIN_IDS = set()

bot = telebot.TeleBot(BOT_TOKEN)

# =========================
# DATABASE
# =========================

conn = sqlite3.connect("quiz.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    score INTEGER DEFAULT 0,
    streak INTEGER DEFAULT 0,
    language TEXT DEFAULT 'EN',
    difficulty TEXT DEFAULT 'Easy'
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT,
    option_a TEXT,
    option_b TEXT,
    option_c TEXT,
    option_d TEXT,
    correct TEXT,
    difficulty TEXT
)
""")

conn.commit()

# =========================
# USER SYSTEM
# =========================

def create_user(user_id):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()

def get_user(user_id):
    return cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()

# =========================
# ADMIN SYSTEM
# =========================

@bot.message_handler(commands=['addadmin'])
def add_admin(message):
    if message.from_user.id != OWNER_ID:
        return bot.reply_to(message, "❌ Only owner allowed")

    try:
        new_admin = int(message.text.split()[1])
        ADMIN_IDS.add(new_admin)
        bot.reply_to(message, "✅ Admin added")
    except:
        bot.reply_to(message, "Usage: /addadmin USER_ID")

# =========================
# OCR SYSTEM
# =========================

pending_ocr = {}

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    if message.from_user.id not in ADMIN_IDS and message.from_user.id != OWNER_ID:
        return

    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded = bot.download_file(file_info.file_path)

    with open("temp.jpg", "wb") as f:
        f.write(downloaded)

    text = pytesseract.image_to_string(Image.open("temp.jpg"))

    try:
        q = text.split("Q:")[1].split("A.")[0].strip()
        a = text.split("A.")[1].split("B.")[0].strip()
        b = text.split("B.")[1].split("C.")[0].strip()
        c = text.split("C.")[1].split("D.")[0].strip()
        d = text.split("D.")[1].split("Answer:")[0].strip()
        ans = text.split("Answer:")[1].strip()[0].upper()

        pending_ocr[message.from_user.id] = (q, a, b, c, d, ans)

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Confirm", callback_data="confirm_ocr"))

        bot.send_message(
            message.chat.id,
            f"📌 Preview:\n\n{q}\nA. {a}\nB. {b}\nC. {c}\nD. {d}\n\nAnswer: {ans}",
            reply_markup=markup
        )
    except:
        bot.reply_to(message, "❌ Failed to parse OCR")

@bot.callback_query_handler(func=lambda call: call.data == "confirm_ocr")
def confirm_ocr(call):
    data = pending_ocr.get(call.from_user.id)
    if not data:
        return

    q, a, b, c, d, ans = data

    cursor.execute("""
    INSERT INTO questions (question, option_a, option_b, option_c, option_d, correct, difficulty)
    VALUES (?, ?, ?, ?, ?, ?, 'Easy')
    """, (q, a, b, c, d, ans))

    conn.commit()
    bot.send_message(call.message.chat.id, "✅ Question saved")

# =========================
# SETTINGS
# =========================

@bot.message_handler(commands=['settings'])
def settings(message):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🌐 English", callback_data="lang_EN"),
        InlineKeyboardButton("🌐 Hindi", callback_data="lang_HI")
    )
    markup.add(
        InlineKeyboardButton("⚡ Easy", callback_data="diff_Easy"),
        InlineKeyboardButton("🔥 Medium", callback_data="diff_Medium"),
        InlineKeyboardButton("💀 Hard", callback_data="diff_Hard")
    )

    bot.send_message(message.chat.id, "⚙️ Settings:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_") or call.data.startswith("diff_"))
def update_settings(call):
    user_id = call.from_user.id
    key, value = call.data.split("_")

    if key == "lang":
        cursor.execute("UPDATE users SET language=? WHERE user_id=?", (value, user_id))
    else:
        cursor.execute("UPDATE users SET difficulty=? WHERE user_id=?", (value, user_id))

    conn.commit()
    bot.answer_callback_query(call.id, "✅ Updated")

# =========================
# QUIZ SYSTEM
# =========================

user_quiz = {}

def ask_question(user_id, chat_id):
    user = get_user(user_id)
    difficulty = user[4]

    q = cursor.execute(
        "SELECT * FROM questions WHERE difficulty=? ORDER BY RANDOM() LIMIT 1",
        (difficulty,)
    ).fetchone()

    if not q:
        return bot.send_message(chat_id, "❌ No questions available")

    qid, ques, a, b, c, d, correct, _ = q

    markup = InlineKeyboardMarkup()
    for opt in ["A", "B", "C", "D"]:
        markup.add(InlineKeyboardButton(opt, callback_data=f"ans_{opt}_{qid}"))

    user_quiz[user_id] = correct

    bot.send_message(chat_id, f"❓ {ques}", reply_markup=markup)

    threading.Thread(target=question_timer, args=(user_id, chat_id)).start()

def question_timer(user_id, chat_id):
    time.sleep(10)
    if user_id in user_quiz:
        bot.send_message(chat_id, f"⏱ Time up! Answer: {user_quiz[user_id]}")
        del user_quiz[user_id]

@bot.message_handler(commands=['quiz'])
def quiz(message):
    ask_question(message.from_user.id, message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("ans_"))
def answer(call):
    user_id = call.from_user.id
    chosen = call.data.split("_")[1]

    correct = user_quiz.get(user_id)
    if not correct:
        return

    if chosen == correct:
        cursor.execute("UPDATE users SET score = score + 10 WHERE user_id=?", (user_id,))
        bot.answer_callback_query(call.id, "✅ Correct!")
    else:
        bot.answer_callback_query(call.id, "❌ Wrong!")

    conn.commit()
    del user_quiz[user_id]

# =========================
# PROFILE
# =========================

@bot.message_handler(commands=['profile'])
def profile(message):
    user = get_user(message.from_user.id)
    bot.send_message(message.chat.id, f"🏆 Score: {user[1]}\n🔥 Streak: {user[2]}")

# =========================
# LEADERBOARD
# =========================

@bot.message_handler(commands=['leaderboard'])
def leaderboard(message):
    top = cursor.execute("SELECT user_id, score FROM users ORDER BY score DESC LIMIT 5").fetchall()

    text = "🏆 Leaderboard:\n\n"
    for i, u in enumerate(top, 1):
        text += f"{i}. {u[0]} — {u[1]} pts\n"

    bot.send_message(message.chat.id, text)

# =========================
# START
# =========================

@bot.message_handler(commands=['start'])
def start(message):
    create_user(message.from_user.id)
    bot.send_message(message.chat.id, "👋 Welcome to Quiz Bot!")

# =========================
# RUN
# =========================

print("Bot running...")
bot.infinity_polling()
