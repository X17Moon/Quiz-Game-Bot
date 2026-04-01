import os
import telebot
import sqlite3
import random
import time
import threading
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

print("🚀 Starting Advanced Quiz Bot...")

# =========================
# TOKEN
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise Exception("❌ BOT_TOKEN not set!")

bot = telebot.TeleBot(BOT_TOKEN)

# =========================
# DATABASE
# =========================

conn = sqlite3.connect("/tmp/quiz.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    score INTEGER DEFAULT 0,
    streak INTEGER DEFAULT 0
)
""")

conn.commit()

# =========================
# QUESTIONS
# =========================

questions = [
    {
        "q": "What is 2 + 2?",
        "options": ["3", "4", "5", "6"],
        "answer": "4"
    },
    {
        "q": "Capital of India?",
        "options": ["Mumbai", "Delhi", "Kolkata", "Chennai"],
        "answer": "Delhi"
    },
    {
        "q": "Which is a programming language?",
        "options": ["Python", "Snake", "Lion", "Tiger"],
        "answer": "Python"
    }
]

# =========================
# USER SYSTEM
# =========================

def create_user(user_id):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()

# =========================
# QUIZ STATE
# =========================

active_quiz = {}

# =========================
# COMMANDS
# =========================

@bot.message_handler(commands=['start'])
def start(message):
    create_user(message.from_user.id)
    bot.send_message(message.chat.id, "👋 Welcome!\nUse /quiz to start.")

@bot.message_handler(commands=['quiz'])
def quiz(message):
    user_id = message.from_user.id
    q = random.choice(questions)

    active_quiz[user_id] = {
        "answer": q["answer"],
        "answered": False
    }

    markup = InlineKeyboardMarkup()

    for opt in q["options"]:
        markup.add(InlineKeyboardButton(opt, callback_data=f"ans_{opt}"))

    bot.send_message(
        message.chat.id,
        f"❓ {q['q']}\n⏱ You have 10 seconds!",
        reply_markup=markup
    )

    # Start timer
    threading.Thread(target=timer, args=(user_id, message.chat.id)).start()

# =========================
# TIMER
# =========================

def timer(user_id, chat_id):
    time.sleep(10)

    if user_id in active_quiz and not active_quiz[user_id]["answered"]:
        correct = active_quiz[user_id]["answer"]
        bot.send_message(chat_id, f"⏱ Time's up!\n✅ Answer: {correct}")
        del active_quiz[user_id]

# =========================
# ANSWER HANDLER
# =========================

@bot.callback_query_handler(func=lambda call: call.data.startswith("ans_"))
def answer(call):
    user_id = call.from_user.id

    if user_id not in active_quiz:
        return

    if active_quiz[user_id]["answered"]:
        return

    selected = call.data.split("_")[1]
    correct = active_quiz[user_id]["answer"]

    active_quiz[user_id]["answered"] = True

    if selected == correct:
        cursor.execute(
            "UPDATE users SET score = score + 10, streak = streak + 1 WHERE user_id=?",
            (user_id,)
        )
        bot.answer_callback_query(call.id, "✅ Correct!")
        bot.send_message(call.message.chat.id, "🎉 Correct! +10 points")
    else:
        cursor.execute(
            "UPDATE users SET streak = 0 WHERE user_id=?",
            (user_id,)
        )
        bot.answer_callback_query(call.id, "❌ Wrong!")
        bot.send_message(call.message.chat.id, f"❌ Wrong!\n✅ Answer: {correct}")

    conn.commit()
    del active_quiz[user_id]

# =========================
# PROFILE
# =========================

@bot.message_handler(commands=['profile'])
def profile(message):
    user = cursor.execute(
        "SELECT score, streak FROM users WHERE user_id=?",
        (message.from_user.id,)
    ).fetchone()

    bot.send_message(
        message.chat.id,
        f"👤 Profile\n\n🏆 Score: {user[0]}\n🔥 Streak: {user[1]}"
    )

# =========================
# LEADERBOARD
# =========================

@bot.message_handler(commands=['leaderboard'])
def leaderboard(message):
    top = cursor.execute(
        "SELECT user_id, score FROM users ORDER BY score DESC LIMIT 5"
    ).fetchall()

    text = "🏆 Leaderboard:\n\n"
    for i, u in enumerate(top, 1):
        text += f"{i}. {u[0]} — {u[1]} pts\n"

    bot.send_message(message.chat.id, text)

# =========================
# RUN (SAFE LOOP)
# =========================

while True:
    try:
        print("🤖 Bot running...")
        bot.infinity_polling()
    except Exception as e:
        print("Error:", e)
        time.sleep(5)
