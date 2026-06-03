# services/scraper/providers/alternativeto — AlternativeTo provider
"""Scrape AlternativeTo for newly launched software alternatives."""

import logging
import re
from datetime import datetime, timedelta
from typing import Callable, Optional

from .base import BaseProvider, ProviderResult

logger = logging.getLogger(__name__)


class AlternativeToProvider(BaseProvider):
    """Scrape AlternativeTo for new software launches."""

    name = "alternativeto"
    base_url = "https://alternativeto.net"
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
                "message": f"Scraping AlternativeTo (last {days_back} days)...",
            })

        try:
            # AlternativeTo has "latest additions" and category pages
            list_urls = [
                f"{self.base_url}/latest/",
                f"{self.base_url}/category/productivity/",
                f"{self.base_url}/category/development/",
                f"{self.base_url}/category/business/",
            ]

            for list_url in list_urls:
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
                    logger.debug(f"[{self.name}] Page failed {list_url}: {e}")
                    continue

            if progress_callback:
                progress_callback({
                    "type": "log",
                    "provider": self.name,
                    "message": f"AlternativeTo: {len(results)} leads collected",
                })

        except Exception as e:
            logger.error(f"[{self.name}] Scraping failed: {e}")
            if progress_callback:
                progress_callback({
                    "type": "error",
                    "provider": self.name,
                    "message": f"AlternativeTo scrape failed: {e}",
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

        # AlternativeTo uses app cards with links to /app/...
        app_links = soup.find_all("a", href=re.compile(r"^/app/[^/]+"))
        seen = set()
        for a_tag in app_links:
            href = a_tag.get("href", "")
            if href in seen:
                continue
            seen.add(href)

            name = a_tag.get_text(strip=True)
            if not name or len(name) < 2 or len(name) > 80:
                continue

            app_url = f"{self.base_url}{href}"
            results.append(ProviderResult(
                name=name,
                website=None,
                description=name,
                domain=None,
                source_provider=self.name,
                source_url=app_url,
                raw_data={"source": "alternativeto", "app_url": app_url},
            ))

        return results
