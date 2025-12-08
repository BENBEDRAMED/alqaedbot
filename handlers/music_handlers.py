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
        """Download audio using multiple fallback strategies"""
        # Strategy 1: yt-dlp with full evasion
        audio_file = self._download_strategy_1(url)
        if audio_file:
            return audio_file

        # Strategy 2: Alternative format selection
        audio_file = self._download_strategy_2(url)
        if audio_file:
            return audio_file

        # Strategy 3: Direct link extraction (last resort)
        return self._download_strategy_3(url)

    def _download_strategy_1(self, url: str) -> Optional[str]:
        """Primary: yt-dlp with cookies, headers, and rate limiting"""
        self._rate_limit()
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': os.path.join(self.download_path, '%(title).100s.%(ext)s'),
                'quiet': False,
                'no_warnings': False,
                'cookiefile': self.cookies_file if os.path.exists(self.cookies_file) else None,
                'user_agent': random.choice(self.user_agents),
                'referer': 'https://www.youtube.com/',
                'sleep_interval': random.randint(2, 5),
                'sleep_interval_requests': random.randint(5, 10),
                'ignoreerrors': True,
                'retries': 10,
                'fragment_retries': 10,
                'skip_unavailable_fragments': True,
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'],
                        'player_skip': ['configs', 'webpage']
                    }
                },
                'http_headers': {
                    'Accept': '*/*',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Sec-Fetch-Mode': 'navigate',
                }
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                mp3_file = os.path.splitext(filename)[0] + '.mp3'
                if os.path.exists(mp3_file):
                    logger.info(f"Strategy 1 succeeded: {mp3_file}")
                    return mp3_file
        except Exception as e:
            logger.warning(f"Strategy 1 failed: {e}")
        return None

    def _download_strategy_2(self, url: str) -> Optional[str]:
        """Alternative: Use m4a format (often less protected)"""
        self._rate_limit()
        try:
            ydl_opts = {
                'format': 'bestaudio[ext=m4a]/bestaudio',
                'outtmpl': os.path.join(self.download_path, '%(title).100s.%(ext)s'),
                'quiet': True,
                'cookiefile': self.cookies_file if os.path.exists(self.cookies_file) else None,
                'user_agent': random.choice(self.user_agents),
                'sleep_interval': 3,
                'ignoreerrors': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                if os.path.exists(filename):
                    # Convert to mp3 if needed
                    if filename.endswith('.m4a'):
                        mp3_file = filename.replace('.m4a', '.mp3')
                        # Simple conversion (requires ffmpeg in PATH)
                        os.system(f'ffmpeg -i "{filename}" -codec:a libmp3lame -q:a 2 "{mp3_file}" -y 2>/dev/null')
                        if os.path.exists(mp3_file):
                            os.remove(filename)  # Clean up m4a
                            return mp3_file
                    return filename
        except Exception as e:
            logger.warning(f"Strategy 2 failed: {e}")
        return None

    def _download_strategy_3(self, url: str) -> Optional[str]:
        """Last resort: Use an external API service (example)"""
        self._rate_limit()
        # This is a conceptual example. Services change frequently.
        # You might integrate with a paid API like https://rapidapi.com/ytjar/api/youtube-mp36/
        # Or use a different open-source backend
        logger.warning("Primary strategies failed, consider implementing a fallback API")
        return None

    def get_video_info(self, url: str) -> Tuple[str, str]:
        """Get title and duration without downloading"""
        self._rate_limit()
        try:
            ydl_opts = {
                'quiet': True,
                'cookiefile': self.cookies_file if os.path.exists(self.cookies_file) else None,
                'user_agent': random.choice(self.user_agents),
                'extract_flat': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get('title', 'Unknown Title')[:100]
                duration = info.get('duration', 0)

                # Format duration
                if duration > 3600:
                    dur_str = f"{duration//3600}:{(duration%3600)//60:02d}:{duration%60:02d}"
                elif duration > 0:
                    dur_str = f"{duration//60}:{duration%60:02d}"
                else:
                    dur_str = "?:??"

                return title, dur_str
        except Exception as e:
            logger.error(f"Could not fetch video info: {e}")
            return "Unknown Title", "?:??"

# Global instance
music_player = AdvancedMusicPlayer()