"""Lead Sources — abstraction layer for external lead providers."""

import logging
from typing import List, Dict, Any

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from backend.providers.leads.base_provider import LeadProvider, Lead
from backend.providers.leads.mock_provider import MockLeadProvider

logger = logging.getLogger(__name__)

REGISTERED_PROVIDERS: List[LeadProvider] = [MockLeadProvider()]


class LeadQuery(BaseModel):
    query: str | None = None
    limit: int = 50


def setup_leads_routes() -> APIRouter:
    router = APIRouter(tags=["leads"])

    @router.get("/api/leads/providers")
    async def list_providers(request: Request) -> Dict[str, Any]:
        return {
            "providers": [
                {
                    "name": p.get_provider_name(),
                    "enabled": p.is_enabled,
                }
                for p in REGISTERED_PROVIDERS
            ]
        }

    @router.post("/api/leads/test")
    async def get_test_leads(request: Request, body: LeadQuery | None = None) -> Dict[str, Any]:
        body = body or LeadQuery()
        provider = next((p for p in REGISTERED_PROVIDERS if p.get_provider_name() == "mock"), None)
        if provider is None:
            raise HTTPException(500, "MockLeadProvider is not registered")
        leads = await provider.fetch_leads(query=body.query, limit=body.limit)
        valid = [lead for lead in leads if provider.validate_lead(lead)]
        return {
            "provider": provider.get_provider_name(),
            "query": body.query,
            "requested": body.limit,
            "returned": len(valid),
            "leads": [lead.model_dump() for lead in valid],
        }

    return router
