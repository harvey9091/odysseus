# services/scraper/scoring/startup_scorer — Startup Scoring Engine
"""Scores startup leads based on quality and outreach potential."""

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)


class StartupScorer:
    """
    Scoring system for startup leads.
    
    Factors:
    - Startup Confidence (from qualification engine)
    - Launch Freshness
    - Founder Visibility
    - Contact Quality
    - Website Quality
    - Directory Quality
    - Industry Relevance
    
    Score: 0-100
    """

    def __init__(self):
        # Weights for each factor (must sum to 1.0)
        self.weights = {
            "startup_confidence": 0.20,      # How confident we are it's a real startup
            "launch_freshness": 0.15,        # How recently launched
            "founder_visibility": 0.15,      # How easy to find founder info
            "contact_quality": 0.20,         # Quality and availability of contact emails
            "website_quality": 0.10,         # Professionalism of website
            "directory_quality": 0.10,       # Quality of source directory/listing
            "industry_relevance": 0.10,      # Relevance to target industries
        }
        
        # Current date for freshness calculations
        self.now = datetime.utcnow()
        
        # Industries we're particularly interested in (can be configured)
        self.target_industries = {
            "ai_ml", "saas", "fintech", "healthtech", "edtech", 
            "devtools", "marketing", "hr_tech", "cybersecurity"
        }

    def score_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Score a startup lead based on multiple factors.
        
        Args:
            lead_data: Dictionary containing all lead information
            
        Returns:
            Dictionary with individual factor scores and final score (0-100)
        """
        try:
            # Calculate individual factor scores
            scores = {}
            
            # 1. Startup Confidence (from qualification)
            scores["startup_confidence"] = self._score_startup_confidence(lead_data)
            
            # 2. Launch Freshness
            scores["launch_freshness"] = self._score_launch_freshness(lead_data)
            
            # 3. Founder Visibility
            scores["founder_visibility"] = self._score_founder_visibility(lead_data)
            
            # 4. Contact Quality
            scores["contact_quality"] = self._score_contact_quality(lead_data)
            
            # 5. Website Quality
            scores["website_quality"] = self._score_website_quality(lead_data)
            
            # 6. Directory Quality
            scores["directory_quality"] = self._score_directory_quality(lead_data)
            
            # 7. Industry Relevance
            scores["industry_relevance"] = self._score_industry_relevance(lead_data)
            
            # Calculate weighted final score
            final_score = 0.0
            for factor, score in scores.items():
                weight = self.weights.get(factor, 0.0)
                final_score += score * weight
            
            # Convert to 0-100 scale
            final_score = int(final_score * 100)
            
            # Ensure bounds
            final_score = max(0, min(100, final_score))
            
            # Prepare detailed result
            result = {
                "startup_score": final_score,
                "factors": scores,
                "scoring_version": "1.0",
                "scored_at": self.now.isoformat()
            }
            
            logger.debug(f"Scored lead {lead_data.get('name', 'Unknown')}: {final_score} "
                        f"(confidence: {scores['startup_confidence']:.2f}, "
                        f"freshness: {scores['launch_freshness']:.2f}, "
                        f"founder: {scores['founder_visibility']:.2f}, "
                        f"contact: {scores['contact_quality']:.2f})")
            
            return result
            
        except Exception as e:
            logger.warning(f"Scoring failed for lead {lead_data.get('name', 'Unknown')}: {e}")
            # Return default scores
            return {
                "startup_score": 0,
                "factors": {factor: 0.0 for factor in self.weights.keys()},
                "scoring_version": "1.0",
                "scored_at": self.now.isoformat(),
                "error": str(e)
            }
    
    def score_lead_legacy_format(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Score a lead and return results in the legacy format expected by existing code.
        
        This ensures backward compatibility with existing APIs and frontend.
        
        Returns:
            Dictionary with fields matching the existing ScraperLead model:
            - affordability_score
            - promo_video_fit_score
            - urgency_score
            - funding_probability
            - ai_summary
            - ai_reasoning
            - outreach_recommendations
        """
        # Get the detailed scores
        detailed_scores = self.score_lead(lead_data)
        
        if "error" in detailed_scores:
            # Return legacy format with defaults on error
            return self._get_legacy_defaults(lead_data)
        
        startup_score = detailed_scores["startup_score"]
        factors = detailed_scores["factors"]
        
        # Map my scores to legacy fields
        legacy_result = {}
        
        # Main score -> affordability_score (what frontend uses for main score and color coding)
        legacy_result["affordability_score"] = startup_score
        
        # Website quality -> promo_video_fit_score
        legacy_result["promo_video_fit_score"] = int(factors.get("website_quality", 0.0) * 100)
        
        # Launch freshness -> urgency_score
        legacy_result["urgency_score"] = int(factors.get("launch_freshness", 0.0) * 100)
        
        # Founder visibility -> funding_probability
        legacy_result["funding_probability"] = int(factors.get("founder_visibility", 0.0) * 100)
        
        # Generate AI summary
        legacy_result["ai_summary"] = self._generate_ai_summary(lead_data, factors)
        
        # Generate AI reasoning (store detailed factors as JSON)
        legacy_result["ai_reasoning"] = json.dumps({
            "scoring_version": "1.0",
            "factors": factors,
            "weights": self.weights,
            "startup_score": startup_score
        })
        
        # Generate outreach recommendations
        legacy_result["outreach_recommendations"] = self._generate_outreach_recommendations(
            lead_data, factors, startup_score
        )
        
        return legacy_result
    
    def _score_startup_confidence(self, lead_data: Dict[str, Any]) -> float:
        """Score based on startup qualification confidence."""
        # This should come from the qualification engine
        confidence = lead_data.get("startup_confidence", 0.0)
        # Ensure it's in 0-1 range
        return max(0.0, min(1.0, confidence))
    
    def _score_launch_freshness(self, lead_data: Dict[str, Any]) -> float:
        """Score based on how recently the startup launched."""
        launch_date_str = lead_data.get("launch_date")
        if not launch_date_str:
            # No launch date - assume moderate freshness
            return 0.5
        
        try:
            # Parse the launch date
            if isinstance(launch_date_str, str):
                # Try common formats
                for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
                           "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y"):
                    try:
                        launch_date = datetime.strptime(launch_date_str, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    # If none worked, try ISO format
                    launch_date = datetime.fromisoformat(lead_date_str.replace("Z", "+00:00"))
            else:
                # Assume it's already a datetime object
                launch_date = launch_date_str
            
            # Calculate days since launch
            delta = self.now - launch_date
            days_old = delta.days
            
            # Scoring: newer is better
            # 0-7 days: excellent (1.0)
            # 8-30 days: good (0.8)
            # 31-90 days: fair (0.5)
            # 91-180 days: poor (0.2)
            # 180+ days: very poor (0.0)
            if days_old <= 7:
                return 1.0
            elif days_old <= 30:
                return 0.8
            elif days_old <= 90:
                return 0.5
            elif days_old <= 180:
                return 0.2
            else:
                return 0.0
                
        except Exception as e:
            logger.debug(f"Could not parse launch date {launch_date_str}: {e}")
            return 0.5  # Default if we can't parse
    
    def _score_founder_visibility(self, lead_data: Dict[str, Any]) -> float:
        """Score based on how easy it is to find founder information."""
        founders = lead_data.get("founders", [])
        if not founders:
            return 0.0
        
        # Score based on number and quality of founder information
        score = 0.0
        max_score = 0.0
        
        for founder in founders:
            max_score += 1.0  # Each founder can contribute up to 1.0
            
            founder_score = 0.0
            
            # Has a name
            if founder.get("name"):
                founder_score += 0.4
                
            # Has a role/title
            if founder.get("role") and founder["role"] != "unknown":
                founder_score += 0.3
                
            # Has profile links (LinkedIn, Twitter, etc.)
            social = founder.get("social", {})
            if social:
                # LinkedIn is particularly valuable
                if social.get("linkedin"):
                    founder_score += 0.2
                # Twitter/X
                if social.get("twitter"):
                    founder_score += 0.1
                # GitHub
                if founder.get("github"):
                    founder_score += 0.1
            
            # Source credibility
            source = founder.get("source", "")
            if source in ["website_content", "founder_discovery", "linkedin"]:
                founder_score += 0.1  # Bonus for credible sources
            
            score += founder_score
        
        # Normalize by number of founders (but cap at reasonable level)
        # Ideal: 1-3 founders with good info
        founder_count = len(founders)
        if founder_count == 0:
            return 0.0
        elif founder_count <= 3:
            # Good range - normalize by actual count
            return min(1.0, score / founder_count) if founder_count > 0 else 0.0
        else:
            # Many founders - might be exaggerated, cap the benefit
            return min(1.0, score / 3.0)
    
    def _score_contact_quality(self, lead_data: Dict[str, Any]) -> float:
        """Score based on quality and availability of contact emails."""
        emails = lead_data.get("emails", [])
        email_details = lead_data.get("email_details", [])
        
        if not emails and not email_details:
            return 0.0
        
        # Use email_details if available (has confidence scores), otherwise use emails
        email_list = email_details if email_details else [{"email": e, "confidence": 50} for e in emails]
        
        if not email_list:
            return 0.0
        
        # Find the best email
        best_email = max(email_list, key=lambda x: x.get("confidence", 0))
        best_confidence = best_email.get("confidence", 0)
        
        # Convert confidence (0-100) to score (0-1.0)
        confidence_score = best_confidence / 100.0
        
        # Bonus for having multiple email options
        if len(email_list) > 1:
            # More options = better for outreach flexibility
            option_bonus = min(0.2, (len(email_list) - 1) * 0.05)  # Up to 0.2 bonus
            confidence_score = min(1.0, confidence_score + option_bonus)
        
        # Bonus for high-priority email patterns
        email = best_email.get("email", "").lower()
        priority_patterns = [
            "founder@", "cofounder@", "ceo@", "hello@", "contact@", "team@", "hi@"
        ]
        if any(email.startswith(pattern) for pattern in priority_patterns):
            confidence_score = min(1.0, confidence_score + 0.1)
        
        return confidence_score
    
    def _score_website_quality(self, lead_data: Dict[str, Any]) -> float:
        """Score based on website professionalism and quality."""
        website = lead_data.get("website", "")
        if not website:
            return 0.0
        
        score = 0.5  # Base score for having a website
        
        try:
            # Check domain characteristics
            from urllib.parse import urlparse
            parsed = urlparse(website)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            
            # Professional TLDs get bonus
            professional_tlds = [".com", ".org", ".net", ".io", ".co", ".ai", ".app", ".dev", ".tech"]
            tld = "." + domain.split(".")[-1] if "." in domain else ""
            if tld in professional_tlds:
                score += 0.2
            elif tld in [".info", ".biz", ".name"]:
                score -= 0.1  # Slightly less professional
            
            # Short, memorable domain names are better
            domain_name = domain.split(".")[0]
            if 3 <= len(domain_name) <= 15:
                score += 0.1
            elif len(domain_name) > 25:
                score -= 0.1  # Very long domains are harder to remember
            
            # HTTPS is better than HTTP
            if website.startswith("https://"):
                score += 0.1
            
            # Clean subdomain usage (not too many subdomains)
            subdomain_count = domain.count(".")
            if subdomain_count == 1:  # domain.tld
                score += 0.1
            elif subdomain_count > 3:  # Too many subdomains
                score -= 0.1
            
        except Exception:
            pass  # If we can't parse, keep base score
        
        return max(0.0, min(1.0, score))
    
    def _score_directory_quality(self, lead_data: Dict[str, Any]) -> float:
        """Score based on quality of the source directory/listing."""
        source_provider = lead_data.get("source_provider", "").lower()
        source_url = lead_data.get("source_url", "").lower()
        
        # High-quality directories (curated, reputable)
        high_quality = {
            "producthunt": 0.9,
            "betalist": 0.85,
            "indiehackers": 0.8,
            "yc": 0.95,  # Y Combinator
            "techstars": 0.9,
            "500startups": 0.85,
            "seedcamp": 0.8,
        }
        
        # Medium quality directories
        medium_quality = {
            "hackernews": 0.6,  # Mixed quality but good signal
            "devhunt": 0.7,
            "alternativeto": 0.75,
            "peerlist": 0.7,
            "uneed": 0.7,
        }
        
        # Low quality sources (to be avoided)
        low_quality = {
            "github": 0.2,  # Unless it's a specific project showcase
            "gitlab": 0.2,
            "medium": 0.3,  # Unless it's the company blog
        }
        
        # Check for exact provider match
        if source_provider in high_quality:
            return high_quality[source_provider]
        elif source_provider in medium_quality:
            return medium_quality[source_provider]
        elif source_provider in low_quality:
            return low_quality[source_provider]
        
        # Check URL patterns for directory quality
        if any(domain in source_url for domain in ["producthunt.com", "betalist.com", "indiehackers.com"]):
            return 0.8
        elif "ycombinator.com" in source_url or "yc.com" in source_url:
            return 0.95
        elif "techstars.com" in source_url:
            return 0.9
        elif "news.ycombinator.com" in source_url:
            return 0.6
        elif "github.com" in source_url:
            # Check if it looks like a company/product repo vs random code
            if any(word in source_url for word in ["company", "product", "app", "software"]):
                return 0.5  # Better than random repo
            else:
                return 0.2
        elif "medium.com" in source_url:
            # Check if it looks like a company publication
            if any(word in source_url for word in ["blog", "news", "press"]):
                return 0.4
            else:
                return 0.2  # Personal medium post
        
        # Default score for unknown sources
        return 0.5
    
    def _score_industry_relevance(self, lead_data: Dict[str, Any]) -> float:
        """Score based on relevance to target industries."""
        industry = lead_data.get("industry", "").lower()
        category = lead_data.get("category", "").lower()
        description = lead_data.get("description", "").lower()
        
        text_to_check = f"{industry} {category} {description}"
        
        # Check if in target industries
        if industry in self.target_industries:
            return 1.0
        
        # Check for industry keywords in description/category
        keyword_matches = 0
        total_keywords = 0
        
        for industry, keywords in self.INDICATORS.items():
            if industry in self.target_industries:
                for keyword in keywords:
                    total_keywords += 1
                    if keyword in text_to_check:
                        keyword_matches += 1
        
        if total_keywords > 0:
            relevance = keyword_matches / total_keywords
            # Boost if we found multiple matches
            if keyword_matches >= 3:
                relevance = min(1.0, relevance + 0.2)
            return relevance
        
        # Default score based on having some industry classification
        if industry or category:
            return 0.5  # Some classification is better than none
        else:
            return 0.3  # No industry info is less relevant
    
    def _generate_ai_summary(self, lead_data: Dict[str, Any], factors: Dict[str, float]) -> str:
        """Generate a brief AI summary of the lead."""
        name = lead_data.get("name", "Unknown startup")
        website = lead_data.get("website", "")
        description = lead_data.get("description", "")
        
        # Truncate description
        if description:
            desc_short = description[:100] + "..." if len(description) > 100 else description
        else:
            desc_short = "No description available"
        
        # Determine key strengths
        strengths = []
        if factors.get("startup_confidence", 0) >= 0.7:
            strengths.append("strong startup signals")
        if factors.get("contact_quality", 0) >= 0.7:
            strengths.append("excellent contact information")
        elif factors.get("contact_quality", 0) >= 0.4:
            strengths.append("available contact paths")
        if factors.get("website_quality", 0) >= 0.7:
            strengths.append("professional website")
        if factors.get("launch_freshness", 0) >= 0.8:
            strengths.append("recently launched")
        
        # Format summary
        if strengths:
            strength_text = ", ".join(strengths[:2])  # Top 2 strengths
            summary = f"{name} is a {strength_text}. {desc_short}"
        else:
            summary = f"{name} appears to be an early-stage startup. {desc_short}"
        
        # Limit length
        if len(summary) > 200:
            summary = summary[:197] + "..."
        
        return summary
    
    def _generate_outreach_recommendations(self, lead_data: Dict[str, Any], 
                                         factors: Dict[str, float], 
                                         startup_score: int) -> str:
        """Generate outreach recommendations for the lead."""
        name = lead_data.get("name", "this startup")
        emails = lead_data.get("emails", [])
        founders = lead_data.get("founders", [])
        
        recommendations = []
        
        # Overall advice based on score
        if startup_score >= 80:
            recommendations.append(f"High-priority target: {name} shows strong startup signals and good contact options.")
        elif startup_score >= 60:
            recommendations.append(f"Good prospect: {name} appears to be a legitimate startup with reasonable contact paths.")
        elif startup_score >= 40:
            recommendations.append(f"Moderate prospect: {name} shows some startup characteristics but may need further verification.")
        else:
            recommendations.append(f"Low priority: {name} has weak startup signals. Consider only if other factors are strong.")
        
        # Email-specific advice
        if emails:
            best_email = ""
            best_confidence = 0
            if lead_data.get("email_details"):
                best_email_obj = max(lead_data["email_details"], key=lambda x: x.get("confidence", 0))
                best_email = best_email_obj.get("email", "")
                best_confidence = best_email_obj.get("confidence", 0)
            elif emails:
                best_email = emails[0]
                best_confidence = 50  # Default
            
            if best_email:
                if "founder@" in best_email or "ceo@" in best_email:
                    recommendations.append(f"Best contact: Reach out directly to founder/CEO at {best_email}")
                elif "team@" in best_email or "hello@" in best_email:
                    recommendations.append(f"Good contact: Try the team email {best_email} for general inquiries")
                else:
                    recommendations.append(f"Available contact: {best_email} (confidence: {best_confidence}%)")
        else:
            recommendations.append("No contact emails found. Consider researching the company website for contact information.")
        
        # Founder-specific advice
        if founders:
            founder_names = [f.get("name", "") for f in founders if f.get("name")]
            if founder_names:
                if len(founder_names) == 1:
                    recommendations.append(f"Founder contact: Try to reach {founder_names[0]} directly via LinkedIn or email")
                else:
                    recommendations.append(f"Founding team: {', '.join(founder_names[:2])} appear to be the key contacts")
        
        # Website advice
        website = lead_data.get("website", "")
        if website:
            recommendations.append(f"Visit {website} for more information and additional contact options")
        
        # Format recommendations
        if recommendations:
            result = " ".join(recommendations[:3])  # Limit to top 3 recommendations
            if len(result) > 300:
                result = result[:297] + "..."
            return result
        else:
            return f"Research {name} further to determine best contact approach."
    
    def _get_legacy_defaults(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Return default legacy format scores on error."""
        return {
            "affordability_score": 0,
            "promo_video_fit_score": 0,
            "urgency_score": 0,
            "funding_probability": 0,
            "ai_summary": "Scoring failed - unable to evaluate this lead",
            "ai_reasoning": "{}",
            "outreach_recommendations": "Manual review recommended due to scoring error"
        }