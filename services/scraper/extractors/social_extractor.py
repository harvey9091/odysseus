# services/scraper/extractors/social_extractor — Social profile extraction
"""Extract social media profiles from websites."""

import logging
import re
from typing import Optional
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class SocialExtractor:
    """Extract social media profiles from websites."""

    # Social URL patterns
    SOCIAL_PATTERNS = {
        "twitter": r"(?:twitter|x)\.com/([A-Za-z0-9_]+)",
        "linkedin_company": r"linkedin\.com/company/([A-Za-z0-9-]+)",
        "github": r"github\.com/([A-Za-z0-9-]+)",
        "facebook": r"facebook\.com/([A-Za-z0-9.]+)",
        "instagram": r"instagram\.com/([A-Za-z0-9_.]+)",
        "youtube": r"youtube\.com/(?:@|c/|channel/)?([A-Za-z0-9_-]+)",
        "crunchbase": r"crunchbase\.com/organization/([A-Za-z0-9-]+)",
    }

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    async def extract(self, website_url: str) -> dict:
        """
        Extract social profiles from a website.

        Returns dict of {"twitter": "...", "linkedin": "...", etc.}
        """
        social = {}

        if not website_url:
            return social

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.get(website_url) as response:
                    if response.status != 200:
                        return social
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")

                    # Find all links
                    links = soup.find_all("a", href=True)
                    for link in links:
                        href = link.get("href", "")
                        for platform, pattern in self.SOCIAL_PATTERNS.items():
                            match = re.search(pattern, href, re.IGNORECASE)
                            if match and platform not in social:
                                # Validate the username
                                username = match.group(1)
                                if username and len(username) > 1 and not username.startswith("share"):
                                    social[platform] = href

        except Exception as e:
            logger.warning(f"Social extraction failed for {website_url}: {e}")

        return social
