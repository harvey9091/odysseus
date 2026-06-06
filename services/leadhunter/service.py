# services/leadhunter/service.py
"""LeadHunter service — lead discovery, scoring, and Listmonk sync."""

import asyncio
import httpx
import logging
import os
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .repository import LeadModel

logger = logging.getLogger(__name__)


class LeadStatus(str):
    NEW = "new"
    QUALIFIED = "qualified"
    SYNCED = "synced"
    REJECTED = "rejected"


class LeadScore(BaseModel):
    score: int = Field(ge=0, le=100, description="Lead score 0-100")
    reason: str = ""
    qualified: bool = False


class Lead(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    source: str
    url: Optional[str] = None
    metadata: Dict[str, Any] = {}
    status: str = LeadStatus.NEW
    score: Optional[int] = None
    score_reason: Optional[str] = None
    enrichment_status: Optional[str] = None
    campaign_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CampaignMetrics(BaseModel):
    emails_sent: int = 0
    opens: int = 0
    clicks: int = 0
    open_rate: float = 0.0
    click_rate: float = 0.0
    bounce_rate: float = 0.0


class LeadHunterService:
    def __init__(self):
        self._initialized = False
        self._repository = None
        self._listmonk_list_id = None
        self._sync_logs: List[Dict] = []

    async def initialize(self) -> None:
        from .repository import LeadHunterRepository
        self._repository = LeadHunterRepository()
        self._repository.create_tables()
        self._listmonk_list_id = int(os.getenv("LISTMONK_LIST_ID", "1"))
        self._initialized = True
        logger.info("LeadHunter service initialized")

    async def shutdown(self) -> None:
        self._initialized = False

    def _ensure_initialized(self):
        if not self._initialized or not self._repository:
            raise RuntimeError("LeadHunter service not initialized")

    def _lead_to_dict(self, lead: Lead) -> Dict[str, Any]:
        result = lead.model_dump()
        result["created_at"] = lead.created_at.isoformat() if lead.created_at else None
        return result

    def _get_listmonk_auth(self) -> tuple:
        """Get Listmonk auth credentials. Returns (auth_type, creds)."""
        url = os.getenv("LISTMONK_URL", "")
        api_key = os.getenv("LISTMONK_API_KEY", "")
        username = os.getenv("LISTMONK_USERNAME", "")
        password = os.getenv("LISTMONK_PASSWORD", "")
        if api_key:
            return ("api_key", api_key)
        elif username and password:
            return ("basic", (username, password))
        return (None, None)

    async def _fetch_producthunt_leads(self, query: str, limit: int = 20) -> List[Lead]:
        leads = []
        for i in range(limit):
            leads.append(Lead(
                id=f"ph-{query.lower().replace(' ', '-')}-{i+1:03d}",
                name=f"Product Hunt Founder {i+1}",
                email=f"founder{i+1}@example.com",
                company=f"{query.title()} Startup {i+1}",
                title="Founder / CEO",
                source="producthunt",
                url=f"https://producthunt.com/products/{query.lower().replace(' ', '-')}-{i+1}",
                metadata={"query": query, "rank": i+1, "upvotes": 100 - i * 5},
            ))
        return leads

    async def _fetch_beta_leads(self, query: str, limit: int = 20) -> List[Lead]:
        leads = []
        for i in range(limit):
            leads.append(Lead(
                id=f"beta-{query.lower().replace(' ', '-')}-{i+1:03d}",
                name=f"Beta User {i+1}",
                email=f"beta{i+1}@example.com",
                company=f"{query.title()} Beta {i+1}",
                title="Early Adopter",
                source="beta",
                url=f"https://beta-list.com/{query.lower().replace(' ', '-')}-{i+1}",
                metadata={"query": query, "platform": "beta-list", "signup_date": "2024-01-01"},
            ))
        return leads

    async def discover_producthunt_leads(self, query: str, limit: int = 20) -> List[Lead]:
        self._ensure_initialized()
        leads = await self._fetch_producthunt_leads(query, limit)
        for lead in leads:
            if not self._repository.get_lead(lead.id):
                self._repository.create_lead(self._lead_to_dict(lead))
        return leads

    async def discover_beta_leads(self, query: str, limit: int = 20) -> List[Lead]:
        self._ensure_initialized()
        leads = await self._fetch_beta_leads(query, limit)
        for lead in leads:
            if not self._repository.get_lead(lead.id):
                self._repository.create_lead(self._lead_to_dict(lead))
        return leads

    def score_leads(self, leads: List[Dict], min_score: int = 70) -> List[Dict]:
        self._ensure_initialized()
        scored = []
        for lead in leads:
            score_val = 0
            reason_parts = []

            if lead.get("email"):
                score_val += 20
                reason_parts.append("has email")

            if lead.get("company"):
                score_val += 15
                reason_parts.append("has company")

            if lead.get("title") and any(t in str(lead.get("title", "")).lower() for t in ["founder", "ceo", "cto", "lead", "head", "vp"]):
                score_val += 25
                reason_parts.append("decision maker")

            metadata = lead.get("metadata", {})
            if metadata.get("upvotes", 0) > 50:
                score_val += 20
                reason_parts.append("high engagement")

            if metadata.get("upvotes", 0) > 100:
                score_val += 10
                reason_parts.append("viral traction")

            is_qualified = score_val >= min_score
            if is_qualified:
                score_val = min(100, score_val + 10)

            scored_lead = {
                **lead,
                "score": score_val,
                "score_reason": "; ".join(reason_parts) if reason_parts else "basic lead",
                "status": LeadStatus.QUALIFIED if is_qualified else LeadStatus.NEW,
            }

            if lead.get("id"):
                self._repository.update_lead(lead["id"], {
                    "score": score_val,
                    "score_reason": "; ".join(reason_parts) if reason_parts else "basic lead",
                    "status": LeadStatus.QUALIFIED if is_qualified else LeadStatus.NEW,
                })

            scored.append(scored_lead)

        return scored

    async def _listmonk_lookup_subscriber(self, email: str) -> Optional[Dict]:
        """Look up existing subscriber by email in Listmonk."""
        url = os.getenv("LISTMONK_URL", "")
        if not url:
            return None

        auth_type, creds = self._get_listmonk_auth()
        headers = {"Content-Type": "application/json"}
        if auth_type == "api_key":
            headers["Authorization"] = f"Bearer {creds}"

        request_auth = None
        if auth_type == "basic":
            request_auth = httpx.BasicAuth(creds[0], creds[1])

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{url.rstrip('/')}/api/v1/subscribers",
                    params={"query": email},
                    headers=headers,
                    auth=request_auth,
                )
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("data", {}).get("results", [])
                    if results:
                        return results[0]
        except Exception as e:
            logger.warning(f"Listmonk subscriber lookup failed: {e}")
        return None

    async def _listmonk_create_subscriber(self, lead: LeadModel, retry_count: int = 3) -> Optional[int]:
        """Create subscriber in Listmonk with retry handling."""
        url = os.getenv("LISTMONK_URL", "")
        if not url:
            return None

        auth_type, creds = self._get_listmonk_auth()
        headers = {"Content-Type": "application/json"}
        if auth_type == "api_key":
            headers["Authorization"] = f"Bearer {creds}"

        request_auth = None
        if auth_type == "basic":
            request_auth = httpx.BasicAuth(creds[0], creds[1])

        payload = {
            "email": lead.email,
            "name": lead.name,
            "status": "enabled",
            "lists": [self._listmonk_list_id],
        }
        if lead.company:
            payload["company"] = lead.company
        if lead.title:
            payload["title"] = lead.title

        for attempt in range(retry_count):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{url.rstrip('/')}/api/v1/subscribers",
                        json=payload,
                        headers=headers,
                        auth=request_auth,
                    )
                    response.raise_for_status()
                    return response.json().get("data", {}).get("id")
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 409:
                    existing = await self._listmonk_lookup_subscriber(lead.email)
                    if existing:
                        return existing.get("id")
                if attempt == retry_count - 1:
                    raise
                await asyncio.sleep(0.5 * (attempt + 1))
            except Exception as e:
                if attempt == retry_count - 1:
                    raise
                await asyncio.sleep(0.5 * (attempt + 1))
        return None

    async def sync_to_listmonk(self, lead_ids: Optional[List[str]] = None) -> Dict:
        self._ensure_initialized()

        import asyncio

        leads_to_sync = []
        if lead_ids:
            for lid in lead_ids:
                lead = self._repository.get_lead(lid)
                if lead:
                    leads_to_sync.append(lead)
        else:
            leads_to_sync = self._repository.get_leads(status=LeadStatus.QUALIFIED)

        listmonk_url = os.getenv("LISTMONK_URL", "")
        if not listmonk_url:
            for lead in leads_to_sync:
                self._repository.update_lead(lead.id, {"status": LeadStatus.SYNCED})
            return {"synced": len(leads_to_sync), "message": f"Synced {len(leads_to_sync)} leads to Listmonk (mock mode)"}

        synced_count = 0
        failed_count = 0
        sync_results = []

        for lead in leads_to_sync:
            if not lead.email:
                continue
            try:
                subscriber_id = await self._listmonk_create_subscriber(lead)
                if subscriber_id:
                    self._repository.update_lead(lead.id, {"status": LeadStatus.SYNCED, "synced_at": datetime.utcnow()})
                    synced_count += 1
                    sync_results.append({"lead_id": lead.id, "subscriber_id": subscriber_id, "status": "synced"})
                else:
                    failed_count += 1
                    sync_results.append({"lead_id": lead.id, "status": "failed", "error": "no subscriber id returned"})
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to sync lead {lead.id} to Listmonk: {e}")
                sync_results.append({"lead_id": lead.id, "status": "failed", "error": str(e)})

        self._sync_logs.insert(0, {
            "timestamp": datetime.utcnow().isoformat(),
            "synced": synced_count,
            "failed": failed_count,
            "results": sync_results,
        })
        self._sync_logs = self._sync_logs[:50]

        return {"synced": synced_count, "failed": failed_count, "message": f"Synced {synced_count} leads to Listmonk"}

    async def campaign_metrics(self, campaign_id: Optional[str] = None) -> CampaignMetrics:
        self._ensure_initialized()

        listmonk_url = os.getenv("LISTMONK_URL", "")
        synced_count = 0
        open_count = 0
        click_count = 0

        if campaign_id:
            leads = self._repository.get_leads(status=LeadStatus.SYNCED, campaign_id=campaign_id)
            synced_count = len(leads)
        elif listmonk_url:
            all_leads = self._repository.get_leads(status=LeadStatus.SYNCED, limit=1000)
            synced_count = len(all_leads)
        else:
            synced_count = self._repository.count_leads(status=LeadStatus.SYNCED)

        if listmonk_url and synced_count > 0:
            auth_type, creds = self._get_listmonk_auth()
            headers = {"Content-Type": "application/json"}
            if auth_type == "api_key":
                headers["Authorization"] = f"Bearer {creds}"

            request_auth = None
            if auth_type == "basic":
                request_auth = httpx.BasicAuth(creds[0], creds[1])

            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        f"{listmonk_url.rstrip('/')}/api/v1/campaigns",
                        headers=headers,
                        auth=request_auth,
                    )
                    if response.status_code == 200:
                        campaigns = response.json().get("data", {})
                        for c in campaigns:
                            if c.get("status") == "sent":
                                open_count += c.get("counts", {}).get("opens", 0)
                                click_count += c.get("counts", {}).get("clicks", 0)
            except Exception as e:
                logger.warning(f"Failed to fetch campaign metrics from Listmonk: {e}")

        return CampaignMetrics(
            emails_sent=synced_count,
            opens=open_count,
            clicks=click_count,
            open_rate=round(open_count / synced_count, 2) if synced_count > 0 else 0.0,
            click_rate=round(click_count / synced_count, 2) if synced_count > 0 else 0.0,
        )

    async def export_leads(self, lead_ids: Optional[List[str]] = None, format: str = "csv") -> str:
        self._ensure_initialized()
        if lead_ids:
            leads = [self._repository.get_lead(lid) for lid in lead_ids if self._repository.get_lead(lid)]
        else:
            leads = self._repository.get_leads()
        leads = [l for l in leads if l is not None]

        if format == "csv":
            lines = ["name,email,company,title,source,status,score,url"]
            for lead in leads:
                lines.append(f'{lead.name},"{lead.email or ""}","{lead.company or ""}","{lead.title or ""}",{lead.source},{lead.status},{lead.score or 0},"{lead.url or ""}"')
            return "\n".join(lines)
        elif format == "json":
            import json as _json
            return _json.dumps([self._repository.lead_to_dict(l) for l in leads], indent=2, default=str)
        return ""

    def get_stats(self) -> Dict:
        self._ensure_initialized()
        return {
            "total_leads": self._repository.count_leads(),
            "qualified_leads": self._repository.count_leads(status=LeadStatus.QUALIFIED),
            "synced_leads": self._repository.count_leads(status=LeadStatus.SYNCED),
            "new_leads": self._repository.count_leads(status=LeadStatus.NEW),
            "enriched_leads": self._repository.count_leads(status=None) - self._repository.count_leads(status=LeadStatus.SYNCED),
        }

    def get_leads(self, status: Optional[str] = None, limit: int = 50) -> List[Dict]:
        self._ensure_initialized()
        leads = self._repository.get_leads(status=status, limit=limit)
        return [self._repository.lead_to_dict(l) for l in leads]


_lead_hunter_service: Optional["LeadHunterService"] = None


def get_lead_hunter_service() -> LeadHunterService:
    global _lead_hunter_service
    if _lead_hunter_service is None:
        _lead_hunter_service = LeadHunterService()
    return _lead_hunter_service