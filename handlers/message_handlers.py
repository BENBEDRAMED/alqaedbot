#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import re
from telegram import Update
from telegram.ext import ContextTypes
from config import CONTROVERSIAL_WORDS

logger = logging.getLogger("groupmanager")

async def detect_controversial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detect and handle controversial content"""
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