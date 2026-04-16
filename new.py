import os
import threading

print("🔥 FORCE EXECUTION TRIGGERED")

def run_bot():
    try:
        print("🚀 Starting bot...")

        # 🔥 Import here (delayed import = no build crash)
        import telebot
        import re
        import requests
        import time
        import shutil
        from telebot import types

        API_TOKEN = '8792639999:AAHEMC_d5ccpQv5f_nz0TlApPSUve0e1lMk'

        BASE_DIR = os.getcwd()
        TEMPLATE_DIR = os.path.join(BASE_DIR, "Templates")
        BUILD_DIR = os.path.join(BASE_DIR, "builds")

        bot = telebot.TeleBot(API_TOKEN)

        user_states = {}
        user_tokens = {}
        history = {}

        os.makedirs(TEMPLATE_DIR, exist_ok=True)
        os.makedirs(BUILD_DIR, exist_ok=True)

        def is_authenticated(chat_id):
            if chat_id not in user_tokens:
                bot.send_message(chat_id, "🔑 Send your Vercel token.")
                bot.register_next_step_handler_by_chat_id(chat_id, save_token)
                return False
            return True

        def save_token(message):
            chat_id = message.chat.id
            token = message.text.strip()

            if token.startswith("vcp_") or len(token) > 20:
                user_tokens[chat_id] = token
                bot.send_message(chat_id, "✅ Token saved!")
            else:
                bot.send_message(chat_id, "❌ Invalid token.")

        @bot.message_handler(commands=['start'])
        def start_cmd(message):
            bot.send_message(message.chat.id, "👋 Welcome!")
            is_authenticated(message.chat.id)

        print("🤖 Bot polling...")
        bot.infinity_polling()

    except Exception as e:
        print("❌ Runtime error:", e)


# 🔥 Run in background (so pip doesn’t hang)
try:
    threading.Thread(target=run_bot, daemon=True).start()
except Exception as e:
    print("❌ Thread error:", e)
