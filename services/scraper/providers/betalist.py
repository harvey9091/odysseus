# services/scraper/providers/betalist — BetaList provider
"""Scrape BetaList for newly launched early-stage startups."""

import logging
import re
from datetime import datetime, timedelta
from typing import Callable, Optional
from urllib.parse import urljoin

from .base import BaseProvider, ProviderResult

logger = logging.getLogger(__name__)


class BetaListProvider(BaseProvider):
    """Scrape BetaList for early-stage startup launches."""

    name = "betalist"
    base_url = "https://betalist.com"
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
                "message": f"Scraping BetaList (last {days_back} days)...",
            })

        try:
            # BetaList has a start page with pagination
            start_urls = [
                f"{self.base_url}/startups?page={n}"
                for n in range(1, 6)  # Up to 5 pages
            ]

            for page_url in start_urls:
                try:
                    html = await self._fetch_page(page_url)
                    if not html:
                        continue

                    page_results = self._parse_startup_list(html, date_after)
                    for r in page_results:
                        if r not in results:
                            results.append(r)
                            if progress_callback:
                                progress_callback({
                                    "type": "lead_found",
                                    "provider": self.name,
                                    "name": r.name,
                                })

                    if progress_callback:
                        progress_callback({
                            "type": "log",
                            "provider": self.name,
                            "message": f"BetaList page {page_url}: {len(page_results)} startups",
                        })

                except Exception as e:
                    logger.debug(f"[{self.name}] Page failed {page_url}: {e}")
                    continue

            if progress_callback:
                progress_callback({
                    "type": "log",
                    "provider": self.name,
                    "message": f"BetaList: {len(results)} leads collected",
                })

        except Exception as e:
            logger.error(f"[{self.name}] Scraping failed: {e}")
            if progress_callback:
                progress_callback({
                    "type": "error",
                    "provider": self.name,
                    "message": f"BetaList scrape failed: {e}",
                })

        return results

    async def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch page with Browser Use fallback."""
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

    def _parse_startup_list(self, html: str, date_after: datetime) -> list[ProviderResult]:
        """Parse BetaList startup listing page."""
        results = []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            return results

        # BetaList uses cards with startup info
        # Try multiple selectors
        cards = (
            soup.find_all("div", class_=re.compile(r"startup|card|item", re.I))
            or soup.find_all("article")
            or soup.find_all("li", class_=re.compile(r"startup|item", re.I))
        )

        for card in cards:
            try:
                result = self._parse_card(card)
                if not result:
                    continue

                # Filter by date if available
                if result.launch_date and result.launch_date < date_after:
                    continue

                results.append(result)
            except Exception:
                continue

        return results

    def _parse_card(self, card) -> Optional[ProviderResult]:
        """Parse a single startup card."""
        from bs4 import BeautifulSoup

        # Name
        name = ""
        for tag in card.find_all(["h2", "h3", "h4", "a", "span", "div"]):
            text = tag.get_text(strip=True)
            if text and 2 < len(text) < 80 and not text.startswith("http"):
                name = text
                break
        if not name:
            return None

        # Website
        website = None
        for a_tag in card.find_all("a", href=re.compile(r"^https?://")):
            href = a_tag.get("href", "")
            if "betalist.com" not in href:
                website = href
                break

        domain = self.extract_domain(website) if website else None

        # Description
        description = ""
        desc_el = card.find("p") or card.find("div", class_=re.compile(r"desc|summary|tagline", re.I))
        if desc_el:
            description = desc_el.get_text(strip=True)[:300]

        # Date
        launch_date = None
        date_el = card.find("time") or card.find("span", class_=re.compile(r"date|time", re.I))
        if date_el:
            dt_str = date_el.get("datetime", "") or date_el.get_text(strip=True)
            if dt_str:
                try:
                    launch_date = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                except Exception:
                    for fmt in ("%B %d, %Y", "%d %B %Y", "%Y-%m-%d"):
                        try:
                            launch_date = datetime.strptime(dt_str[:len(fmt.replace('%',''))+10], fmt)
                            launch_date = launch_date.replace(year=datetime.utcnow().year)
                            break
                        except Exception:
                            pass

        return ProviderResult(
            name=name,
            website=website,
            description=description,
            domain=domain,
            source_provider=self.name,
            launch_date=launch_date,
            raw_data={"source": "betalist"},
        )
