"""Scraper Intelligence System routes — /api/scraper/*."""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ScraperStartRequest(BaseModel):
    source_url: str = Field(..., description="Directory URL or startup listing page to scrape")


class ScraperLeadUpdate(BaseModel):
    notes: Optional[str] = None
    tags: Optional[list[str]] = None


def setup_scraper_routes(scraper_service) -> APIRouter:
    """Create scraper API routes."""
    router = APIRouter(tags=["scraper"])

    # ─────────────────────────────────────────────────────────────────────
    # Run Management
    # ─────────────────────────────────────────────────────────────────────

    @router.post("/api/scraper/start")
    async def start_scrape(request: Request, body: ScraperStartRequest):
        """Start a new discovery scrape."""
        user = _get_user(request)
        result = scraper_service.start_run(source_url=body.source_url, owner=user)
        return result

    @router.post("/api/scraper/stop/{run_id}")
    async def stop_scrape(run_id: str, request: Request):
        """Stop a running scrape."""
        success = scraper_service.stop_run(run_id)
        if not success:
            raise HTTPException(404, "Run not found or not running")
        return {"status": "cancelled"}

    @router.get("/api/scraper/status/{run_id}")
    async def get_status(run_id: str, request: Request):
        """Get current run status."""
        status = scraper_service.get_status(run_id)
        if not status:
            raise HTTPException(404, "Run not found")
        return status

    @router.get("/api/scraper/stream/{run_id}")
    async def stream_progress(run_id: str, request: Request):
        """SSE stream for live scrape progress."""
        status = scraper_service.get_status(run_id)
        if not status:
            raise HTTPException(404, "Run not found")

        async def event_generator():
            entry = scraper_service._active_runs.get(run_id)
            last_event_count = 0

            while True:
                if await request.is_disconnected():
                    break

                current = scraper_service.get_status(run_id)
                if not current:
                    break

                if entry:
                    events = entry.get("progress_events", [])
                    new_events = events[last_event_count:]
                    for event in new_events:
                        yield f"data: {json.dumps(event)}\n\n"
                    last_event_count = len(events)

                if current.get("status") in ("completed", "failed", "cancelled"):
                    yield f"data: {json.dumps({'type': 'done', 'status': current.get('status')})}\n\n"
                    break

                await asyncio.sleep(0.5)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            }
        )

    @router.get("/api/scraper/active")
    async def get_active_runs(request: Request):
        """Get all active runs."""
        user = _get_user(request)
        runs = scraper_service.get_active_runs(owner=user)
        return {"runs": runs}

    # ─────────────────────────────────────────────────────────────────────
    # Leads
    # ─────────────────────────────────────────────────────────────────────

    @router.get("/api/scraper/leads")
    async def list_leads(
        request: Request,
        page: int = Query(1, ge=1),
        limit: int = Query(50, ge=1, le=200),
    ):
        """List leads with pagination."""
        user = _get_user(request)
        result = scraper_service.get_leads(owner=user, page=page, limit=limit)
        return result

    @router.get("/api/scraper/lead/{lead_id}")
    async def get_lead(lead_id: str, request: Request):
        """Get a single lead detail."""
        lead = scraper_service.get_lead(lead_id)
        if not lead:
            raise HTTPException(404, "Lead not found")
        return lead

    @router.delete("/api/scraper/lead/{lead_id}")
    async def delete_lead(lead_id: str, request: Request):
        """Delete a lead."""
        success = scraper_service.delete_lead(lead_id)
        if not success:
            raise HTTPException(404, "Lead not found")
        return {"status": "deleted"}

    @router.post("/api/scraper/lead/{lead_id}/archive")
    async def archive_lead(lead_id: str, request: Request):
        """Archive a lead."""
        success = scraper_service.archive_lead(lead_id)
        if not success:
            raise HTTPException(404, "Lead not found")
        return {"status": "archived"}

    @router.post("/api/scraper/lead/{lead_id}/contacted")
    async def mark_contacted_lead(lead_id: str, request: Request, body: dict):
        """Mark a lead as contacted or not contacted."""
        contacted = body.get("contacted", False)
        success = scraper_service.mark_contacted_lead(lead_id, contacted)
        if not success:
            raise HTTPException(404, "Lead not found")
        return {"status": "updated", "contacted": contacted}

    @router.post("/api/scraper/lead/{lead_id}/favorite")
    async def toggle_favorite_lead(lead_id: str, request: Request):
        """Toggle favorite status of a lead."""
        favorite = scraper_service.toggle_favorite_lead(lead_id)
        if favorite is None:
            raise HTTPException(404, "Lead not found")
        return {"status": "updated", "favorite": favorite}

    # ─────────────────────────────────────────────────────────────────────
    # History & Stats
    # ─────────────────────────────────────────────────────────────────────

    @router.get("/api/scraper/history")
    async def get_history(request: Request, limit: int = Query(50, ge=1, le=200)):
        """Get run history."""
        user = _get_user(request)
        history = scraper_service.get_history(owner=user, limit=limit)
        return {"runs": history}

    @router.get("/api/scraper/stats")
    async def get_stats(request: Request):
        """Get aggregate statistics."""
        user = _get_user(request)
        stats = scraper_service.get_stats(owner=user)
        return stats

    @router.get("/api/scraper/logs/{run_id}")
    async def get_logs(run_id: str, request: Request, limit: int = Query(500, ge=1, le=2000)):
        """Get logs for a run."""
        logs = scraper_service.get_logs(run_id, limit=limit)
        return {"logs": logs}

    # ─────────────────────────────────────────────────────────────────────
    # Export
    # ─────────────────────────────────────────────────────────────────────

    @router.get("/api/scraper/export")
    async def export_csv(request: Request):
        """Export leads to CSV."""
        from fastapi.responses import Response

        user = _get_user(request)
        csv_content = scraper_service.export_csv(owner=user)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=scraper_leads.csv"
            }
        )

    # ─────────────────────────────────────────────────────────────────────
    # Health Monitoring
    # ─────────────────────────────────────────────────────────────────────

    @router.get("/api/scraper/health")
    async def scraper_health(request: Request):
        """Get scraper health status and resource utilization."""
        health = scraper_service.health_check()
        return health

    @router.get("/api/scraper/resources")
    async def scraper_resources(request: Request):
        """Get current resource status (workers, browsers, queue)."""
        status = scraper_service.get_resource_status()
        return status

    @router.get("/api/scraper/metrics")
    async def scraper_metrics(request: Request):
        """Get live system metrics for the bottom bar."""
        metrics = scraper_service.get_system_metrics()
        user = _get_user(request)
        stats = scraper_service.get_stats(owner=user)
        active_runs = scraper_service.get_active_runs(owner=user)
        return {
            "cpu_percent": metrics.get("cpu_percent", 0),
            "ram_percent": metrics.get("ram_percent", 0),
            "active_workers": metrics.get("active_workers", 0),
            "max_workers": metrics.get("max_workers", 5),
            "total_leads": stats.get("total_leads", 0),
            "status": "running" if active_runs else "idle",
            "load_state": metrics.get("load_state", "normal"),
        }

    return router


def _get_user(request: Request) -> str:
    """Get current user from request, or default if auth disabled."""
    from src.auth_helpers import _auth_disabled, get_current_user

    user = get_current_user(request)
    if user:
        return user
    if _auth_disabled():
        return "default"
    raise HTTPException(401, "Not authenticated")