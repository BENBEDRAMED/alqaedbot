#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import logging
import tempfile
import requests
from typing import Optional, Tuple
from pytube import YouTube, Search
from pytube.exceptions import VideoUnavailable

logger = logging.getLogger("groupmanager")

class MusicPlayer:
    def __init__(self):
        self.download_path = "downloads"
        os.makedirs(self.download_path, exist_ok=True)
    
    def search_youtube(self, query: str) -> Optional[str]:
        """Search YouTube and return first video URL"""
        try:
            search = Search(query)
            if search.results:
                return search.results[0].watch_url
            return None
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return None
    
    def download_audio(self, url: str) -> Optional[str]:
        """Download audio from YouTube URL using pytube"""
        try:
            yt = YouTube(url)
            
            # Get audio stream
            audio_stream = yt.streams.filter(only_audio=True).first()
            
            if not audio_stream:
                logger.error("No audio stream found")
                return None
            
            # Download to temp file
            temp_file = tempfile.NamedTemporaryFile(
                suffix='.mp3', 
                delete=False,
                dir=self.download_path
            )
            temp_file.close()
            
            # Download
            audio_stream.download(
                output_path=self.download_path,
                filename=os.path.basename(temp_file.name)
            )
            
            return temp_file.name
            
        except VideoUnavailable:
            logger.error("Video is unavailable")
            return None
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None
    
    def get_video_info(self, url: str) -> Tuple[str, str]:
        """Get video title and duration"""
        try:
            yt = YouTube(url)
            title = yt.title or "Unknown Title"
            duration = yt.length
            
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