# services/scraper/providers/alternativeto — AlternativeTo provider
"""Scrape AlternativeTo for newly launched software."""
import logging
from typing import Callable, Optional
from .base import BaseProvider, ProviderResult

logger = logging.getLogger(__name__)

class AlternativeToProvider(BaseProvider):
    name = "alternativeto"
    base_url = "https://alternativeto.net"
    rate_limit_delay = 2.0

    async def scrape(self, filters: dict, progress_callback: Optional[Callable] = None) -> list[ProviderResult]:
        results = []
        if progress_callback:
            progress_callback({"type": "log", "provider": self.name, "message": "AlternativeTo scraping not yet implemented"})
        return results
