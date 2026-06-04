# services/scraper — Startup lead intelligence system
"""Scraper Intelligence System — autonomous startup discovery and lead qualification."""

from .resource_manager import ResourceManager, get_resource_manager
from .service import ScraperService

__all__ = ["ScraperService", "ResourceManager", "get_resource_manager"]
