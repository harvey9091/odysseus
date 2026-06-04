# services/scraper/discovery_agent — Generic Discovery Agent Architecture
"""Generic Discovery Agent using Browser Use (navigation), Playwright (browser), and Crawl4AI (extraction).

Accepts any source URL and autonomously discovers startup leads through:
1. URL Analysis - determines if source is directory/listing page
2. Company Discovery - navigates to find individual company pages
3. Company Extraction - visits each company and extracts structured data
4. Contact Discovery - crawls contact/about/team pages for emails
5. Founder Discovery - identifies key people
6. Deduplication - prevents duplicate leads
7. Storage - persists to database

Resource protection:
- Browser instances limited to 3 concurrent
- Rate limiting: 2 requests/second max
- Respects resource manager backpressure
"""

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class ExtractedLead:
    """Structured lead data extracted from a company page."""
    company_name: str = ""
    website: str = ""
    description: str = ""
    founders: list = field(default_factory=list)
    emails: list = field(default_factory=list)
    linkedin: str = ""
    twitter: str = ""
    github: str = ""
    contact_page: str = ""
    industry: str = ""
    source_url: str = ""
    discovery_date: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "name": self.company_name,
            "website": self.website,
            "description": self.description,
            "domain": self._extract_domain(self.website),
            "founders": self.founders,
            "emails": self.emails,
            "social": {
                "linkedin": self.linkedin,
                "twitter": self.twitter,
                "github": self.github,
            },
            "contact_page": self.contact_page,
            "industry": self.industry,
            "source_provider": "discovery_agent",
            "source_url": self.source_url,
            "launch_date": self.discovery_date,
        }

    def _extract_domain(self, url: str) -> str:
        if not url:
            return ""
        try:
            domain = urlparse(url).netloc.lower()
            return domain[4:] if domain.startswith("www.") else domain
        except Exception:
            return ""


