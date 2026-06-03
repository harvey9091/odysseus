# services/scraper/validators/lead_validator — Startup lead quality validation
"""Validate leads to filter out articles, blogs, and non-startup pages.
Score domains for quality and startup-likelihood."""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Patterns that indicate a page is an article/blog/news post rather than a
# startup/company/product landing page.
ARTICLE_INDICATORS = re.compile(
        r"(?:/article/|/blog/|/news/|/post/|/posts/|/story/|"
        r"/articles/|/blog-post|/news-post|"
        r"\?utm_source|#comments|/comment|/comments|"
        r"medium\.com/[^/]+/[a-z0-9-]+$|"
        r"substack\.com/p/|"
        r"wordpress\.com|blogspot\.com|"
        r"\.(?:blog|news|article|press|media)[./]|"
        r"(?:read|view)-more|"
        r"(?:archive|category|tag)s?/[a-z0-9-]+/?$)",
        re.IGNORECASE,
    )

# URL path segments that indicate a real product/startup landing page.
LANDING_PAGE_INDICATORS = re.compile(
    r"(?:/pricing|/features|/product|/about|/contact|/demo|"
    r"/signup|/register|/login|/download|/get-started|/tour|"
    r"/docs|/help|/support|/changelog|"
    r"/integrations?|/api|/status|/terms|/privacy|"
    r"/manifest\.json|/robots\.txt|/sitemap\.xml)$",
    re.IGNORECASE,
)

# Top-level domains that are almost always content platforms, not startups.
PLATFORM_DOMAINS = {
    "medium.com", "substack.com", "wordpress.com", "blogger.com",
    "ghost.org", "dev.to", "hashnode.dev", "tumblr.com", "wix.com",
    "wordpress.org", "squarespace.com", "webflow.com", "notion.so",
    "linkedin.com", "twitter.com", "x.com", "facebook.com",
    "instagram.com", "youtube.com", "reddit.com", "hackernews.com",
    "news.ycombinator.com", "github.com", "gitlab.com", "bitbucket.org",
    "quora.com", "stackoverflow.com", "producthunt.com", "betalist.com",
    "alternativeto.net", "indiehackers.com", "devhunt.org", "peerlist.io",
    "uneed.best", "crunchbase.com", "pitchbook.com", "techcrunch.com",
    "theinformation.com", "bloomberg.com", "reuters.com",
    "ycombinator.com", "angel.co", "wellfound.com", "luma.com",
    "cal.com", "calendly.com", "notion.site", "vercel.app",
    "netlify.app", "herokuapp.com", "pages.dev",
}

# TLDs associated with startups/SaaS products.
STARTUP_TLDS = {".io", ".ai", ".co", ".app", ".dev", ".tech", ".so", ".ly", ".to", ".gg", ".xyz"}

# Keywords that strongly indicate a startup/product page when found in HTML.
STARTUP_SIGNALS = re.compile(
    r"(?:get started|free trial|pricing|subscribe|sign up|"
    r"our product|our platform|dashboard|api key|"
    r"founded in|launched|backed by|seed round|series [a-e]|"
    r"our mission|our vision|build better|ship faster|"
    r"integrations?|enterprise|freemium|"
    r"powered by|built with|trusted by|customers|"
    r"features|roadmap|changelog|"
    r"© 20[12][0-9]|© 202[0-9])",
    re.IGNORECASE,
)

# Patterns that indicate a news/blog article page.
ARTICLE_BODY_PATTERNS = re.compile(
    r"(?:by [A-Z][a-z]+ [A-Z][a-z]+|"
    r"published (?:on|at)|updated (?:on|at)|"
    r"reading time|min read|"
    r"follow us on twitter|subscribe to our newsletter|"
    r"related articles|you may also like|read more|"
    r"comments? \(\d+\)|leave a (?:comment|reply)|"
    r"share this (?:article|post)|"
    r"advertisement|sponsored content|"
    r"cookie policy|accept all cookies)",
    re.IGNORECASE,
)


@dataclass
class ValidationResult:
    """Result of lead validation."""
    is_valid: bool = False
    is_startup: bool = False
    is_article: bool = False
    is_platform_page: bool = False
    domain_quality_score: int = 0  # 0-100
    startup_likelihood: int = 0  # 0-100
    rejection_reasons: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


