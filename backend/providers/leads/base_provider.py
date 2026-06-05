from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class Lead(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    source: str
    url: Optional[str] = None
    metadata: Dict[str, Any] = {}


class LeadProvider(ABC):
    @abstractmethod
    async def fetch_leads(self, query: Optional[str] = None, limit: int = 50) -> List[Lead]:
        pass

    @abstractmethod
    def validate_lead(self, lead: Lead) -> bool:
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def is_enabled(self) -> bool:
        pass
