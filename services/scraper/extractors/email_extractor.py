# services/scraper/extractors/email_extractor — Email extraction
"""Extract email addresses from websites."""

import logging
import re
from typing import Optional
from urllib.parse import urljoin

import aiohttp

logger = logging.getLogger(__name__)

# Email regex pattern
EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)

# Common email patterns to prioritize
PRIORITY_EMAILS = [
    r'founder@', r'ceo@', r'hello@', r'contact@', r'info@',
    r'support@', r'team@', r'hi@', r'mail@'
]

# Emails to exclude (generic/system)
EXCLUDE_EMAILS = [
    r'@example\.com$', r'@test\.com$', r'noreply@', r'no-reply@',
    r'@sentry\.io$', r'@wixpress\.com$', r'sentry@'
]


class EmailExtractor:
    """Extract email addresses from websites."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    async def extract(self, website_url: str) -> list[dict]:
        """
        Extract emails from a website.

        Returns list of {"email": "...", "source": "...", "priority": int}
        """
        emails = []
        seen = set()

        if not website_url:
            return emails

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                # Scrape main page
                main_emails = await self._scrape_page(session, website_url, "homepage")
                for e in main_emails:
                    if e["email"] not in seen:
                        seen.add(e["email"])
                        emails.append(e)

                # Try common contact pages
                contact_urls = [
                    urljoin(website_url, "/contact"),
                    urljoin(website_url, "/about"),
                    urljoin(website_url, "/team"),
                    urljoin(website_url, "/contact-us"),
                ]

                for contact_url in contact_urls:
                    try:
                        page_emails = await self._scrape_page(session, contact_url, contact_url.split("/")[-1])
                        for e in page_emails:
                            if e["email"] not in seen:
                                seen.add(e["email"])
                                emails.append(e)
                    except Exception:
                        continue

        except Exception as e:
            logger.warning(f"Email extraction failed for {website_url}: {e}")

        # Sort by priority (lower is better)
        emails.sort(key=lambda x: x.get("priority", 99))
        return emails

    async def _scrape_page(self, session: aiohttp.ClientSession, url: str, source: str) -> list[dict]:
        """Scrape emails from a single page."""
        emails = []
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return emails
                html = await response.text()

                # Find all email matches
                matches = EMAIL_PATTERN.findall(html)
                for email in matches:
                    email_lower = email.lower()

                    # Skip excluded patterns
                    if any(re.search(pat, email_lower) for pat in EXCLUDE_EMAILS):
                        continue

                    # Determine priority
                    priority = 50  # default
                    for i, pat in enumerate(PRIORITY_EMAILS):
                        if re.search(pat, email_lower):
                            priority = i + 1
                            break

                    emails.append({
                        "email": email_lower,
                        "source": source,
                        "priority": priority
                    })

        except Exception:
            pass
        return emails
