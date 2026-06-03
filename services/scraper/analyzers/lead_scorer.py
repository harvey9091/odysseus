# services/scraper/analyzers/lead_scorer — AI-powered lead scoring
"""AI-powered lead qualification and scoring using Odysseus LLM systems."""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Scoring prompt for AI lead qualification
SCORING_PROMPT = """You are a B2B sales intelligence expert specializing in startup analysis for video production services.

Analyze this startup and provide a JSON scoring result. Your goal is to determine:
1. Can they realistically afford $2000+ for a promo video?
2. Would they benefit from a professional promo video?
3. Are they a high-quality outreach lead?

STARTUP DATA:
Name: {name}
Website: {website}
Description: {description}
Category: {category}
Pricing Model: {pricing_model}
Tech Stack: {tech_stack}
Launch Date: {launch_date}
Founders: {founders}

Provide your analysis as a JSON object with these fields:
{{
  "affordability_score": <0-100>,
  "promo_video_fit_score": <0-100>,
  "urgency_score": <0-100>,
  "funding_probability": <0-100>,
  "summary": "<2-3 sentence executive summary>",
  "reasoning": "<detailed explanation of scores>",
  "outreach_recommendations": "<specific suggestions for approaching this lead>"
}}

Scoring guidelines:
- affordability_score: Based on pricing model, tech sophistication, team size signals
- promo_video_fit_score: Based on whether they likely need video marketing (B2B SaaS scores higher)
- urgency_score: Based on recency of launch, growth signals
- funding_probability: Based on maturity, pricing, team signals

Be realistic and conservative. Not every startup can afford $2000+ videos.
Return ONLY the JSON object, no markdown, no additional text."""


class LeadScorer:
    """AI-powered lead qualification and scoring."""

    def __init__(self):
        self._llm_endpoint = None
        self._llm_model = None

    def configure(self, endpoint: str, model: str):
        """Configure the LLM endpoint for scoring."""
        self._llm_endpoint = endpoint
        self._llm_model = model

    async def score(self, lead_data: dict) -> dict:
        """
        Score a lead using AI analysis.

        Args:
            lead_data: Dict with name, website, description, etc.

        Returns:
            Dict with affordability_score, promo_video_fit_score, etc.
        """
        default_scores = {
            "affordability_score": None,
            "promo_video_fit_score": None,
            "urgency_score": None,
            "funding_probability": None,
            "ai_summary": None,
            "ai_reasoning": None,
            "outreach_recommendations": None,
        }

        if not self._llm_endpoint or not self._llm_model:
            logger.warning("LeadScorer not configured with LLM endpoint")
            return default_scores

        try:
            # Build the prompt
            prompt = SCORING_PROMPT.format(
                name=lead_data.get("name", "Unknown"),
                website=lead_data.get("website", "N/A"),
                description=lead_data.get("description", "N/A"),
                category=lead_data.get("category", "N/A"),
                pricing_model=lead_data.get("pricing_model", "N/A"),
                tech_stack=", ".join(lead_data.get("tech_stack", [])) or "N/A",
                launch_date=lead_data.get("launch_date", "N/A"),
                founders=json.dumps(lead_data.get("founders", [])) or "N/A",
            )

            # Call LLM using Odysseus stream_llm
            from src.llm_core import stream_llm

            response_text = ""
            async for chunk in stream_llm(
                endpoint_url=self._llm_endpoint,
                model=self._llm_model,
                messages=[{"role": "user", "content": prompt}],
                stream=False,
            ):
                if isinstance(chunk, dict) and chunk.get("content"):
                    response_text += chunk["content"]
                elif isinstance(chunk, str):
                    response_text += chunk

            # Parse JSON response
            # Strip markdown code fences if present
            response_text = response_text.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

            scores = json.loads(response_text)

            # Validate and normalize scores
            result = default_scores.copy()
            for key in default_scores:
                if key in scores:
                    if key.endswith("_score") or key == "funding_probability":
                        # Ensure score is 0-100 integer
                        try:
                            val = int(scores[key])
                            result[key] = max(0, min(100, val))
                        except (ValueError, TypeError):
                            pass
                    else:
                        result[key] = str(scores[key])[:2000]  # Limit text length

            return result

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse AI scoring response: {e}")
            return default_scores
        except Exception as e:
            logger.error(f"Lead scoring failed: {e}")
            return default_scores
