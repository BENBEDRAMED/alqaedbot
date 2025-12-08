#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import logging
from config import DB_PATH

logger = logging.getLogger("groupmanager")

class Database:
    def __init__(self, path=DB_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
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
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS monitored_users (
                user_id INTEGER,
                chat_id INTEGER,
                action_type TEXT DEFAULT 'muted',
                monitored_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, chat_id)
            )
        ''')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS message_log (
                message_id INTEGER,
                user_id INTEGER,
                chat_id INTEGER,
                text TEXT,
                deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                reason TEXT
            )
        ''')
        
        self.conn.commit()

    def add_warning(self, user_id: int, username: str = ""):
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
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT warnings FROM users WHERE user_id = ?", (user_id,))
            r = cur.fetchone()
            return r[0] if r else 0
        except Exception as e:
            logger.error(f"Error getting warning count: {e}")
            return 0

    def get_user_stats(self, user_id: int):
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
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT COUNT(*) FROM users")
            return cur.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting total users: {e}")
            return 0

    def add_monitored_user(self, user_id: int, chat_id: int, action_type: str = "muted"):
        try:
            cur = self.conn.cursor()
            cur.execute('''
                INSERT OR REPLACE INTO monitored_users 
                (user_id, chat_id, action_type, monitored_at)
                VALUES (?, ?, ?, datetime('now'))
            ''', (user_id, chat_id, action_type))
            self.conn.commit()
            logger.debug(f"Added user {user_id} to monitoring in chat {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding monitored user: {e}")
            return False

    def remove_monitored_user(self, user_id: int, chat_id: int):
        try:
            cur = self.conn.cursor()
            cur.execute('''
                DELETE FROM monitored_users 
                WHERE user_id=? AND chat_id=?
            ''', (user_id, chat_id))
            self.conn.commit()
            logger.debug(f"Removed user {user_id} from monitoring in chat {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Error removing monitored user: {e}")
            return False

    def is_user_monitored(self, user_id: int, chat_id: int, action_type: str = None) -> bool:
        try:
            cur = self.conn.cursor()
            if action_type:
                cur.execute('''
                    SELECT 1 FROM monitored_users 
                    WHERE user_id=? AND chat_id=? AND action_type=?
                ''', (user_id, chat_id, action_type))
            else:
                cur.execute('''
                    SELECT 1 FROM monitored_users 
                    WHERE user_id=? AND chat_id=?
                ''', (user_id, chat_id))
            return cur.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking monitored user: {e}")
            return False

    def get_monitored_users(self, chat_id: int):
        try:
            cur = self.conn.cursor()
            cur.execute('''
                SELECT user_id, action_type, monitored_at 
                FROM monitored_users 
                WHERE chat_id=?
                ORDER BY monitored_at DESC
            ''', (chat_id,))
            return cur.fetchall()
        except Exception as e:
            logger.error(f"Error getting monitored users: {e}")
            return []

    def get_monitored_count(self, chat_id: int) -> int:
        try:
            cur = self.conn.cursor()
            cur.execute('''
                SELECT COUNT(*) FROM monitored_users 
                WHERE chat_id=?
            ''', (chat_id,))
            return cur.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting monitored count: {e}")
            return 0


# In database.py, add:
def add_song_request(self, user_id: int, chat_id: int, song_name: str):
    """Log song requests"""
    with self.conn:
        self.conn.execute('''
            INSERT INTO song_requests (user_id, chat_id, song_name, requested_at)
            VALUES (?, ?, ?, datetime('now'))
        ''', (user_id, chat_id, song_name))

def get_top_songs(self, chat_id: int, limit: int = 10):
    """Get most requested songs in chat"""
    cursor = self.conn.execute('''
        SELECT song_name, COUNT(*) as request_count
        FROM song_requests 
        WHERE chat_id=?
        GROUP BY song_name 
        ORDER BY request_count DESC 
        LIMIT ?
    ''', (chat_id, limit))
    return cursor.fetchall()
    def close(self):
        if self.conn:
            self.conn.close()