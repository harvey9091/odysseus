# services/scraper/qualifiers/startup_qualifier — Startup Qualification Engine
"""Determine if a lead represents a genuine startup."""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class QualificationResult:
    """Result of startup qualification."""
    is_startup: bool = False
    confidence: float = 0.0  # 0.0 to 1.0
    company_stage: str = "unknown"  # idea, early, growth, mature
    signals: List[str] = field(default_factory=list)
    rejection_reasons: List[str] = field(default_factory=list)


class StartupQualifier:
    """
    Dedicated startup classifier.
    
    Output: {
        "is_startup": true,
        "confidence": 0.96,
        "company_stage": "early",
        "signals": [...]
    }
    """

    def __init__(self):
        # Strong startup signals (positive indicators)
        self.startup_signals = {
            # Profile pages on startup platforms
            "startup_profile_page": 0.25,
            "founder_profile": 0.20,
            "launch_listing": 0.20,
            "accelerator_listing": 0.15,
            
            # Product characteristics
            "saas_product": 0.15,
            "ai_startup": 0.15,
            "startup_marketplace": 0.10,
            "recent_launch": 0.10,
            
            # Website indicators
            "company_website": 0.10,
            "pricing_page": 0.08,
            "product_demo": 0.08,
        }
        
        # Negative signals (immediate rejection)
        self.negative_signals = {
            "article": 0.9,
            "news_post": 0.85,
            "blog": 0.8,
            "github_repository": 0.9,
            "documentation": 0.8,
            "tutorial": 0.75,
            "open_source_project": 0.85,
            "mature_company": 0.8,
            "fortune_500": 0.75,
            "public_corporation": 0.8,
        }
        
        # TLDs associated with startups
        self.startup_tlds = {".io", ".ai", ".co", ".app", ".dev", ".tech", ".so", ".ly", ".to", ".gg", ".xyz", ".app"}
        
        # Accelerator/incubator keywords
        self.accelerator_keywords = {
            "y combinator", "yc", "techstars", "500 startups", "seedcamp", 
            "angelpad", "founder institute", "plug and play", "plugandplay",
            "masschallenge", "blast", "dreamit", "alchemist", "boost vc",
            "sosv", "indiebio", "hfx", "zeroth.ai", "h2 venture"
        }
        
        # Startup platform domains
        self.startup_platforms = {
            "producthunt.com", "betalist.com", "indiehackers.com", "devhunt.org",
            "alternativeto.net", "peerlist.io", "uneed.best", "hackernews.com",
            "news.ycombinator.com", "startuprankings.com", "beta.page",
            "betali.st", "makerlog.co", "starterstory.com"
        }

    def qualify(self, lead_data: dict) -> QualificationResult:
        """
        Qualify if a lead represents a genuine startup.
        
        Args:
            lead_data: Dictionary with lead information (name, website, description, etc.)
            
        Returns:
            QualificationResult with is_startup, confidence, company_stage, and signals
        """
        result = QualificationResult()
        
        # Extract key fields
        name = lead_data.get("name", "").strip()
        website = lead_data.get("website", "") or ""
        description = lead_data.get("description", "") or ""
        source_provider = lead_data.get("source_provider", "")
        source_url = lead_data.get("source_url", "")
        
        combined_text = f"{name} {description}".lower().strip()
        
        # Quick rejection checks
        if not name or len(name) < 2:
            result.rejection_reasons.append("Invalid or missing company name")
            return result
            
        if not website:
            result.rejection_reasons.append("No website found")
            return result
        
        # Check for negative signals first (immediate rejection)
        negative_score = self._check_negative_signals(combined_text, website, source_provider, source_url)
        if negative_score > 0.5:  # Threshold for immediate rejection
            result.is_startup = False
            result.confidence = 0.0
            result.rejection_reasons.append(f"Strong negative signals detected (score: {negative_score:.2f})")
            return result
        
        # Calculate positive signals
        positive_score, signals = self._calculate_positive_signals(
            name, website, description, source_provider, source_url, combined_text
        )
        
        # Determine company stage
        company_stage = self._determine_company_stage(
            lead_data, combined_text, website
        )
        
        # Final qualification decision
        # Weighted combination of signals
        total_score = positive_score - (negative_score * 0.5)  # Reduce but don't eliminate
        
        # Normalize to 0-1 range
        confidence = max(0.0, min(1.0, total_score))
        
        # Apply thresholds
        if confidence >= 0.6:  # High confidence startup
            result.is_startup = True
            result.confidence = confidence
            result.company_stage = company_stage
            result.signals = signals
        elif confidence >= 0.3:  # Medium confidence - needs more evidence
            result.is_startup = True  # Give benefit of doubt but with lower confidence
            result.confidence = confidence
            result.company_stage = company_stage
            result.signals = signals
            result.rejection_reasons.append("Medium confidence startup - contact discovery recommended")
        else:  # Low confidence - likely not a startup
            result.is_startup = False
            result.confidence = confidence
            result.rejection_reasons.append(f"Low startup confidence: {confidence:.2f}")
        
        return result
    
    def _check_negative_signals(self, text: str, website: str, source_provider: str, source_url: str) -> float:
        """Check for negative signals that indicate NOT a startup."""
        score = 0.0
        reasons = []
        
        # Check source provider/platform
        if source_provider in self.startup_platforms:
            # These are generally good, but need to check content
            pass
        elif source_provider in ["hackernews"]:
            # HN needs content checking
            pass
            
        # Check URL patterns for articles, blogs, etc.
        article_patterns = [
            r"/article/", r"/blog/", r"/news/", r"/post/", r"/posts/",
            r"/story/", r"/articles/", r"/blog-post", r"/news-post",
            r"medium\.com/[^/]+/[a-z0-9-]+$", r"substack\.com/p/",
            r"wordpress\.com|blogspot\.com", r"\.(?:blog|news|article|press|media)[./]",
            r"(?:read|view)-more", r"(?:archive|category|tag)s?/[a-z0-9-]+/?$"
        ]
        
        for pattern in article_patterns:
            if re.search(pattern, website or "", re.I) or re.search(pattern, source_url or "", re.I):
                score += 0.8
                reasons.append(f"Article/blog URL pattern: {pattern}")
                break
        
        # Check for documentation/tutorial patterns
        doc_patterns = [
            r"/docs/", r"/documentation/", r"/help/", r"/support/",
            r"/guide/", r"/tutorial/", r"/learn/", r"/api/", r"/changelog/"
        ]
        
        for pattern in doc_patterns:
            if re.search(pattern, website or "", re.I):
                score += 0.7
                reasons.append(f"Documentation URL pattern: {pattern}")
                break
                
        # Check for GitHub/GitLab/Bitbucket
        repo_patterns = [
            r"github\.com/[^/]+/[^/]+", r"gitlab\.com/[^/]+/[^/]+",
            r"bitbucket\.org/[^/]+/[^/]+"
        ]
        
        for pattern in repo_patterns:
            if re.search(pattern, website or "", re.I):
                score += 0.9
                reasons.append(f"Source code repository: {pattern}")
                break
        
        # Check text content for article indicators
        article_indicators = [
            r"how we ", r"why we ", r"how i ", r"why i ",
            r"lessons learned", r"what i learned", r"what we learned",
            r"my journey", r"our journey", r"behind the scenes",
            r"deep dive", r"analysis of", r"review of",
            r"case study", r"report:", r"survey:",
            r"monthly report", r"weekly report", r"year in review",
            r"state of ", r"trends in ", r"the future of ",
            r"opinion:", r"op-ed", r"editorial",
            r"published (?:on|at)", r"updated (?:on|at)",
            r"reading time|min read", r"follow us on twitter",
            r"subscribe to our newsletter", r"related articles",
            r"you may also like", r"read more", r"comments? \(\d+\)",
            r"leave a (?:comment|reply)", r"share this (?:article|post)",
            r"advertisement|sponsored content", r"cookie policy"
        ]
        
        for pattern in article_indicators:
            if re.search(pattern, text, re.I):
                score += 0.6
                reasons.append(f"Article content indicator: {pattern}")
                # Don't break - multiple indicators increase confidence
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _calculate_positive_signals(self, name: str, website: str, description: str, 
                                  source_provider: str, source_url: str, text: str) -> tuple[float, List[str]]:
        """Calculate positive startup signals."""
        score = 0.0
        signals = []
        
        # Source platform signals
        if source_provider in self.startup_platforms:
            if source_provider in ["producthunt", "betalist", "devhunt", "indiehackers"]:
                score += 0.25
                signals.append("startup_profile_page")
            elif source_provider == "hackernews":
                # Check if it's Show HN or Launch HN
                if text.startswith("show hn:") or text.startswith("launch hn:"):
                    score += 0.20
                    signals.append("launch_listing")
                else:
                    score += 0.10  # Regular HN post
                    signals.append("hn_post")
        
        # Website-based signals
        parsed = urlparse(website)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
            
        # Check for startup-favorable TLDs
        tld = "." + domain.split(".")[-1] if "." in domain else ""
        if tld in self.startup_tlds:
            score += 0.10
            signals.append("startup_tld")
            
        # Check for company-like website structure
        if parsed.path in ["", "/"] or len(parsed.path) <= 3:
            score += 0.08
            signals.append("company_website")
            
        # Check for pricing page links (would need to fetch page to confirm)
        # For now, look for pricing keywords in description
        if any(word in text for word in ["pricing", "plan", "price", "cost", "$"]):
            score += 0.08
            signals.append("pricing_indicated")
            
        # Check for SAAS/AI indicators
        saas_indicators = [
            "saas", "software as a service", "platform", "api", "dashboard",
            "workspace", "tool", "application", "app", "webservice"
        ]
        if any(indicator in text for indicator in saas_indicators):
            score += 0.15
            signals.append("saas_product")
            
        ai_indicators = [
            "ai", "artificial intelligence", "machine learning", "ml", "deep learning",
            "neural", "llm", "gpt", "language model", "computer vision", "nlp"
        ]
        if any(indicator in text for indicator in ai_indicators):
            score += 0.15
            signals.append("ai_startup")
            
        # Check for recent launch indicators
        recent_indicators = [
            "just launched", "launching today", "now available", "coming soon",
            "early access", "beta", "waitlist", "sign up", "get notified"
        ]
        if any(indicator in text for indicator in recent_indicators):
            score += 0.10
            signals.append("recent_launch")
            
        # Check for accelerator/incubator mentions
        for keyword in self.accelerator_keywords:
            if keyword in text:
                score += 0.15
                signals.append("accelerator_listing")
                break
                
        # Check for founder/team indicators
        founder_indicators = [
            "founder", "co-founder", "ceo", "cto", "team", "built by",
            "created by", "founded by", "started by"
        ]
        if any(indicator in text for indicator in founder_indicators):
            score += 0.10
            signals.append("founder_mentioned")
            
        # Check for product/market indicators
        product_indicators = [
            "product", "solution", "service", "for businesses", "b2b", "b2c",
            "enterprise", "startup", "startup tool"
        ]
        if any(indicator in text for indicator in product_indicators):
            score += 0.08
            signals.append("product_indicated")
        
        # Name heuristics - short, branded names are more likely startups
        if name:
            words = name.split()
            if 1 <= len(words) <= 3 and not name.lower().startswith(("the ", "a ", "an ", "how ", "why ", "what ")):
                score += 0.05
                signals.append("branded_name")
            elif len(name) > 30:
                score -= 0.10  # Overly long names are suspicious
        
        return min(score, 1.0), signals
    
    def _determine_company_stage(self, lead_data: dict, text: str, website: str) -> str:
        """Determine the company stage based on available signals."""
        # Check for very early signals
        early_signals = [
            "idea", "prototype", "mvp", "minimum viable product",
            "just started", "side project", "weekend project",
            "building", "in development", "coming soon",
            "pre-launch", "stealth", "private beta"
        ]
        
        # Check for growth signals
        growth_signals = [
            "series a", "series b", "series c", "funding", "investment",
            "raised", "investors", "vc", "venture capital",
            "growing", "scaling", "expanding", "hiring", "jobs",
            "customers", "users", "clients", "revenue"
        ]
        
        # Check for mature signals
        mature_signals = [
            "established", "founded in", "years", "decade",
            "enterprise", "fortune", "public", "ipo", "acquired",
            "subsidiary", "division"
        ]
        
        text_lower = text.lower()
        
        # Check for accelerator/incubator (usually early stage)
        for keyword in self.accelerator_keywords:
            if keyword in text_lower:
                return "early"
        
        # Count signal matches
        early_count = sum(1 for signal in early_signals if signal in text_lower)
        growth_count = sum(1 for signal in growth_signals if signal in text_lower)
        mature_count = sum(1 for signal in mature_signals if signal in text_lower)
        
        # Determine stage based on strongest signal
        if mature_count > 0 and mature_count >= max(early_count, growth_count):
            return "mature"
        elif growth_count > 0 and growth_count > early_count:
            return "growth"
        elif early_count > 0 or (early_count == 0 and growth_count == 0 and mature_count == 0):
            # Default to early for unknown/no clear signals
            return "early"
        else:
            return "early"  # Default fallback