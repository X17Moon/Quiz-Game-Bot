import os
import telebot

print("Starting bot...")

# Get token from Railway
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Stop if token missing (prevents crash confusion)
if not BOT_TOKEN:
    raise Exception("BOT_TOKEN not found! Add it in Railway Variables.")

bot = telebot.TeleBot(BOT_TOKEN)

# =========================
# COMMANDS
# =========================

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "👋 Bot is working!")

@bot.message_handler(commands=['help'])
def help_cmd(message):
    bot.send_message(message.chat.id, "Use /start to check bot")

# =========================
# RUN BOT (NO CRASH LOOP)
# =========================

while True:
    try:
        print("Bot running...")
        bot.infinity_polling()
    except Exception as e:
        print("Error:", e)
