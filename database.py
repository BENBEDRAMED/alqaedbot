#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import logging
from config import DB_PATH

logger = logging.getLogger("groupmanager")

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

    def add_warning(self, user_id: int, username: str = ""):
        """Add a warning to user"""
        try:
            cur = self.conn.cursor()
            cur.execute("INSERT OR IGNORE INTO users (user_id, username, reputation, warnings) VALUES (?, ?, 0, 0)", 
                       (user_id, username or ""))
            cur.execute("UPDATE users SET warnings = warnings + 1 WHERE user_id = ?", (user_id,))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding warning: {e}")
            return False

    def get_warning_count(self, user_id: int) -> int:
        """Get warning count for user"""
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT warnings FROM users WHERE user_id = ?", (user_id,))
            r = cur.fetchone()
            return r[0] if r else 0
        except Exception as e:
            logger.error(f"Error getting warning count: {e}")
            return 0

    def get_user_stats(self, user_id: int):
        """Get user reputation and warnings"""
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT reputation, warnings FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            if row:
                return {"reputation": row[0], "warnings": row[1]}
            return {"reputation": 0, "warnings": 0}
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {"reputation": 0, "warnings": 0}

    def get_total_users(self) -> int:
        """Get total users count"""
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT COUNT(*) FROM users")
            return cur.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting total users: {e}")
            return 0