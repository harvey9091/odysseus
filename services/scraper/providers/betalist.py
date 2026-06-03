# services/scraper/providers/betalist — BetaList provider
"""Scrape BetaList for startup launches."""
import logging
from typing import Callable, Optional
from .base import BaseProvider, ProviderResult

logger = logging.getLogger(__name__)

class BetaListProvider(BaseProvider):
    name = "betalist"
    base_url = "https://betalist.com"
    rate_limit_delay = 2.0

    async def scrape(self, filters: dict, progress_callback: Optional[Callable] = None) -> list[ProviderResult]:
        results = []
        if progress_callback:
            progress_callback({"type": "log", "provider": self.name, "message": "BetaList scraping not yet implemented"})
        return results
