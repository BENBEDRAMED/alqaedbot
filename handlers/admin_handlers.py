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

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mute a user for specified duration"""
    try:
        logger.info("Handling mute command from %s", update.effective_user.id)
        dump_update_to_file(update)
    except Exception:
        logger.exception("dump failed")

    target, arg_start = await resolve_target_user(update, context)
    if not target:
        await update.message.reply_text("⚡ يجب الرد على رسالة المستخدم أو اذكر @username أو ID. مثال: (رد) + /ban 1h")
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

async def kick_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

# mute the user 
async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add user to auto-delete list (shadow mute)"""
    try:
        # Delete command message
        try:
            await update.message.delete()
        except:
            pass
        
        target, _ = await resolve_target_user(update, context)
        if not target:
            await context.bot.send_message(
                update.effective_user.id,
                "⚡ يجب الرد على رسالة المستخدم أو اذكر @username أو ID"
            )
            return
        
        # Add to monitored users database
        db.add_monitored_user(target.id, update.effective_chat.id, "muted")
        
        # Send confirmation to admin
        await context.bot.send_message(
            update.effective_user.id,
            f"👻 تم إسكات {getattr(target,'first_name',str(target.id))}\n"
            f"سيتم حذف جميع رسائله تلقائياً"
        )
        
        logger.info(f"Shadow muted user {target.id} in chat {update.effective_chat.id}")
        
    except Exception as e:
        logger.exception("shadow_mute failed: %s", e)

#unmute the user
async def unmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove user from auto-delete list"""
    try:
        try:
            await update.message.delete()
        except:
            pass
        
        target, _ = await resolve_target_user(update, context)
        if not target:
            await context.bot.send_message(
                update.effective_user.id,
                "⚡ استخدام: رد على رسالة المستخدم + /unmute أو /unmute @username"
            )
            return
        
        # Remove from monitored users
        db.remove_monitored_user(target.id, update.effective_chat.id)
        
        await context.bot.send_message(
            update.effective_user.id,
            f"🔊 تم إلغاء إسكات {getattr(target,'first_name',str(target.id))}"
        )
        
        logger.info(f"Un-shadow-muted user {target.id}")
        
    except Exception as e:
        logger.exception("unmute failed: %s", e)

#check the muted users 
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show shadow-muted users (ADMIN ONLY)"""
    try:
        # CHECK: Is user admin?
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        try:
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            if chat_member.status not in ["administrator", "creator"]:
                await update.message.reply_text("❌ هذا الأمر للمشرفين فقط")
                return
        except Exception:
            await update.message.reply_text("❌ لا يمكن التحقق من صلاحياتك")
            return
        
        # Get monitored users from database
        monitored = db.get_monitored_users(chat_id)
        
        if not monitored:
            await update.message.reply_text(
                "📊 **حالة المجموعة:**\n"
                "──────────────\n"
                "👥 المستخدمون المكتومون: **0**\n"
                "✅ لا يوجد مستخدمون تحت الإسكات الخفي حالياً."
            )
            return
        
        response = "📊 **حالة المجموعة:**\n"
        response += "──────────────\n"
        response += f"👥 المستخدمون المكتومون: **{len(monitored)}**\n\n"
        
        for user_id, action_type, monitored_at in monitored:
            try:
                # Get user info
                user = await context.bot.get_chat_member(chat_id, user_id)
                name = user.user.first_name or f"ID: {user_id}"
                username = f"@{user.user.username}" if user.user.username else ""
                
                # Format date
                from datetime import datetime
                muted_date = datetime.strptime(monitored_at, "%Y-%m-%d %H:%M:%S")
                time_str = muted_date.strftime("%Y-%m-%d %H:%M")
                
                response += f"👤 **{name}** {username}\n"
                response += f"   📌 حالة: {action_type}\n"
                response += f"   ⏰ منذ: {time_str}\n"
                response += "   ──────\n"
                
            except Exception as e:
                logger.debug(f"Could not get info for user {user_id}: {e}")
                response += f"👤 ID: **{user_id}**\n"
                response += f"   📌 حالة: {action_type}\n"
                response += f"   ⏰ منذ: {monitored_at}\n"
                response += "   ──────\n"
        
        # Add warning stats
        total_warnings = 0
        try:
            cursor = db.conn.cursor()
            cursor.execute("SELECT SUM(warnings) FROM users")
            result = cursor.fetchone()
            total_warnings = result[0] or 0
        except:
            pass
        
        response += f"\n⚠️ **إجمالي التحذيرات:** {total_warnings}"
        
        # Send the status report
        await update.message.reply_text(response, parse_mode="Markdown")
        
    except Exception as e:
        logger.exception("status command failed: %s", e)
        await update.message.reply_text("❌ حدث خطأ أثناء جلب الحالة")

