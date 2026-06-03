# services/scraper/analyzers/video_detector — Video presence detection
"""Detect whether a startup has promo/explainer/demo videos."""

import logging
import re
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Video embed patterns
VIDEO_PATTERNS = [
    # YouTube
    r'youtube\.com/embed/',
    r'youtube\.com/watch\?v=',
    r'youtu\.be/',
    r'youtube-nocookie\.com/embed/',
    # Vimeo
    r'vimeo\.com/\d+',
    r'player\.vimeo\.com/video/',
    # Loom
    r'loom\.com/share/',
    r'loom\.com/embed/',
    # Wistia
    r'wistia\.(?:com|net)/embed/',
    r'fast\.wistia\.(?:com|net)/embed/',
    # Vidyard
    r'vidyard\.com/watch/',
    r'play\.vidyard\.com/',
    # Generic video tags
    r'<video[^>]*src=',
    r'<source[^>]*type=["\']video/',
]

# Compile patterns
VIDEO_REGEX = [re.compile(pat, re.IGNORECASE) for pat in VIDEO_PATTERNS]


class VideoDetector:
    """Detect video presence on startup websites."""

    def __init__(self, timeout: int = 20):
        self.timeout = timeout

    async def check(self, website_url: str) -> dict:
        """
        Check if a website has promo/explainer/demo videos.

        Returns:
            {
                "has_video": bool,
                "video_urls": list[str],
                "video_types": list[str],  # e.g., ["youtube", "vimeo"]
                "confidence": float  # 0.0 - 1.0
            }
        """
        result = {
            "has_video": False,
            "video_urls": [],
            "video_types": [],
            "confidence": 0.0,
        }

        if not website_url:
            return result

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                # Check main page
                main_result = await self._check_page(session, website_url)
                result["video_urls"].extend(main_result["urls"])
                result["video_types"].extend(main_result["types"])

                # If no video found, check common video pages
                if not result["video_urls"]:
                    from urllib.parse import urljoin
                    video_pages = [
                        urljoin(website_url, "/demo"),
                        urljoin(website_url, "/video"),
                        urljoin(website_url, "/tour"),
                    ]
                    for page_url in video_pages:
                        try:
                            page_result = await self._check_page(session, page_url)
                            result["video_urls"].extend(page_result["urls"])
                            result["video_types"].extend(page_result["types"])
                            if page_result["urls"]:
                                break
                        except Exception:
                            continue

        except Exception as e:
            logger.warning(f"Video detection failed for {website_url}: {e}")

        # Deduplicate
        result["video_urls"] = list(set(result["video_urls"]))
        result["video_types"] = list(set(result["video_types"]))
        result["has_video"] = len(result["video_urls"]) > 0
        result["confidence"] = 1.0 if result["has_video"] else 0.0

        return result

    async def _check_page(self, session: aiohttp.ClientSession, url: str) -> dict:
        """Check a single page for videos."""
        urls = []
        types = []

        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return {"urls": urls, "types": types}

                html = await response.text()

                # Check regex patterns
                for i, pattern in enumerate(VIDEO_REGEX):
                    matches = pattern.findall(html)
                    if matches:
                        # Determine video type from pattern index
                        if i < 4:
                            types.append("youtube")
                        elif i < 6:
                            types.append("vimeo")
                        elif i < 8:
                            types.append("loom")
                        elif i < 10:
                            types.append("wistia")
                        elif i < 12:
                            types.append("vidyard")
                        else:
                            types.append("native")

                        # Extract actual URLs
                        for match in matches[:3]:  # Limit matches
                            if isinstance(match, str) and match.startswith("http"):
                                urls.append(match)

                # Parse HTML for video elements
                soup = BeautifulSoup(html, "html.parser")

                # Check <video> tags
                videos = soup.find_all("video")
                for video in videos:
                    src = video.get("src")
                    if src:
                        urls.append(src)
                        types.append("native")
                    source = video.find("source")
                    if source:
                        src = source.get("src")
                        if src:
                            urls.append(src)
                            types.append("native")

                # Check iframes
                iframes = soup.find_all("iframe", src=True)
                for iframe in iframes:
                    src = iframe.get("src", "")
                    for pattern in VIDEO_REGEX[:8]:  # Only check embed patterns
                        if pattern.search(src):
                            urls.append(src)
                            break

        except Exception:
            pass

        return {"urls": urls, "types": types}
