# services/scraper/providers/producthunt — ProductHunt provider
"""Scrape newly launched startups from ProductHunt.
Uses Browser Use for JS-rendered pages, falls back to aiohttp."""

import logging
import re
from datetime import datetime, timedelta
from typing import Callable, Optional
from urllib.parse import urljoin

from .base import BaseProvider, ProviderResult

logger = logging.getLogger(__name__)


class ProductHuntProvider(BaseProvider):
    """Scrape ProductHunt daily leaderboard for newly launched startups."""

    name = "producthunt"
    base_url = "https://www.producthunt.com"
    rate_limit_delay = 2.0

    async def scrape(
        self,
        filters: dict,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> list[ProviderResult]:
        results = []
        days_back = filters.get("days_back", 7)
        date_after = datetime.utcnow() - timedelta(days=days_back)

        if progress_callback:
            progress_callback({
                "type": "log",
                "provider": self.name,
                "message": f"Scraping ProductHunt (last {days_back} days)...",
            })

        try:
            # Collect candidate post URLs across the date range.
            post_urls = await self._collect_post_urls(days_back, progress_callback)
            if progress_callback:
                progress_callback({
                    "type": "log",
                    "provider": self.name,
                    "message": f"Found {len(post_urls)} post pages to inspect",
                })

            # Deduplicate
            seen = set()
            for post_url in post_urls:
                if post_url in seen:
                    continue
                seen.add(post_url)

                try:
                    product = await self._scrape_post_page(post_url)
                    if product and product.launch_date and product.launch_date >= date_after:
                        results.append(product)
                        if progress_callback:
                            progress_callback({
                                "type": "lead_found",
                                "provider": self.name,
                                "name": product.name,
                            })
                except Exception as e:
                    logger.debug(f"[{self.name}] Skipping {post_url}: {e}")
                    continue

            if progress_callback:
                progress_callback({
                    "type": "log",
                    "provider": self.name,
                    "message": f"ProductHunt: {len(results)} leads collected",
                })

        except Exception as e:
            logger.error(f"[{self.name}] Scraping failed: {e}")
            if progress_callback:
                progress_callback({
                    "type": "error",
                    "provider": self.name,
                    "message": f"ProductHunt scrape failed: {e}",
                })

        return results

    async def _collect_post_urls(self, days_back: int, progress_callback) -> list[str]:
        """Collect /posts/ URLs by scraping daily leaderboard pages."""
        urls = []
        seen = set()
        today = datetime.utcnow()

        # Try today's leaderboard first
        date_str = today.strftime("%Y/%m/%d")
        leaderboard_url = f"{self.base_url}/leaderboard/daily/{date_str}"
        try:
            html = await self._fetch_leaderboard(leaderboard_url)
            if html:
                found = self._extract_post_links(html)
                for u in found:
                    if u not in seen:
                        seen.add(u)
                        urls.append(u)
                if progress_callback:
                    progress_callback({
                        "type": "log",
                        "provider": self.name,
                        "message": f"Leaderboard today: {len(found)} posts",
                    })
        except Exception as e:
            logger.debug(f"[{self.name}] Today's leaderboard failed: {e}")

        # Walk back through previous days
        for day_offset in range(1, days_back):
            date_str = (today - timedelta(days=day_offset)).strftime("%Y/%m/%d")
            leaderboard_url = f"{self.base_url}/leaderboard/daily/{date_str}"
            try:
                html = await self._fetch_leaderboard(leaderboard_url)
                if html:
                    found = self._extract_post_links(html)
                    for u in found:
                        if u not in seen:
                            seen.add(u)
                            urls.append(u)
            except Exception as e:
                logger.debug(f"[{self.name}] Leaderboard {date_str} failed: {e}")
                continue

        return urls

    async def _fetch_leaderboard(self, url: str) -> Optional[str]:
        """Fetch a leaderboard page, trying Browser Use first then aiohttp."""
        # Try aiohttp first (faster)
        try:
            html = await self.fetch_page(url)
            if html and len(html) > 5000:
                return html
        except Exception:
            pass

        # Fallback to Browser Use for JS-rendered leaderboard
        try:
            from ..browser_client import BrowserClient
            async with BrowserClient(headless=True, timeout=30) as bc:
                html = await bc.fetch_page(
                    url,
                    wait_for="a[href*='/posts/']",
                    scroll=True,
                )
                return html if html else None
        except Exception as e:
            logger.debug(f"[{self.name}] Browser fetch failed for {url}: {e}")
            return None

    def _extract_post_links(self, html: str) -> list[str]:
        """Extract /posts/ URLs from leaderboard HTML."""
        links = []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            seen = set()
            for a_tag in soup.find_all("a", href=re.compile(r"^/posts/[^/]+$")):
                href = a_tag.get("href", "")
                if href and href not in seen:
                    seen.add(href)
                    links.append(f"{self.base_url}{href}")
        except Exception as e:
            logger.debug(f"[{self.name}] Link extraction failed: {e}")
        return links

    async def _scrape_post_page(self, url: str) -> Optional[ProviderResult]:
        """Scrape details from a single ProductHunt post page."""
        html = None

        # Try aiohttp first
        try:
            html = await self.fetch_page(url)
        except Exception:
            pass

        # Fallback to Browser Use
        if not html or len(html) < 1000:
            try:
                from ..browser_client import BrowserClient
                async with BrowserClient(headless=True, timeout=30) as bc:
                    html = await bc.fetch_page(
                        url,
                        wait_for="h1, [data-test*='post-title']",
                        scroll=True,
                    )
            except Exception as e:
                logger.debug(f"[{self.name}] Browser fallback failed: {e}")

        if not html:
            return None

        return self._parse_post_html(html, url)

    def _parse_post_html(self, html: str, url: str) -> Optional[ProviderResult]:
        """Parse ProductHunt post HTML into a ProviderResult."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            logger.warning(f"[{self.name}] BeautifulSoup parse failed: {e}")
            return None

        # --- Name ---
        name = ""
        h1 = soup.find("h1")
        if h1:
            name = h1.get_text(strip=True)
        if not name:
            og_title = soup.find("meta", {"property": "og:title"})
            if og_title:
                name = og_title.get("content", "").strip()
        if not name:
            title = soup.find("title")
            if title:
                name = title.get_text(strip=True).split("|")[0].strip()
        if not name:
            return None

        # Clean up PH prefixes
        for prefix in ("Product Hunt — ", "Product Hunt - "):
            if name.startswith(prefix):
                name = name[len(prefix):].strip()
        # Remove " | Product Hunt" suffix
        name = re.sub(r'\s*\|\s*Product Hunt.*$', '', name).strip()
        if not name or len(name) < 2:
            return None

        # --- Description ---
        description = ""
        og_desc = soup.find("meta", {"property": "og:description"})
        if og_desc:
            description = og_desc.get("content", "").strip()
        if not description:
            meta_desc = soup.find("meta", {"name": "description"})
            if meta_desc:
                description = meta_desc.get("content", "").strip()

        # --- Website ---
        website = None
        # PH wraps external links in /r/ redirects
        for a_tag in soup.find_all("a", href=re.compile(r"^/r/")):
            href = a_tag.get("href", "")
            if "url=" in href:
                from urllib.parse import unquote, urlparse as _up
                raw = href.split("url=")[-1].split("&")[0]
                decoded = unquote(raw)
                parsed = _up(decoded)
                if parsed.scheme and parsed.netloc:
                    website = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    break
        # Also try direct links to external sites (not PH-internal)
        if not website:
            for a_tag in soup.find_all("a", href=re.compile(r"^https?://")):
                href = a_tag.get("href", "")
                if "producthunt.com" not in href and "pths.si" not in href:
                    website = href
                    break

        domain = self.extract_domain(website) if website else None

        # --- Founders/Makers ---
        founders = []
        for a_tag in soup.find_all("a", href=re.compile(r"^/@[^/]+$")):
            maker_name = a_tag.get_text(strip=True)
            if maker_name and len(maker_name) > 1:
                founders.append({
                    "name": maker_name,
                    "profile_url": f"{self.base_url}{a_tag.get('href', '')}",
                })
        founders = founders[:5]

        # --- Category/Topics ---
        category = None
        topic_links = soup.find_all("a", href=re.compile(r"^/topics/"))
        if topic_links:
            category = topic_links[0].get_text(strip=True)

        # --- Launch date ---
        launch_date = None
        time_el = soup.find("time")
        if time_el:
            dt_str = time_el.get("datetime", "")
            if dt_str:
                try:
                    launch_date = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                except Exception:
                    pass

        # --- Social ---
        social = {}
        for a_tag in soup.find_all("a", href=re.compile(r"(twitter|x)\.com/"), limit=3):
            href = a_tag.get("href", "")
            username = href.rstrip("/").split("/")[-1]
            if username and username not in ("share", "intent", "home"):
                social["twitter"] = href
                break

        # --- External images (avoid PH-internal) ---
        og_image = None
        og_img = soup.find("meta", {"property": "og:image"})
        if og_img:
            content = og_img.get("content", "")
            if content and "producthunt.com" not in content:
                og_image = content

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
            social=social,
            raw_data={"og_image": og_image} if og_image else {},
        )
