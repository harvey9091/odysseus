# services/scraper/extractors/founder_extractor — Founder extraction
"""Extract founder/team information from websites."""

import logging
import re
from typing import Optional
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class FounderExtractor:
    """Extract founder and team information from websites."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    async def extract(self, website_url: str, existing_founders: list = None) -> list[dict]:
        """
        Extract founder info from a website.

        Returns list of {"name": "...", "role": "...", "linkedin": "...", "twitter": "..."}
        """
        founders = list(existing_founders or [])
        seen_names = {f.get("name", "").lower() for f in founders}

        if not website_url:
            return founders

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                # Try about/team pages
                pages_to_check = [
                    urljoin(website_url, "/about"),
                    urljoin(website_url, "/team"),
                    urljoin(website_url, "/about-us"),
                    urljoin(website_url, "/founders"),
                ]

                for page_url in pages_to_check:
                    try:
                        page_founders = await self._scrape_founders(session, page_url)
                        for f in page_founders:
                            name_lower = f.get("name", "").lower()
                            if name_lower and name_lower not in seen_names:
                                seen_names.add(name_lower)
                                founders.append(f)
                    except Exception:
                        continue

        except Exception as e:
            logger.warning(f"Founder extraction failed for {website_url}: {e}")

        return founders[:10]  # Limit to 10 founders

    async def _scrape_founders(self, session: aiohttp.ClientSession, url: str) -> list[dict]:
        """Scrape founder info from a single page."""
        founders = []
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return founders
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")

                # Look for common founder patterns
                # LinkedIn links
                linkedin_links = soup.find_all("a", href=re.compile(r"linkedin\.com/in/"))
                for link in linkedin_links:
                    name = link.get_text(strip=True)
                    href = link.get("href", "")
                    if name and len(name) > 2 and len(name) < 50:
                        founders.append({
                            "name": name,
                            "linkedin": href,
                            "source": url
                        })

                # Twitter links
                twitter_links = soup.find_all("a", href=re.compile(r"(twitter|x)\.com/[^/]+$"))
                for link in twitter_links:
                    href = link.get("href", "")
                    username = href.rstrip("/").split("/")[-1]
                    if username and username not in ["share", "intent", "home"]:
                        # Try to find associated name
                        parent = link.find_parent(["div", "li", "article"])
                        name = ""
                        if parent:
                            name_el = parent.find(["h3", "h4", "strong", "b"])
                            if name_el:
                                name = name_el.get_text(strip=True)
                        if name:
                            founders.append({
                                "name": name,
                                "twitter": f"https://x.com/{username}",
                                "source": url
                            })

        except Exception:
            pass
        return founders
