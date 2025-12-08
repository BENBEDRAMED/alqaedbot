#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import logging
import time
import random
import tempfile
import json
from typing import Optional, Tuple
import yt_dlp
import requests

logger = logging.getLogger("groupmanager")

class AdvancedMusicPlayer:
    def __init__(self, cookies_file: str = "cookies.txt"):
        """
        cookies_file: Path to a Netscape-format cookies file exported from your browser.
                     This is THE MOST IMPORTANT step to avoid blocking.
        """
        self.download_path = "downloads"
        os.makedirs(self.download_path, exist_ok=True)
        self.cookies_file = cookies_file
        self.last_request_time = 0
        self.request_count = 0

        # Real browser User-Agents to rotate
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0'
        ]

    def _rate_limit(self):
        """Intelligent delay between requests to appear human"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        self.request_count += 1

        # Reset counter every 10 requests
        if self.request_count > 10:
            time.sleep(random.uniform(25, 40))  # Long pause
            self.request_count = 0
        elif elapsed < 2.5:  # Don't make requests faster than 2.5 seconds
            sleep_time = 2.5 + random.uniform(0.5, 3)
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def search_youtube(self, query: str) -> Optional[str]:
        """Search using yt-dlp's internal search (most reliable with cookies)"""
        self._rate_limit()
        try:
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'cookiefile': self.cookies_file if os.path.exists(self.cookies_file) else None,
                'user_agent': random.choice(self.user_agents),
                'sleep_interval': 1,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # ytsearch: returns search results
                info = ydl.extract_info(f"ytsearch1:{query}", download=False)
                if info and 'entries' in info and info['entries']:
                    return info['entries'][0]['url']
            return None
        except Exception as e:
            logger.error(f"Search failed (yt-dlp): {e}")
            # Fallback to direct HTML parsing
            return self._search_fallback(query)

    def _search_fallback(self, query: str) -> Optional[str]:
        """Fallback search by scraping YouTube HTML"""
        self._rate_limit()
        try:
            headers = {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
            }
            url = f"https://www.youtube.com/results?search_query={requests.utils.quote(query)}&sp=EgIQAQ%253D%253D"  # Filters to videos
            resp = requests.get(url, headers=headers, timeout=10)
            # More robust regex for video IDs
            patterns = [
                r'{"videoId":"([a-zA-Z0-9_-]{11})"',
                r'watch\?v=([a-zA-Z0-9_-]{11})',
                r'"/watch\?v=([a-zA-Z0-9_-]{11})"'
            ]
            for pattern in patterns:
                matches = re.findall(pattern, resp.text)
                if matches:
                    return f"https://www.youtube.com/watch?v={matches[0]}"
            return None
        except Exception as e:
            logger.error(f"Fallback search failed: {e}")
            return None

def download_audio(self, url: str) -> Optional[str]:
    """Download audio with improved strategies"""
    # Strategy 1: Updated format selection
    audio_file = self._download_strategy_1(url)
    if audio_file:
        return audio_file
    
    # Strategy 2: Alternative format
    audio_file = self._download_strategy_2(url)
    if audio_file:
        return audio_file
    
    # Strategy 3: Direct command bypass
    audio_file = self._download_strategy_3(url)
    if audio_file:
        return audio_file
    
    # Last resort: Try without format specification
    return self._download_last_resort(url)

