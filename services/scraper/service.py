# services/scraper/service — Main ScraperService
"""Main service orchestrating scraper operations."""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, Optional

from .pipeline import ScraperPipeline
from .providers import PROVIDER_REGISTRY, get_provider, get_all_providers
from .storage import LeadStore
from .analyzers import LeadScorer

logger = logging.getLogger(__name__)


class ScraperService:
    """Main service for scraper operations."""

    def __init__(self):
        self._active_runs: Dict[str, dict] = {}
        self._lead_scorer = LeadScorer()
        self.store = LeadStore()

    def configure_llm(self, endpoint: str, model: str):
        """Configure LLM for lead scoring."""
        self._lead_scorer.configure(endpoint, model)

    # ─────────────────────────────────────────────────────────────────────
    # Run Management
    # ─────────────────────────────────────────────────────────────────────

    def start_run(self, providers: list[str], filters: dict, owner: str) -> dict:
        """Start a new scraping run. Returns run info dict."""
        run_id = str(uuid.uuid4())

        # Validate providers
        valid_providers = [p for p in providers if p in PROVIDER_REGISTRY]
        if not valid_providers:
            valid_providers = ["hackernews"]  # Default fallback

        # Create run in DB
        self.store.create_run(run_id, valid_providers, filters, owner)

        # Track in memory
        entry = {
            "run_id": run_id,
            "status": "running",
            "providers": valid_providers,
            "filters": filters,
            "owner": owner,
            "started_at": datetime.utcnow().isoformat(),
            "progress_events": [],
            "pipeline": None,
            "task": None,
        }
        self._active_runs[run_id] = entry

        # Progress callback
        def on_progress(event: dict):
            entry["progress_events"].append({
                **event,
                "timestamp": datetime.utcnow().isoformat()
            })
            # Keep only last 500 events in memory
            if len(entry["progress_events"]) > 500:
                entry["progress_events"] = entry["progress_events"][-500:]

        # Create and start pipeline
        pipeline = ScraperPipeline(run_id, owner, on_progress)
        entry["pipeline"] = pipeline

        # Configure LLM if available
        if self._lead_scorer._llm_endpoint:
            pipeline.lead_scorer.configure(
                self._lead_scorer._llm_endpoint,
                self._lead_scorer._llm_model
            )

        # Run in background
        async def _run():
            try:
                self.store.update_run_status(run_id, "running")
                await pipeline.run(valid_providers, filters)
                entry["status"] = "completed"
            except asyncio.CancelledError:
                entry["status"] = "cancelled"
                self.store.update_run_status(run_id, "cancelled")
            except Exception as e:
                entry["status"] = "failed"
                entry["error"] = str(e)
                self.store.update_run_status(run_id, "failed", error=str(e))

        task = asyncio.create_task(_run())
        entry["task"] = task

        logger.info(f"Started scraper run {run_id} with providers: {valid_providers}")

        return {
            "run_id": run_id,
            "status": "running",
            "providers": valid_providers,
        }

    def stop_run(self, run_id: str) -> bool:
        """Stop a running scrape."""
        entry = self._active_runs.get(run_id)
        if not entry or entry["status"] != "running":
            return False

        # Cancel pipeline
        pipeline = entry.get("pipeline")
        if pipeline:
            pipeline.cancel()

        # Cancel task
        task = entry.get("task")
        if task and not task.done():
            task.cancel()

        entry["status"] = "cancelled"
        return True

    def get_status(self, run_id: str) -> Optional[dict]:
        """Get current run status."""
        # Check in-memory first
        entry = self._active_runs.get(run_id)
        if entry:
            return {
                "run_id": run_id,
                "status": entry["status"],
                "providers": entry.get("providers", []),
                "started_at": entry.get("started_at"),
                "progress_events": entry.get("progress_events", [])[-100:],  # Last 100
            }

        # Check DB
        run = self.store.get_run(run_id)
        if run:
            return {
                "run_id": run.id,
                "status": run.status,
                "providers": run.providers,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "leads_found": run.leads_found,
                "leads_qualified": run.leads_qualified,
                "error": run.error,
            }
        return None

    def get_active_runs(self, owner: Optional[str] = None) -> list:
        """Get all active runs."""
        active = []
        for run_id, entry in self._active_runs.items():
            if entry["status"] == "running":
                if owner is None or entry.get("owner") == owner:
                    active.append({
                        "run_id": run_id,
                        "status": entry["status"],
                        "providers": entry.get("providers", []),
                        "started_at": entry.get("started_at"),
                    })
        return active

    # ─────────────────────────────────────────────────────────────────────
    # Leads
    # ─────────────────────────────────────────────────────────────────────

    def get_leads(self, owner: Optional[str] = None, **filters) -> dict:
        """Get leads with filtering and pagination."""
        return self.store.list_leads(owner=owner, **filters)

    def get_lead(self, lead_id: str) -> Optional[dict]:
        """Get a single lead."""
        lead = self.store.get_lead(lead_id)
        if lead:
            return self.store._lead_to_dict(lead)
        return None

    def delete_lead(self, lead_id: str) -> bool:
        """Delete a lead."""
        from core.database import get_db_session, ScraperLead
        with get_db_session() as db:
            lead = db.query(ScraperLead).filter(ScraperLead.id == lead_id).first()
            if lead:
                db.delete(lead)
                db.commit()
                return True
        return False

    # ─────────────────────────────────────────────────────────────────────
    # Providers
    # ─────────────────────────────────────────────────────────────────────

    def get_providers(self) -> list:
        """Get list of available providers."""
        return [
            {
                "name": name,
                "enabled": True,
                "info": cls().get_info()
            }
            for name, cls in PROVIDER_REGISTRY.items()
        ]

    # ─────────────────────────────────────────────────────────────────────
    # History & Stats
    # ─────────────────────────────────────────────────────────────────────

    def get_history(self, owner: Optional[str] = None, limit: int = 50) -> list:
        """Get run history."""
        runs = self.store.list_runs(owner=owner, limit=limit)
        return [
            {
                "id": run.id,
                "status": run.status,
                "providers": run.providers,
                "filters": run.filters,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "leads_found": run.leads_found,
                "leads_qualified": run.leads_qualified,
                "error": run.error,
            }
            for run in runs
        ]

    def get_stats(self, owner: Optional[str] = None) -> dict:
        """Get aggregate statistics."""
        return self.store.get_stats(owner=owner)

    def get_logs(self, run_id: str, limit: int = 500) -> list:
        """Get logs for a run."""
        return self.store.get_logs(run_id, limit=limit)

    # ─────────────────────────────────────────────────────────────────────
    # Export
    # ─────────────────────────────────────────────────────────────────────

    def export_csv(self, owner: Optional[str] = None, **filters) -> str:
        """Export leads to CSV."""
        import csv
        import io

        leads_data = self.store.list_leads(owner=owner, **filters)
        leads = leads_data.get("leads", [])

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            "name", "website", "domain", "description", "category",
            "source_provider", "launch_date", "emails", "founders",
            "affordability_score", "promo_video_fit_score", "ai_summary"
        ])
        writer.writeheader()

        for lead in leads:
            row = {
                "name": lead.get("name", ""),
                "website": lead.get("website", ""),
                "domain": lead.get("domain", ""),
                "description": lead.get("description", "")[:200],
                "category": lead.get("category", ""),
                "source_provider": lead.get("source_provider", ""),
                "launch_date": lead.get("launch_date", ""),
                "emails": ", ".join(lead.get("emails", [])),
                "founders": ", ".join([f.get("name", "") for f in lead.get("founders", [])]),
                "affordability_score": lead.get("affordability_score", ""),
                "promo_video_fit_score": lead.get("promo_video_fit_score", ""),
                "ai_summary": lead.get("ai_summary", "")[:200],
            }
            writer.writerow(row)

        return output.getvalue()