class LeadValidator:
    """Validate and score leads for startup quality."""

    def __init__(self):
        self._domain_cache: dict[str, int] = {}

    def validate(self, lead_data: dict, page_content: str = "") -> ValidationResult:
        """Validate a lead and return quality assessment."""
        result = ValidationResult()

        website = lead_data.get("website", "") or ""
        domain = lead_data.get("domain", "") or self._extract_domain(website)
        name = lead_data.get("name", "")
        description = lead_data.get("description", "") or ""
        source_url = lead_data.get("source_url", "") or ""
        source_provider = lead_data.get("source_provider", "")

        if not domain:
            result.rejection_reasons.append("No domain found")
            return result

        # --- Stage 1: Platform domain check ---
        if domain.lower() in PLATFORM_DOMAINS:
            result.is_platform_page = True
            result.rejection_reasons.append(f"Platform domain: {domain}")
            return result

        # --- Stage 2: Article/blog detection via URL ---
        if website and ARTICLE_INDICATORS.search(website):
            result.is_article = True
            result.rejection_reasons.append("URL matches article/blog pattern")
            # Don't hard-reject yet — some platforms host product pages with
            # article-like paths; check page content before deciding.

        # --- Stage 3: Article detection via page content ---
        combined_text = f"{description} {page_content}".strip()
        if combined_text and ARTICLE_BODY_PATTERNS.search(combined_text):
            # Only reject if the page looks predominantly like an article
            article_matches = len(ARTICLE_BODY_PATTERNS.findall(combined_text))
            startup_matches = len(STARTUP_SIGNALS.findall(combined_text))
            if article_matches >= 2 and article_matches > startup_matches:
                result.is_article = True
                result.rejection_reasons.append("Page content indicates article/blog")
                return result

        # --- Stage 4: Startup signal detection ---
        startup_score = 0

        # Check source provider (some providers are startup-specific)
        if source_provider in ("producthunt", "betalist", "devhunt", "indiehackers",
                                "peerlist", "uneed", "alternativeto"):
            startup_score += 40
        elif source_provider == "hackernews":
            startup_score += 25  # HN has mixed content

        # Check domain TLD
        parsed = urlparse(website or f"https://{domain}")
        path = parsed.path.lower()
        tld = "." + parsed.netloc.split(".")[-1] if parsed.netloc else ""
        if tld in STARTUP_TLDS:
            startup_score += 20

        # Check page content for startup signals
        if combined_text:
            signal_matches = len(STARTUP_SIGNALS.findall(combined_text))
            startup_score += min(signal_matches * 8, 40)

        # Check for pricing/features pages (good sign)
        if LANDING_PAGE_INDICATORS.search(path):
            startup_score += 15

        # Penalize article paths
        if ARTICLE_INDICATORS.search(website or ""):
            startup_score -= 30

        # Name heuristic: short, branded names are more likely startups
        if name:
            words = name.split()
            if 1 <= len(words) <= 4 and not name.lower().startswith(("the ", "a ", "how ", "why ", "what ")):
                startup_score += 10
            # Penalize titles that look like article headlines
            if name.endswith((":", "...", "?")) or name.count(" ") > 8:
                startup_score -= 20

        # Clamp score
        startup_score = max(0, min(100, startup_score))
        result.startup_likelihood = startup_score

        # --- Stage 5: Domain quality scoring ---
        domain_score = self._score_domain(domain, website)
        result.domain_quality_score = domain_score

        # --- Final verdict ---
        if startup_score >= 45 and domain_score >= 30:
            result.is_valid = True
            result.is_startup = True
        elif startup_score >= 55:
            # High startup likelihood can compensate for lower domain score
            result.is_valid = True
            result.is_startup = True
            result.warnings.append("Lower domain quality but strong startup signals")
        elif startup_score >= 35 and domain_score >= 60:
            # Strong domain but moderate startup signals
            result.is_valid = True
            result.is_startup = True
            result.warnings.append("Moderate startup signals but high domain quality")
        else:
            if startup_score < 35:
                result.rejection_reasons.append(f"Low startup likelihood: {startup_score}")
            if domain_score < 30 and startup_score < 55:
                result.rejection_reasons.append(f"Low domain quality: {domain_score}")

        return result

    def _score_domain(self, domain: str, website: str) -> int:
        """Score a domain for quality (0-100). Cached for deduplication."""
        if domain in self._domain_cache:
            return self._domain_cache[domain]

        score = 50  # Base score

        # Penalize very short or very long domains
        name_part = domain.split(".")[0]
        if len(name_part) < 3:
            score -= 20
        elif len(name_part) > 30:
            score -= 10

        # Penalize generic/suspicious domains
        suspicious = re.compile(
            r"(?:top-|best-|free-|cheap-|review-|reviews-|"
            r"\d{3,}|-ng-|-llc-|-inc-|"
            r"\.(?:tk|ml|ga|cf|gq|buzz|download))$",
            re.IGNORECASE,
        )
        if suspicious.search(domain):
            score -= 25

        # Bonus for HTTPS
        if website.startswith("https://"):
            score += 10

        # Penalize known low-quality TLDs
        low_quality_tlds = {".tk", ".ml", ".ga", ".cf", ".gq", ".buzz", ".download", ".link"}
        tld = "." + domain.split(".")[-1] if "." in domain else ""
        if tld in low_quality_tlds:
            score -= 30

        # Bonus for common startup TLDs
        if tld in STARTUP_TLDS:
            score += 10

        # Penalize excessive subdomains (suggests shared hosting)
        if domain.count(".") > 3:
            score -= 10

        score = max(0, min(100, score))
        self._domain_cache[domain] = score
        return score

    def _extract_domain(self, url: str) -> str:
        """Extract clean domain from URL."""
        if not url:
            return ""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return ""

    def clear_cache(self):
        """Clear domain score cache."""
        self._domain_cache.clear()
