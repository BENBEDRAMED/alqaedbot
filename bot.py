#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import asyncio
import re
from telegram import BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from config import BOT_TOKEN

# Import handlers directly from their modules to avoid circular imports
from handlers.admin_handlers import delete_messages, warn_user, mute_user, ban_user , kick_user,status,unmute_user
from handlers.user_handlers import start, help_command, check_reputation, monitor_user,  test_command, welcome_new_member
from handlers.message_handlers import detect_controversial, arabic_help, arabic_delete, arabic_warn, arabic_mute, arabic_ban, arabic_rep, arabic_monitor

logger = logging.getLogger("groupmanager")

class GroupManagerBot:
    def __init__(self, token: str):
        self.token = token
        self.application = Application.builder().token(token).build()
        self.loop = None
        self.setup_handlers()
        logger.info("Bot object initialized")

    def setup_handlers(self):
        # Basic commands
        self.application.add_handler(CommandHandler("start", start))
        self.application.add_handler(CommandHandler("help", help_command))
        self.application.add_handler(CommandHandler("delete", delete_messages))
        self.application.add_handler(CommandHandler("warn", warn_user))
        self.application.add_handler(CommandHandler("mute", mute_user))
        self.application.add_handler(CommandHandler("unmute", unmute_user))
        self.application.add_handler(CommandHandler("ban", ban_user))

        self.application.add_handler(CommandHandler("kick", kick_user))
        self.application.add_handler(CommandHandler("rep", check_reputation))
        self.application.add_handler(CommandHandler("monitor", monitor_user))
       
        self.application.add_handler(CommandHandler("status", status))
        self.application.add_handler(CommandHandler("test", test_command))

        # Message handlers
        self.application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
        self.application.add_handler(MessageHandler(
            filters.ALL & ~filters.COMMAND & ~filters.StatusUpdate.ALL,
            detect_controversial
        ))

        # Arabic command wrappers
        self.application.add_handler(MessageHandler(filters.Regex(re.compile(r'^/مساعدة(?:\s|$)', re.IGNORECASE)), arabic_help))
        self.application.add_handler(MessageHandler(filters.Regex(re.compile(r'^/حذف(?:\s|$)', re.IGNORECASE)), arabic_delete))
        self.application.add_handler(MessageHandler(filters.Regex(re.compile(r'^/تحذير(?:\s|$)', re.IGNORECASE)), arabic_warn))
        self.application.add_handler(MessageHandler(filters.Regex(re.compile(r'^/كتم(?:\s|$)', re.IGNORECASE)), arabic_mute))
        self.application.add_handler(MessageHandler(filters.Regex(re.compile(r'^/حظر(?:\s|$)', re.IGNORECASE)), arabic_ban))
        self.application.add_handler(MessageHandler(filters.Regex(re.compile(r'^/سمعة(?:\s|$)', re.IGNORECASE)), arabic_rep))
        self.application.add_handler(MessageHandler(filters.Regex(re.compile(r'^/مراقبة(?:\s|$)', re.IGNORECASE)), arabic_monitor))

    async def setup_webhook(self, webhook_url: str):
        """Initialize application and set webhook"""
        try:
            await self.application.initialize()
            await self.application.bot.set_webhook(webhook_url)
            logger.info("Set webhook to %s", webhook_url)

            # Register bot commands
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
            self.loop = asyncio.get_running_loop()
            logger.info("Application started and event loop captured")
        except Exception:
            logger.exception("setup_webhook failed")
            raise