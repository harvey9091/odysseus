# services/scraper/pipeline — Scrape pipeline orchestration
"""Pipeline: scrape → validate → extract → dedupe → score."""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Callable, Optional

from .providers import get_provider, PROVIDER_REGISTRY
from .extractors import EmailExtractor, FounderExtractor, SocialExtractor, MetadataExtractor
from .analyzers import VideoDetector, LeadScorer
from .storage import LeadStore
from .validators import LeadValidator

logger = logging.getLogger(__name__)


class ScraperPipeline:
    """Orchestrates: scrape → validate → extract contacts → dedupe → score."""

    def __init__(self, run_id: str, owner: str, progress_callback: Optional[Callable] = None):
        self.run_id = run_id
        self.owner = owner
        self.progress = progress_callback or (lambda x: None)
        self._cancelled = False

        self.validator = LeadValidator()
        self.email_extractor = EmailExtractor()
        self.founder_extractor = FounderExtractor()
        self.social_extractor = SocialExtractor()
        self.metadata_extractor = MetadataExtractor()
        self.video_detector = VideoDetector()
        self.lead_scorer = LeadScorer()
        self.store = LeadStore()

        # Cross-provider dedup within a single run
        self._run_seen_domains: set[str] = set()

    def cancel(self):
        self._cancelled = True

    async def run(self, providers: list[str], filters: dict):
        """
        Execute: scrape → validate → extract contacts → dedupe → score.

        New stages vs old:
        - validate: URL + content filtering (articles/platforms/non-startups)
        - domain_quality: score domains
        - cross_provider_dedup: skip duplicates found by earlier providers
        """
        total_leads = 0
        total_qualified = 0

        try:
            self.progress({"type": "log", "message": f"Starting scrape with providers: {', '.join(providers)}"})

            # Pre-load existing domain dedup cache from DB (avoid re-saving
            # startups that were already found in previous runs).
            try:
                existing_domains = self.store.get_all_active_domains()
                self._run_seen_domains.update(d.lower() for d in existing_domains if d)
                self.validator._domain_cache.update({d: 50 for d in self._run_seen_domains})
            except Exception:
                pass

            for provider_name in providers:
                if self._cancelled:
                    self.progress({"type": "warning", "message": "Run cancelled"})
                    break

                provider = get_provider(provider_name)
                if not provider:
                    self.progress({"type": "warning", "provider": provider_name,
                                   "message": f"Unknown provider: {provider_name}"})
                    continue

                self.progress({"type": "provider_update", "provider": provider_name, "status": "scraping"})

                try:
                    raw_results = await provider.scrape(filters, self.progress)
                    self.progress({
                        "type": "log",
                        "provider": provider_name,
                        "message": f"Scraped {len(raw_results)} raw results",
                    })

                    qualified = 0
                    skipped_article = 0
                    skipped_platform = 0
                    skipped_dup = 0
                    skipped_low_quality = 0

                    for result in raw_results:
                        if self._cancelled:
                            break

                        lead_data = result.to_dict()

                        # ── Stage 2: Validate lead quality ──
                        validation = self.validator.validate(lead_data)

                        if validation.is_article:
                            skipped_article += 1
                            self.progress({
                                "type": "log",
                                "provider": provider_name,
                                "message": f"Excluded (article): {lead_data.get('name', '?')}",
                            })
                            continue

                        if validation.is_platform_page:
                            skipped_platform += 1
                            continue

                        if not validation.is_valid:
                            skipped_low_quality += 1
                            self.progress({
                                "type": "log",
                                "provider": provider_name,
                                "message": f"Excluded (low quality): {lead_data.get('name', '?')} — {validation.rejection_reasons}",
                            })
                            continue

                        # Add validation metadata to lead
                        lead_data["domain_quality_score"] = validation.domain_quality_score
                        lead_data["startup_likelihood"] = validation.startup_likelihood
                        if validation.warnings:
                            lead_data["validation_warnings"] = validation.warnings

                        # ── Stage 2b: Cross-provider dedup ──
                        domain = (lead_data.get("domain") or "").lower()
                        if domain and domain in self._run_seen_domains:
                            skipped_dup += 1
                            continue
                        if domain:
                            self._run_seen_domains.add(domain)

                        # ── Stage 3: Video detection ──
                        if lead_data.get("website"):
                            try:
                                video_result = await self.video_detector.check(lead_data["website"])
                                if video_result["has_video"]:
                                    skipped_article += 0  # count as excluded but not article
                                    self.progress({
                                        "type": "log",
                                        "provider": provider_name,
                                        "message": f"Excluded (has video): {lead_data['name']}",
                                    })
                                    continue
                            except Exception:
                                pass

                        # ── Stage 4: Extract contacts + metadata ──
                        if lead_data.get("website"):
                            try:
                                emails_task = self.email_extractor.extract(lead_data["website"])
                                founders_task = self.founder_extractor.extract(
                                    lead_data["website"], lead_data.get("founders")
                                )
                                social_task = self.social_extractor.extract(lead_data["website"])
                                metadata_task = self.metadata_extractor.extract(lead_data["website"])

                                emails, founders, social, metadata = await asyncio.gather(
                                    emails_task, founders_task, social_task, metadata_task,
                                    return_exceptions=True,
                                )

                                if isinstance(emails, list):
                                    lead_data["emails"] = [
                                        e["email"] if isinstance(e, dict) else e for e in emails
                                    ]
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
                                    if metadata.get("og_image"):
                                        lead_data.setdefault("raw_data", {})["og_image"] = metadata["og_image"]
                            except Exception:
                                pass

                        # ── Stage 5: Store lead ──
                        lead = self.store.create_lead(self.run_id, lead_data, self.owner)
                        if lead:
                            total_leads += 1
                            qualified += 1
                            self.progress({
                                "type": "lead_found",
                                "provider": provider_name,
                                "lead": {"id": lead.id, "name": lead.name, "website": lead.website},
                            })

                            # ── Stage 6: AI scoring (optional) ──
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

                        # Rate limit between leads
                        await asyncio.sleep(0.3)

                    self.progress({
                        "type": "log",
                        "provider": provider_name,
                        "message": (
                            f"Pipeline: {qualified} qualified, "
                            f"{skipped_article} articles, {skipped_platform} platforms, "
                            f"{skipped_dup} dupes, {skipped_low_quality} low-quality"
                        ),
                    })

                except Exception as e:
                    logger.error(f"[{provider_name}] Pipeline error: {e}")
                    self.progress({
                        "type": "error",
                        "provider": provider_name,
                        "message": f"Error: {str(e)}",
                    })

                # Close provider
                try:
                    await provider.close()
                except Exception:
                    pass

                self.progress({"type": "provider_update", "provider": provider_name, "status": "done"})

            self.store.update_run_status(
                self.run_id, "completed",
                leads_found=total_leads,
                leads_qualified=total_qualified,
            )
            self.progress({
                "type": "completed",
                "stats": {
                    "leads_found": total_leads,
                    "leads_qualified": total_qualified,
                },
            })

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            self.store.update_run_status(self.run_id, "failed", error=str(e))
            self.progress({"type": "error", "message": f"Pipeline failed: {str(e)}"})
            raise
