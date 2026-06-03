# services/scraper/providers/uneed — Uneed provider
"""Scrape Uneed for newly launched products."""

import logging
import re
from datetime import datetime, timedelta
from typing import Callable, Optional

from .base import BaseProvider, ProviderResult

logger = logging.getLogger(__name__)


class UneedProvider(BaseProvider):
    """Scrape Uneed for newly launched products."""

    name = "uneed"
    base_url = "https://www.uneed.best"
    rate_limit_delay = 1.5

    async def scrape(
        self,
        filters: dict,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> list[ProviderResult]:
        results = []
        days_back = filters.get("days_back", 14)

        if progress_callback:
            progress_callback({
                "type": "log",
                "provider": self.name,
                "message": f"Scraping Uneed (last {days_back} days)...",
            })

        try:
            for page in range(1, 4):
                list_url = f"{self.base_url}/?page={page}"
                try:
                    html = await self._fetch_page(list_url)
                    if not html:
                        continue
                    page_results = self._parse_listing(html)
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
                    logger.debug(f"[{self.name}] Page {page} failed: {e}")
                    continue

            if progress_callback:
                progress_callback({
                    "type": "log",
                    "provider": self.name,
                    "message": f"Uneed: {len(results)} leads collected",
                })

        except Exception as e:
            logger.error(f"[{self.name}] Scraping failed: {e}")
            if progress_callback:
                progress_callback({
                    "type": "error",
                    "provider": self.name,
                    "message": f"Uneed scrape failed: {e}",
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

    def _parse_listing(self, html: str) -> list[ProviderResult]:
        results = []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            return results

        cards = (
            soup.find_all("div", class_=re.compile(r"product|card|item", re.I))
            or soup.find_all("article")
        )

        for card in cards:
            try:
                name = ""
                for tag in card.find_all(["h2", "h3", "h4", "a", "span"]):
                    text = tag.get_text(strip=True)
                    if text and 2 < len(text) < 80:
                        name = text
                        break
                if not name:
                    continue

                website = None
                for a_tag in card.find_all("a", href=re.compile(r"^https?://")):
                    href = a_tag.get("href", "")
                    if "uneed.best" not in href:
                        website = href
                        break

                domain = self.extract_domain(website) if website else None
                desc = ""
                desc_el = card.find("p") or card.find("div", class_=re.compile(r"desc", re.I))
                if desc_el:
                    desc = desc_el.get_text(strip=True)[:200]

                results.append(ProviderResult(
                    name=name,
                    website=website,
                    description=desc,
                    domain=domain,
                    source_provider=self.name,
                    raw_data={"source": "uneed"},
                ))
            except Exception:
                continue

        return results
