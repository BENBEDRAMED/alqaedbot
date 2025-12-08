#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import logging
from datetime import datetime
from config import DB_PATH

logger = logging.getLogger("groupmanager")

class Database:
    def __init__(self, path=DB_PATH):
        # Ensure the data directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        self.path = path
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cur = self.conn.cursor()
        
        # Users table (existing)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                reputation INTEGER DEFAULT 0,
                warnings INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # NEW: Monitored users (for shadow-mute)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS monitored_users (
                user_id INTEGER,
                chat_id INTEGER,
                action_type TEXT DEFAULT 'muted',  # 'muted', 'monitored', etc.
                monitored_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, chat_id)
            )
        ''')
        
        # NEW: Message log (optional - track deleted messages)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS message_log (
                message_id INTEGER,
                user_id INTEGER,
                chat_id INTEGER,
                text TEXT,
                deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                reason TEXT  # 'shadow_mute', 'controversial', 'admin_delete'
            )
        ''')
        
        self.conn.commit()

    # ===== EXISTING FUNCTIONS =====
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

    # ===== NEW: SHADOW-MUTE FUNCTIONS =====
    
    def add_monitored_user(self, user_id: int, chat_id: int, action_type: str = "muted"):
        """Add user to shadow-mute monitoring"""
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
        """Remove user from monitoring"""
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
        """Check if user is being monitored (shadow-muted)"""
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
        """Get all monitored users in a chat"""
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
        """Count how many users are monitored in chat"""
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

    # ===== NEW: MESSAGE LOGGING =====
    
    def log_deleted_message(self, message_id: int, user_id: int, chat_id: int, 
                           text: str = "", reason: str = "shadow_mute"):
        """Log deleted messages for audit trail"""
        try:
            cur = self.conn.cursor()
            cur.execute('''
                INSERT INTO message_log 
                (message_id, user_id, chat_id, text, reason)
                VALUES (?, ?, ?, ?, ?)
            ''', (message_id, user_id, chat_id, text[:500], reason))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error logging message: {e}")
            return False

    def get_deleted_messages(self, user_id: int = None, chat_id: int = None, 
                            limit: int = 50):
        """Get deleted messages log (for admin)"""
        try:
            cur = self.conn.cursor()
            if user_id and chat_id:
                cur.execute('''
                    SELECT * FROM message_log 
                    WHERE user_id=? AND chat_id=?
                    ORDER BY deleted_at DESC LIMIT ?
                ''', (user_id, chat_id, limit))
            elif user_id:
                cur.execute('''
                    SELECT * FROM message_log 
                    WHERE user_id=?
                    ORDER BY deleted_at DESC LIMIT ?
                ''', (user_id, limit))
            elif chat_id:
                cur.execute('''
                    SELECT * FROM message_log 
                    WHERE chat_id=?
                    ORDER BY deleted_at DESC LIMIT ?
                ''', (chat_id, limit))
            else:
                cur.execute('''
                    SELECT * FROM message_log 
                    ORDER BY deleted_at DESC LIMIT ?
                ''', (limit,))
            return cur.fetchall()
        except Exception as e:
            logger.error(f"Error getting deleted messages: {e}")
            return []

    # ===== NEW: CLEANUP FUNCTIONS =====
    
    def cleanup_old_logs(self, days: int = 30):
        """Delete old message logs to save space"""
        try:
            cur = self.conn.cursor()
            cur.execute('''
                DELETE FROM message_log 
                WHERE deleted_at < datetime('now', ?)
            ''', (f'-{days} days',))
            self.conn.commit()
            deleted = cur.rowcount
            logger.info(f"Cleaned up {deleted} old message logs")
            return deleted
        except Exception as e:
            logger.error(f"Error cleaning up logs: {e}")
            return 0

    def reset_user_warnings(self, user_id: int):
        """Reset warnings for a user"""
        try:
            cur = self.conn.cursor()
            cur.execute('''
                UPDATE users SET warnings = 0 WHERE user_id = ?
            ''', (user_id,))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error resetting warnings: {e}")
            return False

    # ===== NEW: REPUTATION SYSTEM =====
    
    def update_reputation(self, user_id: int, change: int):
        """Add or subtract reputation points"""
        try:
            cur = self.conn.cursor()
            cur.execute("INSERT OR IGNORE INTO users (user_id, reputation, warnings) VALUES (?, ?, 0)", 
                       (user_id, max(0, change)))
            cur.execute("UPDATE users SET reputation = reputation + ? WHERE user_id = ?", 
                       (change, user_id))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating reputation: {e}")
            return False

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()