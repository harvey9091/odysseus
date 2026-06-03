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

    # ─────────────────────────────────────────────────────────────────────
    # Runs
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def create_run(run_id: str, providers: list, filters: dict, owner: str) -> ScraperRun:
        """Create a new scraper run."""
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
        """Update run status and optional fields."""
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
        """Get a run by ID."""
        with get_db_session() as db:
            return db.query(ScraperRun).filter(ScraperRun.id == run_id).first()

    @staticmethod
    def list_runs(owner: Optional[str] = None, limit: int = 50) -> list:
        """List recent runs."""
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
        """Create a lead with dedupe by domain."""
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
                source_provider=lead_data.get("source_provider"),
                source_url=lead_data.get("source_url"),
                category=lead_data.get("category"),
                country=lead_data.get("country"),
                emails=lead_data.get("emails", []),
                founders=lead_data.get("founders", []),
                social=lead_data.get("social", {}),
                pricing_model=lead_data.get("pricing_model"),
                tech_stack=lead_data.get("tech_stack", []),
                owner=owner,
            )

            # Parse launch_date
            launch_date = lead_data.get("launch_date")
            if launch_date and isinstance(launch_date, str):
                try:
                    lead.launch_date = datetime.fromisoformat(launch_date.replace("Z", "+00:00"))
                except Exception:
                    pass

            db.add(lead)
            db.commit()
            db.refresh(lead)
            return lead

    @staticmethod
    def update_lead_scores(lead_id: str, scores: dict):
        """Update AI scoring for a lead."""
        with get_db_session() as db:
            lead = db.query(ScraperLead).filter(ScraperLead.id == lead_id).first()
            if lead:
                lead.affordability_score = scores.get("affordability_score")
                lead.promo_video_fit_score = scores.get("promo_video_fit_score")
                lead.urgency_score = scores.get("urgency_score")
                lead.funding_probability = scores.get("funding_probability")
                lead.ai_summary = scores.get("ai_summary")
                lead.ai_reasoning = scores.get("ai_reasoning")
                lead.outreach_recommendations = scores.get("outreach_recommendations")
                db.commit()

    @staticmethod
    def update_lead_video(lead_id: str, video_data: dict):
        """Update video detection results."""
        with get_db_session() as db:
            lead = db.query(ScraperLead).filter(ScraperLead.id == lead_id).first()
            if lead:
                lead.has_video = video_data.get("has_video", False)
                lead.video_urls = video_data.get("video_urls", [])
                if lead.has_video:
                    lead.excluded = True
                    lead.exclude_reason = "Has existing promo video"
                db.commit()

    @staticmethod
    def update_lead_contacts(lead_id: str, emails: list, founders: list, social: dict):
        """Update contact information."""
        with get_db_session() as db:
            lead = db.query(ScraperLead).filter(ScraperLead.id == lead_id).first()
            if lead:
                if emails:
                    lead.emails = emails
                if founders:
                    lead.founders = founders
                if social:
                    lead.social = social
                db.commit()

    @staticmethod
    def get_lead(lead_id: str) -> Optional[ScraperLead]:
        """Get a lead by ID."""
        with get_db_session() as db:
            return db.query(ScraperLead).filter(ScraperLead.id == lead_id).first()

    @staticmethod
    def list_leads(
        owner: Optional[str] = None,
        exclude_with_video: bool = True,
        min_score: Optional[int] = None,
        provider: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
    ) -> dict:
        """List leads with filtering and pagination."""
        with get_db_session() as db:
            q = db.query(ScraperLead)

            if owner:
                q = q.filter(ScraperLead.owner == owner)
            if exclude_with_video:
                q = q.filter(ScraperLead.excluded == False)
            if min_score is not None:
                q = q.filter(ScraperLead.affordability_score >= min_score)
            if provider:
                q = q.filter(ScraperLead.source_provider == provider)

            total = q.count()
            leads = q.order_by(
                ScraperLead.affordability_score.desc().nullslast(),
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
        """Get aggregate statistics."""
        with get_db_session() as db:
            q = db.query(ScraperLead)
            if owner:
                q = q.filter(ScraperLead.owner == owner)

            total = q.count()
            qualified = q.filter(ScraperLead.affordability_score >= 70).count()
            with_video = q.filter(ScraperLead.has_video == True).count()

            # Average scores
            from sqlalchemy import func
            avg_affordability = db.query(func.avg(ScraperLead.affordability_score)).filter(
                ScraperLead.affordability_score.isnot(None)
            ).scalar()

            runs_total = db.query(ScraperRun).count() if not owner else db.query(ScraperRun).filter(ScraperRun.owner == owner).count()
            runs_completed = db.query(ScraperRun).filter(ScraperRun.status == "completed").count() if not owner else db.query(ScraperRun).filter(ScraperRun.owner == owner, ScraperRun.status == "completed").count()

            return {
                "total_leads": total,
                "qualified_leads": qualified,
                "leads_with_video": with_video,
                "avg_affordability_score": round(avg_affordability or 0, 1),
                "total_runs": runs_total,
                "completed_runs": runs_completed,
            }

    @staticmethod
    def get_all_active_domains() -> list:
        """Get all active (non-excluded) domains for cross-run dedup."""
        with get_db_session() as db:
            rows = db.query(ScraperLead.domain).filter(
                ScraperLead.excluded == False,
                ScraperLead.domain.isnot(None),
                ScraperLead.domain != "",
            ).all()
            return [row[0] for row in rows if row[0]]

    @staticmethod
    def _lead_to_dict(lead: ScraperLead) -> dict:
        """Convert a lead to dict."""
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
            "country": lead.country,
            "emails": lead.emails or [],
            "founders": lead.founders or [],
            "social": lead.social or {},
            "has_video": lead.has_video,
            "video_urls": lead.video_urls or [],
            "affordability_score": lead.affordability_score,
            "promo_video_fit_score": lead.promo_video_fit_score,
            "urgency_score": lead.urgency_score,
            "funding_probability": lead.funding_probability,
            "ai_summary": lead.ai_summary,
            "ai_reasoning": lead.ai_reasoning,
            "outreach_recommendations": lead.outreach_recommendations,
            "pricing_model": lead.pricing_model,
            "tech_stack": lead.tech_stack or [],
            "excluded": lead.excluded,
            "exclude_reason": lead.exclude_reason,
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
        }

    # ─────────────────────────────────────────────────────────────────────
    # Logs
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def create_log(run_id: str, level: str, message: str, provider: str = None, data: dict = None):
        """Create a log entry."""
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
        """Get logs for a run."""
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
