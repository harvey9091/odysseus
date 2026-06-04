# services/scraper/storage — Database operations
"""Storage layer for scraper data with dedupe support."""

import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import and_, or_
from core.database import get_db_session, ScraperRun, ScraperLead, ScraperLog, ScraperProvider

logger = logging.getLogger(__name__)


class LeadStore:
    """Database operations for scraper leads and runs."""

    @staticmethod
    def create_run(run_id: str, providers: list, filters: dict, owner: str) -> ScraperRun:
        with get_db_session() as db:
            run = ScraperRun(
                id=run_id,
                status="pending",
                providers=providers,
                filters=filters,
                owner=owner,
            )
            db.add(run)
            db.commit()
            db.refresh(run)
            return run

    @staticmethod
    def update_run_status(run_id: str, status: str, **kwargs):
        with get_db_session() as db:
            run = db.query(ScraperRun).filter(ScraperRun.id == run_id).first()
            if run:
                run.status = status
                if status == "running" and not run.started_at:
                    run.started_at = datetime.utcnow()
                if status in ("completed", "failed", "cancelled"):
                    run.completed_at = datetime.utcnow()
                for key, value in kwargs.items():
                    if hasattr(run, key):
                        setattr(run, key, value)
                db.commit()

    @staticmethod
    def get_run(run_id: str) -> Optional[ScraperRun]:
        with get_db_session() as db:
            return db.query(ScraperRun).filter(ScraperRun.id == run_id).first()

    @staticmethod
    def list_runs(owner: Optional[str] = None, limit: int = 50) -> list:
        with get_db_session() as db:
            q = db.query(ScraperRun).order_by(ScraperRun.created_at.desc())
            if owner:
                q = q.filter(ScraperRun.owner == owner)
            return q.limit(limit).all()

    # ─────────────────────────────────────────────────────────────────────
    # Leads
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def create_lead(run_id: str, lead_data: dict, owner: str) -> Optional[ScraperLead]:
        domain = lead_data.get("domain")

        with get_db_session() as db:
            # Check for duplicate by domain
            if domain:
                existing = db.query(ScraperLead).filter(
                    ScraperLead.domain == domain,
                    ScraperLead.excluded == False
                ).first()
                if existing:
                    logger.debug(f"Lead dedupe: {domain} already exists")
                    return None

            lead = ScraperLead(
                id=str(uuid.uuid4()),
                run_id=run_id,
                name=lead_data.get("name", ""),
                website=lead_data.get("website"),
                description=lead_data.get("description"),
                domain=domain,
                source_provider=lead_data.get("source_provider", "discovery_agent"),
                source_url=lead_data.get("source_url"),
                category=lead_data.get("category") or lead_data.get("industry"),
                country=lead_data.get("country"),
                emails=lead_data.get("emails", []),
                founders=lead_data.get("founders", []),
                social=lead_data.get("social", {}),
                pricing_model=lead_data.get("pricing_model"),
                tech_stack=lead_data.get("tech_stack", []),
                owner=owner,
            )

            db.add(lead)
            db.commit()
            db.refresh(lead)
            return lead

    @staticmethod
    def update_lead_scores(lead_id: str, scores: dict):
        with get_db_session() as db:
            lead = db.query(ScraperLead).filter(ScraperLead.id == lead_id).first()
            if lead:
                lead.affordability_score = scores.get("affordability_score")
                lead.promo_video_fit_score = scores.get("promo_video_fit_score")
                lead.urgency_score = scores.get("urgency_score")
                lead.funding_probability = scores.get("funding_probability")
                lead.ai_summary = scores.get("ai_summary")
                db.commit()

    @staticmethod
    def update_lead_video(lead_id: str, video_data: dict):
        with get_db_session() as db:
            lead = db.query(ScraperLead).filter(ScraperLead.id == lead_id).first()
            if lead:
                lead.has_video = video_data.get("has_video", False)
                lead.video_urls = video_data.get("video_urls", [])
                db.commit()

    @staticmethod
    def get_lead(lead_id: str) -> Optional[ScraperLead]:
        with get_db_session() as db:
            return db.query(ScraperLead).filter(ScraperLead.id == lead_id).first()

    @staticmethod
    def list_leads(
        owner: Optional[str] = None,
        min_score: Optional[int] = None,
        provider: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
    ) -> dict:
        with get_db_session() as db:
            q = db.query(ScraperLead)

            if owner:
                q = q.filter(ScraperLead.owner == owner)
            q = q.filter(ScraperLead.excluded == False)
            if provider:
                q = q.filter(ScraperLead.source_provider == provider)

            total = q.count()
            leads = q.order_by(
                ScraperLead.created_at.desc()
            ).offset((page - 1) * limit).limit(limit).all()

            return {
                "leads": [LeadStore._lead_to_dict(l) for l in leads],
                "total": total,
                "page": page,
                "limit": limit,
            }

    @staticmethod
    def get_stats(owner: Optional[str] = None) -> dict:
        with get_db_session() as db:
            q = db.query(ScraperLead)
            if owner:
                q = q.filter(ScraperLead.owner == owner)
            q = q.filter(ScraperLead.excluded == False)

            total = q.count()
            with_video = q.filter(ScraperLead.has_video == True).count()

            from sqlalchemy import func
            runs_total = db.query(ScraperRun).filter().count() if not owner else db.query(ScraperRun).filter(ScraperRun.owner == owner).count()
            runs_completed = db.query(ScraperRun).filter(ScraperRun.status == "completed").count()

            return {
                "total_leads": total,
                "leads_with_video": with_video,
                "total_runs": runs_total,
                "completed_runs": runs_completed,
            }

    @staticmethod
    def get_all_active_domains() -> list:
        with get_db_session() as db:
            rows = db.query(ScraperLead.domain).filter(
                ScraperLead.excluded == False,
                ScraperLead.domain.isnot(None),
                ScraperLead.domain != "",
            ).all()
            return [row[0] for row in rows if row[0]]

    @staticmethod
    def _lead_to_dict(lead: ScraperLead) -> dict:
        return {
            "id": lead.id,
            "run_id": lead.run_id,
            "name": lead.name,
            "website": lead.website,
            "description": lead.description,
            "domain": lead.domain,
            "source_provider": lead.source_provider,
            "source_url": lead.source_url,
            "launch_date": lead.launch_date.isoformat() if lead.launch_date else None,
            "category": lead.category,
            "industry": lead.category,
            "country": lead.country,
            "emails": lead.emails or [],
            "contact": lead.emails or [],
            "founders": lead.founders or [],
            "social": lead.social or {},
            "has_video": lead.has_video,
            "affordability_score": lead.affordability_score,
            "excluded": lead.excluded,
            "contacted": lead.contacted,
            "favorite": lead.favorite,
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
        }

    @staticmethod
    def create_log(run_id: str, level: str, message: str, provider: str = None, data: dict = None):
        with get_db_session() as db:
            log = ScraperLog(
                id=str(uuid.uuid4()),
                run_id=run_id,
                level=level,
                message=message,
                provider=provider,
                data=data,
            )
            db.add(log)
            db.commit()

    @staticmethod
    def get_logs(run_id: str, limit: int = 500) -> list:
        with get_db_session() as db:
            logs = db.query(ScraperLog).filter(
                ScraperLog.run_id == run_id
            ).order_by(ScraperLog.created_at.desc()).limit(limit).all()
            return [
                {
                    "id": log.id,
                    "level": log.level,
                    "provider": log.provider,
                    "message": log.message,
                    "data": log.data,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ]