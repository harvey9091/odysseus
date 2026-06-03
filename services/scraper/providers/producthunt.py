# services/scraper/providers/producthunt — ProductHunt provider
"""Scrape newly launched products from ProductHunt."""

import logging
import re
from datetime import datetime, timedelta
from typing import Callable, Optional

from bs4 import BeautifulSoup

from .base import BaseProvider, ProviderResult

logger = logging.getLogger(__name__)


class ProductHuntProvider(BaseProvider):
    """Scrape ProductHunt for newly launched startups."""

    name = "producthunt"
    base_url = "https://www.producthunt.com"
    rate_limit_delay = 2.0  # PH is stricter with rate limits

    async def scrape(
        self,
        filters: dict,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> list[ProviderResult]:
        """Scrape recent ProductHunt launches."""
        results = []

        # Determine date range
        days_back = filters.get("days_back", 7)
        date_after = datetime.utcnow() - timedelta(days=days_back)

        if progress_callback:
            progress_callback({"type": "log", "provider": self.name, "message": f"Scraping ProductHunt launches from last {days_back} days..."})

        try:
            # Scrape the leaderboard page for recent posts
            # Note: ProductHunt has an API but requires auth; we scrape the public pages
            url = f"{self.base_url}/leaderboard/daily/{datetime.utcnow().strftime('%Y/%m/%d')}"
            html = await self.fetch_page(url)

            soup = BeautifulSoup(html, "html.parser")

            # Find product cards
            # PH uses various class patterns; we look for links to /posts/
            post_links = soup.find_all("a", href=re.compile(r"^/posts/[^/]+$"))

            seen_urls = set()
            for link in post_links:
                href = link.get("href", "")
                if href and href not in seen_urls:
                    seen_urls.add(href)
                    post_url = f"{self.base_url}{href}"

                    # Extract name from link text or data attributes
                    name = link.get_text(strip=True) or href.replace("/posts/", "").replace("-", " ").title()

                    if len(name) < 2 or len(name) > 100:
                        continue

                    if progress_callback:
                        progress_callback({"type": "log", "provider": self.name, "message": f"Found: {name}"})

                    # Try to get more details from the post page
                    product = await self._scrape_post_page(post_url, name)
                    if product:
                        results.append(product)

            if progress_callback:
                progress_callback({"type": "log", "provider": self.name, "message": f"ProductHunt: Found {len(results)} startups"})

        except Exception as e:
            logger.error(f"[{self.name}] Scraping failed: {e}")
            if progress_callback:
                progress_callback({"type": "error", "provider": self.name, "message": f"ProductHunt scrape failed: {e}"})

        return results

    async def _scrape_post_page(self, url: str, fallback_name: str) -> Optional[ProviderResult]:
        """Scrape details from a single ProductHunt post page."""
        try:
            html = await self.fetch_page(url)
            soup = BeautifulSoup(html, "html.parser")

            # Extract name
            name = fallback_name
            h1 = soup.find("h1")
            if h1:
                name = h1.get_text(strip=True)

            # Extract tagline/description
            description = ""
            tagline = soup.find("meta", {"property": "og:description"})
            if tagline:
                description = tagline.get("content", "")

            # Extract website link
            website = None
            visit_btn = soup.find("a", href=re.compile(r"/r/.*url="))
            if visit_btn:
                href = visit_btn.get("href", "")
                # Extract URL from redirect
                if "url=" in href:
                    website = href.split("url=")[-1].split("&")[0]
                    from urllib.parse import unquote
                    website = unquote(website)

            # Extract makers/founders
            founders = []
            maker_links = soup.find_all("a", href=re.compile(r"^/@"))
            for maker in maker_links[:5]:  # Limit to 5 makers
                maker_name = maker.get_text(strip=True)
                if maker_name:
                    founders.append({
                        "name": maker_name,
                        "profile_url": f"{self.base_url}{maker.get('href', '')}"
                    })

            # Extract topics/categories
            category = None
            topic_links = soup.find_all("a", href=re.compile(r"^/topics/"))
            if topic_links:
                category = topic_links[0].get_text(strip=True)

            # Extract launch date from meta
            launch_date = None
            time_el = soup.find("time")
            if time_el:
                datetime_str = time_el.get("datetime", "")
                if datetime_str:
                    try:
                        launch_date = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
                    except Exception:
                        pass

            domain = self.extract_domain(website) if website else None

            return ProviderResult(
                name=name,
                website=website,
                description=description,
                domain=domain,
                source_provider=self.name,
                source_url=url,
                launch_date=launch_date,
                category=category,
                founders=founders,
                raw_data={"scraped_at": datetime.utcnow().isoformat()}
            )

        except Exception as e:
            logger.warning(f"[{self.name}] Failed to scrape post page {url}: {e}")
            return None
