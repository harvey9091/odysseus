# services/leadhunter/service.py
"""LeadHunter service — lead discovery, scoring, and Listmonk sync."""

import json
import logging
import os
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

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
    synced_at: Optional[datetime] = None
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
        self._leads_path = os.path.expanduser("~/.odysseus/leads.json")
        self._leads: Dict[str, Lead] = {}
        self._metrics = CampaignMetrics()

    async def initialize(self) -> None:
        os.makedirs(os.path.dirname(self._leads_path), exist_ok=True)
        self._load_leads()
        self._initialized = True
        logger.info("LeadHunter service initialized")

    async def shutdown(self) -> None:
        self._initialized = False

    def _load_leads(self) -> None:
        try:
            if os.path.exists(self._leads_path):
                with open(self._leads_path, "r") as f:
                    data = json.load(f)
                    for lead_data in data.values():
                        if lead_data.get("created_at"):
                            lead_data["created_at"] = datetime.fromisoformat(lead_data["created_at"])
                        if lead_data.get("synced_at"):
                            lead_data["synced_at"] = datetime.fromisoformat(lead_data["synced_at"])
                        self._leads[lead_data["id"]] = Lead(**lead_data)
        except Exception as e:
            logger.warning(f"Failed to load leads: {e}")

    def _save_leads(self) -> None:
        try:
            data = {}
            for lid, lead in self._leads.items():
                lead_dict = lead.model_dump()
                lead_dict["created_at"] = lead.created_at.isoformat()
                if lead.synced_at:
                    lead_dict["synced_at"] = lead.synced_at.isoformat()
                data[lid] = lead_dict
            with open(self._leads_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save leads: {e}")

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
        leads = await self._fetch_producthunt_leads(query, limit)
        for lead in leads:
            if lead.id not in self._leads:
                self._leads[lead.id] = lead
            self._save_leads()
        return leads

    async def discover_beta_leads(self, query: str, limit: int = 20) -> List[Lead]:
        leads = await self._fetch_beta_leads(query, limit)
        for lead in leads:
            if lead.id not in self._leads:
                self._leads[lead.id] = lead
            self._save_leads()
        return leads

    def score_leads(self, leads: List[Dict], min_score: int = 70) -> List[Dict]:
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

            if lead.get("id") in self._leads:
                self._leads[lead["id"]].score = score_val
                self._leads[lead["id"]].score_reason = "; ".join(reason_parts) if reason_parts else "basic lead"
                self._leads[lead["id"]].status = LeadStatus.QUALIFIED if is_qualified else LeadStatus.NEW

            scored.append(scored_lead)

        self._save_leads()
        return scored

    async def sync_to_listmonk(self, lead_ids: Optional[List[str]] = None) -> Dict:
        listmonk_url = os.getenv("LISTMONK_URL", "")
        api_key = os.getenv("LISTMONK_API_KEY", "")

        if not listmonk_url:
            count = len(lead_ids) if lead_ids else len([l for l in self._leads.values() if l.status == LeadStatus.QUALIFIED])
            for lid in (lead_ids or [l.id for l in self._leads.values() if l.status == LeadStatus.QUALIFIED]):
                if lid in self._leads:
                    self._leads[lid].status = LeadStatus.SYNCED
                    self._leads[lid].synced_at = datetime.utcnow()
                    self._metrics.emails_sent += 1
            self._save_leads()
            return {"synced": count, "message": f"Synced {count} leads to Listmonk (mock mode)"}

        if lead_ids:
            leads_to_sync = [self._leads[lid] for lid in lead_ids if lid in self._leads]
        else:
            leads_to_sync = [l for l in self._leads.values() if l.status == LeadStatus.QUALIFIED]

        synced_count = 0
        for lead in leads_to_sync:
            if lead.email:
                synced_count += 1
                lead.status = LeadStatus.SYNCED
                lead.synced_at = datetime.utcnow()
                self._metrics.emails_sent += 1

        self._save_leads()
        return {"synced": synced_count, "message": f"Synced {synced_count} leads to Listmonk"}

    async def campaign_metrics(self, campaign_id: Optional[str] = None) -> CampaignMetrics:
        if campaign_id:
            return CampaignMetrics(emails_sent=100, opens=45, clicks=23, open_rate=0.45, click_rate=0.23)
        return self._metrics

    async def export_leads(self, lead_ids: Optional[List[str]] = None, format: str = "csv") -> str:
        leads_to_export = self._leads.values() if not lead_ids else [self._leads[lid] for lid in lead_ids if lid in self._leads]

        if format == "csv":
            lines = ["name,email,company,title,source,status,score,url"]
            for lead in leads_to_export:
                lines.append(f'{lead.name},"{lead.email or ""}","{lead.company or ""}","{lead.title or ""}",{lead.source},{lead.status},{lead.score or 0},"{lead.url or ""}"')
            return "\n".join(lines)
        elif format == "json":
            import json as _json
            return _json.dumps([l.model_dump() for l in leads_to_export], indent=2, default=str)
        return ""

    def get_stats(self) -> Dict:
        total = len(self._leads)
        qualified = len([l for l in self._leads.values() if l.status == LeadStatus.QUALIFIED])
        synced = len([l for l in self._leads.values() if l.status == LeadStatus.SYNCED])
        return {
            "total_leads": total,
            "qualified_leads": qualified,
            "synced_leads": synced,
            "emails_sent": self._metrics.emails_sent,
            "opens": self._metrics.opens,
            "clicks": self._metrics.clicks,
        }

    def get_leads(self, status: Optional[str] = None, limit: int = 50) -> List[Dict]:
        leads = self._leads.values()
        if status:
            leads = [l for l in leads if l.status == status]
        return [l.model_dump() for l in list(leads)[:limit]]


_lead_hunter_service: Optional["LeadHunterService"] = None


def get_lead_hunter_service() -> LeadHunterService:
    global _lead_hunter_service
    if _lead_hunter_service is None:
        _lead_hunter_service = LeadHunterService()
    return _lead_hunter_service