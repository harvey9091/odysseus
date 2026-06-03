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
    providers: list[str] = Field(default_factory=lambda: ["hackernews"])
    filters: dict = Field(default_factory=dict)


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
        """Start a new scraping run."""
        user = _get_user(request)
        result = scraper_service.start_run(
            providers=body.providers,
            filters=body.filters,
            owner=user,
        )
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
            # Get the in-memory entry for progress events
            entry = scraper_service._active_runs.get(run_id)
            last_event_count = 0

            while True:
                # Check if request was cancelled
                if await request.is_disconnected():
                    break

                # Get current status
                current = scraper_service.get_status(run_id)
                if not current:
                    break

                # Emit new progress events
                if entry:
                    events = entry.get("progress_events", [])
                    new_events = events[last_event_count:]
                    for event in new_events:
                        yield f"data: {json.dumps(event)}\n\n"
                    last_event_count = len(events)

                # Check if run is complete
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
        min_score: Optional[int] = Query(None, ge=0, le=100),
        provider: Optional[str] = Query(None),
        exclude_with_video: bool = Query(True),
    ):
        """List leads with filtering and pagination."""
        user = _get_user(request)
        result = scraper_service.get_leads(
            owner=user,
            page=page,
            limit=limit,
            min_score=min_score,
            provider=provider,
            exclude_with_video=exclude_with_video,
        )
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

    # ─────────────────────────────────────────────────────────────────────
    # Providers
    # ─────────────────────────────────────────────────────────────────────

    @router.get("/api/scraper/providers")
    async def list_providers(request: Request):
        """List available scraper providers."""
        providers = scraper_service.get_providers()
        return {"providers": providers}

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
    async def export_csv(
        request: Request,
        min_score: Optional[int] = Query(None, ge=0, le=100),
        provider: Optional[str] = Query(None),
    ):
        """Export leads to CSV."""
        from fastapi.responses import Response

        user = _get_user(request)
        csv_content = scraper_service.export_csv(
            owner=user,
            min_score=min_score,
            provider=provider,
        )
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=scraper_leads.csv"
            }
        )

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
