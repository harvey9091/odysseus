# services/scraper/providers/base — Abstract base provider
"""Base class for all scraper providers."""

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional
from urllib.parse import urlparse

import aiohttp

logger = logging.getLogger(__name__)

# Common user agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


@dataclass
class ProviderResult:
    """Normalized result from a provider scrape."""
    name: str
    website: Optional[str] = None
    description: Optional[str] = None
    domain: Optional[str] = None
    source_provider: str = ""
    source_url: Optional[str] = None
    launch_date: Optional[datetime] = None
    category: Optional[str] = None
    country: Optional[str] = None
    founders: list[dict] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    social: dict = field(default_factory=dict)
    pricing_model: Optional[str] = None
    tech_stack: list[str] = field(default_factory=list)
    raw_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "name": self.name,
            "website": self.website,
            "description": self.description,
            "domain": self.domain,
            "source_provider": self.source_provider,
            "source_url": self.source_url,
            "launch_date": self.launch_date.isoformat() if self.launch_date else None,
            "category": self.category,
            "country": self.country,
            "founders": self.founders,
            "emails": self.emails,
            "social": self.social,
            "pricing_model": self.pricing_model,
            "tech_stack": self.tech_stack,
        }


class BaseProvider(ABC):
    """Abstract base class for scraper providers."""

    name: str = "base"
    base_url: str = ""
    rate_limit_delay: float = 1.0  # seconds between requests
    max_retries: int = 3
    timeout: int = 30

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._request_count = 0

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": "text/html,application/xhtml+xml,application/json",
                    "Accept-Language": "en-US,en;q=0.9",
                }
            )
        return self._session

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def fetch_page(self, url: str, as_json: bool = False) -> str | dict:
        """Fetch a page with retry logic and rate limiting."""
        session = await self._get_session()
        last_error = None

        for attempt in range(self.max_retries):
            try:
                # Rate limiting
                if self._request_count > 0:
                    await asyncio.sleep(self.rate_limit_delay)

                # Rotate user agent
                session.headers["User-Agent"] = random.choice(USER_AGENTS)
                self._request_count += 1

                async with session.get(url) as response:
                    if response.status == 429:  # Rate limited
                        wait_time = int(response.headers.get("Retry-After", 60))
                        logger.warning(f"[{self.name}] Rate limited, waiting {wait_time}s")
                        await asyncio.sleep(wait_time)
                        continue

                    if response.status >= 500:
                        raise aiohttp.ClientResponseError(
                            response.request_info,
                            response.history,
                            status=response.status,
                            message=f"Server error: {response.status}"
                        )

                    response.raise_for_status()

                    if as_json:
                        return await response.json()
                    return await response.text()

            except asyncio.TimeoutError:
                last_error = "Timeout"
                logger.warning(f"[{self.name}] Timeout on attempt {attempt + 1} for {url}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

            except aiohttp.ClientError as e:
                last_error = str(e)
                logger.warning(f"[{self.name}] Client error on attempt {attempt + 1}: {e}")
                await asyncio.sleep(2 ** attempt)

            except Exception as e:
                last_error = str(e)
                logger.error(f"[{self.name}] Unexpected error: {e}")
                raise

        raise Exception(f"[{self.name}] Failed after {self.max_retries} attempts: {last_error}")

    def extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        if not url:
            return None
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www prefix
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return None

    @abstractmethod
    async def scrape(
        self,
        filters: dict,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> list[ProviderResult]:
        """
        Scrape startups from this provider.

        Args:
            filters: Scrape filters (date_range, categories, etc.)
            progress_callback: Optional callback for progress updates

        Returns:
            List of normalized ProviderResult objects
        """
        pass

    def get_info(self) -> dict:
        """Get provider metadata."""
        return {
            "name": self.name,
            "base_url": self.base_url,
            "rate_limit_delay": self.rate_limit_delay,
        }
