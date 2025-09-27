#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import logging
import asyncio
import threading
import time
import requests
from flask import Flask, request

from config import BOT_TOKEN, RENDER_APP_URL, PORT
from bot import GroupManagerBot

# Setup logging
os.makedirs("data", exist_ok=True)
log_file = os.path.join("data", "bot.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8")
    ]
)
logger = logging.getLogger("groupmanager")

# Initialize bot
group_bot = GroupManagerBot(BOT_TOKEN)

# Flask app
app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "🟢 Telegram webhook bot running."

@app.route("/webhook", methods=["POST"])
def webhook():
    """Receive Telegram updates"""
    try:
        data = request.get_json(force=True)
        from telegram import Update
        update = Update.de_json(data, group_bot.application.bot)
        logger.info("Incoming webhook update_id=%s", data.get("update_id"))
        
        if getattr(group_bot, "loop", None):
            fut = asyncio.run_coroutine_threadsafe(group_bot.application.update_queue.put(update), group_bot.loop)
            return "OK"
        else:
            logger.error("Received webhook but bot loop not ready yet")
            return "NO_LOOP", 500
    except Exception:
        logger.exception("Webhook handling failed")
        return "ERROR", 500

@app.route("/health", methods=["GET"])
def health():
    return {"status":"healthy", "timestamp": time.time()}

@app.route("/wakeup", methods=["GET"])
def wakeup():
    return {"status":"awake", "timestamp": time.time()}

def keep_alive():
    """Keep the app awake"""
    def _run():
        while True:
            try:
                requests.get(f"{RENDER_APP_URL.rstrip('/')}/wakeup", timeout=8)
            except Exception:
                pass
            time.sleep(300)
    thr = threading.Thread(target=_run, daemon=True)
    thr.start()

async def main():
    """Main async function"""
    try:
        webhook_url = f"{RENDER_APP_URL.rstrip('/')}/webhook"
        await group_bot.setup_webhook(webhook_url)
        keep_alive()
        logger.info("Bot ready and running (webhook mode).")
        await asyncio.Event().wait()  # Keep running
    except Exception:
        logger.exception("Main failed")
        raise

if __name__ == "__main__":
    # Start Flask in background thread
    def run_flask():
        app.run(host="0.0.0.0", port=PORT, debug=False)

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Start the bot
    asyncio.run(main())