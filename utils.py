#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import random
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions
from config import WELCOME_MESSAGES

logger = logging.getLogger("groupmanager")

def dump_update_to_file(update: Update, filename="data/last_update.json"):
    """Write full update.to_dict() to a file for debugging"""
    try:
        data = update.to_dict()
    except Exception:
        data = {"repr": repr(update)}
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("✅ Wrote last update to %s", filename)
    except Exception:
        logger.exception("Failed to write update dump")

def get_welcome_message(name: str) -> str:
    """Get random welcome message"""
    return random.choice(WELCOME_MESSAGES).format(name=name)

def parse_duration(duration_str: str):
    """Parse duration string like '1h' or '30m'"""
    try:
        if duration_str.endswith("h"):
            hours = int(duration_str[:-1])
            return datetime.now() + timedelta(hours=hours)
        elif duration_str.endswith("m"):
            minutes = int(duration_str[:-1])
            return datetime.now() + timedelta(minutes=minutes)
        else:
            return None
    except ValueError:
        return None

async def resolve_target_user(update, context):
    """
    Resolve target user from reply, mention, or user ID
    Returns (user, args_consumed_count)
    """
    # 1) Check if it's a reply
    if update.message and update.message.reply_to_message:
        try:
            user = update.message.reply_to_message.from_user
            return user, 0
        except Exception:
            pass

    # 2) Check text mentions
    if update.message and getattr(update.message, "entities", None):
        for ent in update.message.entities:
            if ent.type == "text_mention" and getattr(ent, "user", None):
                return ent.user, 0

    # 3) Check username mentions
    if update.message and getattr(update.message, "entities", None):
        for ent in update.message.entities:
            if ent.type == "mention":
                username = update.message.text[ent.offset: ent.offset + ent.length]
                try:
                    admins = await context.bot.get_chat_administrators(update.effective_chat.id)
                    for adm in admins:
                        if adm.user.username and ("@" + adm.user.username).lower() == username.lower():
                            return adm.user, 1
                except Exception:
                    logger.debug("Could not fetch admins while resolving mention")

    # 4) Check numeric ID in args
    if context.args:
        try:
            uid = int(context.args[0])
            try:
                member = await context.bot.get_chat_member(update.effective_chat.id, uid)
                return member.user, 1
            except Exception:
                pass
        except ValueError:
            pass

    return None, 0

async def check_bot_permissions(context, chat_id, bot_id):
    """Check if bot has required permissions"""
    try:
        me_member = await context.bot.get_chat_member(chat_id, bot_id)
        can_restrict = getattr(me_member, "can_restrict_members", None)
        return can_restrict is not False
    except Exception:
        logger.debug("Could not determine bot permissions")
        return True  # Try anyway