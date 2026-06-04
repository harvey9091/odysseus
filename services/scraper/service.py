# services/scraper/service — Generic Discovery Agent Service
"""Main service orchestrating Generic Discovery Agent operations."""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, Optional

from .discovery_agent import DiscoveryAgent
from .storage import LeadStore

logger = logging.getLogger(__name__)


class ScraperService:
    """Service for Generic Discovery Agent scraper operations."""

    def __init__(self):
        self._active_runs: Dict[str, dict] = {}
        self._agent = DiscoveryAgent(headless=True, timeout=30)
        self.store = LeadStore()

    # ─────────────────────────────────────────────────────────────────────
    # Run Management
    # ─────────────────────────────────────────────────────────────────────

    def start_run(self, source_url: str, owner: str) -> dict:
        """Start a new discovery run. Returns run info dict."""
        run_id = str(uuid.uuid4())

        # Validate URL
        if not source_url or not self._is_valid_url(source_url):
            return {"error": "Invalid source URL provided", "run_id": None}

        # Create run in DB
        self.store.create_run(run_id, ["discovery_agent"], {"source_url": source_url}, owner)

        # Track in memory
        entry = {
            "run_id": run_id,
            "status": "running",
            "source_url": source_url,
            "owner": owner,
            "started_at": datetime.utcnow().isoformat(),
            "progress_events": [],
            "task": None,
        }
        self._active_runs[run_id] = entry

        # Progress callback
        def on_progress(event: dict):
            entry["progress_events"].append({
                **event,
                "timestamp": datetime.utcnow().isoformat()
            })
            if len(entry["progress_events"]) > 500:
                entry["progress_events"] = entry["progress_events"][-500:]

        # Run in background
        async def _run():
            try:
                self.store.update_run_status(run_id, "running")
                await self._execute_discovery(run_id, source_url, on_progress)
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

        logger.info(f"Started discovery run {run_id} from {source_url}")
        return {"run_id": run_id, "status": "running", "source_url": source_url}

    def stop_run(self, run_id: str) -> bool:
        """Stop a running discovery."""
        entry = self._active_runs.get(run_id)
        if not entry or entry["status"] != "running":
            return False

        task = entry.get("task")
        if task and not task.done():
            task.cancel()

        entry["status"] = "cancelled"
        return True

    def get_status(self, run_id: str) -> Optional[dict]:
        """Get current run status."""
        entry = self._active_runs.get(run_id)
        if entry:
            return {
                "run_id": run_id,
                "status": entry["status"],
                "source_url": entry.get("source_url"),
                "started_at": entry.get("started_at"),
                "progress_events": entry.get("progress_events", [])[-100:],
            }

        run = self.store.get_run(run_id)
        if run:
            return {
                "run_id": run.id,
                "status": run.status,
                "source_url": run.filters.get("source_url") if run.filters else None,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "leads_found": run.leads_found,
            }
        return None

    def get_active_runs(self, owner: Optional[str] = None) -> list:
        """Get all active runs."""
        return [
            {"run_id": run_id, "status": entry["status"], "source_url": entry.get("source_url")}
            for run_id, entry in self._active_runs.items()
            if entry["status"] == "running" and (owner is None or entry.get("owner") == owner)
        ]

    async def _execute_discovery(self, run_id: str, source_url: str, progress_callback):
        """Execute the discovery pipeline."""
        progress_callback({"type": "log", "message": f"Starting Generic Discovery Agent..."})

        leads = await self._agent.discover(source_url, progress_callback)

        stored_count = 0
        for lead in leads:
            lead_data = lead.to_dict()
            stored_lead = self.store.create_lead(run_id, lead_data, "discovery_agent run")
            if stored_lead:
                stored_count += 1
                progress_callback({
                    "type": "lead_found",
                    "name": lead.company_name,
                    "website": lead.website,
                    "emails": len(lead.emails)
                })

        self.store.update_run_status(run_id, "completed", leads_found=stored_count)
        progress_callback({"type": "completed", "stats": {"stored_leads": stored_count}})

    def _is_valid_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            return bool(parsed.scheme and parsed.netloc)
        except Exception:
            return False

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

    def archive_lead(self, lead_id: str) -> bool:
        """Archive a lead."""
        from core.database import get_db_session, ScraperLead
        with get_db_session() as db:
            lead = db.query(ScraperLead).filter(ScraperLead.id == lead_id).first()
            if lead:
                lead.excluded = True
                lead.exclude_reason = "Manually archived"
                db.commit()
                return True
        return False

    def mark_contacted_lead(self, lead_id: str, contacted: bool) -> bool:
        """Mark a lead as contacted."""
        from core.database import get_db_session, ScraperLead
        with get_db_session() as db:
            lead = db.query(ScraperLead).filter(ScraperLead.id == lead_id).first()
            if lead:
                lead.contacted = contacted
                db.commit()
                return True
        return False

    def toggle_favorite_lead(self, lead_id: str) -> Optional[bool]:
        """Toggle favorite status."""
        from core.database import get_db_session, ScraperLead
        with get_db_session() as db:
            lead = db.query(ScraperLead).filter(ScraperLead.id == lead_id).first()
            if lead:
                lead.favorite = not lead.favorite
                db.commit()
                return lead.favorite
        return None

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
        fieldnames = [
            "company_name", "website", "description", "founders", "emails",
            "linkedin", "twitter", "github", "contact_page", "industry", "source_url", "discovery_date"
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for lead in leads:
            row = {
                "company_name": lead.get("name", ""),
                "website": lead.get("website", ""),
                "description": lead.get("description", "")[:300],
                "founders": ", ".join(f.get("name", "") for f in lead.get("founders", [])),
                "emails": ", ".join(lead.get("emails", [])),
                "linkedin": lead.get("social", {}).get("linkedin", ""),
                "twitter": lead.get("social", {}).get("twitter", ""),
                "github": lead.get("social", {}).get("github", ""),
                "contact_page": lead.get("contact_page", ""),
                "industry": lead.get("industry", ""),
                "source_url": lead.get("source_url", ""),
                "discovery_date": lead.get("launch_date", lead.get("created_at", "")),
            }
            writer.writerow(row)

        return output.getvalue()


# Backward compatibility
ScraperPipeline = None