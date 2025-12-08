#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import logging
import time
import random
import tempfile
import requests
from typing import Optional, Dict, Tuple
from urllib.parse import quote, unquote

logger = logging.getLogger("groupmanager")

class SaveFromDownloader:
    def __init__(self):
        # Create downloads directory
        self.download_path = "downloads"
        os.makedirs(self.download_path, exist_ok=True)
        
        # Multiple savefrom domains
        self.domains = [
            'https://en.savefrom.net',
            'https://www.savefrom.net', 
            'https://savefrom.net',
            'https://ssyoutube.com',
            'https://savefrom.io',
        ]
        
        # Real browser headers
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }
        
        self.last_request = 0
    
    def _wait_if_needed(self):
        """Add delay between requests to avoid blocking"""
        current = time.time()
        if current - self.last_request < 2:  # 2 seconds between requests
            time.sleep(2 + random.uniform(0, 1))
        self.last_request = time.time()
    
    def search_youtube(self, query: str) -> Optional[str]:
        """Search YouTube and return first video URL"""
        self._wait_if_needed()
        try:
            encoded = quote(query)
            url = f"https://www.youtube.com/results?search_query={encoded}"
            
            response = requests.get(url, headers=self.headers, timeout=10)
            
            # Try multiple patterns to find video ID
            patterns = [
                r'"videoId":"([a-zA-Z0-9_-]{11})"',
                r'watch\?v=([a-zA-Z0-9_-]{11})',
                r'/watch\?v=([a-zA-Z0-9_-]{11})"',
                r'embed/([a-zA-Z0-9_-]{11})'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, response.text)
                if matches:
                    video_id = matches[0]
                    return f"https://www.youtube.com/watch?v={video_id}"
            
            return None
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return None
    
    def get_mp3_download_url(self, youtube_url: str) -> Optional[Tuple[str, str]]:
        """
        Get direct MP3 download URL from savefrom.net
        Returns: (download_url, title) or (None, None)
        """
        self._wait_if_needed()
        
        # Try each domain
        for domain in self.domains:
            try:
                url, title = self._get_mp3_from_domain(domain, youtube_url)
                if url:
                    logger.info(f"Found MP3 URL from {domain}")
                    return url, title
            except Exception as e:
                logger.debug(f"Domain {domain} failed: {e}")
                continue
        
        # Try API as fallback
        try:
            url, title = self._get_mp3_from_api(youtube_url)
            if url:
                return url, title
        except Exception as e:
            logger.debug(f"API failed: {e}")
        
        return None, None
    
    def _get_mp3_from_domain(self, domain: str, youtube_url: str) -> Tuple[Optional[str], str]:
        """Extract MP3 download URL from savefrom domain"""
        # Format: https://en.savefrom.net/#url=https://youtube.com/watch?v=ABC123
        savefrom_url = f"{domain}/#url={youtube_url}"
        
        response = requests.get(savefrom_url, headers=self.headers, timeout=15)
        
        # Extract title
        title_match = re.search(r'<title>(.*?) - SaveFrom', response.text)
        title = title_match.group(1).strip() if title_match else "Unknown Title"
        
        # Look for MP3 download links - multiple patterns
        mp3_patterns = [
            r'data-link="(https://[^"]*format=mp3[^"]*)"',
            r'href="(https://[^"]*\.mp3[^"]*)"',
            r'download_url":"([^"]*\.mp3[^"]*)"',
            r'"url":"(https://[^"]*\.mp3[^"]*)"',
            r'"(https://[^"]*redirector\.googlevideo\.com[^"]*mp3[^"]*)"',
        ]
        
        for pattern in mp3_patterns:
            matches = re.findall(pattern, response.text, re.IGNORECASE)
            for link in matches:
                # Clean up the URL
                link = unquote(link.replace('\\/', '/'))
                if 'mp3' in link.lower() or 'audio' in link.lower():
                    return link, title
        
        return None, title
    
    def _get_mp3_from_api(self, youtube_url: str) -> Tuple[Optional[str], str]:
        """Try to get MP3 URL from savefrom API"""
        api_url = "https://savefrom.net/api/convert"
        
        data = {
            'url': youtube_url,
            'format': 'mp3',
        }
        
        headers = {
            **self.headers,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://savefrom.net',
            'Referer': 'https://savefrom.net/',
        }
        
        response = requests.post(api_url, data=data, headers=headers, timeout=15)
        
        if response.status_code == 200:
            try:
                data = response.json()
                if 'url' in data:
                    title = data.get('meta', {}).get('title', 'Unknown Title')
                    return data['url'], title
            except:
                pass
        
        return None, "Unknown Title"
    
    def download_mp3(self, youtube_url: str) -> Optional[Tuple[str, str]]:
        """
        Download MP3 from YouTube via savefrom.net
        Returns: (file_path, title) or (None, None)
        """
        try:
            # Step 1: Get MP3 download URL
            mp3_url, title = self.get_mp3_download_url(youtube_url)
            if not mp3_url:
                logger.error("No MP3 URL found")
                return None, title
            
            # Step 2: Create temp file
            video_id = youtube_url.split('v=')[-1].split('&')[0]
            temp_file = tempfile.NamedTemporaryFile(
                suffix='.mp3', 
                delete=False,
                dir=self.download_path
            )
            temp_file.close()
            
            # Step 3: Download the MP3
            logger.info(f"Downloading MP3: {title}")
            
            # Special headers for the download
            download_headers = {
                'User-Agent': self.headers['User-Agent'],
                'Accept': '*/*',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Referer': 'https://savefrom.net/',
            }
            
            # Download with stream (for large files)
            response = requests.get(mp3_url, headers=download_headers, stream=True, timeout=60)
            response.raise_for_status()
            
            # Check file size (Telegram limit: 50MB)
            file_size = int(response.headers.get('content-length', 0))
            if file_size > 50 * 1024 * 1024:  # 50MB
                logger.error(f"File too large: {file_size/1024/1024:.1f}MB")
                return None, title
            
            # Download with progress tracking
            downloaded = 0
            with open(temp_file.name, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
            
            # Verify file was downloaded
            if os.path.getsize(temp_file.name) > 1024:  # At least 1KB
                logger.info(f"Downloaded: {title} ({os.path.getsize(temp_file.name)/1024/1024:.1f}MB)")
                return temp_file.name, title
            else:
                logger.error("Downloaded empty file")
                os.remove(temp_file.name)
                return None, title
                
        except Exception as e:
            logger.error(f"Download MP3 failed: {e}")
            # Clean up if file exists
            if 'temp_file' in locals() and os.path.exists(temp_file.name):
                os.remove(temp_file.name)
            return None, "Unknown Title"

# Global instance
savefrom_downloader = SaveFromDownloader()