# services/scraper/providers/hackernews — Hacker News provider
"""Scrape Hacker News for Show HN and launch posts.
Fetches top, new, and best stories with improved startup filtering."""

import logging
import re
from datetime import datetime, timedelta
from typing import Callable, Optional

from .base import BaseProvider, ProviderResult

logger = logging.getLogger(__name__)


class HackerNewsProvider(BaseProvider):
    """Scrape Hacker News for Show HN and startup launches."""

    name = "hackernews"
    base_url = "https://hacker-news.firebaseio.com/v0"
    rate_limit_delay = 0.1

    # HN feeds to scrape (ordered by startup density)
    FEEDS = [
        ("topstories", "top"),
        ("newstories", "new"),
        ("beststories", "best"),
        ("askstories", "ask"),
        ("showstories", "show"),
    ]

    async def scrape(
        self,
        filters: dict,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> list[ProviderResult]:
        results = []

        days_back = filters.get("days_back", 7)
        date_after = datetime.utcnow() - timedelta(days=days_back)
        min_score = filters.get("min_score", 5)
        max_stories = filters.get("max_stories", 300)

        if progress_callback:
            progress_callback({
                "type": "log",
                "provider": self.name,
                "message": f"Scraping HN feeds (last {days_back} days, min score {min_score})...",
            })

        seen_ids: set[int] = set()
        seen_domains: set[str] = set()

        for feed_name, feed_label in self.FEEDS:
            if len(results) >= max_stories:
                break

            try:
                story_ids = await self._fetch_feed(feed_name)
                if not story_ids:
                    continue

                # Take a slice to keep it bounded
                batch = story_ids[:150]
                if progress_callback:
                    progress_callback({
                        "type": "log",
                        "provider": self.name,
                        "message": f"[{feed_label}] Checking {len(batch)} stories...",
                    })

                feed_count = 0
                for story_id in batch:
                    if story_id in seen_ids:
                        continue
                    seen_ids.add(story_id)

                    story = await self._fetch_story(story_id)
                    if not story:
                        continue

                    # Score filter
                    score = story.get("score", 0)
                    if score < min_score:
                        continue

                    # Date filter
                    post_time = datetime.fromtimestamp(story.get("time", 0))
                    if post_time < date_after:
                        continue

                    title = story.get("title", "")

                    # Classify the post
                    classification = self._classify_post(title, story)

                    if classification == "skip":
                        continue

                    url = story.get("url", "")

                    # For Show HN posts, the HN discussion IS the page;
                    # try to find an actual external URL from the text
                    if not url and classification == "show_hn":
                        url = self._extract_url_from_text(story)

                    if not url:
                        continue

                    domain = self.extract_domain(url)
                    if not domain:
                        continue

                    # Skip if we already have this domain (dedup within run)
                    if domain in seen_domains:
                        continue

                    # Skip known content/platform domains
                    if self._is_platform_domain(domain):
                        continue

                    # Extra filter: verify the URL doesn't look like an article
                    if self._looks_like_article_url(url):
                        continue

                    seen_domains.add(domain)

                    # Clean up the name
                    clean_name = self._clean_name(title)

                    results.append(ProviderResult(
                        name=clean_name,
                        website=url,
                        description=title,
                        domain=domain,
                        source_provider=self.name,
                        source_url=f"https://news.ycombinator.com/item?id={story_id}",
                        launch_date=post_time,
                        founders=[{"name": story.get("by", ""), "source": "hn_username"}] if story.get("by") else [],
                        raw_data={
                            "hn_score": score,
                            "hn_comments": story.get("descendants", 0),
                            "hn_id": story_id,
                            "hn_feed": feed_label,
                            "hn_classification": classification,
                        },
                    ))
                    feed_count += 1

                if progress_callback:
                    progress_callback({
                        "type": "log",
                        "provider": self.name,
                        "message": f"[{feed_label}] {feed_count} leads from this feed",
                    })

            except Exception as e:
                logger.error(f"[{self.name}] Feed {feed_name} failed: {e}")
                if progress_callback:
                    progress_callback({
                        "type": "error",
                        "provider": self.name,
                        "message": f"[{feed_label}] Error: {e}",
                    })
                continue

        if progress_callback:
            progress_callback({
                "type": "log",
                "provider": self.name,
                "message": f"Hacker News: {len(results)} total leads collected",
            })

        return results

    async def _fetch_feed(self, feed_name: str) -> list:
        """Fetch story IDs for a feed."""
        try:
            data = await self.fetch_page(f"{self.base_url}/{feed_name}.json", as_json=True)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    async def _fetch_story(self, story_id: int) -> Optional[dict]:
        """Fetch a single story from HN API."""
        try:
            return await self.fetch_page(f"{self.base_url}/item/{story_id}.json", as_json=True)
        except Exception:
            return None

    # URL paths that indicate the page is an article/blog/news
    ARTICLE_PATH_RE = re.compile(
        r"(?:/article/|/blog/|/news/|/post/|/posts/|"
        r"/stories?/|/archive/|/category/|/tag/|"
        r"\?p=|/page/\d+/?$|"
        r"medium\.com/|substack\.com/|"
        r"\.(?:blog|news|press|media)[./])",
        re.IGNORECASE,
    )

    # Domains that are primarily content platforms, not startups
    PLATFORM_DOMAIN_RE = re.compile(
        r"(?:medium\.com|substack\.com|blogspot\.com|wordpress\.com|"
        r"dev\.to|hashnode\.dev|tumblr\.com|ghost\.org|"
        r"youtube\.com|youtu\.be|vimeo\.com|"
        r"twitter\.com|x\.com|linkedin\.com|reddit\.com|"
        r"github\.com|gitlab\.com|bitbucket\.org|"
        r"stackoverflow\.com|quora\.com|"
        r"techcrunch\.com|theinformation\.com|bloomberg\.com|reuters\.com|"
        r"news\.ycombinator\.com|producthunt\.com|betalist\.com|"
        r"alternativeto\.net|indiehackers\.com|devhunt\.org|"
        r"peerlist\.io|uneed\.best|crunchbase\.com|pitchbook\.com|"
        r"angellist\.com|wellfound\.com|luma\.com)",
        re.IGNORECASE,
    )

    STARTUP_KEYWORDS = [
        "show hn:", "launch hn:", "launching", "launched", "introducing",
        "announcing", "new startup", "side project", "open source",
        "built", "created", "we built", "i built", "just released",
        "now available", "beta", "early access", "join waitlist",
        "launch", "debut", "debuts", "debuting",
    ]

    ARTICLE_KEYWORDS = [
        "how we ", "why we ", "how i ", "why i ",
        "lessons learned", "what i learned", "what we learned",
        "my journey", "our journey", "behind the scenes",
        "deep dive", "analysis of", "review of",
        "case study", "report:", "survey:",
        "monthly report", "weekly report", "year in review",
        "state of ", "trends in ", "the future of ",
        "opinion:", "op-ed", "editorial",
    ]

    def _classify_post(self, title: str, story: dict) -> str:
        """Classify a HN post. Returns: 'show_hn', 'startup', 'article', 'discussion', 'skip'."""
        title_lower = title.lower().strip()

        # Show HN — strong startup signal
        if title_lower.startswith("show hn:"):
            return "show_hn"

        # Launch HN
        if title_lower.startswith("launch hn:"):
            return "show_hn"

        # Ask HN — usually not a startup launch
        if title_lower.startswith("ask hn:") or title_lower.startswith("ask yc:"):
            return "discussion"

        # Detect article-like titles
        for kw in self.ARTICLE_KEYWORDS:
            if title_lower.startswith(kw) or f" {kw}" in title_lower:
                return "article"

        # Detect startup signals
        for kw in self.STARTUP_KEYWORDS:
            if kw in title_lower:
                return "startup"

        # If no URL, it's an internal HN discussion
        if not story.get("url"):
            return "discussion"

        # If it has a URL and no strong signals, check comment count
        # High comments + low score = discussion, not launch
        score = story.get("score", 0)
        comments = story.get("descendants", 0)
        if comments > score * 5 and score < 20:
            return "discussion"

        # Default: if it has an external URL, treat as potential startup
        return "startup"

    def _extract_url_from_text(self, story: dict) -> str:
        """Try to find a URL in the HN item text."""
        text = story.get("text", "") or ""
        # Look for HN-escaped URLs
        match = re.search(r'href="(https?://[^"]+)"', text)
        if match:
            return match.group(1)
        # Look for raw URLs
        match = re.search(r'https?://[^\s<"]+\.[a-z]{2,}', text)
        if match:
            return match.group(0)
        return ""

    def _is_platform_domain(self, domain: str) -> bool:
        """Check if domain is a content/platform site."""
        return bool(self.PLATFORM_DOMAIN_RE.search(domain))

    def _looks_like_article_url(self, url: str) -> bool:
        """Check if URL path looks like an article/blog post."""
        return bool(self.ARTICLE_PATH_RE.search(url))

    def _clean_name(self, title: str) -> str:
        """Clean up a HN title into a product/company name."""
        name = title
        for prefix in ("Show HN: ", "Launch HN: ", "Launch HN – ", "Show HN – "):
            if name.startswith(prefix):
                name = name[len(prefix):]
                break
        # Truncate overly long titles
        if len(name) > 80:
            name = name[:77] + "..."
        return name.strip()
