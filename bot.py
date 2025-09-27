#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import logging
import asyncio
import json
import requests
import threading
from flask import Flask, request
from datetime import datetime, timedelta
import sqlite3
import time
import re
import random
import traceback

from telegram import Update, ChatPermissions, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ----------------------------
# Configuration & env check
# ----------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
RENDER_APP_URL = os.environ.get("RENDER_APP_URL")  # MUST be HTTPS public URL
PORT = int(os.environ.get("PORT", 10000))

if not BOT_TOKEN:
    print("❌ BOT_TOKEN missing (set env var BOT_TOKEN).")
    sys.exit(1)

if not RENDER_APP_URL:
    print("❌ RENDER_APP_URL missing. This script is webhook-only; set RENDER_APP_URL to your public HTTPS URL.")
    sys.exit(1)

# ----------------------------
# Logging: console + file
# ----------------------------
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

# ----------------------------
# Simple SQLite DB helper
# ----------------------------
DB_PATH = os.path.join("data", "group_manager.db")

class Database:
    def __init__(self, path=DB_PATH):
        self.path = path
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cur = self.conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                reputation INTEGER DEFAULT 0,
                warnings INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

db = Database()

# ----------------------------
# Flask app for webhook
# ----------------------------
app = Flask(__name__)

# ----------------------------
# Bot config
# ----------------------------
CONTROVERSIAL_WORDS = [
    "سياسة", "طائفية", "عنصرية", "شتيمة", "سب", "تحريض",
    "كره", "تطرف", "إساءة", "فساد", "فاسد", "سخرية"
]

WELCOME_MESSAGES = [
    "أهلاً وسهلاً 🌹 نورت المجموعة يا {name}! نتمنى لك وقتاً ممتعاً معنا.",
    "مرحباً بك {name} 🤗 اقرأ القواعد واستمتع بالتجربة!",
    "يا هلا ويا مرحب بيك {name} 💫 نورت مجموعتنا!",
    "أهلاً بك {name} في مجموعتنا 🎉 نرجو لك الفائدة والمتعة!"
]

# ----------------------------
# Utility helpers
# ----------------------------
def dump_update_to_file(update: Update, filename="data/last_update.json"):
    """Write full update.to_dict() to a file for debugging (human readable)."""
    try:
        data = update.to_dict()
    except Exception:
        # fallback minimal repr
        data = {"repr": repr(update)}
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("✅ Wrote last update to %s", filename)
    except Exception:
        logger.exception("Failed to write update dump")