async def unkick_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban a user (remove from ban list)"""
    try:
        # Optional: Delete command message
        try:
            await update.message.delete()
        except:
            pass
        
        target, _ = await resolve_target_user(update, context)
        if not target:
            await update.message.reply_text(
                "⚡ استخدام: رد على رسالة المستخدم + /unkick أو /unkick @username\n"
                "أو: /unkick user_id"
            )
            return
        
        # Unban the user
        try:
            await context.bot.unban_chat_member(
                chat_id=update.effective_chat.id,
                user_id=target.id,
                only_if_banned=True  # Only unban if currently banned
            )
            
            await update.message.reply_text(
                f"✅ تم إلغاء حظر {getattr(target, 'first_name', str(target.id))}"
            )
            logger.info(f"Unbanned user {target.id} from chat {update.effective_chat.id}")
            
        except Exception as e:
            if "user not banned" in str(e).lower():
                await update.message.reply_text(
                    f"ℹ️ المستخدم {getattr(target, 'first_name', str(target.id))} ليس محظوراً"
                )
            else:
                logger.exception(f"Failed to unban user: {e}")
                await update.message.reply_text(f"❌ تعذر إلغاء حظر المستخدم: {e}")
                
    except Exception as e:
        logger.exception("unkick_user failed: %s", e)
        await update.message.reply_text("❌ حدث خطأ أثناء محاولة إلغاء الحظر")

async def play_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search, download, and send YouTube audio"""
    try:
        if not context.args:
            await update.message.reply_text("🎵 استخدام: /play [اسم الأغنية]")
            return

        query = " ".join(context.args)
        status_msg = await update.message.reply_text(f"🔍 جاري البحث عن: '{query}'...")

        # Use the advanced player
        from handlers.music_handlers import music_player
        url = music_player.search_youtube(query)

        if not url:
            await status_msg.edit_text("❌ لم أتمكن من العثور على الأغنية.")
            return

        # Get video info for feedback
        title, duration = music_player.get_video_info(url)
        await status_msg.edit_text(f"🎵 تم العثور على: **{title}**\n⏳ جاري التحميل...", parse_mode="Markdown")

        # Download audio (this uses the multi-strategy method)
        audio_file = music_player.download_audio(url)

        if not audio_file or not os.path.exists(audio_file):
            await status_msg.edit_text("❌ فشل في تحميل الصوت. قد يكون الفيديو محمياً أو هناك مشكلة في الشبكة.")
            return

        # Send the audio file
        await status_msg.edit_text("📤 جاري إرسال الملف...")
        try:
            with open(audio_file, 'rb') as f:
                await context.bot.send_audio(
                    chat_id=update.effective_chat.id,
                    audio=f,
                    title=title[:64],  # Telegram title limit
                    duration=int(duration.split(':')[0])*60 + int(duration.split(':')[1]) if ':' in duration else 0,
                    performer="YouTube",
                    caption=f"🎵 {title}"
                )
            # Cleanup
            os.remove(audio_file)
            await status_msg.edit_text(f"✅ تم إرسال: **{title}**", parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to send audio: {e}")
            await status_msg.edit_text("❌ فشل في إرسال الملف. قد يكون الملف كبيراً جداً.")
            if os.path.exists(audio_file):
                os.remove(audio_file)
    except Exception as e:
        logger.exception(f"play_music failed: {e}")
        try:
            await update.message.reply_text("❌ حدث خطأ داخلي أثناء معالجة طلبك.")
        except:
            pass