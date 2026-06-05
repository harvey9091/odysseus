"""LeadHunter routes — /api/leadhunter/*"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.auth_helpers import get_current_user
from services.leadhunter import LeadHunterService, get_lead_hunter_service

logger = logging.getLogger(__name__)


def setup_leadhunter_routes() -> APIRouter:
    router = APIRouter(tags=["leadhunter"])
    service = get_lead_hunter_service()

    class LeadQuery(BaseModel):
        query: str
        limit: Optional[int] = 20

    class ScoreRequest(BaseModel):
        leads: list
        min_score: Optional[int] = 70

    class SyncRequest(BaseModel):
        lead_ids: Optional[list] = None

    class CampaignRequest(BaseModel):
        campaign_id: Optional[str] = None

    class ExportRequest(BaseModel):
        lead_ids: Optional[list] = None
        format: Optional[str] = "csv"

    @router.post("/api/leadhunter/discover/producthunt")
    async def discover_producthunt(body: LeadQuery, request: Request):
        """Discover leads from Product Hunt."""
        get_current_user(request)
        leads = await service.discover_producthunt_leads(body.query, body.limit)
        return {"leads": [l.model_dump() for l in leads]}

    @router.post("/api/leadhunter/discover/beta")
    async def discover_beta(body: LeadQuery, request: Request):
        """Discover leads from beta platforms."""
        get_current_user(request)
        leads = await service.discover_beta_leads(body.query, body.limit)
        return {"leads": [l.model_dump() for l in leads]}

    @router.post("/api/leadhunter/score")
    async def score_leads(body: ScoreRequest, request: Request):
        """Score leads based on quality signals."""
        get_current_user(request)
        scored = service.score_leads(body.leads, body.min_score)
        return {"scored_leads": scored}

    @router.post("/api/leadhunter/sync")
    async def sync_leads(body: SyncRequest, request: Request):
        """Sync leads to Listmonk."""
        get_current_user(request)
        result = await service.sync_to_listmonk(body.lead_ids)
        return result

    @router.post("/api/leadhunter/metrics")
    async def get_metrics(body: CampaignRequest, request: Request):
        """Get campaign metrics."""
        get_current_user(request)
        metrics = await service.campaign_metrics(body.campaign_id)
        return {"metrics": metrics.model_dump()}

    @router.post("/api/leadhunter/export")
    async def export(body: ExportRequest, request: Request):
        """Export leads to CSV or JSON."""
        get_current_user(request)
        data = await service.export_leads(body.lead_ids, body.format)
        return {"data": data, "format": body.format}

    @router.get("/api/leadhunter/stats")
    async def get_stats(request: Request):
        """Get LeadHunter statistics."""
        get_current_user(request)
        return service.get_stats()

    @router.get("/api/leadhunter/leads")
    async def list_leads(request: Request, status: Optional[str] = None, limit: int = 50):
        """List leads, optionally filtered by status."""
        get_current_user(request)
        return {"leads": service.get_leads(status, limit)}

    return router