# ----------------------------
# GroupManagerBot class
# ----------------------------
class GroupManagerBot:
    def __init__(self, token: str):
        self.token = token
        self.application = Application.builder().token(token).build()
        self.loop = None
        self.setup_handlers()
        logger.info("Bot object initialized")

    def setup_handlers(self):
        # ASCII command names registered with CommandHandler
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("delete", self.delete_messages))
        self.application.add_handler(CommandHandler("warn", self.warn_user))
        self.application.add_handler(CommandHandler("mute", self.mute_user))
        self.application.add_handler(CommandHandler("ban", self.ban_user))
        self.application.add_handler(CommandHandler("rep", self.check_reputation))
        self.application.add_handler(CommandHandler("monitor", self.monitor_user))
        self.application.add_handler(CommandHandler("status", self.status))
        self.application.add_handler(CommandHandler("test", self.test_command))

        # Welcome & controversial detectors
        self.application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.welcome_new_member))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.detect_controversial))

        # Arabic wrappers using compiled regex patterns
        self.application.add_handler(MessageHandler(filters.Regex(re.compile(r'^/مساعدة(?:\s|$)', re.IGNORECASE)), self.arabic_help))
        self.application.add_handler(MessageHandler(filters.Regex(re.compile(r'^/حذف(?:\s|$)', re.IGNORECASE)), self.arabic_delete))
        self.application.add_handler(MessageHandler(filters.Regex(re.compile(r'^/تحذير(?:\s|$)', re.IGNORECASE)), self.arabic_warn))
        self.application.add_handler(MessageHandler(filters.Regex(re.compile(r'^/كتم(?:\s|$)', re.IGNORECASE)), self.arabic_mute))
        self.application.add_handler(MessageHandler(filters.Regex(re.compile(r'^/حظر(?:\s|$)', re.IGNORECASE)), self.arabic_ban))
        self.application.add_handler(MessageHandler(filters.Regex(re.compile(r'^/سمعة(?:\s|$)', re.IGNORECASE)), self.arabic_rep))
        self.application.add_handler(MessageHandler(filters.Regex(re.compile(r'^/مراقبة(?:\s|$)', re.IGNORECASE)), self.arabic_monitor))

    # --------------------------
    # Core command handlers
    # --------------------------
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.info("Received /start from %s", update.effective_user.id)
        await update.message.reply_text("مرحباً! أنا بوت إدارة المجموعات 🛡️\nاستخدم /help لرؤية الأوامر المتاحة")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "🛡️ **أوامر إدارة المجموعة:**\n\n"
            "/delete [عدد] - حذف آخر عدد من الرسائل\n"
            "/warn [السبب] - تحذير مستخدم (بالرد أو @mention)\n"
            "/mute [المدة] - كتم مستخدم (بالرد أو @mention)\n"
            "/ban - حظر مستخدم (بالرد أو @mention)\n"
            "/monitor - إحصائيات\n"
            "/rep - عرض السمعة\n"
            "\nيمكنك أيضا استخدام الأوامر بالعربية مثل /مساعدة و /تحذير (مُلتقطة عبر wrappers)."
        )
        await update.message.reply_text(help_text)

    async def delete_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not context.args:
                await update.message.reply_text("⚡ استخدام: /delete [عدد الرسائل]")
                return
            count = int(context.args[0])
            if count > 100:
                await update.message.reply_text("❌ الحد الأقصى 100 رسالة")
                return
            chat_id = update.effective_chat.id
            message_id = update.message.message_id
            deleted = 0
            for i in range(count + 1):
                try:
                    await context.bot.delete_message(chat_id, message_id - i)
                    deleted += 1
                except Exception:
                    pass
            await update.message.reply_text(f"🗑️ تم حذف {deleted} رسائل بنجاح")
        except Exception as e:
            logger.exception("delete_messages failed: %s", e)
            await update.message.reply_text("❌ خطأ أثناء محاولة الحذف")

    async def welcome_new_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            for member in update.message.new_chat_members:
                me = await context.bot.get_me()
                if member.id == me.id:
                    continue
                name = getattr(member, "first_name", None) or getattr(member, "full_name", None) or "صديق"
                await update.message.reply_text(random.choice(WELCOME_MESSAGES).format(name=name))
        except Exception:
            logger.exception("welcome handler error")

    async def detect_controversial(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            text = (update.message.text or "").lower()
            found = [w for w in CONTROVERSIAL_WORDS if w in text]
            if found:
                try:
                    await update.message.delete()
                except Exception:
                    logger.debug("Could not delete message (maybe missing rights)")
                await context.bot.send_message(update.effective_chat.id, "⚠️ تم حذف رسالة تحتوي على كلمات مثيرة للجدل")
        except Exception:
            logger.exception("detect_controversial failed")

    async def ban_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # re-use helper to resolve user (below), simplified: require reply or mention
        target, _ = await self._resolve_target_user(update, context)
        if not target:
            await update.message.reply_text("⚡ استخدام: رد على رسالة المستخدم + /ban أو /ban @username")
            return
        try:
            await context.bot.ban_chat_member(update.effective_chat.id, target.id)
            await update.message.reply_text("🚫 تم حظر المستخدم")
        except Exception as e:
            logger.exception("ban failed: %s", e)
            await update.message.reply_text(f"❌ تعذر حظر المستخدم: {e}")

    async def check_reputation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.reply_to_message.from_user.id if update.message.reply_to_message else update.effective_user.id
        cur = db.conn.cursor()
        cur.execute("SELECT reputation, warnings FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if row:
            rep, warns = row
            stars = "⭐" * min(rep, 5)
            await update.message.reply_text(f"🌟 السمعة: {rep}\n📊 التحذيرات: {warns}\n{stars}")
        else:
            await update.message.reply_text("❌ المستخدم غير موجود في قاعدة البيانات")

    async def monitor_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        cur = db.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]
        await update.message.reply_text(f"📊 الأعضاء: {count}\n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🟢 البوت يعمل مع Webhooks ✅")

    async def test_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("✅ الاختبار ناجح!")

    # --------------------------
    # Warning & mute helpers
    # --------------------------
    async def add_warning(self, user_id: int, reason: str, username: str = ""):
        try:
            cur = db.conn.cursor()
            cur.execute("INSERT OR IGNORE INTO users (user_id, username, reputation, warnings) VALUES (?, ?, 0, 0)", (user_id, username or ""))
            cur.execute("UPDATE users SET warnings = warnings + 1 WHERE user_id = ?", (user_id,))
            db.conn.commit()
        except Exception:
            logger.exception("add_warning DB error")

    def get_warning_count(self, user_id: int) -> int:
        try:
            cur = db.conn.cursor()
            cur.execute("SELECT warnings FROM users WHERE user_id = ?", (user_id,))
            r = cur.fetchone()
            return r[0] if r else 0
        except Exception:
            return 0

    async def _resolve_target_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Return (telegram.User or None, arg_index:int)
        arg_index indicates how many initial args to skip (0 if no mention/id in args).
        """
        # 1) reply
        if update.message and update.message.reply_to_message:
            try:
                user = update.message.reply_to_message.from_user
                return user, 0
            except Exception:
                pass

        # 2) check entities for text_mention
        if update.message and getattr(update.message, "entities", None):
            for ent in update.message.entities:
                if ent.type == "text_mention" and getattr(ent, "user", None):
                    return ent.user, 0

        # 3) check mention entities (@username) - try to match among chat admins (fast)
        if update.message and getattr(update.message, "entities", None):
            for ent in update.message.entities:
                if ent.type == "mention":
                    username = update.message.text[ent.offset: ent.offset + ent.length]  # includes '@'
                    try:
                        admins = await context.bot.get_chat_administrators(update.effective_chat.id)
                        for adm in admins:
                            if adm.user.username and ("@" + adm.user.username).lower() == username.lower():
                                return adm.user, 1
                    except Exception:
                        logger.debug("Could not fetch admins while resolving mention")

        # 4) numeric id in first arg
        if context.args:
            first = context.args[0]
            try:
                uid = int(first)
                try:
                    member = await context.bot.get_chat_member(update.effective_chat.id, uid)
                    return member.user, 1
                except Exception:
                    pass
            except ValueError:
                pass

        return None, None

    async def warn_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Warns a user. Works when command is:
         - a reply: (reply -> /warn reason)
         - a mention (text_mention)
         - /warn @username reason (if admin present)
         - /warn <id> reason
        The handler always dumps the raw update for debugging at data/last_update.json.
        """
        try:
            logger.info("Handling warn command from %s in chat %s", update.effective_user.id, update.effective_chat.id if update.effective_chat else "N/A")
            dump_update_to_file(update)
        except Exception:
            logger.exception("dump failed")

        target, arg_start = await self._resolve_target_user(update, context)
        if not target:
            await update.message.reply_text(
                "⚡ يجب الرد على رسالة المستخدم أو اذكر @username أو ID.\n"
                "مثال: (رد على رسالة) + /warn سبب\nأو: /warn @username سبب\nأو: /warn 123456 سبب"
            )
            return

        # reason starts after arg_start (if mention/id consumed)
        reason = "(بدون سبب محدد)"
        if context.args:
            parts = context.args[arg_start:]
            if parts:
                reason = " ".join(parts).strip()

        try:
            await self.add_warning(target.id, reason, getattr(target, "username", "") or "")
            count = self.get_warning_count(target.id)
            await update.message.reply_text(f"⚠️ تم تحذير {getattr(target, 'first_name', str(target.id))}\nالسبب: {reason}\nعدد التحذيرات: {count}/3")
            logger.info("Warned user %s (id=%s). Reason: %s", getattr(target,'username',None), target.id, reason)
        except Exception:
            logger.exception("Failed to store warning")
            await update.message.reply_text("❌ خطأ داخلي أثناء حفظ التحذير")

    async def mute_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Mute user by reply/mention/id. Example usage:
         - (reply) /mute 1h
         - /mute @username 30m
         - /mute 123456 1h
        Writes update to data/last_update.json for debugging.
        """
        try:
            logger.info("Handling mute command from %s", update.effective_user.id)
            dump_update_to_file(update)
        except Exception:
            logger.exception("dump failed")

        target, arg_start = await self._resolve_target_user(update, context)
        if not target:
            await update.message.reply_text("⚡ يجب الرد على رسالة المستخدم أو اذكر @username أو ID. مثال: (رد) + /mute 1h")
            return

        # Determine duration argument index
        dur = None
        if context.args:
            # if mention/id consumed, duration is at index arg_start, else at 0
            idx = arg_start if isinstance(arg_start, int) else 0
            if len(context.args) > idx:
                dur = context.args[idx]

        if not dur:
            await update.message.reply_text("❌ يرجى تحديد مدة (مثال: 1h أو 30m).")
            return

        # parse duration
        try:
            if dur.endswith("h"):
                hours = int(dur[:-1])
                until = datetime.now() + timedelta(hours=hours)
            elif dur.endswith("m"):
                minutes = int(dur[:-1])
                until = datetime.now() + timedelta(minutes=minutes)
            else:
                await update.message.reply_text("❌ صيغة المدة غير صحيحة. استخدم 1h أو 30m.")
                return
        except Exception:
            await update.message.reply_text("❌ صيغة المدة غير صحيحة. مثال: 1h أو 30m.")
            return

        # Check bot permission to restrict members
        try:
            me = await context.bot.get_me()
            me_member = await context.bot.get_chat_member(update.effective_chat.id, me.id)
            # Some ChatMember objects have attribute can_restrict_members
            can_restrict = getattr(me_member, "can_restrict_members", None)
            if can_restrict is False:
                await update.message.reply_text("❌ لا أملك صلاحية تقييد الأعضاء. رجاءً ارفعني مشرفاً ومنحني صلاحية Restrict Members.")
                return
        except Exception:
            logger.debug("Could not determine bot admin permissions; attempting to restrict anyway")

        # Try to restrict
        try:
            perms = ChatPermissions(can_send_messages=False)
            await context.bot.restrict_chat_member(update.effective_chat.id, target.id, perms, until_date=until)
            await update.message.reply_text(f"🔇 تم كتم {getattr(target,'first_name',str(target.id))} لمدة {dur}")
            logger.info("Muted user %s until %s", target.id, until.isoformat())
        except Exception as e:
            logger.exception("restrict failed: %s", e)
            await update.message.reply_text(f"❌ تعذر كتم المستخدم: {e}")

    # Arabic wrappers: simply call main implementations
    async def arabic_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.help_command(update, context)

    async def arabic_delete(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.delete_messages(update, context)

    async def arabic_warn(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.warn_user(update, context)

    async def arabic_mute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.mute_user(update, context)

    async def arabic_ban(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.ban_user(update, context)

    async def arabic_rep(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.check_reputation(update, context)

    async def arabic_monitor(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.monitor_user(update, context)

    # --------------------------
    # Webhook setup
    # --------------------------
    async def setup_webhook(self):
        """
        Initialize PTB application, set webhook, start application, capture loop for Flask.
        """
        webhook_url = f"{RENDER_APP_URL.rstrip('/')}/webhook"
        try:
            # initialize -> set webhook -> start -> capture loop
            await self.application.initialize()
            await self.application.bot.set_webhook(webhook_url)
            logger.info("Set webhook to %s", webhook_url)

            # register visible commands in client
            try:
                commands = [
                    BotCommand("start", "Start"),
                    BotCommand("help", "Help"),
                    BotCommand("delete", "Delete messages"),
                    BotCommand("warn", "Warn user"),
                    BotCommand("mute", "Mute user"),
                    BotCommand("ban", "Ban user"),
                ]
                await self.application.bot.set_my_commands(commands)
            except Exception:
                logger.debug("Could not register commands (non-fatal)")

            await self.application.start()
            # capture running loop to allow Flask thread to schedule updates
            self.loop = asyncio.get_running_loop()
            logger.info("Application started and event loop captured")
        except Exception:
            logger.exception("setup_webhook failed")
            raise

# Instantiate bot
group_bot = GroupManagerBot(BOT_TOKEN)

# ----------------------------
# Flask routes
# ----------------------------
@app.route("/", methods=["GET"])
def home():
    return "🟢 Telegram webhook bot running."

@app.route("/webhook", methods=["POST"])
def webhook():
    """
    Receive Telegram update via POST and schedule putting it into application.update_queue.
    We use asyncio.run_coroutine_threadsafe to queue the Update on the bot's event loop.
    """
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, group_bot.application.bot)
        logger.info("Incoming webhook update_id=%s chat=%s user=%s", data.get("update_id"), data.get("message", {}).get("chat", {}).get("id"), data.get("message", {}).get("from", {}).get("id"))
        if getattr(group_bot, "loop", None):
            fut = asyncio.run_coroutine_threadsafe(group_bot.application.update_queue.put(update), group_bot.loop)
            # optionally wait briefly: fut.result(timeout=2)
            return "OK"
        else:
            logger.error("Received webhook but bot loop not ready yet")
            return "NO_LOOP", 500
    except Exception:
        logger.exception("Webhook handling failed")
        return "ERROR", 500

@app.route("/health", methods=["GET"])
def health():
    return {"status":"healthy", "timestamp": datetime.now().isoformat()}

@app.route("/wakeup", methods=["GET"])
def wakeup():
    return {"status":"awake", "timestamp": datetime.now().isoformat()}

# ----------------------------
# Keep-alive (optional)
# ----------------------------
def keep_alive():
    def _run():
        while True:
            try:
                requests.get(f"{RENDER_APP_URL.rstrip('/')}/wakeup", timeout=8)
            except Exception:
                pass
            time.sleep(300)
    thr = threading.Thread(target=_run, daemon=True)
    thr.start()

# ----------------------------
# Runner: start Flask thread then PTB main loop
# ----------------------------
async def main():
    try:
        await group_bot.setup_webhook()
        keep_alive()
        logger.info("Bot ready and running (webhook mode).")
        await asyncio.Event().wait()  # keep running
    except Exception:
        logger.exception("Main failed")
        raise

if __name__ == "__main__":
    # Start Flask in background thread (so it can accept incoming webhook requests)
    def run_flask():
        # NOTE: For production, run behind Gunicorn/Waitress/uvicorn; Flask dev server will show a dev warning.
        app.run(host="0.0.0.0", port=PORT, debug=False)

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Start the PTB application in the main thread's asyncio loop
    asyncio.run(main())
