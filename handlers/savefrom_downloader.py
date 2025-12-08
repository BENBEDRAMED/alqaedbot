#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import logging
import time
import random
import tempfile
import requests
import json
from typing import Optional, Tuple
from urllib.parse import quote, unquote, urlparse, parse_qs

logger = logging.getLogger("groupmanager")

class SaveFromDownloader:
    def __init__(self):
        self.download_path = "downloads"
        os.makedirs(self.download_path, exist_ok=True)
        
        # Updated domains with working ones
        self.domains = [
            'https://en.savefrom.net',
            'https://www.savefrom.net',
            'https://savefrom.io',
            'https://ssyoutube.com',
            'https://sfrom.net',
            'https://savefrom.vip',
        ]
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.youtube.com/',
            'Origin': 'https://www.youtube.com',
            'DNT': '1',
        }
    
    def _wait(self):
        """Add random delay"""
        time.sleep(random.uniform(2, 4))
    
    def search_youtube(self, query: str) -> Optional[str]:
        """Search YouTube - Updated with better patterns"""
        self._wait()
        try:
            encoded = quote(query)
            url = f"https://www.youtube.com/results?search_query={encoded}"
            
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            # Multiple patterns to find video ID
            patterns = [
                r'"videoId":"([a-zA-Z0-9_-]{11})"',
                r'watch\?v=([a-zA-Z0-9_-]{11})[^"]*',
                r'/watch\?v=([a-zA-Z0-9_-]{11})"',
                r'embed/([a-zA-Z0-9_-]{11})',
                r'videoId=([a-zA-Z0-9_-]{11})'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, response.text)
                if matches:
                    # Get first unique match
                    video_id = matches[0]
                    logger.info(f"Found video ID: {video_id}")
                    return f"https://www.youtube.com/watch?v={video_id}"
            
            # Alternative: Search using YouTube API
            try:
                search_url = f"https://www.youtube.com/youtubei/v1/search?key=AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
                payload = {
                    "context": {
                        "client": {
                            "hl": "en",
                            "gl": "US",
                            "clientName": "WEB",
                            "clientVersion": "2.20241208.00.00"
                        }
                    },
                    "query": query
                }
                response = requests.post(search_url, json=payload, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    # Parse response to find video ID
                    import json
                    videos = json.dumps(data)
                    match = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', videos)
                    if match:
                        return f"https://www.youtube.com/watch?v={match.group(1)}"
            except:
                pass
                
            return None
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return None
    
    def _extract_with_savefrom_api(self, youtube_url: str) -> Tuple[Optional[str], str]:
        """Try to use SaveFrom API directly"""
        try:
            # Direct API endpoint
            api_url = "https://api.savefrom.net/api/convert"
            
            params = {
                'url': youtube_url,
                'token': '',
                'format': 'mp3',
                'device': 'desktop'
            }
            
            response = requests.get(api_url, params=params, headers=self.headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if 'url' in data and data['url']:
                    title = data.get('meta', {}).get('title', 'YouTube Audio')
                    return data['url'], title
        except Exception as e:
            logger.debug(f"SaveFrom API failed: {e}")
        
        return None, "Unknown Title"
    
    def _extract_with_ytmp3_api(self, youtube_url: str) -> Tuple[Optional[str], str]:
        """Use ytmp3.nu API"""
        try:
            video_id = youtube_url.split('v=')[-1].split('&')[0]
            
            # Get info first
            info_url = f"https://ytmp3.nu/api/info/{video_id}"
            response = requests.get(info_url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'durl' in data:
                    title = data.get('title', 'YouTube Audio')
                    # Get download URL
                    dl_url = f"https://ytmp3.nu/api/button/mp3/{video_id}"
                    dl_response = requests.get(dl_url, headers=self.headers, timeout=10)
                    if dl_response.status_code == 200:
                        dl_data = dl_response.json()
                        if 'url' in dl_data:
                            return dl_data['url'], title
        except Exception as e:
            logger.debug(f"ytmp3 API failed: {e}")
        
        return None, "Unknown Title"
    
    def _extract_with_yt5s(self, youtube_url: str) -> Tuple[Optional[str], str]:
        """Use yt5s.com API"""
        try:
            video_id = youtube_url.split('v=')[-1].split('&')[0]
            
            # Get token first
            token_url = "https://yt5s.com/api/ajaxSearch/index"
            payload = {
                'q': youtube_url,
                'vt': 'mp3'
            }
            
            headers = {
                **self.headers,
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': 'https://yt5s.com',
                'Referer': 'https://yt5s.com/',
            }
            
            response = requests.post(token_url, data=payload, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if 'vid' in data:
                    # Get download URL
                    convert_url = "https://yt5s.com/api/ajaxConvert/convert"
                    convert_payload = {
                        'vid': video_id,
                        'k': data.get('k', ''),
                        'ftype': 'mp3',
                        'fquality': '128'
                    }
                    
                    convert_response = requests.post(convert_url, data=convert_payload, headers=headers, timeout=15)
                    
                    if convert_response.status_code == 200:
                        convert_data = convert_response.json()
                        if 'd_url' in convert_data:
                            title = data.get('title', 'YouTube Audio')
                            return convert_data['d_url'], title
        except Exception as e:
            logger.debug(f"yt5s API failed: {e}")
        
        return None, "Unknown Title"
    
    def get_mp3_download_url(self, youtube_url: str) -> Optional[Tuple[str, str]]:
        """Get MP3 download URL - Multiple fallback methods"""
        self._wait()
        
        # Method 1: Try SaveFrom API
        logger.info("Trying SaveFrom API...")
        result = self._extract_with_savefrom_api(youtube_url)
        if result[0]:
            return result
        
        # Method 2: Try ytmp3.nu
        logger.info("Trying ytmp3.nu...")
        result = self._extract_with_ytmp3_api(youtube_url)
        if result[0]:
            return result
        
        # Method 3: Try yt5s.com
        logger.info("Trying yt5s.com...")
        result = self._extract_with_yt5s(youtube_url)
        if result[0]:
            return result
        
        # Method 4: Try direct HTML parsing as last resort
        logger.info("Trying HTML parsing...")
        result = self._extract_from_html(youtube_url)
        if result[0]:
            return result
        
        logger.error("All download methods failed")
        return None, "Unknown Title"
    
    def _extract_from_html(self, youtube_url: str) -> Tuple[Optional[str], str]:
        """Extract download URL from HTML as fallback"""
        for domain in self.domains:
            try:
                savefrom_url = f"{domain}/#url={youtube_url}"
                
                headers = {
                    **self.headers,
                    'Referer': domain,
                }
                
                response = requests.get(savefrom_url, headers=headers, timeout=20)
                html = response.text
                
                # Extract title
                title = "Unknown Title"
                title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
                if title_match:
                    title = title_match.group(1).split(' - ')[0].strip()
                
                # Multiple patterns for MP3 links
                patterns = [
                    r'href="(https?://[^"]+\.mp3[^"]*)"',
                    r'data-link="(https?://[^"]+)"[^>]*data-type="mp3"',
                    r'"downloadUrl":"(https?://[^"]+\.mp3[^"]*)"',
                    r'"url":"(https?://[^"]+\.mp3[^"]*)"',
                    r'<a[^>]*href="(https?://[^"]+)"[^>]*>.*?MP3.*?</a>',
                    r'"(https?://[^"]*\.googlevideo\.com[^"]*mime=audio[^"]*)"',
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, html, re.IGNORECASE)
                    for link in matches:
                        link = unquote(link.replace('\\/', '/'))
                        
                        # Clean URL
                        if link.startswith('//'):
                            link = 'https:' + link
                        elif link.startswith('/'):
                            link = domain + link
                        
                        # Verify it's an audio link
                        if any(keyword in link.lower() for keyword in ['.mp3', 'audio', 'mime=audio']):
                            # Check if URL is accessible
                            try:
                                head = requests.head(link, headers=self.headers, timeout=5, allow_redirects=True)
                                if head.status_code == 200:
                                    content_type = head.headers.get('content-type', '')
                                    if 'audio' in content_type.lower() or 'mp3' in content_type.lower():
                                        logger.info(f"Found valid MP3 link: {link[:100]}...")
                                        return link, title
                            except:
                                continue
                
            except Exception as e:
                logger.debug(f"HTML extraction from {domain} failed: {e}")
                continue
        
        return None, "Unknown Title"
    
    def download_mp3(self, youtube_url: str) -> Optional[Tuple[str, str]]:
        """Download MP3 file with better error handling"""
        try:
            # Get download URL
            mp3_url, title = self.get_mp3_download_url(youtube_url)
            
            if not mp3_url:
                logger.error("❌ No MP3 URL found")
                return None, title
            
            # Clean title for filename
            safe_title = re.sub(r'[<>:"/\\|?*]', '', title)[:100]
            video_id = youtube_url.split('v=')[-1].split('&')[0]
            filename = f"{video_id}_{safe_title}_{int(time.time())}.mp3"
            filepath = os.path.join(self.download_path, filename)
            
            logger.info(f"⬇️ Downloading: {title}")
            
            # Download with retry
            for attempt in range(3):
                try:
                    headers = {
                        **self.headers,
                        'Range': 'bytes=0-',
                        'Accept-Ranges': 'bytes',
                    }
                    
                    response = requests.get(mp3_url, headers=headers, stream=True, timeout=30)
                    response.raise_for_status()
                    
                    # Check size
                    content_length = response.headers.get('content-length')
                    if content_length and int(content_length) > 45 * 1024 * 1024:  # 45MB limit
                        logger.error(f"File too large: {int(content_length)/1024/1024:.1f}MB")
                        return None, title
                    
                    # Download
                    with open(filepath, 'wb') as f:
                        downloaded = 0
                        start_time = time.time()
                        
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                # Log progress every 1MB
                                if downloaded % (1024 * 1024) == 0:
                                    elapsed = time.time() - start_time
                                    speed = downloaded / elapsed / 1024 if elapsed > 0 else 0
                                    logger.debug(f"Downloaded: {downloaded/1024/1024:.1f}MB ({speed:.1f} KB/s)")
                    
                    # Verify
                    if os.path.exists(filepath) and os.path.getsize(filepath) > 10240:  # > 10KB
                        size_mb = os.path.getsize(filepath) / 1024 / 1024
                        logger.info(f"✅ Downloaded: {title} ({size_mb:.1f}MB)")
                        return filepath, title
                    else:
                        logger.warning(f"Downloaded file too small, attempt {attempt + 1}")
                        if os.path.exists(filepath):
                            os.remove(filepath)
                        continue
                        
                except Exception as e:
                    logger.warning(f"Download attempt {attempt + 1} failed: {e}")
                    if attempt < 2:
                        time.sleep(2)
                    continue
            
            # All attempts failed
            if os.path.exists(filepath):
                os.remove(filepath)
            return None, title
                
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None, "Unknown Title"

# Global instance
savefrom_downloader = SaveFromDownloader()