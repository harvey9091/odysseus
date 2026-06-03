# services/scraper/providers/peerlist — Peerlist provider
"""Scrape Peerlist for newly launched startups."""
import logging
from typing import Callable, Optional
from .base import BaseProvider, ProviderResult

logger = logging.getLogger(__name__)

class PeerlistProvider(BaseProvider):
    name = "peerlist"
    base_url = "https://peerlist.io"
    rate_limit_delay = 2.0

    async def scrape(self, filters: dict, progress_callback: Optional[Callable] = None) -> list[ProviderResult]:
        results = []
        if progress_callback:
            progress_callback({"type": "log", "provider": self.name, "message": "Peerlist scraping not yet implemented"})
        return results
