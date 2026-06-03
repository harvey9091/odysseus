# services/scraper/providers/peerlist — Peerlist provider
"""Scrape Peerlist for newly launched startups and projects."""

import logging
import re
from datetime import datetime, timedelta
from typing import Callable, Optional

from .base import BaseProvider, ProviderResult

logger = logging.getLogger(__name__)


class PeerlistProvider(BaseProvider):
    """Scrape Peerlist for startup/project launches."""

    name = "peerlist"
    base_url = "https://peerlist.io"
    rate_limit_delay = 2.0

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
                "message": f"Scraping Peerlist (last {days_back} days)...",
            })

        try:
            list_urls = [
                f"{self.base_url}/launches",
                f"{self.base_url}/launches/recent",
                f"{self.base_url}/projects",
            ]

            for list_url in list_urls:
                try:
                    html = await self._fetch_page(list_url)
                    if not html:
                        continue
                    page_results = self._parse_launches(html)
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
                    logger.debug(f"[{self.name}] Page failed {list_url}: {e}")
                    continue

            if progress_callback:
                progress_callback({
                    "type": "log",
                    "provider": self.name,
                    "message": f"Peerlist: {len(results)} leads collected",
                })

        except Exception as e:
            logger.error(f"[{self.name}] Scraping failed: {e}")
            if progress_callback:
                progress_callback({
                    "type": "error",
                    "provider": self.name,
                    "message": f"Peerlist scrape failed: {e}",
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

    def _parse_launches(self, html: str) -> list[ProviderResult]:
        results = []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            return results

        cards = soup.find_all(["a", "div", "article"], class_=re.compile(
            r"project|launch|card|item", re.I
        ))

        seen_names = set()
        for card in cards:
            try:
                name = card.get_text(strip=True)
                if not name or len(name) < 2 or len(name) > 80:
                    continue
                if name.lower() in seen_names:
                    continue
                seen_names.add(name.lower())

                website = None
                for a_tag in card.find_all("a", href=re.compile(r"^https?://")):
                    href = a_tag.get("href", "")
                    if "peerlist.io" not in href:
                        website = href
                        break

                domain = self.extract_domain(website) if website else None

                results.append(ProviderResult(
                    name=name,
                    website=website,
                    description=name,
                    domain=domain,
                    source_provider=self.name,
                    raw_data={"source": "peerlist"},
                ))
            except Exception:
                continue

        return results
