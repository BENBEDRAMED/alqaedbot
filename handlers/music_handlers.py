#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import logging
import asyncio
import tempfile
from typing import Optional, Tuple
import yt_dlp
import requests
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger("groupmanager")

class MusicPlayer:
    def __init__(self):
        self.download_path = "downloads"
        os.makedirs(self.download_path, exist_ok=True)
        
        # YouTube DL options for audio only
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(self.download_path, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'max_downloads': 1,
        }
    
    def search_youtube(self, query: str) -> Optional[str]:
        """Search YouTube and return first video URL"""
        try:
            # Simple search using YouTube search
            search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(search_url, headers=headers)
            video_ids = re.findall(r'watch\?v=(\S{11})', response.text)
            
            if video_ids:
                return f"https://www.youtube.com/watch?v={video_ids[0]}"
            return None
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return None
    
    def download_audio(self, url: str) -> Optional[str]:
        """Download audio from YouTube URL"""
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                # Convert to mp3 filename
                if filename.endswith('.webm'):
                    mp3_filename = filename.replace('.webm', '.mp3')
                elif filename.endswith('.m4a'):
                    mp3_filename = filename.replace('.m4a', '.mp3')
                else:
                    mp3_filename = filename + '.mp3'
                
                if os.path.exists(mp3_filename):
                    return mp3_filename
                    
            return None
            
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None
    
    def get_video_info(self, url: str) -> Tuple[str, str]:
        """Get video title and duration"""
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get('title', 'Unknown Title')
                duration = info.get('duration', 0)
                
                # Format duration
                if duration > 3600:
                    duration_str = f"{duration//3600}:{(duration%3600)//60:02d}:{duration%60:02d}"
                else:
                    duration_str = f"{duration//60}:{duration%60:02d}"
                
                return title, duration_str
        except:
            return "Unknown Title", "0:00"

# Create global instance
music_player = MusicPlayer()