# services/scraper/enrichment/lead_enrichment — Lead Enrichment Engine
"""Collects comprehensive data for startup leads."""

import logging
import re
import json
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin, urlparse
import asyncio
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class LeadEnrichmentEngine:
    """
    For every startup collect:
    Company Name
    Website
    Description
    Launch Source
    Launch Date
    Industry
    Category
    Country
    Founder Names
    LinkedIn
    Twitter/X
    GitHub
    Contact Email
    Additional Emails
    Funding Stage
    Pricing
    Tech Stack
    Employee Estimate
    """

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        
        # Industry/category keywords
        self.INDICATORS = {
            "ai_ml": ["ai", "artificial intelligence", "machine learning", "ml", "deep learning", "neural", "llm", "nlp", "computer vision"],
            "fintech": ["fintech", "financial", "banking", "payment", "crypto", "blockchain", "wallet", "trading", "investment"],
            "healthtech": ["health", "medical", "healthcare", "clinic", "hospital", "telemed", "healthtech", "biotech"],
            "edtech": ["education", "learning", "student", "teacher", "school", "university", "edtech", "elearning", "course"],
            "saas": ["saas", "software as a service", "platform", "api", "dashboard", "workspace", "tool"],
            "ecommerce": ["ecommerce", "e-commerce", "retail", "shop", "store", "marketplace", "cart", "checkout"],
            "devtools": ["developer", "dev", "programming", "code", "github", "git", "api", "sdk", "framework", "library"],
            "marketing": ["marketing", "advertising", "ads", "campaign", "social media", "seo", "analytics", "crm"],
            "hr_tech": ["hr", "human resources", "recruiting", "hiring", "employee", "workforce", "payroll", "ats"],
            "cybersecurity": ["security", "cyber", "encryption", "firewall", "vpn", "antivirus", "malware", "breach", "secure"],
            "gaming": ["game", "gaming", "esports", "stream", "twitch", "youtube", "mobile game", "video game"],
            "food_tech": ["food", "restaurant", "delivery", "cooking", "recipe", "meal", "grocery", "foodtech"],
            "travel": ["travel", "trip", "hotel", "flight", "booking", "airbnb", "expedia", "tourism"],
            "real_estate": ["real estate", "property", "rental", "lease", "mortgage", "housing", "realestate"],
            "logistics": ["logistics", "shipping", "delivery", "supply chain", "warehouse", "transportation", "freight"],
        }
        
        # Funding stage indicators
        self.FUNDING_STAGES = {
            "bootstrapped": ["bootstrapped", "self-funded", "self funded", "no external funding"],
            "pre_seed": ["pre-seed", "pre seed", "idea stage", "prototype"],
            "seed": ["seed", "seed round", "angel", "angel investor"],
            "series_a": ["series a", "series-a", "series a round"],
            "series_b": ["series b", "series-b", "series b round"],
            "series_c": ["series c", "series-c", "series c round"],
            "growth": ["growth equity", "growth fund", "late stage"],
        }
        
        # Country indicators (TLDs and mentions)
        self.COUNTRIES = {
            "us": ["united states", "usa", "u.s.", "america", ".com", ".org", ".net"],
            "uk": ["united kingdom", "uk", "u.k.", "england", ".co.uk", ".uk"],
            "ca": ["canada", "canadian", ".ca"],
            "au": ["australia", "australian", ".au"],
            "de": ["germany", "german", ".de"],
            "fr": ["france", "french", ".fr"],
            "in": ["india", "indian", ".in"],
            "sg": ["singapore", ".sg"],
            "jp": ["japan", "japanese", ".jp"],
            "nl": ["netherlands", "dutch", ".nl"],
        }

    async def enrich_lead(self, lead_data: dict, emails: List[Dict] = None, 
                         founders: List[Dict] = None, social: Dict = None) -> Dict:
        """
        Enrich lead data with comprehensive information.
        
        Args:
            lead_data: Basic lead information from extraction
            emails: List of discovered emails (from contact discovery)
            founders: List of founder information
            social: Social media profiles
            
        Returns:
            Enriched lead dictionary with all required data points
        """
        enriched = lead_data.copy()  # Start with existing data
        
        website = lead_data.get("website", "")
        description = lead_data.get("description", "") or ""
        name = lead_data.get("name", "")
        
        # Ensure we have a website
        if not website:
            logger.warning(f"No website for lead {name}, skipping enrichment")
            return enriched
        
        try:
            # Fetch website content for analysis
            website_content = await self._fetch_website_content(website)
            
            # Extract enhanced description
            if website_content:
                desc_from_site = self._extract_description_from_content(website_content)
                if desc_from_site and len(desc_from_site) > len(description):
                    enriched["description"] = desc_from_site
            
            # Extract industry/category
            industry = self._determine_industry(description, website_content or "")
            if industry:
                enriched["industry"] = industry
            
            # Extract category (more specific than industry)
            category = self._determine_category(description, website_content or "")
            if category:
                enriched["category"] = category
            
            # Extract launch date
            launch_date = self._extract_launch_date(lead_data, website_content or "")
            if launch_date:
                enriched["launch_date"] = launch_date
            
            # Extract country
            country = self._extract_country(description, website_content or "", website)
            if country:
                enriched["country"] = country
            
            # Extract founder names (enhance what we might have)
            if founders:
                enriched["founders"] = founders
            elif website_content:
                extracted_founders = self._extract_founders_from_content(website_content)
                if extracted_founders:
                    existing_founders = enriched.get("founders", [])
                    if not existing_founders:
                        enriched["founders"] = extracted_founders
                    else:
                        # Merge and deduplicate
                        all_founders = existing_founders + extracted_founders
                        enriched["founders"] = self._deduplicate_founders(all_founders)
            
            # Extract social media profiles
            if social:
                enriched["social"] = social
            elif website_content:
                social_profiles = self._extract_social_from_content(website_content, website)
                if social_profiles:
                    enriched["social"] = social_profiles
            
            # Extract pricing information
            pricing = self._extract_pricing_info(website_content or "")
            if pricing:
                enriched["pricing_model"] = pricing
            
            # Extract tech stack
            tech_stack = self._extract_tech_stack(website_content or "")
            if tech_stack:
                enriched["tech_stack"] = tech_stack
            
            # Estimate employee count
            employee_estimate = self._estimate_employee_count(website_content or "", description)
            if employee_estimate:
                enriched["employee_estimate"] = employee_estimate
            
            # Determine funding stage
            funding_stage = self._determine_funding_stage(description, website_content or "")
            if funding_stage:
                enriched["funding_stage"] = funding_stage
            
            # Add emails from contact discovery
            if emails:
                # Format emails for storage
                email_list = [email["email"] for email in emails if email.get("email")]
                enriched["emails"] = email_list
                # Also store detailed email info if needed
                enriched["email_details"] = emails
            
            # Add launch source (should already be present)
            if "source_provider" not in enriched:
                enriched["source_provider"] = lead_data.get("source_provider", "unknown")
            if "source_url" not in enriched:
                enriched["source_url"] = lead_data.get("source_url", "")
            
        except Exception as e:
            logger.warning(f"Enrichment failed for {name}: {e}")
        
        return enriched
    
    async def _fetch_website_content(self, url: str) -> str:
        """Fetch and return text content from a website."""
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        html = await response.text()
                        # Extract text content using BeautifulSoup
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Remove script, style, nav, footer elements that add noise
                        for element in soup(["script", "style", "nav", "footer", "header"]):
                            element.decompose()
                        
                        # Get text content
                        text = soup.get_text()
                        
                        # Clean up whitespace
                        lines = (line.strip() for line in text.splitlines())
                        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                        text = '\n'.join(chunk for chunk in chunks if chunk)
                        
                        return text
                    else:
                        logger.debug(f"HTTP {response.status} for {url}")
        except Exception as e:
            logger.warning(f"Failed to fetch website content for {url}: {e}")
        
        return ""
    
    def _extract_description_from_content(self, content: str) -> str:
        """Extract a good description from website content."""
        if not content:
            return ""
        
        # Look for meta description patterns or prominent text
        lines = content.split('\n')
        
        # Skip very short lines and common navigation text
        skip_patterns = ['home', 'about', 'services', 'products', 'contact', 'login', 'sign up', 
                        'menu', 'nav', 'navigation', 'copyright', 'privacy', 'terms']
        
        candidate_lines = []
        for line in lines:
            line_lower = line.lower().strip()
            if len(line) < 20 or len(line) > 500:
                continue
            if any(skip in line_lower for skip in skip_patterns):
                continue
            # Look for lines that seem descriptive
            if len(line.split()) >= 5 and not line.isupper():
                candidate_lines.append(line.strip())
        
        if candidate_lines:
            # Return the first good candidate, or the longest if it seems like a tagline
            if len(candidate_lines[0].split()) >= 8:
                return candidate_lines[0]
            else:
                # Look for a longer descriptive line
                for line in candidate_lines:
                    if len(line.split()) >= 10:
                        return line
                return candidate_lines[0] if candidate_lines else ""
        
        return ""
    
    def _determine_industry(self, description: str, content: str) -> str:
        """Determine industry based on keywords."""
        text = (description + " " + content).lower()
        
        industry_scores = {}
        for industry, keywords in self.INDICATORS.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                industry_scores[industry] = score
        
        if industry_scores:
            return max(industry_scores.items(), key=lambda x: x[1])[0]
        
        return ""
    
    def _determine_category(self, description: str, content: str) -> str:
        """Determine more specific category."""
        text = (description + " " + content).lower()
        
        # More specific category patterns
        category_patterns = {
            "customer_support": ["support", "help desk", "ticket", "chatbot", "customer service"],
            "project_management": ["project management", "task management", "workflow", "collaboration", "trello", "asana"],
            "marketing_automation": ["marketing automation", "email marketing", "campaign management", "lead generation"],
            "sales_crm": ["crm", "sales", "customer relationship", "pipeline", "lead management"],
            "analytics": ["analytics", "data analysis", "business intelligence", "reporting", "dashboard"],
            "design_tools": ["design", "ui/ux", "prototyping", "wireframe", "figma", "sketch"],
            "development_tools": ["ide", "code editor", "version control", "ci/cd", "devops", "testing"],
            "finance_tools": ["accounting", "bookkeeping", "invoicing", "expense", "payroll", "financial"],
            "hr_tools": ["hr", "human resources", "recruiting", "onboarding", "performance", "training"],
            "health_wellness": ["health", "wellness", "fitness", "meditation", "mental health", "therapy"],
            "education_tools": ["education", "learning", "training", "course", "school", "student"],
            "ecommerce_platform": ["ecommerce", "online store", "shopping cart", "inventory", "product catalog"],
            "food_delivery": ["food delivery", "restaurant", "meal", "delivery", "takeaway"],
            "travel_booking": ["travel", "booking", "hotel", "flight", "vacation", "tour"],
            "real_estate_tech": ["real estate", "property", "rental", "lease", "property management"],
        }
        
        category_scores = {}
        for category, keywords in category_patterns.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                category_scores[category] = score
        
        if category_scores:
            return max(category_scores.items(), key=lambda x: x[1])[0]
        
        return ""
    
    def _extract_launch_date(self, lead_data: dict, content: str) -> str:
        """Extract launch date from lead data or content."""
        # First check if we already have a launch date
        if "launch_date" in lead_data and lead_data["launch_date"]:
            return lead_data["launch_date"]
        
        # Try to extract from content
        date_patterns = [
            r'launched\s+(\w+\s+\d{1,2},?\s+\d{4})',
            r'founded\s+(\w+\s+\d{1,2},?\s+\d{4})',
            r'started\s+(\w+\s+\d{1,2},?\s+\d{4})',
            r'since\s+(\w+\s+\d{1,2},?\s+\d{4})',
            r'(\w+\s+\d{1,2},?\s+\d{4})\s+launch',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, content, re.I)
            if match:
                date_str = match.group(1)
                # Try to parse and reformat
                try:
                    # This is simplified - in practice would use date parsing library
                    return date_str  # Return as found for now
                except:
                    pass
        
        return ""
    
    def _extract_country(self, description: str, content: str, website: str) -> str:
        """Extract country from TLD, description, or content."""
        text = (description + " " + content).lower()
        
        # Check TLD first
        try:
            domain = urlparse(website).netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            
            tld = "." + domain.split(".")[-1] if "." in domain else ""
            
            for country, indicators in self.COUNTRIES.items():
                if tld in indicators:
                    return country
        except:
            pass
        
        # Check text content
        for country, indicators in self.COUNTRIES.items():
            for indicator in indicators:
                if indicator in text:
                    return country
        
        return "us"  # Default fallback
    
    def _extract_founders_from_content(self, content: str) -> List[Dict]:
        """Extract founder information from website content."""
        founders = []
        
        if not content:
            return founders
        
        # Look for common founder patterns
        founder_patterns = [
            r'(?:founder|co-founder|ceo|cto)[\s:]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:founder|co-founder|ceo|cto)',
        ]
        
        for pattern in founder_patterns:
            matches = re.findall(pattern, content, re.I)
            for match in matches:
                name = match.strip()
                if len(name) > 2 and len(name.split()) >= 1:
                    # Determine role from context
                    role = "founder"  # Default
                    # Look for the role near the name (simplified)
                    name_pos = content.lower().find(name.lower())
                    if name_pos != -1:
                        context = content[max(0, name_pos-50):name_pos+50].lower()
                        if "ceo" in context:
                            role = "ceo"
                        elif "cto" in context:
                            role = "cto"
                        elif "co-founder" in context or "cofounder" in context:
                            role = "co-founder"
                    
                    founders.append({
                        "name": name,
                        "role": role,
                        "source": "website_content"
                    })
        
        # Deduplicate by name
        seen_names = set()
        unique_founders = []
        for founder in founders:
            name_lower = founder["name"].lower()
            if name_lower not in seen_names:
                seen_names.add(name_lower)
                unique_founders.append(founder)
        
        return unique_founders
    
    def _extract_social_from_content(self, content: str, website: str) -> Dict:
        """Extract social media profiles from website content."""
        social = {}
        
        if not content:
            return social
        
        # LinkedIn patterns
        linkedin_patterns = [
            r'linkedin\.com/(?:in|company)/([^\s/"]+)',
            r'linkedin\.com/school/([^\s/"]+)',
        ]
        
        for pattern in linkedin_patterns:
            match = re.search(pattern, content, re.I)
            if match:
                social["linkedin"] = match.group(0)
                break
        
        # Twitter/X patterns
        twitter_patterns = [
            r'twitter\.com/([^\s/"]+)',
            r'x\.com/([^\s/"]+)',
        ]
        
        for pattern in twitter_patterns:
            match = re.search(pattern, content, re.I)
            if match:
                social["twitter"] = match.group(0)
                break
        
        # GitHub patterns
        github_patterns = [
            r'github\.com/([^\s/"]+)',
        ]
        
        for pattern in github_patterns:
            match = re.search(pattern, content, re.I)
            if match:
                social["github"] = match.group(0)
                break
        
        return social
    
    def _extract_pricing_info(self, content: str) -> str:
        """Extract pricing information from content."""
        if not content:
            return ""
        
        # Look for pricing patterns
        pricing_indicators = [
            r'\$\d+(?:\.\d{2})?(?:\s*\/\s*\w+)?',  # $10, $10.99, $10/month, $10/user
            r'free\s+plan|free\s+tier|freemium',
            r'paid\s+plan|subscription\s+plan',
            r'pricing\s*:?\s*[^\n]{0,100}',
            r'monthly\s*:?\s*\$?\d+(?:\.\d{2})?',
            r'annually\s*:?\s*\$?\d+(?:\.\d{2})?',
        ]
        
        for pattern in pricing_indicators:
            match = re.search(pattern, content, re.I)
            if match:
                pricing_text = match.group(0).strip()
                if len(pricing_text) > 5 and len(pricing_text) < 200:
                    return pricing_text
        
        return ""
    
    def _extract_tech_stack(self, content: str) -> List[str]:
        """Extract technology stack from content."""
        if not content:
            return []
        
        # Common tech keywords
        tech_keywords = [
            # Languages
            "python", "javascript", "js", "typescript", "ts", "java", "c#", "c++", "ruby", "php", "go", "golang", "rust", "swift", "kotlin",
            # Frontend
            "react", "vue", "angular", "svelte", "html", "css", "scss", "sass", "bootstrap", "tailwind", "jquery",
            # Backend/Databases
            "node.js", "express", "django", "flask", "spring", "laravel", "mysql", "postgresql", "mongodb", "redis", "elasticsearch",
            # Cloud/DevOps
            "aws", "azure", "google cloud", "gcp", "docker", "kubernetes", "k8s", "terraform", "jenkins", "ci/cd",
            # Other
            "api", "rest", "graphql", "websocket", "microservices", "serverless", "lambda"
        ]
        
        found_tech = []
        content_lower = content.lower()
        
        for tech in tech_keywords:
            if tech in content_lower:
                found_tech.append(tech)
        
        # Deduplicate and return
        return list(dict.fromkeys(found_tech))  # Preserves order while deduplicating
    
    def _estimate_employee_count(self, content: str, description: str) -> str:
        """Estimate employee count from content."""
        text = (content + " " + description).lower()
        
        # Look for explicit mentions
        employee_patterns = [
            r'(\d+)\s*(?:employees?|team members?|staff|people)',
            r'team\s+of\s+(\d+)',
            r'(\d+)\s+people\s+team',
            r'we\s+are\s+(\d+)\s+(?:people|person)',
        ]
        
        for pattern in employee_patterns:
            match = re.search(pattern, text)
            if match:
                count = match.group(1)
                try:
                    count_int = int(count)
                    if count_int <= 10:
                        return "1-10"
                    elif count_int <= 25:
                        return "11-25"
                    elif count_int <= 50:
                        return "26-50"
                    elif count_int <= 100:
                        return "51-100"
                    elif count_int <= 200:
                        return "101-200"
                    else:
                        return "200+"
                except ValueError:
                    pass
        
        # Look for funding hints
        if any(word in text for word in ["seed", "series a", "funded", "investment"]):
            # Early stage companies likely small
            return "2-10"
        elif any(word in text for word in ["series b", "series c", "growth", "expanding"]):
            # Growth stage
            return "11-50"
        
        # Default based on common startup sizes
        return "2-10"  # Most early startups are small
    
    def _determine_funding_stage(self, description: str, content: str) -> str:
        """Determine funding stage from text."""
        text = (description + " " + content).lower()
        
        for stage, indicators in self.FUNDING_STAGES.items():
            for indicator in indicators:
                if indicator in text:
                    return stage
        
        # Default based on other signals
        if any(word in text for word in ["just launched", "launching", "beta", "early access", "prototype"]):
            return "pre_seed"
        elif any(word in text for word in ["seed", "angel"]):
            return "seed"
        
        return "bootstrapped"  # Default assumption for unknown
    
    def _deduplicate_founders(self, founders: List[Dict]) -> List[Dict]:
        """Deduplicate founder list by name."""
        seen = set()
        unique = []
        for founder in founders:
            name_key = founder["name"].lower().strip()
            if name_key not in seen:
                seen.add(name_key)
                unique.append(founder)
        return unique