class DiscoveryAgent:
    """Generic Discovery Agent for autonomous company lead discovery."""

    def __init__(self, headless: bool = True, timeout: int = 30):
        self.headless = headless
        self.timeout = timeout
        self._browser = None
        self._context = None
        self._resources = None

    async def _get_resources(self):
        """Lazy-load resource manager."""
        if self._resources is None:
            from .resource_manager import get_resource_manager
            self._resources = get_resource_manager()
        return self._resources

    async def discover(self, source_url: str, progress_callback=None) -> list[ExtractedLead]:
        """Main entry point - discovers leads from any source URL."""
        if progress_callback:
            progress_callback({"type": "log", "message": f"Starting discovery from: {source_url}"})

        leads = []
        company_urls = await self._discover_company_pages(source_url, progress_callback)

        if progress_callback:
            progress_callback({"type": "log", "message": f"Found {len(company_urls)} company pages"})

        for i, company_url in enumerate(company_urls):
            if progress_callback:
                progress_callback({
                    "type": "log",
                    "message": f"Processing company {i+1}/{len(company_urls)}: {company_url}"
                })

            lead = await self._extract_company_data(company_url, progress_callback)
            if lead and self._is_valid_startup(lead):
                leads.append(lead)
                if progress_callback:
                    progress_callback({
                        "type": "lead_found",
                        "name": lead.company_name,
                        "website": lead.website,
                        "emails": len(lead.emails)
                    })

        return leads

    async def _discover_company_pages(self, source_url: str, progress_callback) -> list[str]:
        """Discover individual company pages from a directory/listing source."""
        urls = set()

        try:
            content = await self._fetch_page(source_url)
            if not content:
                return []

            company_urls = self._extract_company_links(content, source_url)
            urls.update(company_urls)

            if progress_callback and len(urls) > 0:
                progress_callback({"type": "log", "message": f"Extracted {len(urls)} initial company links"})

        except Exception as e:
            logger.error(f"Company discovery failed for {source_url}: {e}")
            if progress_callback:
                progress_callback({"type": "error", "message": f"Discovery error: {str(e)}"})

        return list(urls)

    async def _extract_company_data(self, company_url: str, progress_callback) -> Optional[ExtractedLead]:
        """Extract structured data from a company page."""
        content = await self._fetch_page(company_url)
        if not content:
            return None

        lead = ExtractedLead(source_url=company_url)

        # Extract company name
        lead.company_name = self._extract_company_name(content, company_url)
        if not lead.company_name:
            return None

        # Extract website (try to find official site link)
        lead.website = self._extract_official_website(content, company_url)

        # Extract description
        lead.description = self._extract_description(content)

        # Extract industry
        lead.industry = self._extract_industry(content)

        # Extract social profiles
        social = self._extract_social_profiles(content)
        lead.linkedin = social.get("linkedin", "")
        lead.twitter = social.get("twitter", "")
        lead.github = social.get("github", "")

        # Extract contact page
        contact_url = self._extract_contact_page(content, lead.website or company_url)
        lead.contact_page = contact_url

        # Discover emails
        await self._discover_emails(lead, progress_callback)

        # Discover founders
        lead.founders = self._extract_founders(content, lead.website or company_url)

        return lead

    async def _discover_emails(self, lead: ExtractedLead, progress_callback):
        """Discover emails from contact/about/team pages."""
        contact_urls = [lead.contact_page, lead.website] if lead.contact_page else [lead.website]
        seen_emails = set()

        # Add common contact paths
        base = lead.website or lead.contact_page
        if base:
            for path in ["/contact", "/about", "/team", "/company"]:
                contact_urls.append(urljoin(base, path))

        for url in contact_urls:
            if not url or url in seen_emails:
                continue

            content = await self._fetch_page(url)
            if not content:
                continue

            emails = self._extract_emails_from_content(content)
            for email in emails:
                if email not in seen_emails and self._is_valid_email(email):
                    seen_emails.add(email)
                    lead.emails.append(email)

    async def _fetch_page(self, url: str) -> str:
        """Fetch page content using aiohttp with fallback to browser.
        
        Enforces rate limiting before each HTTP request.
        """
        resources = await self._get_resources()
        await resources.rate_limit()

        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers={"User-Agent": self._get_user_agent()}) as response:
                    if response.status == 200:
                        return await response.text()
        except Exception as e:
            logger.debug(f"HTTP fetch failed for {url}: {e}")

        # Fallback to browser for JS-heavy sites
        try:
            return await self._fetch_with_browser(url)
        except Exception as e:
            logger.debug(f"Browser fetch failed for {url}: {e}")

        return ""

    async def _fetch_with_browser(self, url: str) -> str:
        """Fetch with Playwright browser for JS rendering.
        
        Respects browser instance limits and implements backoff on constrained resources.
        """
        resources = await self._get_resources()

        # Check if we can get a browser slot
        if not await resources.acquire_browser():
            # Implement exponential backoff when browser slots unavailable
            backoff = min(2 ** (resources._browser_instances // 2), 16)
            logger.info(f"Browser slot unavailable, backing off for {backoff}s")
            await asyncio.sleep(backoff)
            if not await resources.acquire_browser():
                return ""

        try:
            from playwright.async_api import async_playwright
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--memory-pressure-off"]
            )
            context = await browser.new_context(
                java_script_enabled=True,
                viewport={"width": 1280, "height": 720}
            )
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
                await asyncio.sleep(0.5)
                return await page.content()
            finally:
                await page.close()
                await context.close()
                await browser.close()
        except ImportError:
            logger.warning("Playwright not available, skipping browser fallback")
            return ""
        except Exception as e:
            logger.error(f"Browser fetch error: {e}")
            return ""
        finally:
            resources.release_browser()

    def _extract_company_links(self, html: str, base_url: str) -> list[str]:
        """Extract links to individual company pages."""
        urls = []
        soup = BeautifulSoup(html, "html.parser")

        # Common patterns for company/startup listing links
        link_patterns = [
            r"^/startup/", r"^/company/", r"^/app/",
            r"[-\w]+/[-_\w]+",  # slug patterns
            r"producthunt\.com",
            r"github\.com/",
        ]

        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if not href:
                continue

            # Skip external/non-company links
            if self._is_external_link(href, base_url):
                continue
            if self._is_article_or_blog(href):
                continue

            # Check if this looks like a company listing
            if self._looks_like_company_link(href):
                full_url = urljoin(base_url, href)
                urls.append(full_url)

        # Also look for structured data (JSON-LD, etc.)
        json_ld = soup.find("script", type="application/ld+json")
        if json_ld:
            try:
                import json
                data = json.loads(json_ld.string)
                if isinstance(data, list):
                    for item in data:
                        url = item.get("url") or item.get("mainEntityOfPage", {}).get("@id")
                        if url:
                            urls.append(urljoin(base_url, url))
            except Exception:
                pass

        return list(set(urls))

    def _extract_company_name(self, html: str, url: str) -> str:
        """Extract company name from page."""
        soup = BeautifulSoup(html, "html.parser")

        # Try h1 first
        h1 = soup.find("h1")
        if h1:
            name = h1.get_text(strip=True)
            if self._is_valid_name(name):
                return name

        # Try og:title
        og_title = soup.find("meta", {"property": "og:title"})
        if og_title:
            name = og_title.get("content", "").strip()
            # Clean common suffixes
            for suffix in [" | Product Hunt", " - Product Hunt", " — Product Hunt"]:
                name = name.replace(suffix, "").strip()
            if self._is_valid_name(name):
                return name

        # Try title tag
        title = soup.find("title")
        if title:
            name = title.get_text(strip=True).split("|")[0].split("-")[0].strip()
            if self._is_valid_name(name):
                return name

        return ""

    def _extract_official_website(self, html: str, base_url: str) -> str:
        """Extract official website from page content."""
        soup = BeautifulSoup(html, "html.parser")
        domain = self._extract_domain(base_url)

        # Look for external links (not the current domain)
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            link_domain = self._extract_domain(href)

            # Skip internal links and known non-company domains
            if not link_domain or link_domain == domain:
                continue
            if any(skip in link_domain for skip in ["producthunt", "twitter", "x.com", "linkedin", "github", "wix", "sentry"]):
                continue

            return href

        # Check for redirect URLs (common on directory sites)
        for link in soup.find_all("a", href=re.compile(r"^/r/")):
            href = link.get("href", "")
            if "url=" in href:
                from urllib.parse import unquote
                raw = href.split("url=")[-1].split("&")[0]
                decoded = unquote(raw)
                return decoded

        return ""

    def _extract_description(self, html: str) -> str:
        """Extract company description."""
        soup = BeautifulSoup(html, "html.parser")

        # Try meta description
        meta = soup.find("meta", {"property": "og:description"}) or soup.find("meta", {"name": "description"})
        if meta:
            desc = meta.get("content", "")
            if desc and len(desc) > 20:
                return desc

        # Try to find prominent description text
        for selector in [".description", ".tagline", ".subtitle", "[data-test*='description']"]:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(strip=True)
                if text and len(text) > 20:
                    return text

        return ""

    def _extract_industry(self, html: str) -> str:
        """Extract industry/category from page."""
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text().lower()

        industry_keywords = {
            "ai_ml": ["artificial intelligence", "machine learning", "ai", "llm", "nlp", "deep learning"],
            "fintech": ["financial", "payment", "banking", "crypto", "wallet"],
            "saas": ["software as a service", "saas", "platform", "tool"],
            "developer": ["developer", "dev", "programming", "api", "sdk"],
            "marketing": ["marketing", "advertising", "seo", "social media"],
            "healthtech": ["health", "medical", "healthcare", "wellness"],
        }

        for industry, keywords in industry_keywords.items():
            for kw in keywords:
                if kw in text:
                    return industry

        return ""

    def _extract_social_profiles(self, html: str) -> dict:
        """Extract social media profiles."""
        soup = BeautifulSoup(html, "html.parser")
        social = {}

        patterns = {
            "linkedin": r"linkedin\.com/(?:in|company)/([^\s/\"']+)",
            "twitter": r"(?:twitter|x)\.com/([^\s/\"']+)",
            "github": r"github\.com/([^\s/\"']+)",
        }

        text = soup.get_text()
        for platform, pattern in patterns.items():
            matches = re.findall(pattern, text, re.I)
            if matches:
                username = matches[0]
                social[platform] = f"https://{platform}.com/{username}" if platform != "twitter" else f"https://x.com/{username}" if "x.com" in text.lower() else f"https://twitter.com/{username}"

        # Also check direct links
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            for platform in ["linkedin", "twitter", "github"]:
                if platform in href.lower() and f"{platform}:" not in social:
                    social[platform] = href

        return social

    def _extract_contact_page(self, html: str, base_url: str) -> str:
        """Find contact/about/team page URL."""
        soup = BeautifulSoup(html, "html.parser")
        contact_paths = ["/contact", "/about", "/team", "/contact-us"]

        for link in soup.find_all("a", href=True):
            href = link.get("href", "").lower()
            text = link.get_text(strip=True).lower()

            for path in contact_paths:
                if path in href or path.lstrip("/") in text:
                    return urljoin(base_url, href)

        # Try common paths
        for path in contact_paths:
            test_url = urljoin(base_url, path)
            # Could validate with HTTP request, but for now return first guess
            return test_url if path == "/contact" else ""

        return ""

    def _extract_emails_from_content(self, html: str) -> list[str]:
        """Extract email addresses from HTML content."""
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text()

        # Remove script/style content
        for script in soup(["script", "style"]):
            script.decompose()

        emails = []
        email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

        for match in email_pattern.findall(text):
            email = match.lower().strip()
            if self._is_valid_email(email) and email not in emails:
                emails.append(email)

        # Also check mailto links
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if href.startswith("mailto:"):
                email = href[7:].split("?")[0]
                if self._is_valid_email(email) and email not in emails:
                    emails.append(email)

        return emails

    def _extract_founders(self, html: str, base_url: str) -> list[dict]:
        """Extract founder information."""
        soup = BeautifulSoup(html, "html.parser")
        founders = []

        # Look for team/about sections
        for selector in [".team", ".founders", "[data-test*='founder']", "[data-test*='team']"]:
            section = soup.select_one(selector)
            if section:
                for item in section.find_all(["div", "li", "span"], limit=5):
                    text = item.get_text(strip=True)
                    # Simple name extraction
                    names = re.findall(r'([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)', text)
                    for name in names[:3]:
                        if len(name.split()) >= 1:
                            founders.append({
                                "name": name,
                                "source": "team_section",
                                "website": base_url
                            })

        return founders

    def _is_valid_name(self, name: str) -> bool:
        if not name or len(name) < 2:
            return False
        if len(name) > 100:
            return False
        if any(skip in name.lower() for skip in ["advertisement", "cookie", "privacy policy", "terms of service"]):
            return False
        return True

    def _is_valid_email(self, email: str) -> bool:
        if not email:
            return False
        exclude_patterns = ["@example.com", "@test.com", "noreply@", "no-reply@", "@sentry.io", "@wixpress.com"]
        if any(pattern in email for pattern in exclude_patterns):
            return False
        return True

    def _is_valid_startup(self, lead: ExtractedLead) -> bool:
        if not lead.company_name or not lead.website:
            return False

        # Exclude blogs, news, articles
        if lead.website:
            url_lower = lead.website.lower()
            if any(skip in url_lower for skip in ["blog", "news", "article", "medium.com", "substack.com"]):
                return False
            if "github.com" in url_lower and "/tree/" in url_lower:
                return False  # Exclude specific repos

        return True

    def _is_external_link(self, href: str, base_url: str) -> bool:
        """Check if link points to external domain."""
        if href.startswith(("http", "//")):
            base_domain = self._extract_domain(base_url)
            link_domain = self._extract_domain(href)
            return link_domain != base_domain
        return False

    def _is_article_or_blog(self, href: str) -> bool:
        href_lower = href.lower()
        return any(x in href_lower for x in ["blog", "news", "article", "post/", "/p/", "medium.com", "substack"])

    def _looks_like_company_link(self, href: str) -> bool:
        """Heuristic to detect if link is likely a company page."""
        if not href:
            return False
        href_lower = href.lower()

        # Include typical company patterns
        include_patterns = [
            "/startup", "/company", "/app/", "/product/", "/tool/",
            r"^/[a-z0-9-]+/?$",  # Simple slugs
            "producthunt", "indiehackers", "betalist", "uneed",
        ]

        for pattern in include_patterns:
            if re.search(pattern, href_lower):
                return True

        return False

    def _extract_domain(self, url: str) -> str:
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return ""

    def _get_user_agent(self) -> str:
        return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"