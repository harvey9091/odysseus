# services/scraper/providers/uneed — Uneed provider
"""Scrape Uneed for newly launched products."""
import logging
from typing import Callable, Optional
from .base import BaseProvider, ProviderResult

logger = logging.getLogger(__name__)

class UneedProvider(BaseProvider):
    name = "uneed"
    base_url = "https://www.uneed.best"
    rate_limit_delay = 1.5

    async def scrape(self, filters: dict, progress_callback: Optional[Callable] = None) -> list[ProviderResult]:
        results = []
        if progress_callback:
            progress_callback({"type": "log", "provider": self.name, "message": "Uneed scraping not yet implemented"})
        return results
