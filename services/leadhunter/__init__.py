# services/leadhunter/__init__.py
"""LeadHunter service — lead discovery, scoring, and Listmonk sync."""

from .service import LeadHunterService, Lead, LeadStatus, CampaignMetrics, LeadScore, get_lead_hunter_service
from .repository import LeadHunterRepository, LeadModel, CampaignModel

__all__ = [
    "LeadHunterService",
    "Lead",
    "LeadStatus",
    "CampaignMetrics",
    "LeadScore",
    "get_lead_hunter_service",
    "LeadHunterRepository",
    "LeadModel",
    "CampaignModel",
]