# services/scraper/contact_discovery/email_discovery — Email-First Lead Discovery Engine
"""Implements the 8-step email discovery pipeline for startup leads."""

import logging
import re
import asyncio
from typing import List, Dict, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse
import aiohttp
from bs4 import BeautifulSoup
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EmailResult:
    """Result of email discovery."""
    email: str = ""
    confidence: int = 0  # 0-100
    source: str = ""  # where the email was found
    verified: bool = False
    priority: str = ""  # high, medium, low, very_low


class EmailDiscoveryEngine:
    """
    Implements the 8-step email discovery pipeline:
    
    Step 1: Extract email directly from source page
    Step 2: Extract official website
    Step 3: Visit official website and search for emails
    Step 4: Parse HTML for email patterns
    Step 5: Search common email patterns
    Step 6: Founder Discovery
    Step 7: Website Contact Graph
    Step 8: Email Validation and Prioritization
    """

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        
        # Email regex pattern
        self.EMAIL_PATTERN = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        )
        
        # Priority email patterns (higher priority = lower number)
        self.PRIORITY_PATTERNS = [
            (r'founder@', 10),      # Highest priority
            (r'cofounder@', 10),
            (r'ceo@', 10),
            (r'hello@', 20),
            (r'contact@', 20),
            (r'team@', 20),
            (r'hi@', 25),
            (r'support@', 30),
            (r'info@', 30),
            (r'mail@', 35),
            (r'admin@', 40),
        ]
        
        # Excluded email patterns
        self.EXCLUDE_PATTERNS = [
            r'@example\.com$',
            r'@test\.com$',
            r'noreply@',
            r'no-reply@',
            r'@sentry\.io$',
            r'@wixpress\.com$',
            r'sentry@',
            r'@.*\.png$',
            r'@.*\.jpg$',
            r'@.*\.jpeg$',
            r'@.*\.gif$',
        ]
        
        # Common contact page paths to check
        self.CONTACT_PATHS = [
            "/contact", "/about", "/team", "/company", "/founders",
            "/support", "/connect", "/get-in-touch", "/contact-us",
            "/our-team", "/meet-the-team", "/leadership", "/management",
            "/help", "/support", "/careers", "/jobs", "/press", "/media"
        ]
        
        # Founder/team page indicators
        self.FOUNDER_INDICATORS = [
            "founder", "co-founder", "ceo", "cto", "team", "leadership",
            "management", "our team", "meet the team", "leadership team",
            "executive", "staff", "people", "about us"
        ]

    async def discover_emails(self, lead_data: dict) -> List[Dict]:
        """
        Execute the 8-step email discovery pipeline.
        
        Args:
            lead_data: Dictionary with lead information (name, website, description, etc.)
            
        Returns:
            List of email dictionaries sorted by priority and confidence
        """
        website = lead_data.get("website", "")
        name = lead_data.get("name", "")
        description = lead_data.get("description", "")
        source_page = lead_data.get("source_url", "")  # Original source where lead was found
        
        if not website:
            logger.warning(f"No website for lead {name}, skipping email discovery")
            return []
        
        all_emails = []  # List of {"email": str, "confidence": int, "source": str, "verified": bool}
        seen_emails = set()
        
        logger.info(f"Starting email discovery for {name} ({website})")
        
        # Step 1: Extract email directly from source page
        if source_page:
            emails = await self._extract_emails_from_page(source_page, f"source_page:{lead_data.get('source_provider', 'unknown')}")
            for email in emails:
                if self._is_valid_email(email["email"]) and email["email"] not in seen_emails:
                    seen_emails.add(email["email"])
                    all_emails.append(email)
        
        # Step 2: Extract official website (already have it from lead_data)
        # Step 3: Visit official website and search for emails
        homepage_emails = await self._extract_emails_from_page(website, "homepage")
        for email in homepage_emails:
            if self._is_valid_email(email["email"]) and email["email"] not in seen_emails:
                seen_emails.add(email["email"])
                all_emails.append(email)
        
        # If we found high-confidence emails on homepage, we might skip deeper discovery
        high_confidence_emails = [e for e in all_emails if e["confidence"] >= 80]
        if len(high_confidence_emails) >= 2:
            logger.info(f"Found {len(high_confidence_emails)} high-confidence emails from homepage for {name}")
            return self._prioritize_emails(all_emails)
        
        # Step 4: Parse HTML for email patterns (already done in _extract_emails_from_page)
        # Step 5: Search common email patterns (handled by priority scoring)
        
        # Step 6: Founder Discovery
        founder_emails = await self._discover_via_founders(website, name, description)
        for email in founder_emails:
            if self._is_valid_email(email["email"]) and email["email"] not in seen_emails:
                seen_emails.add(email["email"])
                all_emails.append(email)
        
        # Step 7: Website Contact Graph
        contact_emails = await self._discover_via_contact_graph(website)
        for email in contact_emails:
            if self._is_valid_email(email["email"]) and email["email"] not in seen_emails:
                seen_emails.add(email["email"])
                all_emails.append(email)
        
        # Step 8: Email Validation and Prioritization
        prioritized_emails = self._prioritize_emails(all_emails)
        
        logger.info(f"Email discovery for {name}: found {len(prioritized_emails)} emails")
        if prioritized_emails:
            logger.info(f"Top email: {prioritized_emails[0]['email']} (confidence: {prioritized_emails[0]['confidence']})")
        
        return prioritized_emails
    
    async def _extract_emails_from_page(self, url: str, source: str) -> List[Dict]:
        """Extract emails from a single web page."""
        emails = []
        
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.debug(f"HTTP {response.status} for {url}")
                        return emails
                    
                    html = await response.text()
                    emails = self._parse_emails_from_html(html, source, url)
                    
        except asyncio.TimeoutError:
            logger.warning(f"Timeout fetching {url}")
        except Exception as e:
            logger.warning(f"Failed to extract emails from {url}: {e}")
        
        return emails
    
    def _parse_emails_from_html(self, html: str, source: str, page_url: str) -> List[Dict]:
        """Parse email addresses from HTML content."""
        emails = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text content
            text = soup.get_text()
            
            # Find all email matches
            matches = self.EMAIL_PATTERN.findall(text)
            
            for email in matches:
                email_lower = email.lower().strip()
                
                # Skip excluded patterns
                if any(re.search(pattern, email_lower) for pattern in self.EXCLUDE_PATTERNS):
                    continue
                
                # Calculate confidence based on context and pattern
                confidence = self._calculate_email_confidence(email_lower, soup, page_url)
                
                emails.append({
                    "email": email_lower,
                    "confidence": confidence,
                    "source": source,
                    "verified": False,  # Will be verified in later step if needed
                    "page_url": page_url
                })
                
                # Also look for mailto links
            for link in soup.find_all('a', href=True):
                href = link['href']
                if href.startswith('mailto:'):
                    email = href[7:].split('?')[0]  # Remove mailto: and any parameters
                    email_lower = email.lower().strip()
                    if self._is_valid_email_format(email_lower) and not any(re.search(pattern, email_lower) for pattern in self.EXCLUDE_PATTERNS):
                        confidence = self._calculate_email_confidence(email_lower, soup, page_url)
                        # mailto links get higher confidence
                        confidence = min(100, confidence + 15)
                        
                        emails.append({
                            "email": email_lower,
                            "confidence": confidence,
                            "source": source,
                            "verified": False,
                            "page_url": page_url,
                            "mailto": True
                        })
                        
        except Exception as e:
            logger.warning(f"Failed to parse HTML for emails: {e}")
        
        return emails
    
    def _is_valid_email_format(self, email: str) -> bool:
        """Basic email format validation."""
        return bool(self.EMAIL_PATTERN.match(email))
    
    def _is_valid_email(self, email: str) -> bool:
        """Check if email is valid and not excluded."""
        if not self._is_valid_email_format(email):
            return False
        return not any(re.search(pattern, email) for pattern in self.EXCLUDE_PATTERNS)
    
    def _calculate_email_confidence(self, email: str, soup: BeautifulSoup, page_url: str) -> int:
        """Calculate confidence score for an email (0-100)."""
        confidence = 50  # Base confidence
        
        # Check for priority patterns
        for pattern, priority_bonus in self.PRIORITY_PATTERNS:
            if re.search(pattern, email):
                confidence = max(confidence, 100 - priority_bonus)  # Lower number = higher priority
                break
        
        # Boost for emails found in specific contexts
        text_content = soup.get_text().lower()
        
        # Check if email appears near founder/team keywords
        founder_context = False
        for indicator in self.FOUNDER_INDICATORS:
            if indicator in text_content:
                # Check if email is near this indicator (simplified check)
                founder_context = True
                break
        
        if founder_context:
            confidence = min(100, confidence + 20)
        
        # Boost for emails in footer/header (common locations for contact info)
        # This is a simplified check - in practice we'd analyze position
        if soup.find('footer') or soup.find('header'):
            # Could check if email is near these elements
            confidence = min(100, confidence + 10)
        
        # Reduce confidence for generic emails
        generic_prefixes = ['info@', 'support@', 'hello@', 'contact@']
        if any(email.startswith(prefix) for prefix in generic_prefixes):
            confidence = max(20, confidence - 10)  # Don't go too low
        
        # Boost for personal-sounding emails (firstname.lastname@domain.com)
        if re.match(r'^[a-z]+\.[a-z]+@', email):
            confidence = min(100, confidence + 15)
        elif re.match(r'^[a-z]+@[a-z]+\.[a-z]+$', email):  # Simple pattern like founder@company.io
            # Check if local part looks like a name/role
            local_part = email.split('@')[0]
            if local_part in ['founder', 'ceo', 'cto', 'cofounder', 'team', 'hello', 'contact']:
                confidence = min(100, confidence + 10)
        
        return max(0, min(100, confidence))
    
    async def _discover_via_founders(self, website: str, name: str, description: str) -> List[Dict]:
        """Discover emails by finding founders and searching for their contact info."""
        emails = []
        
        try:
            # Extract founder names from lead data or website
            founder_names = []
            
            # Try to get from lead data first
            if "founders" in lead_data and isinstance(lead_data["founders"], list):
                for founder in lead_data["founders"]:
                    if isinstance(founder, dict) and "name" in founder:
                        founder_names.append(founder["name"])
                    elif isinstance(founder, str):
                        founder_names.append(founder)
            
            # If no founders in lead data, try to extract from website
            if not founder_names:
                founder_names = await self._extract_founders_from_website(website)
            
            # For each founder, try to guess email patterns
            for founder_name in founder_names[:3]:  # Limit to top 3 founders
                if not founder_name or len(founder_name.strip()) < 2:
                    continue
                
                # Clean founder name
                clean_name = re.sub(r'[^\w\s]', '', founder_name.strip()).lower()
                name_parts = clean_name.split()
                
                if not name_parts:
                    continue
                
                # Generate email guesses
                domain = self._extract_domain(website)
                if not domain:
                    continue
                
                guesses = []
                first_name = name_parts[0]
                last_name = name_parts[-1] if len(name_parts) > 1 else ''
                
                # Common email patterns for founders
                if len(name_parts) >= 2:
                    guesses.extend([
                        f"{first_name}@{domain}",
                        f"{last_name}@{domain}",
                        f"{first_name}.{last_name}@{domain}",
                        f"{first_name[0]}{last_name}@{domain}",
                        f"{first_name}_{last_name}@{domain}",
                    ])
                else:
                    # Single name
                    guesses.extend([
                        f"{first_name}@{domain}",
                        f"{first_name[0]}@{domain}",
                    ])
                
                # Also try role-based emails
                role_based = [
                    f"founder@{domain}",
                    f"ceo@{domain}",
                    f"cto@{domain}",
                ]
                guesses.extend(role_based)
                
                # Validate each guess by checking if domain accepts email (basic syntax) and try to verify
                for guess in guesses:
                    email = guess  # Already formatted correctly
                    if self._is_valid_email(email):
                        # Try to verify by checking if we can find evidence on the website
                        confidence = await self._verify_founder_email(email, website, founder_name)
                        if confidence > 30:  # Only include if we have some verification
                            emails.append({
                                "email": email,
                                "confidence": confidence,
                                "source": "founder_discovery",
                                "verified": confidence > 70,
                                "founder": founder_name
                            })
        
        except Exception as e:
            logger.warning(f"Founder discovery failed for {website}: {e}")
        
        return emails
    
    async def _extract_founders_from_website(self, website: str) -> List[str]:
        """Extract founder names from the website."""
        founders = []
        
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Check homepage and about/team pages
                urls_to_check = [website]
                urls_to_check.extend([urljoin(website, path) for path in ["/about", "/team", "/founders", "/leadership"]])
                
                for url in urls_to_check[:3]:  # Limit to avoid too many requests
                    try:
                        async with session.get(url) as response:
                            if response.status == 200:
                                html = await response.text()
                                soup = BeautifulSoup(html, 'html.parser')
                                
                                # Look for common founder/team patterns
                                text = soup.get_text()
                                
                                # Look for patterns like "Founded by John Doe" or "CEO: Jane Smith"
                                founder_patterns = [
                                    r'founded\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                                    r'ceo\s*:?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                                    r'cto\s*:?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                                    r'founder\s*:?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                                    r'co-founder\s*:?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                                ]
                                
                                for pattern in founder_patterns:
                                    matches = re.findall(pattern, text, re.I)
                                    for match in matches:
                                        if len(match.strip()) > 2:
                                            founders.append(match.strip())
                                
                                # Also look for team pages with names
                                # This is simplified - in practice would parse team member cards
                                name_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})'
                                potential_names = re.findall(name_pattern, text)
                                # Filter out common non-names
                                non_names = {'the', 'and', 'for', 'with', 'this', 'that', 'our', 'we', 'are', 'inc', 'llc', 'ltd', 'company', 'corporation'}
                                for name in potential_names[:10]:  # Limit processing
                                    if name.lower() not in non_names and len(name.split()) >= 2:
                                        founders.append(name)
                                        
                    except Exception:
                        continue  # Skip failed URLs
                        
        except Exception as e:
            logger.warning(f"Failed to extract founders from website {website}: {e}")
        
        # Deduplicate and return
        seen = set()
        unique_founders = []
        for founder in founders:
            if founder not in seen:
                seen.add(founder)
                unique_founders.append(founder)
        
        return unique_founders[:5]  # Return top 5
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return ""
    
    async def _verify_founder_email(self, email: str, website: str, founder_name: str) -> int:
        """Try to verify that a founder email is valid by looking for evidence on the website."""
        # This is a simplified verification - in practice might involve checking
        # if the email appears on the site, or checking social profiles
        
        confidence = 30  # Base for syntactically valid guess
        
        try:
            # Check if we can find evidence of this email or name on the website
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(website) as response:
                    if response.status == 200:
                        html = await response.text()
                        text = html.lower()
                        
                        # Check if founder name appears
                        if founder_name.lower() in text:
                            confidence += 20
                        
                        # Check if email appears (strong evidence)
                        if email.lower() in text:
                            confidence += 30
                        
                        # Check for contextual clues
                        email_prefix = email.split('@')[0]
                        if email_prefix in ['founder', 'ceo', 'cto'] and any(role in text for role in ['founder', 'ceo', 'cto']):
                            confidence += 15
                            
        except Exception:
            pass  # If we can't verify, keep base confidence
        
        return min(100, confidence)
    
    async def _discover_via_contact_graph(self, website: str) -> List[Dict]:
        """Discover emails by traversing the website contact graph."""
        emails = []
        seen_urls = set()
        
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Start with homepage
                urls_to_visit = [(website, "homepage")]
                
                # Add common contact pages
                for path in self.CONTACT_PATHS:
                    url = urljoin(website, path)
                    urls_to_visit.append((url, f"contact_page:{path.strip('/')}"))
                
                # Process URLs (breadth-first, limited depth)
                for url, source in urls_to_visit:
                    if url in seen_urls or len(seen_urls) > 10:  # Limit to avoid excessive requests
                        continue
                    
                    seen_urls.add(url)
                    
                    try:
                        async with session.get(url) as response:
                            if response.status == 200:
                                html = await response.text()
                                page_emails = self._parse_emails_from_html(html, source, url)
                                
                                for email in page_emails:
                                    # Boost confidence for contact page emails
                                    if "contact_page" in email["source"]:
                                        email["confidence"] = min(100, email["confidence"] + 10)
                                    
                                    emails.append(email)
                                    
                    except Exception as e:
                        logger.debug(f"Failed to fetch {url}: {e}")
                        continue
                        
        except Exception as e:
            logger.warning(f"Contact graph discovery failed for {website}: {e}")
        
        return emails
    
    def _prioritize_emails(self, emails: List[Dict]) -> List[Dict]:
        """Prioritize and deduplicate emails."""
        # Group by email address, keeping the highest confidence version
        email_map = {}
        
        for email_dict in emails:
            email_addr = email_dict["email"]
            if email_addr not in email_map or email_dict["confidence"] > email_map[email_addr]["confidence"]:
                email_map[email_addr] = email_dict
        
        # Convert to list and sort by priority
        prioritized = list(email_map.values())
        
        # Sort by: confidence (desc), then by source priority
        def sort_key(email_dict):
            confidence = email_dict["confidence"]
            source = email_dict["source"]
            
            # Source priority (lower number = higher priority)
            source_priority = {
                "source_page": 1,
                "homepage": 2,
                "founder_discovery": 3,
                "contact_page": 4,
                "mailto": 5  # mailto links are strong signals
            }.get(source.split(":")[0], 10)  # Default priority
            
            return (-confidence, source_priority)
        
        prioritized.sort(key=sort_key)
        
        # Format for final output (remove internal fields)
        result = []
        for email_dict in prioritized:
            result.append({
                "email": email_dict["email"],
                "confidence": email_dict["confidence"],
                "source": email_dict["source"],
                "verified": email_dict["verified"]
            })
        
        return result