# services/scraper/pipeline — Scrape pipeline orchestration
"""Pipeline for scraping, filtering, extraction, and scoring."""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Callable, Optional

from .providers import get_provider, PROVIDER_REGISTRY
from .extractors import EmailExtractor, FounderExtractor, SocialExtractor, MetadataExtractor
from .analyzers import VideoDetector, LeadScorer
from .storage import LeadStore

logger = logging.getLogger(__name__)


class ScraperPipeline:
    """Orchestrates the full scrape -> filter -> extract -> score pipeline."""

    def __init__(self, run_id: str, owner: str, progress_callback: Optional[Callable] = None):
        self.run_id = run_id
        self.owner = owner
        self.progress = progress_callback or (lambda x: None)
        self._cancelled = False

        # Components
        self.email_extractor = EmailExtractor()
        self.founder_extractor = FounderExtractor()
        self.social_extractor = SocialExtractor()
        self.metadata_extractor = MetadataExtractor()
        self.video_detector = VideoDetector()
        self.lead_scorer = LeadScorer()
        self.store = LeadStore()

    def cancel(self):
        """Cancel the pipeline."""
        self._cancelled = True

    async def run(self, providers: list[str], filters: dict):
        """
        Execute the full pipeline.

        Pipeline stages:
        1. Scrape providers for raw leads
        2. Filter out leads with existing videos
        3. Extract contact info (emails, founders, social)
        4. AI-powered lead scoring
        """
        total_leads = 0
        total_qualified = 0

        try:
            self.progress({"type": "log", "message": f"Starting scrape run with providers: {', '.join(providers)}"})

            # Stage 1: Scrape providers
            for provider_name in providers:
                if self._cancelled:
                    self.progress({"type": "warning", "message": "Run cancelled"})
                    break

                provider = get_provider(provider_name)
                if not provider:
                    self.progress({"type": "warning", "provider": provider_name, "message": f"Unknown provider: {provider_name}"})
                    continue

                self.progress({"type": "provider_update", "provider": provider_name, "status": "scraping"})

                try:
                    results = await provider.scrape(filters, self.progress)
                    self.progress({"type": "log", "provider": provider_name, "message": f"Scraped {len(results)} raw leads"})

                    # Stage 2 & 3: Process each lead
                    for result in results:
                        if self._cancelled:
                            break

                        lead_data = result.to_dict()

                        # Check for existing video
                        if lead_data.get("website"):
                            video_result = await self.video_detector.check(lead_data["website"])
                            if video_result["has_video"]:
                                self.progress({
                                    "type": "log",
                                    "provider": provider_name,
                                    "message": f"Excluded (has video): {lead_data['name']}"
                                })
                                continue

                        # Extract additional data
                        if lead_data.get("website"):
                            # Run extractors in parallel
                            emails_task = self.email_extractor.extract(lead_data["website"])
                            founders_task = self.founder_extractor.extract(lead_data["website"], lead_data.get("founders"))
                            social_task = self.social_extractor.extract(lead_data["website"])
                            metadata_task = self.metadata_extractor.extract(lead_data["website"])

                            emails, founders, social, metadata = await asyncio.gather(
                                emails_task, founders_task, social_task, metadata_task,
                                return_exceptions=True
                            )

                            # Merge extracted data
                            if isinstance(emails, list):
                                lead_data["emails"] = [e["email"] if isinstance(e, dict) else e for e in emails]
                            if isinstance(founders, list):
                                lead_data["founders"] = founders
                            if isinstance(social, dict):
                                lead_data["social"] = social
                            if isinstance(metadata, dict):
                                if metadata.get("tech_stack"):
                                    lead_data["tech_stack"] = metadata["tech_stack"]
                                if metadata.get("pricing_model"):
                                    lead_data["pricing_model"] = metadata["pricing_model"]
                                if metadata.get("description") and not lead_data.get("description"):
                                    lead_data["description"] = metadata["description"]

                        # Store the lead
                        lead = self.store.create_lead(self.run_id, lead_data, self.owner)
                        if lead:
                            total_leads += 1
                            self.progress({
                                "type": "lead_found",
                                "provider": provider_name,
                                "lead": {"id": lead.id, "name": lead.name, "website": lead.website}
                            })

                            # Stage 4: AI scoring (optional, if configured)
                            if self.lead_scorer._llm_endpoint:
                                try:
                                    scores = await self.lead_scorer.score(lead_data)
                                    self.store.update_lead_scores(lead.id, scores)
                                    total_qualified += 1
                                    self.progress({
                                        "type": "lead_scored",
                                        "lead_id": lead.id,
                                        "name": lead.name,
                                        "affordability_score": scores.get("affordability_score"),
                                    })
                                except Exception as e:
                                    logger.warning(f"Scoring failed for {lead.name}: {e}")

                        # Small delay between leads
                        await asyncio.sleep(0.5)

                except Exception as e:
                    logger.error(f"[{provider_name}] Pipeline error: {e}")
                    self.progress({
                        "type": "error",
                        "provider": provider_name,
                        "message": f"Error: {str(e)}"
                    })

                # Close provider session
                try:
                    await provider.close()
                except Exception:
                    pass

                self.progress({"type": "provider_update", "provider": provider_name, "status": "done"})

            # Update run with totals
            self.store.update_run_status(
                self.run_id,
                "completed",
                leads_found=total_leads,
                leads_qualified=total_qualified
            )

            self.progress({
                "type": "completed",
                "stats": {
                    "leads_found": total_leads,
                    "leads_qualified": total_qualified,
                }
            })

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            self.store.update_run_status(self.run_id, "failed", error=str(e))
            self.progress({"type": "error", "message": f"Pipeline failed: {str(e)}"})
            raise
