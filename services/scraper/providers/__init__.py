# services/scraper/providers — Modular data source adapters
"""Provider adapters for scraping startup launch platforms."""

from .base import BaseProvider, ProviderResult
from .producthunt import ProductHuntProvider
from .hackernews import HackerNewsProvider
from .peerlist import PeerlistProvider
from .devhunt import DevHuntProvider
from .indiehackers import IndieHackersProvider
from .betalist import BetaListProvider
from .uneed import UneedProvider
from .alternativeto import AlternativeToProvider

# Registry of all available providers
PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {
    "producthunt": ProductHuntProvider,
    "hackernews": HackerNewsProvider,
    "peerlist": PeerlistProvider,
    "devhunt": DevHuntProvider,
    "indiehackers": IndieHackersProvider,
    "betalist": BetaListProvider,
    "uneed": UneedProvider,
    "alternativeto": AlternativeToProvider,
}


def get_provider(name: str) -> BaseProvider | None:
    """Get a provider instance by name."""
    cls = PROVIDER_REGISTRY.get(name.lower())
    return cls() if cls else None


def get_all_providers() -> list[BaseProvider]:
    """Get instances of all registered providers."""
    return [cls() for cls in PROVIDER_REGISTRY.values()]


__all__ = [
    "BaseProvider",
    "ProviderResult",
    "PROVIDER_REGISTRY",
    "get_provider",
    "get_all_providers",
]
