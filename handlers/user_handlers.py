#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from database import Database
from utils import get_welcome_message

logger = logging.getLogger("groupmanager")
db = Database()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    logger.info("Received /start from %s", update.effective_user.id)
    await update.message.reply_text("مرحباً! أنا بوت إدارة المجموعات 🛡️\nاستخدم /help لرؤية الأوامر المتاحة")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
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

async def check_reputation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check user reputation"""
    user_id = update.message.reply_to_message.from_user.id if update.message.reply_to_message else update.effective_user.id
    
    stats = db.get_user_stats(user_id)
    stars = "⭐" * min(stats["reputation"], 5)
    await update.message.reply_text(
        f"🌟 السمعة: {stats['reputation']}\n"
        f"📊 التحذيرات: {stats['warnings']}\n{stars}"
    )

async def monitor_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show group statistics"""
    count = db.get_total_users()
    await update.message.reply_text(f"📊 الأعضاء: {count}\n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M')}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check bot status"""
    await update.message.reply_text("🟢 البوت يعمل مع Webhooks ✅")

async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test command"""
    await update.message.reply_text("✅ الاختبار ناجح!")

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome new group members"""
    try:
        for member in update.message.new_chat_members:
            me = await context.bot.get_me()
            if member.id == me.id:
                continue
            name = getattr(member, "first_name", None) or getattr(member, "full_name", None) or "صديق"
            await update.message.reply_text(get_welcome_message(name))
    except Exception:
        logger.exception("welcome handler error")