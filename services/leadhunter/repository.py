# services/leadhunter/repository.py
"""LeadHunter repository — SQLite-backed lead storage."""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, String, Text, Integer, DateTime, JSON, ForeignKey, func
from sqlalchemy.orm import relationship
from core.database import Base, SessionLocal, TimestampMixin

logger = logging.getLogger(__name__)


class LeadModel(TimestampMixin, Base):
    """SQLAlchemy model for lead storage."""
    __tablename__ = "leadhunter_leads"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    company = Column(String, nullable=True)
    title = Column(String, nullable=True)
    source = Column(String, nullable=False)
    url = Column(String, nullable=True)
    status = Column(String, nullable=False, default="new")
    score = Column(Integer, nullable=True)
    score_reason = Column(Text, nullable=True)
    enrichment_status = Column(String, nullable=True)
    synced_at = Column(DateTime, nullable=True)
    campaign_id = Column(String, ForeignKey("leadhunter_campaigns.id"), nullable=True, index=True)
    lead_metadata = Column(JSON, nullable=True)

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )


class CampaignModel(TimestampMixin, Base):
    """Campaign model for grouping leads and tracking metrics."""
    __tablename__ = "leadhunter_campaigns"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    leads = relationship("LeadModel", backref="campaign", lazy="dynamic")


class LeadHunterRepository:
    """Repository for LeadHunter database operations."""

    def __init__(self):
        pass

    def _get_session(self):
        return SessionLocal()

    def create_lead(self, lead_data: Dict[str, Any]) -> LeadModel:
        lead = LeadModel(
            id=str(uuid.uuid4())[:8],
            name=lead_data.get("name", ""),
            email=lead_data.get("email"),
            company=lead_data.get("company"),
            title=lead_data.get("title"),
            source=lead_data.get("source", "unknown"),
            url=lead_data.get("url"),
            status=lead_data.get("status", "new"),
            score=lead_data.get("score"),
            score_reason=lead_data.get("score_reason"),
            enrichment_status=lead_data.get("enrichment_status"),
            campaign_id=lead_data.get("campaign_id"),
            lead_metadata=lead_data.get("metadata"),
        )
        session = self._get_session()
        try:
            session.add(lead)
            session.commit()
            session.refresh(lead)
        finally:
            session.close()
        return lead

    def get_lead(self, lead_id: str) -> Optional[LeadModel]:
        session = self._get_session()
        try:
            return session.query(LeadModel).filter(LeadModel.id == lead_id).first()
        finally:
            session.close()

    def get_leads(
        self,
        status: Optional[str] = None,
        campaign_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[LeadModel]:
        session = self._get_session()
        try:
            query = session.query(LeadModel)
            if status:
                query = query.filter(LeadModel.status == status)
            if campaign_id:
                query = query.filter(LeadModel.campaign_id == campaign_id)
            return query.order_by(LeadModel.created_at.desc()).offset(offset).limit(limit).all()
        finally:
            session.close()

    def update_lead(self, lead_id: str, updates: Dict[str, Any]) -> Optional[LeadModel]:
        session = self._get_session()
        try:
            lead = session.query(LeadModel).filter(LeadModel.id == lead_id).first()
            if not lead:
                return None
            for key, value in updates.items():
                if key == "metadata":
                    lead.lead_metadata = value
                elif hasattr(lead, key):
                    setattr(lead, key, value)
            session.commit()
            session.refresh(lead)
            return lead
        finally:
            session.close()

    def delete_lead(self, lead_id: str) -> bool:
        session = self._get_session()
        try:
            lead = session.query(LeadModel).filter(LeadModel.id == lead_id).first()
            if not lead:
                return False
            session.delete(lead)
            session.commit()
            return True
        finally:
            session.close()

    def count_leads(self, status: Optional[str] = None, campaign_id: Optional[str] = None) -> int:
        session = self._get_session()
        try:
            query = session.query(func.count(LeadModel.id))
            if status:
                query = query.filter(LeadModel.status == status)
            if campaign_id:
                query = query.filter(LeadModel.campaign_id == campaign_id)
            return query.scalar()
        finally:
            session.close()

    def create_campaign(self, name: str, description: Optional[str] = None) -> CampaignModel:
        campaign = CampaignModel(
            id=str(uuid.uuid4())[:8],
            name=name,
            description=description,
        )
        session = self._get_session()
        try:
            session.add(campaign)
            session.commit()
            session.refresh(campaign)
        finally:
            session.close()
        return campaign

    def get_campaign(self, campaign_id: str) -> Optional[CampaignModel]:
        session = self._get_session()
        try:
            return session.query(CampaignModel).filter(CampaignModel.id == campaign_id).first()
        finally:
            session.close()

    def get_campaigns(self, limit: int = 50) -> List[CampaignModel]:
        session = self._get_session()
        try:
            return session.query(CampaignModel).order_by(CampaignModel.created_at.desc()).limit(limit).all()
        finally:
            session.close()

    def delete_campaign(self, campaign_id: str) -> bool:
        session = self._get_session()
        try:
            campaign = session.query(CampaignModel).filter(CampaignModel.id == campaign_id).first()
            if not campaign:
                return False
            session.delete(campaign)
            session.commit()
            return True
        finally:
            session.close()

    def lead_to_dict(self, lead: LeadModel) -> Dict[str, Any]:
        result = {
            "id": lead.id,
            "name": lead.name,
            "email": lead.email,
            "company": lead.company,
            "title": lead.title,
            "source": lead.source,
            "url": lead.url,
            "status": lead.status,
            "score": lead.score,
            "score_reason": lead.score_reason,
            "enrichment_status": lead.enrichment_status,
            "campaign_id": lead.campaign_id,
            "metadata": lead.lead_metadata,
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
            "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
            "synced_at": lead.synced_at.isoformat() if lead.synced_at else None,
        }
        return result

    def get_campaign_leads(self, campaign_id: str, limit: int = 50) -> List[LeadModel]:
        session = self._get_session()
        try:
            return session.query(LeadModel).filter(LeadModel.campaign_id == campaign_id).limit(limit).all()
        finally:
            session.close()

    def mark_enriched(self, lead_id: str, enrichment_data: Dict[str, Any]) -> Optional[LeadModel]:
        return self.update_lead(lead_id, {
            "enrichment_status": "completed",
            "metadata": enrichment_data,
        })

    def mark_synced(self, lead_id: str, synced: bool = True) -> Optional[LeadModel]:
        return self.update_lead(lead_id, {
            "status": "synced" if synced else "qualified",
        })

    def score_lead(self, lead_id: str, score: int, reason: str) -> Optional[LeadModel]:
        return self.update_lead(lead_id, {
            "score": score,
            "score_reason": reason,
        })

    def create_tables(self) -> None:
        """Create Lead and Campaign tables if they don't exist."""
        from core.database import engine
        LeadModel.metadata.create_all(bind=engine)
        CampaignModel.metadata.create_all(bind=engine)
        logger.info("LeadHunter tables created")