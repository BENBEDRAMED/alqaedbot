#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import re
from telegram import Update
from telegram.ext import ContextTypes
from config import CONTROVERSIAL_WORDS

logger = logging.getLogger("groupmanager")

async def detect_controversial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detect controversial content AND shadow-muted users"""
    try:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # CHECK 1: Is this user shadow-muted?
        if db.is_user_monitored(user_id, chat_id, "muted"):
            try:
                await update.message.delete()
                logger.debug(f"Auto-deleted message from shadow-muted user {user_id}")
                # Optional: Send them a private warning
                try:
                    await context.bot.send_message(
                        user_id,
                        "⚠️ أنت مكتوم في هذه المجموعة. رسائلك سيتم حذفها تلقائياً."
                    )
                except:
                    pass  # Can't send DM
                return  # Stop further processing
            except Exception as e:
                logger.warning(f"Could not delete shadow-muted message: {e}")
        
        # CHECK 2: Original controversial words detection
        text = (update.message.text or "").lower()
        found = [w for w in CONTROVERSIAL_WORDS if w in text]
        if found:
            try:
                await update.message.delete()
            except Exception:
                logger.debug("Could not delete controversial message")
            await context.bot.send_message(chat_id, "⚠️ تم حذف رسالة تحتوي على كلمات مثيرة للجدل")
            
    except Exception:
        logger.exception("detect_controversial failed")
# Arabic command wrappers - import inside functions to avoid circular imports
async def arabic_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from handlers.user_handlers import help_command
    await help_command(update, context)

async def arabic_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from handlers.admin_handlers import delete_messages
    await delete_messages(update, context)

async def arabic_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from handlers.admin_handlers import warn_user
    await warn_user(update, context)

async def arabic_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from handlers.admin_handlers import mute_user
    await mute_user(update, context)

async def arabic_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from handlers.admin_handlers import ban_user
    await ban_user(update, context)

async def arabic_rep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from handlers.user_handlers import check_reputation
    await check_reputation(update, context)

async def arabic_monitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from handlers.user_handlers import monitor_user
    await monitor_user(update, context)