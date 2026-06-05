import random
import string
from typing import List, Optional
from .base_provider import LeadProvider, Lead


class MockLeadProvider(LeadProvider):
    """Returns deterministic test leads for development and testing."""

    FIRST_NAMES = ["Ava", "Liam", "Sophia", "Noah", "Isabella", "Ethan", "Mia", "Mason"]
    LAST_NAMES = ["Chen", "Patel", "Kim", "Rivera", "Williams", "Garcia", "Andersen", "Nakamura"]
    COMPANIES = ["Acme Corp", "Globex", "Initech", "Hooli", "Pied Piper", "Massive Dynamic", "Soylent Corp", "Umbrella Co"]
    TITLES = ["CTO", "VP Engineering", "Head of Data", "AI Lead", "Sr. Engineer", "Product Manager", "DevOps Lead"]
    DOMAINS = ["example.com", "acme.test", "globex.dev", "initech.io", "demo.local"]

    def __init__(self, seed: Optional[int] = None):
        self._seed = seed
        if seed is not None:
            random.seed(seed)

    @property
    def is_enabled(self) -> bool:
        return True

    def get_provider_name(self) -> str:
        return "mock"

    def _make_lead(self, idx: int) -> Lead:
        first = self.FIRST_NAMES[idx % len(self.FIRST_NAMES)]
        last = self.LAST_NAMES[idx % len(self.LAST_NAMES)]
        company = self.COMPANIES[idx % len(self.COMPANIES)]
        domain = self.DOMAINS[idx % len(self.DOMAINS)]
        email = f"{first.lower()}.{last.lower()}@{domain}"
        return Lead(
            id=f"mock-{idx+1:03d}",
            name=f"{first} {last}",
            email=email,
            company=company,
            title=self.TITLES[idx % len(self.TITLES)],
            source="mock",
            url=f"https://{domain}/team/{first.lower()}-{last.lower()}",
            metadata={"generated": True, "seed": self._seed},
        )

    async def fetch_leads(self, query: Optional[str] = None, limit: int = 50) -> List[Lead]:
        count = min(limit, 20)
        return [self._make_lead(i) for i in range(count)]

    def validate_lead(self, lead: Lead) -> bool:
        if not lead.name or not lead.email:
            return False
        if "@" not in lead.email or "." not in lead.email.split("@")[-1]:
            return False
        return True
