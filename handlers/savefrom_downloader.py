#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import logging
import time
import random
import tempfile
import requests
from typing import Optional, Tuple
from urllib.parse import quote, unquote, urlparse

logger = logging.getLogger("groupmanager")

class SaveFromDownloader:
    def __init__(self):
        self.download_path = "downloads"
        os.makedirs(self.download_path, exist_ok=True)
        
        # Updated domains (savefrom changes frequently)
        self.domains = [
            'https://en.savefrom.net',
            'https://www.savefrom.net',
            'https://savefrom.io',
            'https://ssyoutube.com',
            'https://sfrom.net',
        ]
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }
    
    def _wait(self):
        """Add random delay"""
        time.sleep(random.uniform(1, 3))
    
    def search_youtube(self, query: str) -> Optional[str]:
        """Search YouTube - THIS WORKS!"""
        self._wait()
        try:
            encoded = quote(query)
            url = f"https://www.youtube.com/results?search_query={encoded}"
            
            response = requests.get(url, headers=self.headers, timeout=10)
            
            # Multiple patterns to find video ID
            patterns = [
                r'"videoId":"([a-zA-Z0-9_-]{11})"',
                r'watch\?v=([a-zA-Z0-9_-]{11})',
                r'/watch\?v=([a-zA-Z0-9_-]{11})"',
                r'embed/([a-zA-Z0-9_-]{11})'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, response.text)
                if matches:
                    return f"https://www.youtube.com/watch?v={matches[0]}"
            
            return None
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return None
    
    def get_mp3_download_url(self, youtube_url: str) -> Optional[Tuple[str, str]]:
        """Get MP3 download URL - FIXED PATTERNS"""
        self._wait()
        
        # Try each domain with NEW patterns
        for domain in self.domains:
            try:
                url, title = self._extract_with_new_patterns(domain, youtube_url)
                if url:
                    logger.info(f"✅ Found MP3 from {domain}")
                    return url, title
            except Exception as e:
                logger.debug(f"Domain {domain} failed: {e}")
                continue
        
        # Try alternative services if savefrom fails
        return self._try_alternative_services(youtube_url)
    
    def _extract_with_new_patterns(self, domain: str, youtube_url: str) -> Tuple[Optional[str], str]:
        """NEW: Updated extraction for savefrom.net 2024"""
        savefrom_url = f"{domain}/#url={youtube_url}"
        
        response = requests.get(savefrom_url, headers=self.headers, timeout=15)
        html = response.text
        
        # Extract title - multiple patterns
        title = "Unknown Title"
        title_patterns = [
            r'<title>(.*?) - SaveFrom',
            r'"title":"(.*?)"',
            r'<h1[^>]*>(.*?)</h1>',
            r'og:title"[^>]*content="(.*?)"',
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                break
        
        # NEW: Look for download buttons with data attributes
        # SaveFrom now uses data-link attributes
        download_patterns = [
            # Pattern 1: data-link attribute (most common)
            r'data-link="(https?://[^"]+)"[^>]*data-type="mp3"',
            r'data-link="(https?://[^"]+\.mp3[^"]*)"',
            
            # Pattern 2: href with download class
            r'<a[^>]*class="[^"]*download[^"]*"[^>]*href="(https?://[^"]+\.mp3[^"]*)"',
            
            # Pattern 3: JSON data in script tags
            r'"url":"(https?://[^"]+\.mp3[^"]*)"',
            r'"downloadUrl":"(https?://[^"]+\.mp3[^"]*)"',
            
            # Pattern 4: New savefrom format
            r'href="(https?://[^"]+/download/[^"]+\.mp3[^"]*)"',
            
            # Pattern 5: Generic MP3 links
            r'"(https?://[^"]*\.googlevideo\.com[^"]*mime=audio%2Fmp4[^"]*)"',
        ]
        
        for pattern in download_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for link in matches:
                # Clean and decode URL
                link = unquote(link.replace('\\/', '/'))
                
                # Verify it's an MP3 link
                if any(keyword in link.lower() for keyword in ['mp3', 'mime=audio', 'audio', '.mp3']):
                    # Sometimes it's a relative URL
                    if link.startswith('//'):
                        link = 'https:' + link
                    elif link.startswith('/'):
                        link = domain + link
                    
                    logger.debug(f"Found MP3 link: {link[:100]}...")
                    return link, title
        
        return None, title
    
    def _try_alternative_services(self, youtube_url: str) -> Optional[Tuple[str, str]]:
        """Try other MP3 download services if savefrom fails"""
        video_id = youtube_url.split('v=')[-1].split('&')[0]
        
        # Try ytmp3 API
        try:
            api_url = f"https://ytmp3.nu/api/info/{video_id}"
            response = requests.get(api_url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'url' in data:
                    return data['url'], data.get('title', 'YouTube Audio')
        except:
            pass
        
        # Try yt5s API
        try:
            api_url = "https://yt5s.com/api/ajaxSearch/index"
            data = {
                'q': youtube_url,
                'vt': 'mp3'
            }
            headers = {
                **self.headers,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://yt5s.com',
                'Referer': 'https://yt5s.com/',
            }
            
            response = requests.post(api_url, data=data, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'vid' in data:
                    dl_url = f"https://yt5s.com/api/ajaxConvert/convert"
                    return dl_url, data.get('title', 'YouTube Audio')
        except:
            pass
        
        return None, "Unknown Title"
    
    def download_mp3(self, youtube_url: str) -> Optional[Tuple[str, str]]:
        """Download MP3 file"""
        try:
            # Get download URL
            mp3_url, title = self.get_mp3_download_url(youtube_url)
            
            if not mp3_url:
                logger.error("❌ No MP3 URL found")
                return None, title
            
            # Create temp file
            video_id = youtube_url.split('v=')[-1].split('&')[0]
            filename = f"{video_id}_{int(time.time())}.mp3"
            filepath = os.path.join(self.download_path, filename)
            
            logger.info(f"⬇️ Downloading: {title}")
            
            # Download the file
            response = requests.get(mp3_url, headers=self.headers, stream=True, timeout=60)
            response.raise_for_status()
            
            # Check size (Telegram limit: 50MB)
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > 50 * 1024 * 1024:
                logger.error("File too large for Telegram")
                return None, title
            
            # Download with progress
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Verify download
            if os.path.exists(filepath) and os.path.getsize(filepath) > 1024:
                size_mb = os.path.getsize(filepath) / 1024 / 1024
                logger.info(f"✅ Downloaded: {title} ({size_mb:.1f}MB)")
                return filepath, title
            else:
                if os.path.exists(filepath):
                    os.remove(filepath)
                return None, title
                
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None, "Unknown Title"

# Global instance
savefrom_downloader = SaveFromDownloader()