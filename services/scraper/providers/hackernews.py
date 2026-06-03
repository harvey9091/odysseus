# services/scraper/providers/hackernews — Hacker News provider
"""Scrape Show HN and launch posts from Hacker News API."""

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
    rate_limit_delay = 0.1  # HN API is generous

    async def scrape(
        self,
        filters: dict,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> list[ProviderResult]:
        """Scrape recent Show HN posts from Hacker News."""
        results = []

        days_back = filters.get("days_back", 7)
        date_after = datetime.utcnow() - timedelta(days=days_back)
        min_score = filters.get("min_score", 10)

        if progress_callback:
            progress_callback({"type": "log", "provider": self.name, "message": f"Scraping Hacker News Show HN posts from last {days_back} days..."})

        try:
            # Get top stories
            top_ids = await self.fetch_page(f"{self.base_url}/topstories.json", as_json=True)

            # Limit to first 100 stories for efficiency
            story_ids = top_ids[:100] if top_ids else []

            for i, story_id in enumerate(story_ids):
                if progress_callback and i % 10 == 0:
                    progress_callback({"type": "progress", "provider": self.name, "current": i, "total": len(story_ids)})

                story = await self._fetch_story(story_id)
                if not story:
                    continue

                # Check if it's a Show HN or launch post
                title = story.get("title", "")
                if not self._is_startup_post(title):
                    continue

                # Check date
                post_time = datetime.fromtimestamp(story.get("time", 0))
                if post_time < date_after:
                    continue

                # Check minimum score
                score = story.get("score", 0)
                if score < min_score:
                    continue

                # Extract website URL
                url = story.get("url", "")
                if not url:
                    continue

                domain = self.extract_domain(url)

                if progress_callback:
                    progress_callback({"type": "lead_found", "provider": self.name, "name": title, "score": score})

                results.append(ProviderResult(
                    name=title.replace("Show HN: ", "").replace("Launch HN: ", ""),
                    website=url,
                    description=title,
                    domain=domain,
                    source_provider=self.name,
                    source_url=f"https://news.ycombinator.com/item?id={story_id}",
                    launch_date=post_time,
                    founders=[{"name": story.get("by", "")}] if story.get("by") else [],
                    raw_data={
                        "hn_score": score,
                        "hn_comments": story.get("descendants", 0),
                        "hn_id": story_id,
                    }
                ))

            if progress_callback:
                progress_callback({"type": "log", "provider": self.name, "message": f"Hacker News: Found {len(results)} startup posts"})

        except Exception as e:
            logger.error(f"[{self.name}] Scraping failed: {e}")
            if progress_callback:
                progress_callback({"type": "error", "provider": self.name, "message": f"Hacker News scrape failed: {e}"})

        return results

    async def _fetch_story(self, story_id: int) -> Optional[dict]:
        """Fetch a single story from HN API."""
        try:
            return await self.fetch_page(f"{self.base_url}/item/{story_id}.json", as_json=True)
        except Exception:
            return None

    def _is_startup_post(self, title: str) -> bool:
        """Check if a post looks like a startup launch."""
        title_lower = title.lower()

        # Show HN posts are usually launches
        if title.startswith("Show HN:"):
            return True

        # Launch HN posts
        if title.startswith("Launch HN:"):
            return True

        # Common startup keywords
        startup_keywords = [
            "launching", "launched", "introducing", "announcing",
            "new startup", "side project", "built", "created",
            "my first", "just released", "open source"
        ]
        return any(kw in title_lower for kw in startup_keywords)
