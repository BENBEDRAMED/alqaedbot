#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import asyncio
import requests
from telegram import Update, ChatPermissions
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime, timedelta
import sqlite3
import threading
from flask import Flask, request
import time
import re
import random
import sys

# -----------------------
# Logging
# -----------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -----------------------
# Environment
# -----------------------
BOT_TOKEN = os.environ.get('BOT_TOKEN')
RENDER_APP_URL = os.environ.get('RENDER_APP_URL')  # e.g., https://your-app.onrender.com
PORT = int(os.environ.get('PORT', 10000))

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not found in environment variables")
    sys.exit(1)

# -----------------------
# Flask app (for webhook)
# -----------------------
app = Flask(__name__)

# -----------------------
# Ensure data dir
# -----------------------
os.makedirs('data', exist_ok=True)

# -----------------------
# Simple SQLite DB helper
# -----------------------
class Database:
    def __init__(self):
        db_path = os.path.join('data', 'group_manager.db')
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
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

# -----------------------
# Bot config
# -----------------------
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

# -----------------------
# Main bot class
# -----------------------
class GroupManagerBot:
    def __init__(self, token: str):
        self.token = token
        self.application = Application.builder().token(token).build()
        self.loop = None  # Will hold the asyncio loop where the application runs (when using webhook)
        self.setup_handlers()
        logger.info("✅ Bot application created successfully")
    
    def setup_handlers(self):
        # Register ASCII command names with CommandHandler (safe for library validation)
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

        # Arabic command wrappers: use compiled regex patterns (cannot pass flags kw directly)
        self.application.add_handler(MessageHandler(filters.Regex(re.compile(r'^/مساعدة(?:\s|$)', re.IGNORECASE)), self.arabic_help))
        self.application.add_handler(MessageHandler(filters.Regex(re.compile(r'^/حذف(?:\s|$)', re.IGNORECASE)), self.arabic_delete))
        self.application.add_handler(MessageHandler(filters.Regex(re.compile(r'^/تحذير(?:\s|$)', re.IGNORECASE)), self.arabic_warn))
        self.application.add_handler(MessageHandler(filters.Regex(re.compile(r'^/كتم(?:\s|$)', re.IGNORECASE)), self.arabic_mute))
        self.application.add_handler(MessageHandler(filters.Regex(re.compile(r'^/حظر(?:\s|$)', re.IGNORECASE)), self.arabic_ban))
        self.application.add_handler(MessageHandler(filters.Regex(re.compile(r'^/سمعة(?:\s|$)', re.IGNORECASE)), self.arabic_rep))
        self.application.add_handler(MessageHandler(filters.Regex(re.compile(r'^/مراقبة(?:\s|$)', re.IGNORECASE)), self.arabic_monitor))

    # -------------------
    # Command implementations
    # -------------------
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("مرحباً! أنا بوت إدارة المجموعات 🛡️\nاستخدم /help لرؤية الأوامر المتاحة")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """
🛡️ **أوامر إدارة المجموعة:**

**الحذف:**
/delete [عدد] - حذف آخر عدد من الرسائل

**التحذير والعقوبات:**
/warn [السبب] - تحذير مستخدم (بالرد)
/mute [المدة] - كتم مستخدم (مثال: /mute 1h)
/ban - حظر مستخدم (بالرد)

**المراقبة:**
/monitor - إحصائيات المراقبة
/rep - عرض السمعة

**المساعدة:**
/مساعدة - عرض الأوامر (عربي)
/help - عرض الأوامر (انجليزي)
"""
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
            
            chat_id = update.message.chat_id
            message_id = update.message.message_id
            
            messages_deleted = 0
            for i in range(count + 1):
                try:
                    await context.bot.delete_message(chat_id, message_id - i)
                    messages_deleted += 1
                except Exception:
                    pass
            
            confirm_msg = await update.message.reply_text(f"🗑️ تم حذف {messages_deleted} رسائل بنجاح")
            await asyncio.sleep(3)
            try:
                await confirm_msg.delete()
            except:
                pass
                
        except ValueError:
            await update.message.reply_text("❌ يرجى إدخال رقم صحيح")

    async def welcome_new_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        for member in update.message.new_chat_members:
            # avoid welcoming the bot itself
            me = await context.bot.get_me()
            if member.id != me.id:
                welcome_text = random.choice(WELCOME_MESSAGES).format(name=getattr(member, "first_name", "صديق") or "صديق")
                await update.message.reply_text(welcome_text)

    async def detect_controversial(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message_text = (update.message.text or "").lower()
        found_words = [word for word in CONTROVERSIAL_WORDS if word in message_text]
        
        if found_words:
            try:
                await update.message.delete()
                await context.bot.send_message(update.message.chat_id, "⚠️ تنبيه: تم حذف رسالة تحتوي على كلمات مثيرة للجدل")
            except Exception as e:
                logger.error(f"Error deleting message: {e}")

    async def warn_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message.reply_to_message or not context.args:
            await update.message.reply_text("⚡ استخدام: رد على رسالة المستخدم + /warn [السبب]")
            return
        
        user_id = update.message.reply_to_message.from_user.id
        reason = " ".join(context.args)
        
        await self.add_warning(user_id, reason)
        warning_count = self.get_warning_count(user_id)
        
        await update.message.reply_text(f"⚠️ تم تحذير المستخدم\nالسبب: {reason}\nعدد التحذيرات: {warning_count}/3")

    async def mute_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message.reply_to_message or not context.args:
            await update.message.reply_text("⚡ استخدام: رد على رسالة المستخدم + /mute [المدة]")
            return
        
        duration = context.args[0]
        user_id = update.message.reply_to_message.from_user.id
        
        try:
            if duration.endswith('h'):
                hours = int(duration[:-1])
                until_date = datetime.now() + timedelta(hours=hours)
            elif duration.endswith('m'):
                minutes = int(duration[:-1])
                until_date = datetime.now() + timedelta(minutes=minutes)
            else:
                await update.message.reply_text("❌ صيغة المدة غير صحيحة (استخدم 1h, 30m)")
                return
            
            permissions = ChatPermissions(can_send_messages=False)
            await context.bot.restrict_chat_member(update.message.chat_id, user_id, permissions, until_date=until_date)
            await update.message.reply_text(f"🔇 تم كتم المستخدم لمدة {duration}")
            
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ في الكتم: {e}")

    async def ban_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.reply_to_message:
            user_id = update.message.reply_to_message.from_user.id
            await context.bot.ban_chat_member(update.message.chat_id, user_id)
            await update.message.reply_text("🚫 تم حظر المستخدم")
        else:
            await update.message.reply_text("⚡ استخدام: رد على رسالة المستخدم + /ban")

    async def check_reputation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.reply_to_message:
            user_id = update.message.reply_to_message.from_user.id
        else:
            user_id = update.message.from_user.id
        
        cursor = db.conn.cursor()
        cursor.execute('SELECT reputation, warnings FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if result:
            reputation, warnings = result
            stars = "⭐" * min(reputation, 5)
            await update.message.reply_text(f"🌟 السمعة: {reputation}\n📊 التحذيرات: {warnings}\n🎖️ {stars}")
        else:
            await update.message.reply_text("❌ المستخدم غير موجود")

    async def monitor_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        cursor = db.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        
        await update.message.reply_text(f"📊 إحصائيات:\n👥 الأعضاء: {user_count}\n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🟢 البوت يعمل بشكل طبيعي مع Webhooks! 🚀")

    async def test_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("✅ الاختبار ناجح! البوت يعمل مع Webhooks")

    # DB helpers
    async def add_warning(self, user_id: int, reason: str):
        cursor = db.conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, reputation, warnings)
            VALUES (?, ?, 0, 0)
        ''', (user_id, ""))
        cursor.execute('UPDATE users SET warnings = warnings + 1 WHERE user_id = ?', (user_id,))
        db.conn.commit()

    def get_warning_count(self, user_id: int) -> int:
        cursor = db.conn.cursor()
        cursor.execute('SELECT warnings FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 0

    # -------------------
    # Arabic wrappers (parse args from message text)
    # -------------------
    async def arabic_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.help_command(update, context)

    async def arabic_delete(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text or ""
        parts = text.split(maxsplit=1)
        if len(parts) == 1:
            await update.message.reply_text("⚡ استخدام: /حذف [عدد الرسائل]")
            return
        try:
            count = int(parts[1].strip())
        except Exception:
            await update.message.reply_text("❌ يرجى إدخال رقم صحيح")
            return
        
        chat_id = update.message.chat_id
        message_id = update.message.message_id
        messages_deleted = 0
        for i in range(count + 1):
            try:
                await context.bot.delete_message(chat_id, message_id - i)
                messages_deleted += 1
            except Exception:
                pass
        confirm_msg = await update.message.reply_text(f"🗑️ تم حذف {messages_deleted} رسائل بنجاح")
        await asyncio.sleep(3)
        try:
            await confirm_msg.delete()
        except:
            pass

    async def arabic_warn(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text or ""
        if not update.message.reply_to_message:
            await update.message.reply_text("⚡ استخدام: رد على رسالة المستخدم + /تحذير [السبب]")
            return
        parts = text.split(maxsplit=1)
        if len(parts) == 1:
            await update.message.reply_text("⚡ اذكر سبب التحذير بعد الأمر")
            return
        reason = parts[1].strip()
        user_id = update.message.reply_to_message.from_user.id
        await self.add_warning(user_id, reason)
        warning_count = self.get_warning_count(user_id)
        await update.message.reply_text(f"⚠️ تم تحذير المستخدم\nالسبب: {reason}\nعدد التحذيرات: {warning_count}/3")

    async def arabic_mute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text or ""
        if not update.message.reply_to_message:
            await update.message.reply_text("⚡ استخدام: رد على رسالة المستخدم + /كتم [المدة]")
            return
        parts = text.split(maxsplit=1)
        if len(parts) == 1:
            await update.message.reply_text("⚡ اذكر المدة بعد الأمر (مثال: /كتم 1h)")
            return
        duration = parts[1].strip()
        user_id = update.message.reply_to_message.from_user.id
        try:
            if duration.endswith('h'):
                hours = int(duration[:-1])
                until_date = datetime.now() + timedelta(hours=hours)
            elif duration.endswith('m'):
                minutes = int(duration[:-1])
                until_date = datetime.now() + timedelta(minutes=minutes)
            else:
                await update.message.reply_text("❌ صيغة المدة غير صحيحة (استخدم 1h, 30m)")
                return
            permissions = ChatPermissions(can_send_messages=False)
            await context.bot.restrict_chat_member(update.message.chat_id, user_id, permissions, until_date=until_date)
            await update.message.reply_text(f"🔇 تم كتم المستخدم لمدة {duration}")
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ في الكتم: {e}")

    async def arabic_ban(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.reply_to_message:
            user_id = update.message.reply_to_message.from_user.id
            try:
                await context.bot.ban_chat_member(update.message.chat_id, user_id)
                await update.message.reply_text("🚫 تم حظر المستخدم")
            except Exception as e:
                await update.message.reply_text(f"❌ خطأ في الحظر: {e}")
        else:
            await update.message.reply_text("⚡ استخدام: رد على رسالة المستخدم + /حظر")

    async def arabic_rep(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.check_reputation(update, context)

    async def arabic_monitor(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.monitor_user(update, context)

    # -------------------
    # Webhook / Polling setup
    # -------------------
    async def setup_webhook(self):
        """
        If RENDER_APP_URL is set, configure webhook and start the application in the current asyncio loop.
        Save that loop in self.loop so external threads (Flask) can schedule tasks safely using
        asyncio.run_coroutine_threadsafe.
        If RENDER_APP_URL is not set, fallback to polling by running run_polling inside a background thread
        with its own asyncio.run(...) call (so the coroutine is actually awaited).
        """
        if RENDER_APP_URL:
            webhook_url = f"{RENDER_APP_URL}/webhook"
            await self.application.bot.set_webhook(webhook_url)
            logger.info(f"✅ Webhook set to: {webhook_url}")
            # initialize and start the application (non-blocking start)
            await self.application.initialize()
            await self.application.start()
            # capture the running loop so Flask route can safely schedule to it
            try:
                self.loop = asyncio.get_running_loop()
                logger.info("✅ Application initialized and started (webhook mode). Event loop captured.")
            except RuntimeError:
                logger.warning("⚠️ Could not capture running loop (unexpected).")
        else:
            # Polling fallback: run asyncio.run(self.application.run_polling()) inside a thread
            logger.warning("❌ RENDER_APP_URL not set, starting polling fallback in a background thread.")
            def run_polling():
                try:
                    asyncio.run(self.application.run_polling(poll_interval=1.0))
                except Exception as e:
                    logger.error(f"Polling failed: {e}")
            thr = threading.Thread(target=run_polling, daemon=True)
            thr.start()

# -----------------------
# Create bot instance
# -----------------------
group_bot = GroupManagerBot(BOT_TOKEN)

# -----------------------
# Flask routes
# -----------------------
@app.route('/')
def home():
    return "🟢 Telegram Bot is Running! Use /start in Telegram"

@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Receive Telegram updates via webhook and put them into the application's update_queue.
    We use asyncio.run_coroutine_threadsafe(coro, loop) to schedule the coroutine on the bot's
    running loop (captured earlier in group_bot.loop), which is thread-safe.
    """
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, group_bot.application.bot)

        # If we have the bot loop (webhook mode), schedule queue.put coroutine on that loop
        if getattr(group_bot, "loop", None):
            fut = asyncio.run_coroutine_threadsafe(group_bot.application.update_queue.put(update), group_bot.loop)
            # optional: wait for result with timeout (not necessary)
            # fut.result(timeout=2)
            return 'OK'
        else:
            # Polling mode: we won't be receiving webhooks normally; return 400
            logger.warning("Received webhook but bot is in polling fallback (no loop captured).")
            return 'NOOP', 400

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'ERROR', 500

@app.route('/health')
def health_check():
    return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}

@app.route('/wakeup')
def wake_up():
    return {'status': 'awake', 'timestamp': datetime.now().isoformat()}

# -----------------------
# Keep-alive thread (optional)
# -----------------------
def keep_alive():
    def run():
        while True:
            try:
                if RENDER_APP_URL:
                    # ping our app to keep awake if desired
                    requests.get(f"{RENDER_APP_URL}/wakeup", timeout=10)
                    logger.debug("✅ Keep-alive request sent")
            except Exception as e:
                logger.debug(f"Keep-alive error: {e}")
            time.sleep(300)
    thread = threading.Thread(target=run, daemon=True)
    thread.start()

# -----------------------
# Starter
# -----------------------
async def main():
    try:
        await group_bot.setup_webhook()
        keep_alive()
        logger.info("✅ Bot setup complete.")
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")

if __name__ == '__main__':
    # Run setup (starts the PTB application either in current loop (webhook) or as a background polling thread)
    asyncio.run(main())

    # Start Flask (blocking)
    # Note: Render/production will provide a proper host; this is fine for many hosts.
    app.run(host='0.0.0.0', port=PORT, debug=False)