def _download_last_resort(self, url: str) -> Optional[str]:
    """Try downloading without format restrictions"""
    try:
        ydl_opts = {
            # Empty format = let yt-dlp choose
            'format': '',
            'outtmpl': os.path.join(self.download_path, '%(id)s.%(ext)s'),
            'quiet': True,
            'cookiefile': self.cookies_file if os.path.exists(self.cookies_file) else None,
            'user_agent': random.choice(self.user_agents),
            'ignoreerrors': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Manually find and convert audio
            import glob
            video_id = url.split('v=')[-1].split('&')[0]
            pattern = os.path.join(self.download_path, f'{video_id}.*')
            files = glob.glob(pattern)
            
            for file in files:
                # If it's an audio file, convert to mp3
                if file.endswith(('.webm', '.m4a', '.opus')):
                    mp3_file = os.path.splitext(file)[0] + '.mp3'
                    os.system(f'ffmpeg -i "{file}" -codec:a libmp3lame -q:a 2 "{mp3_file}" -y 2>/dev/null')
                    
                    if os.path.exists(mp3_file):
                        os.remove(file)
                        return mp3_file
            
            return files[0] if files else None
            
    except Exception as e:
        logger.error(f"Last resort failed: {e}")
    return None
 def _download_strategy_1(self, url: str) -> Optional[str]:
    """Primary: yt-dlp with correct format selection for 2024"""
    self._rate_limit()
    try:
        ydl_opts = {
            # ===== FIXED FORMAT SELECTION =====
            'format': 'bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best',
            
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            
            'outtmpl': os.path.join(self.download_path, '%(id)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'cookiefile': self.cookies_file if os.path.exists(self.cookies_file) else None,
            'user_agent': random.choice(self.user_agents),
            
            # ===== CRITICAL: Add these YouTube extractor args =====
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'web'],
                    'player_skip': ['configs', 'webpage', 'js'],
                    'formats': ['audio']
                }
            },
            
            # ===== Add JavaScript runtime =====
            'extractor_retries': 3,
            'ignoreerrors': True,
            'retries': 10,
            'fragment_retries': 10,
            'skip_unavailable_fragments': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Convert to mp3
            base, ext = os.path.splitext(filename)
            mp3_filename = base + '.mp3'
            
            if os.path.exists(mp3_filename):
                logger.info(f"✅ Strategy 1 succeeded: {mp3_filename}")
                return mp3_filename
            elif os.path.exists(filename):
                # File downloaded but not converted
                return filename
                
    except Exception as e:
        logger.warning(f"Strategy 1 failed: {e}")
    return None
 def _download_strategy_2(self, url: str) -> Optional[str]:
    """Alternative: Use specific format bypass"""
    self._rate_limit()
    try:
        # Extract video ID first
        video_id = url.split('v=')[-1].split('&')[0]
        
        ydl_opts = {
            # Try different approach
            'format': 'worstaudio/worst',
            'outtmpl': os.path.join(self.download_path, f'{video_id}.%(ext)s'),
            'quiet': True,
            'cookiefile': self.cookies_file if os.path.exists(self.cookies_file) else None,
            'user_agent': random.choice(self.user_agents),
            
            # Bypass JavaScript requirement
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                    'skip': ['dash', 'hls']
                }
            },
            
            'ignoreerrors': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Find the downloaded file
            import glob
            pattern = os.path.join(self.download_path, f'{video_id}.*')
            files = glob.glob(pattern)
            
            if files:
                downloaded_file = files[0]
                
                # If it's webm/m4a, convert to mp3
                if downloaded_file.endswith(('.webm', '.m4a')):
                    mp3_file = os.path.splitext(downloaded_file)[0] + '.mp3'
                    os.system(f'ffmpeg -i "{downloaded_file}" -codec:a libmp3lame -q:a 2 "{mp3_file}" -y 2>/dev/null')
                    
                    if os.path.exists(mp3_file):
                        os.remove(downloaded_file)
                        return mp3_file
                
                return downloaded_file
                
    except Exception as e:
        logger.warning(f"Strategy 2 failed: {e}")
    return None
 def _download_strategy_3(self, url: str) -> Optional[str]:
    """Direct download using yt-dlp's internal methods"""
    self._rate_limit()
    try:
        video_id = url.split('v=')[-1].split('&')[0]
        
        # Create temp file
        temp_file = tempfile.NamedTemporaryFile(
            suffix='.mp3', 
            delete=False,
            dir=self.download_path
        )
        temp_file.close()
        
        # Use yt-dlp command directly with special args
        import subprocess
        
        cmd = [
            'yt-dlp',
            '-x', '--audio-format', 'mp3',
            '--audio-quality', '192K',
            '--output', temp_file.name,
            '--user-agent', random.choice(self.user_agents),
            '--cookies', self.cookies_file if os.path.exists(self.cookies_file) else '',
            '--extractor-args', 'youtube:player_client=android,skip=dash',
            '--no-check-certificate',
            url
        ]
        
        # Remove empty --cookies if no file
        if not os.path.exists(self.cookies_file):
            cmd.remove('--cookies')
            cmd.remove('')
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            # Check if file was created
            if os.path.exists(temp_file.name + '.mp3'):
                return temp_file.name + '.mp3'
            elif os.path.exists(temp_file.name):
                return temp_file.name
        
        return None
        
    except Exception as e:
        logger.warning(f"Strategy 3 failed: {e}")
    return None
# Global instance
music_player = AdvancedMusicPlayer()