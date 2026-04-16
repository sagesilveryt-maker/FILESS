import telebot
import os
import re
import requests
import time
import shutil
from telebot import types

# ================= CONFIG =================
# KEEP YOUR BOT TOKEN HERE OR USE ENV VARS
API_TOKEN = '8792639999:AAHEMC_d5ccpQv5f_nz0TlApPSUve0e1lMk'

BASE_DIR = os.getcwd()
TEMPLATE_DIR = os.path.join(BASE_DIR, "Templates")
BUILD_DIR = os.path.join(BASE_DIR, "builds")

bot = telebot.TeleBot(API_TOKEN)

# Storage
user_states = {}
user_uploads = {}
user_tokens = {} # Stores {chat_id: vercel_token}
history = {}

# ================= INIT =================
os.makedirs(TEMPLATE_DIR, exist_ok=True)
os.makedirs(BUILD_DIR, exist_ok=True)

# ================= AUTH HELPER =================
def is_authenticated(chat_id):
    if chat_id not in user_tokens:
        bot.send_message(chat_id, "🔑 **Access Denied.**\nPlease send your Vercel Access Token to continue.")
        bot.register_next_step_handler_by_chat_id(chat_id, save_token)
        return False
    return True

def save_token(message):
    chat_id = message.chat.id
    token = message.text.strip()
    
    if token.startswith("vcp_") or len(token) > 20: # Basic validation
        user_tokens[chat_id] = token
        bot.send_message(chat_id, "✅ Token saved! You can now use /templates or /new_template.")
    else:
        bot.send_message(chat_id, "❌ Invalid token format. Please try again.")

# ================= DEPLOY =================
def deploy_to_vercel(folder_path, project_name, token):
    url = "https://api.vercel.com/v13/deployments"

    headers = {
        "Authorization": f"Bearer {token}",
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
        else:
            return None
    except Exception:
        return None

# ================= COMMANDS =================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "👋 Welcome! To use this bot, I need your Vercel API Token.")
    is_authenticated(chat_id)

@bot.message_handler(commands=['templates'])
def list_templates(message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id): return

    templates = [f for f in os.listdir(TEMPLATE_DIR) if os.path.isdir(os.path.join(TEMPLATE_DIR, f))]

    if not templates:
        bot.send_message(chat_id, "📂 No templates found. Use /new_template")
        return

    markup = types.InlineKeyboardMarkup()
    for t in templates:
        markup.add(types.InlineKeyboardButton(t, callback_data=f"tpl::{t}"))
    bot.send_message(chat_id, "✨ Select a template:", reply_markup=markup)

# ================= UPDATED BUILD + DEPLOY =================
def build_and_deploy(chat_id):
    state = user_states[chat_id]
    token = user_tokens.get(chat_id)
    
    if not token:
        bot.send_message(chat_id, "❌ Token missing. Use /start")
        return

    bot.send_message(chat_id, "⚙️ Building project...")
    
    # ... (Same directory logic as your original code) ...
    build_path = os.path.join(BUILD_DIR, f"{chat_id}_{int(time.time())}")
    shutil.copytree(os.path.join(TEMPLATE_DIR, state["template"]), build_path)
    
    index_file = os.path.join(build_path, "index.html")
    with open(index_file, "r", encoding="utf-8") as f:
        html = f.read()
    for k, v in state["answers"].items():
        html = html.replace(f"{{{{{k}}}}}", v)
    with open(index_file, "w", encoding="utf-8") as f:
        f.write(html)

    # Pass the user-specific token here
    url = deploy_to_vercel(build_path, f"site-{int(time.time())}", token)

    if url:
        history.setdefault(chat_id, []).append(url)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🌐 Open Site", url=url))
        bot.send_message(chat_id, f"✅ Deployed successfully!\n{url}", reply_markup=markup)
    else:
        bot.send_message(chat_id, "❌ Deploy failed. Check if your Vercel token is still valid.")

    user_states.pop(chat_id, None)

# ================= REST OF HANDLERS =================
# (Keep your existing callback_query_handlers, upload_file, and done handlers)
# Just ensure you add 'if not is_authenticated(chat_id): return' to the top of 
# 'new_template' and 'sites' functions.

@bot.message_handler(commands=['logout'])
def logout(message):
    user_tokens.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "🔐 Logged out. Token removed from session.")

print("🔥 Bot with dynamic Auth running...")
bot.infinity_polling()

