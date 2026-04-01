import os
import telebot
import sqlite3
import random
import time
import threading
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

print("🚀 Starting Kahoot Quiz Bot...")

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
    score INTEGER DEFAULT 0
)
""")

conn.commit()

# =========================
# QUESTIONS
# =========================

questions = [
    {"q": "2+2?", "options": ["3", "4", "5", "6"], "answer": "4"},
    {"q": "Capital of India?", "options": ["Mumbai", "Delhi", "Goa", "Chennai"], "answer": "Delhi"},
    {"q": "Python is?", "options": ["Animal", "Language", "Car", "Game"], "answer": "Language"}
]

# =========================
# GAME STATE
# =========================

group_games = {}

# =========================
# START GAME
# =========================

@bot.message_handler(commands=['startgame'])
def start_game(message):
    chat_id = message.chat.id

    if message.chat.type == "private":
        return bot.send_message(chat_id, "❌ Use this in a group!")

    group_games[chat_id] = {
        "scoreboard": {},
        "current": 0,
        "active": True,
        "answered": False
    }

    bot.send_message(chat_id, "🎮 Game started! Get ready...")
    ask_group_question(chat_id)

# =========================
# ASK QUESTION
# =========================

def ask_group_question(chat_id):
    game = group_games.get(chat_id)

    if not game or not game["active"]:
        return

    if game["current"] >= len(questions):
        end_game(chat_id)
        return

    q = questions[game["current"]]
    game["answered"] = False

    markup = InlineKeyboardMarkup()

    for opt in q["options"]:
        markup.add(InlineKeyboardButton(opt, callback_data=f"gans_{opt}"))

    bot.send_message(
        chat_id,
        f"❓ {q['q']}\n⏱ 10 seconds!",
        reply_markup=markup
    )

    threading.Thread(target=group_timer, args=(chat_id,)).start()

# =========================
# TIMER
# =========================

def group_timer(chat_id):
    time.sleep(10)

    game = group_games.get(chat_id)
    if not game or game["answered"]:
        return

    correct = questions[game["current"]]["answer"]

    bot.send_message(chat_id, f"⏱ Time's up!\n✅ Answer: {correct}")

    game["current"] += 1
    ask_group_question(chat_id)

# =========================
# ANSWER HANDLER
# =========================

@bot.callback_query_handler(func=lambda call: call.data.startswith("gans_"))
def handle_group_answer(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id

    game = group_games.get(chat_id)

    if not game or game["answered"]:
        return

    selected = call.data.split("_")[1]
    correct = questions[game["current"]]["answer"]

    if selected == correct:
        game["answered"] = True

        # update score
        if user_id not in game["scoreboard"]:
            game["scoreboard"][user_id] = 0

        game["scoreboard"][user_id] += 10

        bot.send_message(
            chat_id,
            f"🏆 {call.from_user.first_name} answered first!\n+10 points"
        )

        game["current"] += 1
        time.sleep(2)
        ask_group_question(chat_id)

# =========================
# END GAME
# =========================

def end_game(chat_id):
    game = group_games.get(chat_id)

    if not game:
        return

    text = "🏁 Game Over!\n\n🏆 Final Leaderboard:\n\n"

    sorted_scores = sorted(game["scoreboard"].items(), key=lambda x: x[1], reverse=True)

    for i, (uid, score) in enumerate(sorted_scores, 1):
        text += f"{i}. {uid} — {score} pts\n"

    bot.send_message(chat_id, text)

    del group_games[chat_id]

# =========================
# RUN
# =========================

while True:
    try:
        print("🤖 Bot running...")
        bot.infinity_polling()
    except Exception as e:
        print("Error:", e)
        time.sleep(5)
