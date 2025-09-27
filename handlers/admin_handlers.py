#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from telegram import Update
from telegram.ext import ContextTypes

from database import Database
from utils import dump_update_to_file, resolve_target_user, parse_duration, check_bot_permissions

logger = logging.getLogger("groupmanager")
db = Database()

async def delete_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete specified number of messages"""
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

async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Warn a user"""
    try:
        logger.info("Handling warn command from %s", update.effective_user.id)
        dump_update_to_file(update)
    except Exception:
        logger.exception("dump failed")

    target, arg_start = await resolve_target_user(update, context)
    if not target:
        await update.message.reply_text(
            "⚡ يجب الرد على رسالة المستخدم أو اذكر @username أو ID.\n"
            "مثال: (رد على رسالة) + /warn سبب\nأو: /warn @username سبب\nأو: /warn 123456 سبب"
        )
        return

    reason = "(بدون سبب محدد)"
    if context.args and len(context.args) > arg_start:
        reason = " ".join(context.args[arg_start:]).strip()

    try:
        db.add_warning(target.id, getattr(target, "username", "") or "")
        count = db.get_warning_count(target.id)
        await update.message.reply_text(
            f"⚠️ تم تحذير {getattr(target, 'first_name', str(target.id))}\n"
            f"السبب: {reason}\nعدد التحذيرات: {count}/3"
        )
        logger.info("Warned user %s (id=%s). Reason: %s", getattr(target,'username',None), target.id, reason)
    except Exception:
        logger.exception("Failed to store warning")
        await update.message.reply_text("❌ خطأ داخلي أثناء حفظ التحذير")

async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mute a user for specified duration"""
    try:
        logger.info("Handling mute command from %s", update.effective_user.id)
        dump_update_to_file(update)
    except Exception:
        logger.exception("dump failed")

    target, arg_start = await resolve_target_user(update, context)
    if not target:
        await update.message.reply_text("⚡ يجب الرد على رسالة المستخدم أو اذكر @username أو ID. مثال: (رد) + /mute 1h")
        return

    # Get duration
    dur = None
    if context.args and len(context.args) > arg_start:
        dur = context.args[arg_start]

    if not dur:
        await update.message.reply_text("❌ يرجى تحديد مدة (مثال: 1h أو 30m).")
        return

    until = parse_duration(dur)
    if not until:
        await update.message.reply_text("❌ صيغة المدة غير صحيحة. مثال: 1h أو 30m.")
        return

    # Check permissions
    me = await context.bot.get_me()
    if not await check_bot_permissions(context, update.effective_chat.id, me.id):
        await update.message.reply_text("❌ لا أملك صلاحية تقييد الأعضاء. رجاءً ارفعني مشرفاً ومنحني صلاحية Restrict Members.")
        return

    # Apply mute
    try:
        from telegram import ChatPermissions
        perms = ChatPermissions(can_send_messages=False)
        await context.bot.restrict_chat_member(update.effective_chat.id, target.id, perms, until_date=until)
        await update.message.reply_text(f"🔇 تم كتم {getattr(target,'first_name',str(target.id))} لمدة {dur}")
        logger.info("Muted user %s until %s", target.id, until.isoformat())
    except Exception as e:
        logger.exception("restrict failed: %s", e)
        await update.message.reply_text(f"❌ تعذر كتم المستخدم: {e}")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a user"""
    target, _ = await resolve_target_user(update, context)
    if not target:
        await update.message.reply_text("⚡ استخدام: رد على رسالة المستخدم + /ban أو /ban @username")
        return
    
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await update.message.reply_text("🚫 تم حظر المستخدم")
    except Exception as e:
        logger.exception("ban failed: %s", e)
        await update.message.reply_text(f"❌ تعذر حظر المستخدم: {e}")