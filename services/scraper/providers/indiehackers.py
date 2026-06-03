# services/scraper/providers/indiehackers — Indie Hackers provider
"""Scrape Indie Hackers for startup/project launches."""

import logging
import re
from datetime import datetime, timedelta
from typing import Callable, Optional

from .base import BaseProvider, ProviderResult

logger = logging.getLogger(__name__)


class IndieHackersProvider(BaseProvider):
    """Scrape Indie Hackers for newly launched side projects and startups."""

    name = "indiehackers"
    base_url = "https://www.indiehackers.com"
    rate_limit_delay = 2.0

    async def scrape(
        self,
        filters: dict,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> list[ProviderResult]:
        results = []
        days_back = filters.get("days_back", 14)
        date_after = datetime.utcnow() - timedelta(days=days_back)

        if progress_callback:
            progress_callback({
                "type": "log",
                "provider": self.name,
                "message": f"Scraping Indie Hackers (last {days_back} days)...",
            })

        try:
            # IH has topic pages and a "latest" feed
            feed_urls = [
                f"{self.base_url}/topics/launches",
                f"{self.base_url}/topics/show-ih",
                f"{self.base_url}/posts",
            ]

            for base_url in feed_urls:
                page_urls = [base_url]
                # Add pagination
                for p in range(2, 4):
                    page_urls.append(f"{base_url}?page={p}")

                for page_url in page_urls:
                    try:
                        html = await self._fetch_page(page_url)
                        if not html:
                            continue

                        page_results = self._parse_feed_page(html, date_after)
                        for r in page_results:
                            if r not in results:
                                results.append(r)
                                if progress_callback:
                                    progress_callback({
                                        "type": "lead_found",
                                        "provider": self.name,
                                        "name": r.name,
                                    })

                    except Exception as e:
                        logger.debug(f"[{self.name}] Feed page failed {page_url}: {e}")
                        continue

            if progress_callback:
                progress_callback({
                    "type": "log",
                    "provider": self.name,
                    "message": f"Indie Hackers: {len(results)} leads collected",
                })

        except Exception as e:
            logger.error(f"[{self.name}] Scraping failed: {e}")
            if progress_callback:
                progress_callback({
                    "type": "error",
                    "provider": self.name,
                    "message": f"Indie Hackers scrape failed: {e}",
                })

        return results

    async def _fetch_page(self, url: str) -> Optional[str]:
        try:
            html = await self.fetch_page(url)
            if html and len(html) > 2000:
                return html
        except Exception:
            pass
        try:
            from ..browser_client import BrowserClient
            async with BrowserClient(headless=True, timeout=30) as bc:
                return await bc.fetch_page(url, scroll=True)
        except Exception as e:
            logger.debug(f"[{self.name}] Browser fetch failed for {url}: {e}")
            return None

    def _parse_feed_page(self, html: str, date_after: datetime) -> list[ProviderResult]:
        results = []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            return results

        # IH post links typically point to /posts/...
        post_links = soup.find_all("a", href=re.compile(r"^/posts/[a-z0-9-]+"))
        seen = set()
        for a_tag in post_links:
            href = a_tag.get("href", "")
            if href in seen:
                continue
            seen.add(href)

            post_url = f"{self.base_url}{href}"
            title = a_tag.get_text(strip=True)
            if not title or len(title) < 3 or len(title) > 120:
                continue

            # Skip non-launch posts
            title_lower = title.lower()
            skip_words = ("how i ", "why i ", "my journey", "lessons learned",
                          "what i learned", "reflections on", "monthly recap",
                          "weekly recap", "ama:", "q&a:")
            if any(title_lower.startswith(sw) for sw in skip_words):
                continue

            domain = None
            # Try to find the project URL in nearby text
            parent = a_tag.find_parent(["div", "article", "li"])
            if parent:
                for link in parent.find_all("a", href=re.compile(r"^https?://")):
                    href = link.get("href", "")
                    if "indiehackers.com" not in href:
                        domain = self.extract_domain(href)
                        break

            results.append(ProviderResult(
                name=title,
                website=None,
                description=title,
                domain=domain,
                source_provider=self.name,
                source_url=post_url,
                raw_data={"source": "indiehackers", "post_url": post_url},
            ))

        return results
