#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

# Bot Configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN")
RENDER_APP_URL = os.environ.get("RENDER_APP_URL")
PORT = int(os.environ.get("PORT", 10000))

# Database
DB_PATH = os.path.join("data", "group_manager.db")

# Content filtering
CONTROVERSIAL_WORDS = [
    "سياسة", "طائفية", "عنصرية", "شتيمة", "سب", "تحذير",
    "كره", "تطرف", "إساءة", "فساد", "فاسد", "سخرية"
]

WELCOME_MESSAGES = [
    "أهلاً وسهلاً 🌹 نورت المجموعة يا {name}! نتمنى لك وقتاً ممتعاً معنا.",
    "مرحباً بك {name} 🤗 اقرأ القواعد واستمتع بالتجربة!",
    "يا هلا ويا مرحب بيك {name} 💫 نورت مجموعتنا!",
    "أهلاً بك {name} في مجموعتنا 🎉 نرجو لك الفائدة والمتعة!"
]

# Validation
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN missing (set env var BOT_TOKEN).")

if not RENDER_APP_URL:
    raise ValueError("❌ RENDER_APP_URL missing. Set RENDER_APP_URL to your public HTTPS URL.")