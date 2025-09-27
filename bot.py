#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
from telegram import Update, ChatPermissions
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from datetime import datetime, timedelta
import sqlite3
import threading
from threading import Timer

# إعدادات التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# جلب المتغيرات البيئية من Render
BOT_TOKEN = os.environ.get('BOT_TOKEN')
PORT = int(os.environ.get('PORT', 8443))
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '')

if not BOT_TOKEN:
    logging.error("❌ BOT_TOKEN not found in environment variables")
    exit(1)

# قاعدة البيانات البسيطة
class Database:
    def __init__(self):
        # استخدام مسار مطلق للتخزين المستمر في Render
        db_path = os.path.join(os.getcwd(), 'data', 'group_manager.db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                reputation INTEGER DEFAULT 0,
                warnings INTEGER DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                reason TEXT,
                admin_id INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scheduled_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                message_text TEXT,
                scheduled_time DATETIME,
                is_sent INTEGER DEFAULT 0
            )
        ''')
        self.conn.commit()

db = Database()

# الكلمات المثيرة للجدل
CONTROVERSIAL_WORDS = [
    "سياسة", "طائفية", "عنصرية", "شتيمة", "سب", "تحريض", 
    "كره", "تطرف", "إساءة", "فساد", "فاسد", "سخرية"
]

# رسائل الترحيب
WELCOME_MESSAGES = [
    "أهلاً وسهلاً 🌹 نورت المجموعة يا {name}! نتمنى لك وقتاً ممتعاً معنا.",
    "مرحباً بك {name} 🤗 اقرأ القواعد واستمتع بالتجربة!",
    "يا هلا ويا مرحب بيك {name} 💫 نورت مجموعتنا!",
    "أهلاً بك {name} في مجموعتنا 🎉 نرجو لك الفائدة والمتعة!"
]

class GroupManagerBot:
    def __init__(self, token):
        self.token = token
        self.updater = Updater(token, use_context=True)
        self.dispatcher = self.updater.dispatcher
        self.job_queue = self.updater.job_queue
        
        # صلاحيات المشرفين
        self.admin_roles = {
            "super_admin": ["all"],
            "mod_manager": ["warn", "mute", "delete", "monitor"],
            "junior_mod": ["warn", "delete"]
        }
        
        self.setup_handlers()
    
    def setup_handlers(self):
        # أوامر الحذف
        self.dispatcher.add_handler(CommandHandler("حذف", self.delete_messages))
        self.dispatcher.add_handler(CommandHandler("مسح", self.delete_messages))
        self.dispatcher.add_handler(CommandHandler("تنظيف", self.delete_messages))
        
        # أوامر التحذير والعقوبات
        self.dispatcher.add_handler(CommandHandler("تحذير", self.warn_user))
        self.dispatcher.add_handler(CommandHandler("كتم", self.mute_user))
        self.dispatcher.add_handler(CommandHandler("حظر", self.ban_user))
        self.dispatcher.add_handler(CommandHandler("فك_الحظر", self.unban_user))
        
        # أوامر المراقبة
        self.dispatcher.add_handler(CommandHandler("مراقبة", self.monitor_user))
        self.dispatcher.add_handler(CommandHandler("نشاط", self.group_activity))
        self.dispatcher.add_handler(CommandHandler("تقرير", self.daily_report))
        
        # أوامر السمعة
        self.dispatcher.add_handler(CommandHandler("سمعة", self.check_reputation))
        self.dispatcher.add_handler(CommandHandler("تقييم", self.rate_user))
        self.dispatcher.add_handler(CommandHandler("أفضل_الأعضاء", self.top_members))
        
        # أوامر الجدولة
        self.dispatcher.add_handler(CommandHandler("جدولة", self.schedule_message))
        self.dispatcher.add_handler(CommandHandler("إعلان", self.schedule_announcement))
        
        # الترحيب التلقائي
        self.dispatcher.add_handler(MessageHandler(Filters.status_update.new_chat_members, self.welcome_new_member))
        
        # كشف الرسائل المثيرة للجدل
        self.dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, self.detect_controversial))
        
        # أوامر المساعدة
        self.dispatcher.add_handler(CommandHandler("مساعدة", self.help_command))
        self.dispatcher.add_handler(CommandHandler("start", self.start))
        self.dispatcher.add_handler(CommandHandler("status", self.status))

    # 1. حذف الرسائل
    async def delete_messages(self, update: Update, context: CallbackContext):
        if not await self.check_permission(update, "delete"):
            await update.message.reply_text("❌ ليس لديك صلاحية حذف الرسائل")
            return
        
        if not context.args:
            await update.message.reply_text("⚡ استخدام: /حذف [عدد الرسائل]")
            return
        
        try:
            count = int(context.args[0])
            if count > 100:
                await update.message.reply_text("❌ الحد الأقصى 100 رسالة")
                return
            
            chat_id = update.message.chat_id
            message_id = update.message.message_id
            
            # حذف الرسائل بشكل عكسي
            messages_deleted = 0
            for i in range(count + 1):  # +1 لحذف الأمر نفسه
                try:
                    await context.bot.delete_message(chat_id, message_id - i)
                    messages_deleted += 1
                except Exception as e:
                    logger.error(f"Error deleting message: {e}")
                    break
            
            # إرسال تأكيد الحذف
            confirm_msg = await context.bot.send_message(
                chat_id, 
                f"🗑️ تم حذف {messages_deleted} رسائل بنجاح"
            )
            
            # حذف رسالة التأكيد بعد 3 ثواني
            Timer(3.0, lambda: asyncio.create_task(self.delete_message_safe(context.bot, chat_id, confirm_msg.message_id))).start()
            
        except ValueError:
            await update.message.reply_text("❌ يرجى إدخال رقم صحيح")

    async def delete_message_safe(self, bot, chat_id, message_id):
        try:
            await bot.delete_message(chat_id, message_id)
        except Exception as e:
            logger.error(f"Error deleting confirmation message: {e}")

    # 2. الترحيب التلقائي
    async def welcome_new_member(self, update: Update, context: CallbackContext):
        for member in update.message.new_chat_members:
            if member.id == context.bot.id:
                await update.message.reply_text("شكراً لإضافتي! سأقوم بإدارة المجموعة 🛡️")
            else:
                import random
                welcome_text = random.choice(WELCOME_MESSAGES).format(name=member.first_name)
                await update.message.reply_text(welcome_text)
                
                # تسجيل العضو في قاعدة البيانات
                cursor = db.conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO users (user_id, username, reputation) 
                    VALUES (?, ?, ?)
                ''', (member.id, member.username or "", 0))
                db.conn.commit()

    # 3. كشف المواضيع المثيرة
    async def detect_controversial(self, update: Update, context: CallbackContext):
        message_text = update.message.text.lower()
        
        found_words = [word for word in CONTROVERSIAL_WORDS if word in message_text]
        
        if found_words:
            try:
                await update.message.delete()
            except Exception as e:
                logger.error(f"Error deleting message: {e}")
            
            warning_msg = f"⚠️ تنبيه: تم حذف رسالة تحتوي على كلمات مثيرة للجدل"
            await context.bot.send_message(
                update.message.chat_id,
                warning_msg
            )

    # 4. جدولة الإعلانات
    async def schedule_message(self, update: Update, context: CallbackContext):
        if not context.args or len(context.args) < 2:
            await update.message.reply_text("⚡ استخدام: /جدولة [الوقت] [النص]\nمثال: /جدولة 1h مرحبا بالجميع")
            return
        
        time_str = context.args[0]
        message_text = " ".join(context.args[1:])
        
        try:
            if time_str.endswith('h'):
                hours = int(time_str[:-1])
                delta = timedelta(hours=hours)
            elif time_str.endswith('m'):
                minutes = int(time_str[:-1])
                delta = timedelta(minutes=minutes)
            elif time_str.endswith('d'):
                days = int(time_str[:-1])
                delta = timedelta(days=days)
            else:
                await update.message.reply_text("❌ صيغة الوقت غير صحيحة (استخدم 1h, 30m, 2d)")
                return
            
            scheduled_time = datetime.now() + delta
            
            cursor = db.conn.cursor()
            cursor.execute('''
                INSERT INTO scheduled_messages (chat_id, message_text, scheduled_time)
                VALUES (?, ?, ?)
            ''', (update.message.chat_id, message_text, scheduled_time))
            db.conn.commit()
            
            await update.message.reply_text(f"✅ تم جدولة الإعلان لـ {time_str} من الآن")
            
        except ValueError:
            await update.message.reply_text("❌ يرجى إدخال وقت صحيح")

    # 5. نظام السمعة
    async def check_reputation(self, update: Update, context: CallbackContext):
        if update.message.reply_to_message:
            user_id = update.message.reply_to_message.from_user.id
        else:
            user_id = update.message.from_user.id
        
        cursor = db.conn.cursor()
        cursor.execute('SELECT reputation, warnings FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if result:
            reputation, warnings = result
            stars = "⭐" * min(reputation, 5)
            await update.message.reply_text(
                f"🌟 سمعة المستخدم: {reputation}\n"
                f"📊 التحذيرات: {warnings}\n"
                f"🎖️ التقييم: {stars}"
            )
        else:
            await update.message.reply_text("❌ المستخدم غير موجود في قاعدة البيانات")

    # 6. المراقبة
    async def monitor_user(self, update: Update, context: CallbackContext):
        if not await self.check_permission(update, "monitor"):
            await update.message.reply_text("❌ ليس لديك صلاحية المراقبة")
            return
        
        cursor = db.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM warnings WHERE date(timestamp) = date("now")')
        warnings_today = cursor.fetchone()[0]
        
        await update.message.reply_text(
            f"📊 إحصائيات المراقبة:\n"
            f"👥 عدد الأعضاء المسجلين: {user_count}\n"
            f"⚠️ التحذيرات اليوم: {warnings_today}\n"
            f"🕒 آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )

    # 7. التحذير والعقوبات
    async def warn_user(self, update: Update, context: CallbackContext):
        if not await self.check_permission(update, "warn"):
            await update.message.reply_text("❌ ليس لديك صلاحية التحذير")
            return
        
        if not update.message.reply_to_message or not context.args:
            await update.message.reply_text("⚡ استخدام: رد على رسالة المستخدم + /تحذير [السبب]")
            return
        
        user_id = update.message.reply_to_message.from_user.id
        reason = " ".join(context.args)
        
        await self.add_warning(user_id, reason, update.message.from_user.id)
        
        warning_count = self.get_warning_count(user_id)
        
        await update.message.reply_text(
            f"⚠️ تم تحذير المستخدم\n"
            f"السبب: {reason}\n"
            f"عدد التحذيرات: {warning_count}/3"
        )
        
        # حظر تلقائي بعد 3 تحذيرات
        if warning_count >= 3:
            await context.bot.ban_chat_member(update.message.chat_id, user_id)
            await update.message.reply_text("🚫 تم حظر المستخدم تلقائياً بعد 3 تحذيرات")

    async def mute_user(self, update: Update, context: CallbackContext):
        if not await self.check_permission(update, "mute"):
            await update.message.reply_text("❌ ليس لديك صلاحية الكتم")
            return
        
        if not update.message.reply_to_message or not context.args:
            await update.message.reply_text("⚡ استخدام: رد على رسالة المستخدم + /كتم [المدة]")
            return
        
        duration = context.args[0]
        user_id = update.message.reply_to_message.from_user.id
        
        try:
            if duration.endswith('h'):
                hours = int(duration[:-1])
                until_date = datetime.now() + timedelta(hours=hours)
            elif duration.endswith('m'):
                minutes = int(duration[:-1])
                until_date = datetime.now() + timedelta(minutes=minutes)
            else:
                await update.message.reply_text("❌ صيغة المدة غير صحيحة (استخدم 1h, 30m)")
                return
            
            permissions = ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_other_messages=False
            )
            
            await context.bot.restrict_chat_member(
                update.message.chat_id,
                user_id,
                permissions,
                until_date=until_date
            )
            
            await update.message.reply_text(f"🔇 تم كتم المستخدم لمدة {duration}")
            
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ في الكتم: {e}")

    async def ban_user(self, update: Update, context: CallbackContext):
        if not await self.check_permission(update, "ban"):
            await update.message.reply_text("❌ ليس لديك صلاحية الحظر")
            return
        
        if update.message.reply_to_message:
            user_id = update.message.reply_to_message.from_user.id
            await context.bot.ban_chat_member(update.message.chat_id, user_id)
            await update.message.reply_text("🚫 تم حظر المستخدم")
        else:
            await update.message.reply_text("⚡ استخدام: رد على رسالة المستخدم + /حظر")

    async def unban_user(self, update: Update, context: CallbackContext):
        if not context.args:
            await update.message.reply_text("⚡ استخدام: /فك_الحظر [user_id]")
            return
        
        try:
            user_id = int(context.args[0])
            await context.bot.unban_chat_member(update.message.chat_id, user_id)
            await update.message.reply_text("✅ تم إلغاء حظر المستخدم")
        except ValueError:
            await update.message.reply_text("❌ يرجى إدخال رقم مستخدم صحيح")

    # وظائف مساعدة
    async def check_permission(self, update: Update, permission: str):
        # في الإصدار الحقيقي، تحقق من أن المستخدم مشرف في المجموعة
        return True

    async def add_warning(self, user_id: int, reason: str, admin_id: int):
        cursor = db.conn.cursor()
        cursor.execute('''
            INSERT INTO warnings (user_id, reason, admin_id) 
            VALUES (?, ?, ?)
        ''', (user_id, reason, admin_id))
        
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, warnings) 
            VALUES (?, ?, 0)
        ''', (user_id, ""))
        
        cursor.execute('''
            UPDATE users SET warnings = warnings + 1 
            WHERE user_id = ?
        ''', (user_id,))
        
        db.conn.commit()

    def get_warning_count(self, user_id: int) -> int:
        cursor = db.conn.cursor()
        cursor.execute('SELECT warnings FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 0

    async def status(self, update: Update, context: CallbackContext):
        cursor = db.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM warnings')
        warning_count = cursor.fetchone()[0]
        
        await update.message.reply_text(
            f"📊 حالة البوت:\n"
            f"👥 الأعضاء المسجلين: {user_count}\n"
            f"⚠️ إجمالي التحذيرات: {warning_count}\n"
            f"🟢 البوت يعمل بشكل طبيعي\n"
            f"🕒 وقت التشغيل: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )

    async def help_command(self, update: Update, context: CallbackContext):
        help_text = """
🛡️ **أوامر إدارة المجموعة:**

**الحذف:**
/حذف [عدد] - حذف آخر عدد من الرسائل
/مسح [عدد] - تنظيف الرسائل

**التحذير والعقوبات:**
/تحذير [السبب] - تحذير مستخدم (بالرد)
/كتم [المدة] - كتم مستخدم (مثال: /كتم 1h)
/حظر - حظر مستخدم (بالرد)
/فك_الحظر [user_id] - إلغاء حظر

**المراقبة:**
/مراقبة - إحصائيات المراقبة
/تقرير - تقرير المجموعة

**السمعة:**
/سمعة - عرض السمعة (بالرد أو بدون)

**الجدولة:**
/جدولة [الوقت] [النص] - جدولة إعلان

**المساعدة:**
/مساعدة - عرض هذه الرسالة
/status - حالة البوت
        """
        await update.message.reply_text(help_text)

    async def start(self, update: Update, context: CallbackContext):
        await update.message.reply_text(
            "مرحباً! أنا بوت إدارة المجموعات 🛡️\n"
            "استخدم /مساعدة لرؤية الأوامر المتاحة"
        )

    def run(self):
        # إذا كان هناك WEBHOOK_URL، استخدم webhook، وإلا استخدم polling
        if WEBHOOK_URL:
            self.updater.start_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path=self.token,
                webhook_url=f"{WEBHOOK_URL}/{self.token}"
            )
            print(f"✅ البوت يعمل على الويب هوك: {WEBHOOK_URL}")
        else:
            self.updater.start_polling()
            print("✅ البوت يعمل على البولينغ...")
        
        self.updater.idle()

# تشغيل البوت
if __name__ == '__main__':
    bot = GroupManagerBot(BOT_TOKEN)
    bot.run()