# services/scraper/extractors/metadata_extractor — Website metadata extraction
"""Extract metadata like tech stack, pricing model, etc."""

import logging
import re
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Common tech stack indicators
TECH_STACK_PATTERNS = {
    "React": r"react",
    "Next.js": r"next[_-]?js|__next",
    "Vue": r"vue\.js|vuejs",
    "Angular": r"angular",
    "Tailwind": r"tailwindcss",
    "Bootstrap": r"bootstrap",
    "WordPress": r"wp-content|wordpress",
    "Shopify": r"shopify",
    "Stripe": r"stripe",
    "AWS": r"amazonaws|aws",
    "Vercel": r"vercel",
    "Netlify": r"netlify",
}

# Pricing model indicators
PRICING_PATTERNS = {
    "freemium": r"free|freemium|start.*free",
    "subscription": r"subscription|monthly|yearly|per.*month|/mo|/yr",
    "one-time": r"one[- ]?time|lifetime|pay.*once",
    "usage-based": r"pay.*as.*you.*go|usage|per.*request|credits",
    "enterprise": r"enterprise|contact.*sales|custom.*pricing",
}


class MetadataExtractor:
    """Extract website metadata and tech stack."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    async def extract(self, website_url: str) -> dict:
        """
        Extract metadata from a website.

        Returns dict with tech_stack, pricing_model, description, etc.
        """
        metadata = {
            "tech_stack": [],
            "pricing_model": None,
            "description": None,
            "og_image": None,
        }

        if not website_url:
            return metadata

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.get(website_url) as response:
                    if response.status != 200:
                        return metadata
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")

                    # Extract description
                    meta_desc = soup.find("meta", {"name": "description"}) or \
                                soup.find("meta", {"property": "og:description"})
                    if meta_desc:
                        metadata["description"] = meta_desc.get("content", "")

                    # Extract OG image
                    og_image = soup.find("meta", {"property": "og:image"})
                    if og_image:
                        metadata["og_image"] = og_image.get("content", "")

                    # Detect tech stack
                    html_lower = html.lower()
                    for tech, pattern in TECH_STACK_PATTERNS.items():
                        if re.search(pattern, html_lower, re.IGNORECASE):
                            metadata["tech_stack"].append(tech)

                    # Detect pricing model from /pricing page
                    pricing_url = None
                    pricing_links = soup.find_all("a", href=re.compile(r"/pricing|/plans", re.I))
                    if pricing_links:
                        pricing_url = pricing_links[0].get("href", "")
                        if not pricing_url.startswith("http"):
                            from urllib.parse import urljoin
                            pricing_url = urljoin(website_url, pricing_url)

                    if pricing_url:
                        try:
                            async with session.get(pricing_url) as pricing_response:
                                if pricing_response.status == 200:
                                    pricing_html = await pricing_response.text()
                                    pricing_lower = pricing_html.lower()

                                    for model, pattern in PRICING_PATTERNS.items():
                                        if re.search(pattern, pricing_lower, re.IGNORECASE):
                                            metadata["pricing_model"] = model
                                            break
                        except Exception:
                            pass

        except Exception as e:
            logger.warning(f"Metadata extraction failed for {website_url}: {e}")

        return metadata
