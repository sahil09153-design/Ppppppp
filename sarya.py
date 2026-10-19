import logging
import asyncio
import random
import os
import threading
from flask import Flask
from telegram import Update
from telegram.error import RetryAfter, Forbidden
from telegram.ext import Application, MessageHandler, ContextTypes, filters

# ─── LOGGING FIX (Render Logs Full Na Ho Isliye) ───
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("werkzeug").setLevel(logging.WARNING) 

# ─── FLASK WEB SERVER (Render 24/7 ke liye) ───
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "NC BOT IS ALIVE!"
def run_web(): 
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# ─── CONFIGURATION ───
OWNER_ID = int(os.environ.get("OWNER_ID", "0")) 
DELAY = 0.3  # 👈 Fixed Speed: 0.3 seconds
EMOJIS = ["🔥", "⚡", "💀", "🚀", "🌞", "✅", "💋", "😝"]

# ─── CONTROLLER ───
class Controller:
    def __init__(self):
        self.active = {}

    def stop_chat(self, chat_id):
        if chat_id in self.active:
            tasks = self.active.pop(chat_id)
            for task in tasks:
                if not task.done():
                    task.cancel()

ctrl = Controller()
bots = []

# ─── NC LOOP ───
async def nc_loop(bot, chat_id, text):
    while True:
        try:
            e = random.choice(EMOJIS)
            title = f"{e}{text}{e}"[:255]
            await bot.set_chat_title(chat_id=chat_id, title=title)
            
            await asyncio.sleep(DELAY)
            
        except asyncio.CancelledError:
            break 
        except RetryAfter as e:
            logger.warning(f"Flood wait: {e.retry_after}s")
            await asyncio.sleep(e.retry_after + 1) 
        except Forbidden:
            break 
        except Exception as e:
            logger.error(f"NC Error: {e}")
            await asyncio.sleep(2) 

# ─── COMMAND ROUTER ───
async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg: return
    text = msg.text or ""
    if not (text.startswith("/") or text.startswith(".")): return

    user = update.effective_user
    if not user or user.id != OWNER_ID: return

    parts = text.split(maxsplit=1)
    cmd = parts[0][1:].split("@")[0].lower()
    args = parts[1].split() if len(parts) > 1 else []

    if cmd == "nc":
        if not args: return await msg.reply_text("Usage: /nc <text>")
        target = ' '.join(args)
        chat_id = update.effective_chat.id
        
        ctrl.stop_chat(chat_id)
        ctrl.active[chat_id] = []
        
        for b in bots:
            task = asyncio.create_task(nc_loop(b['bot'], chat_id, target))
            ctrl.active[chat_id].append(task)
            
        await msg.reply_text(f"✅ NC STARTED: {target}\n⚡ Fixed Speed: {DELAY}s")

    elif cmd == "stop":
        chat_id = update.effective_chat.id
        if ctrl.active.get(chat_id):
            ctrl.stop_chat(chat_id)
            await msg.reply_text("🛑 STOPPED")
        else:
            await msg.reply_text("⚠️ NO ACTIVE NC")

# ─── MAIN RUNNER (Single Bot) ───
async def run_bot(tok):
    try:
        app = Application.builder().token(tok).connect_timeout(10).read_timeout(30).build()
        me = await app.bot.get_me()
        
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router))
        app.add_handler(MessageHandler(filters.COMMAND, router))
        
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True) 
        
        bots.append({'id': me.id, 'bot': app.bot, 'app': app})
        print(f"✅ Started @{me.username}")
        
        await asyncio.Event().wait() 
    except Exception as e:
        print(f"❌ Fail: {e}")

async def main():
    print("[*] Starting Web Server...")
    threading.Thread(target=run_web, daemon=True).start()

    tok = os.environ.get("BOT_TOKEN")
    if not tok:
        print("[!] ERROR: BOT_TOKEN not found in Render.")
        return

    print(f"[*] Starting Bot with fixed {DELAY}s delay...")
    await run_bot(tok.strip())

if __name__ == "__main__":
    asyncio.run(main())
