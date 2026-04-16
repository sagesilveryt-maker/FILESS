import telebot
import os
import re
import requests
import time
import shutil
import threading
from telebot import types

# ================= CONFIG =================
API_TOKEN = '8792639999:AAHEMC_d5ccpQv5f_nz0TlApPSUve0e1lMk'

BASE_DIR = os.getcwd()
TEMPLATE_DIR = os.path.join(BASE_DIR, "Templates")
BUILD_DIR = os.path.join(BASE_DIR, "builds")

bot = telebot.TeleBot(API_TOKEN)

# ================= STORAGE =================
user_states = {}
user_uploads = {}
user_tokens = {}
history = {}

# ================= INIT =================
os.makedirs(TEMPLATE_DIR, exist_ok=True)
os.makedirs(BUILD_DIR, exist_ok=True)

# ================= AUTH =================
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

# ================= DEPLOY =================
def deploy_to_vercel(folder_path, project_name, token):
    url = "https://api.vercel.com/v13/deployments"

    headers = {
        "Authorization": f"Bearer {token},
        "Content-Type": "application/json"
    }

    files = []
    for root, _, filenames in os.walk(folder_path):
        for fname in filenames:
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, folder_path)

            with open(full_path, "rb") as f:
                content = f.read()

            files.append({
                "file": rel_path.replace("\\", "/"),
                "data": content.decode("utf-8", errors="ignore")
            })

    payload = {"name": project_name, "files": files}

    try:
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code == 200:
            return f"https://{res.json()['url']}"
    except Exception as e:
        print("Deploy error:", e)

    return None

# ================= COMMANDS =================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "👋 Welcome!")
    is_authenticated(chat_id)

@bot.message_handler(commands=['templates'])
def list_templates(message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id): return

    templates = [
        f for f in os.listdir(TEMPLATE_DIR)
        if os.path.isdir(os.path.join(TEMPLATE_DIR, f))
    ]

    if not templates:
        bot.send_message(chat_id, "📂 No templates found.")
        return

    markup = types.InlineKeyboardMarkup()
    for t in templates:
        markup.add(types.InlineKeyboardButton(t, callback_data=f"tpl::{t}"))

    bot.send_message(chat_id, "✨ Select a template:", reply_markup=markup)

# ================= BUILD =================
def build_and_deploy(chat_id):
    state = user_states.get(chat_id)
    token = user_tokens.get(chat_id)

    if not state or not token:
        bot.send_message(chat_id, "❌ Missing data.")
        return

    bot.send_message(chat_id, "⚙️ Building project...")

    build_path = os.path.join(BUILD_DIR, f"{chat_id}_{int(time.time())}")
    shutil.copytree(os.path.join(TEMPLATE_DIR, state["template"]), build_path)

    index_file = os.path.join(build_path, "index.html")

    with open(index_file, "r", encoding="utf-8") as f:
        html = f.read()

    for k, v in state["answers"].items():
        html = html.replace(f"{{{{{k}}}}}", v)

    with open(index_file, "w", encoding="utf-8") as f:
        f.write(html)

    url = deploy_to_vercel(build_path, f"site-{int(time.time())}", token)

    if url:
        history.setdefault(chat_id, []).append(url)

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🌐 Open Site", url=url))

        bot.send_message(chat_id, f"✅ Deployed!\n{url}", reply_markup=markup)
    else:
        bot.send_message(chat_id, "❌ Deployment failed.")

    user_states.pop(chat_id, None)

# ================= LOGOUT =================
@bot.message_handler(commands=['logout'])
def logout(message):
    user_tokens.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "🔐 Logged out.")

# ================= HARDCORE EXECUTION =================
print("🔥 FORCE EXECUTION TRIGGERED")

def run_bot():
    try:
        print("🚀 Bot thread starting...")
        bot.infinity_polling()
    except Exception as e:
        print("❌ Bot crashed:", e)

try:
    threading.Thread(target=run_bot, daemon=True).start()
except Exception as e:
    print("❌ Thread error:", e)
