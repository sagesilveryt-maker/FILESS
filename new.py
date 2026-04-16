import telebot
import os
import re
import requests
import time
import shutil
from telebot import types

# ================= CONFIG =================
API_TOKEN = '8792639999:AAH5ZVI8WSGc42ddbQTOuVItlM6cZdRemYc'
VERCEL_TOKEN = 'vcp_24JcADhn43icJVfaoRr36ndUZlIUx273nm6GB4aaVhuChahyZF2nuNgq'

BASE_DIR = os.getcwd()
TEMPLATE_DIR = os.path.join(BASE_DIR, "Templates")
BUILD_DIR = os.path.join(BASE_DIR, "builds")

bot = telebot.TeleBot(API_TOKEN)

user_states = {}
user_uploads = {}
history = {}

# ================= INIT =================
os.makedirs(TEMPLATE_DIR, exist_ok=True)
os.makedirs(BUILD_DIR, exist_ok=True)

# ================= DEPLOY =================
def deploy_to_vercel(folder_path, project_name):
    url = "https://api.vercel.com/v13/deployments"

    headers = {
        "Authorization": f"Bearer {VERCEL_TOKEN}",
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

    payload = {
        "name": project_name,
        "files": files
    }

    try:
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code == 200:
            return f"https://{res.json()['url']}"
        else:
            print("Vercel Error:", res.text)
            return None
    except Exception as e:
        print("Deploy Error:", e)
        return None

# ================= START =================
@bot.message_handler(commands=['start', 'templates'])
def list_templates(message):
    chat_id = message.chat.id
    user_states.pop(chat_id, None)

    templates = [f for f in os.listdir(TEMPLATE_DIR)
                 if os.path.isdir(os.path.join(TEMPLATE_DIR, f))]

    if not templates:
        bot.send_message(chat_id, "📂 No templates. Use /new_template")
        return

    markup = types.InlineKeyboardMarkup()
    for t in templates:
        markup.add(types.InlineKeyboardButton(t, callback_data=f"tpl::{t}"))

    bot.send_message(chat_id, "✨ Select template:", reply_markup=markup)

# ================= TEMPLATE SELECT =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("tpl::"))
def select_template(call):
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)

    name = call.data.split("::")[1]
    index_path = os.path.join(TEMPLATE_DIR, name, "index.html")

    if not os.path.exists(index_path):
        bot.send_message(chat_id, "❌ index.html missing.")
        return

    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()

    matches = re.findall(r"\{\{(.*?)(?::(.*?))?\}\}", html)

    user_states[chat_id] = {
        "template": name,
        "vars": [m[0] for m in matches],
        "defaults": {m[0]: m[1] for m in matches if m[1]},
        "answers": {},
        "index": 0,
        "raw_html": html
    }

    ask_next(chat_id)

# ================= VARIABLE INPUT =================
def ask_next(chat_id):
    state = user_states[chat_id]

    if state["index"] >= len(state["vars"]):
        preview(chat_id)
        return

    var = state["vars"][state["index"]]
    default = state["defaults"].get(var, "")

    text = f"📝 {var}"
    if default:
        text += f"\n(Default: {default})"

    msg = bot.send_message(chat_id, text)
    bot.register_next_step_handler(msg, save_input)

def save_input(message):
    chat_id = message.chat.id
    if chat_id not in user_states:
        return

    state = user_states[chat_id]
    var = state["vars"][state["index"]]

    val = message.text.strip() if message.text else ""
    if not val:
        val = state["defaults"].get(var, "")

    state["answers"][var] = val
    state["index"] += 1

    ask_next(chat_id)

# ================= PREVIEW =================
def preview(chat_id):
    state = user_states[chat_id]
    html = state["raw_html"]

    for k, v in state["answers"].items():
        html = html.replace(f"{{{{{k}}}}}", v)

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🚀 Deploy", callback_data="deploy::yes"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="deploy::no")
    )

    bot.send_message(chat_id, f"<code>{html[:600]}</code>",
                     parse_mode="HTML", reply_markup=markup)

# ================= DEPLOY ACTION =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("deploy::"))
def handle_deploy(call):
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)

    if call.data.endswith("no"):
        user_states.pop(chat_id, None)
        bot.send_message(chat_id, "❌ Cancelled.")
        return

    build_and_deploy(chat_id)

# ================= BUILD + DEPLOY =================
def build_and_deploy(chat_id):
    state = user_states[chat_id]
    template_name = state["template"]

    bot.send_message(chat_id, "⚙️ Building...")

    build_path = os.path.join(BUILD_DIR, f"{chat_id}_{int(time.time())}")
    shutil.copytree(os.path.join(TEMPLATE_DIR, template_name), build_path)

    index_file = os.path.join(build_path, "index.html")

    with open(index_file, "r", encoding="utf-8") as f:
        html = f.read()

    for k, v in state["answers"].items():
        html = html.replace(f"{{{{{k}}}}}", v)

    with open(index_file, "w", encoding="utf-8") as f:
        f.write(html)

    url = deploy_to_vercel(build_path, f"site-{int(time.time())}")

    if url:
        history.setdefault(chat_id, []).append(url)

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🌐 Open", url=url))

        bot.send_message(chat_id, f"✅ Deployed:\n{url}", reply_markup=markup)
    else:
        bot.send_message(chat_id, "❌ Deploy failed.")

    user_states.pop(chat_id, None)

# ================= TEMPLATE UPLOAD =================
@bot.message_handler(commands=['new_template'])
def new_template(message):
    msg = bot.send_message(message.chat.id, "📁 Template name:")
    bot.register_next_step_handler(msg, create_template)

def create_template(message):
    chat_id = message.chat.id
    name = message.text.strip()

    path = os.path.join(TEMPLATE_DIR, name)

    if os.path.exists(path):
        bot.send_message(chat_id, "⚠️ Exists already.")
        return

    os.makedirs(path)

    user_uploads[chat_id] = {"path": path}

    bot.send_message(chat_id, "📤 Upload files. Use /done when finished.")

# ================= FILE HANDLER =================
@bot.message_handler(content_types=['document'])
def upload_file(message):
    chat_id = message.chat.id

    if chat_id not in user_uploads:
        return

    file_info = bot.get_file(message.document.file_id)
    file_data = bot.download_file(file_info.file_path)

    fname = message.document.file_name
    save_path = os.path.join(user_uploads[chat_id]["path"], fname)

    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    with open(save_path, "wb") as f:
        f.write(file_data)

    bot.send_message(chat_id, f"✅ {fname}")

# ================= DONE =================
@bot.message_handler(commands=['done'])
def finish_template(message):
    chat_id = message.chat.id

    if chat_id not in user_uploads:
        return

    path = user_uploads[chat_id]["path"]

    if not os.path.exists(os.path.join(path, "index.html")):
        bot.send_message(chat_id, "❌ index.html required.")
        return

    user_uploads.pop(chat_id)
    bot.send_message(chat_id, "✅ Template ready.")

# ================= HISTORY =================
@bot.message_handler(commands=['my_sites'])
def sites(message):
    chat_id = message.chat.id
    links = history.get(chat_id, [])

    if not links:
        bot.send_message(chat_id, "No sites.")
    else:
        bot.send_message(chat_id, "\n".join(links))

# ================= CANCEL =================
@bot.message_handler(commands=['cancel'])
def cancel(message):
    user_states.pop(message.chat.id, None)
    user_uploads.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "❌ Cancelled.")

# ================= RUN =================
print("🔥 Hardcore bot running...")
bot.infinity_polling()