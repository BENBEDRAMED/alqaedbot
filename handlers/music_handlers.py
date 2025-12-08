async def play_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search and send YouTube music"""
    try:
        # Check if user provided song name
        if not context.args:
            await update.message.reply_text(
                "🎵 استخدام: /play [اسم الأغنية]\n"
                "مثال: /play Shape of You\n"
                "أو: /play أغنية حبيبي"
            )
            return
        
        # Get song query
        query = " ".join(context.args)
        
        # Send searching message
        search_msg = await update.message.reply_text(
            f"🔍 جاري البحث عن: {query}\n⏳ قد يستغرق بضع ثواني..."
        )
        
        # Search YouTube
        from music_player import music_player
        url = music_player.search_youtube(query + " audio")
        
        if not url:
            await search_msg.edit_text("❌ لم أتمكن من العثور على الأغنية")
            return
        
        # Get video info
        title, duration = music_player.get_video_info(url)
        await search_msg.edit_text(f"🎶 تم العثور على:\n**{title}** ({duration})")
        
        # Download audio
        download_msg = await update.message.reply_text("⬇️ جاري تحميل الصوت...")
        audio_file = music_player.download_audio(url)
        
        if not audio_file:
            await download_msg.edit_text("❌ فشل في تحميل الصوت")
            return
        
        # Send audio file
        await download_msg.edit_text("📤 جاري إرسال الملف...")
        
        try:
            with open(audio_file, 'rb') as audio:
                await context.bot.send_audio(
                    chat_id=update.effective_chat.id,
                    audio=audio,
                    title=title,
                    duration=int(duration.replace(':', '')) if ':' in duration else 0,
                    performer="YouTube",
                    caption=f"🎵 {title}"
                )
            
            # Cleanup
            os.remove(audio_file)
            await download_msg.delete()
            await search_msg.edit_text(f"✅ تم إرسال: **{title}**")
            
        except Exception as e:
            logger.error(f"Failed to send audio: {e}")
            await download_msg.edit_text("❌ فشل في إرسال الملف")
            
    except Exception as e:
        logger.exception(f"play_music failed: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء تشغيل الموسيقى")