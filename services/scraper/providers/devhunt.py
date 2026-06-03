# services/scraper/providers/devhunt — DevHunt provider
"""Scrape DevHunt for newly launched developer tools."""

import logging
import re
from datetime import datetime, timedelta
from typing import Callable, Optional

from .base import BaseProvider, ProviderResult

logger = logging.getLogger(__name__)


class DevHuntProvider(BaseProvider):
    """Scrape DevHunt for newly launched dev tools."""

    name = "devhunt"
    base_url = "https://devhunt.org"
    rate_limit_delay = 1.5

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
                "message": f"Scraping DevHunt (last {days_back} days)...",
            })

        try:
            # DevHunt lists tools by date; try main listing + sort by date
            listing_urls = [
                f"{self.base_url}/?sort=date&page={n}"
                for n in range(1, 4)
            ]

            for list_url in listing_urls:
                try:
                    html = await self._fetch_page(list_url)
                    if not html:
                        continue

                    page_results = self._parse_listing(html, date_after)
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
                    logger.debug(f"[{self.name}] Listing failed {list_url}: {e}")
                    continue

            if progress_callback:
                progress_callback({
                    "type": "log",
                    "provider": self.name,
                    "message": f"DevHunt: {len(results)} leads collected",
                })

        except Exception as e:
            logger.error(f"[{self.name}] Scraping failed: {e}")
            if progress_callback:
                progress_callback({
                    "type": "error",
                    "provider": self.name,
                    "message": f"DevHunt scrape failed: {e}",
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

    def _parse_listing(self, html: str, date_after: datetime) -> list[ProviderResult]:
        results = []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            return results

        # DevHunt uses cards/tool links
        cards = (
            soup.find_all("div", class_=re.compile(r"tool|card|item", re.I))
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
                    if "devhunt.org" not in href:
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
                    raw_data={"source": "devhunt"},
                ))
            except Exception:
                continue

        return results
