"""Agent routes — /api/agents, /api/agents/current, /api/agents/switch."""

import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.auth_helpers import get_current_user
from src.agent_manager import get_agent_manager
from src.settings import get_setting, save_settings, load_settings

logger = logging.getLogger(__name__)


def setup_agent_routes() -> APIRouter:
    router = APIRouter(tags=["agents"])

    class SwitchAgentRequest(BaseModel):
        backend: str

    @router.get("/api/agents")
    async def list_agents(request: Request):
        """List all registered agent backends with their status."""
        get_current_user(request)
        mgr = get_agent_manager()
        return mgr.list_backends()

    @router.get("/api/agents/current")
    async def get_current_agent(request: Request):
        """Return the currently active agent backend name and info."""
        get_current_user(request)
        mgr = get_agent_manager()
        active = mgr.get_active_backend()
        info = active.get_info()
        info["name"] = active.name
        return info

    @router.post("/api/agents/switch")
    async def switch_agent(request: Request, body: SwitchAgentRequest):
        """Switch the active agent backend. Persists the choice to settings."""
        user = get_current_user(request)
        mgr = get_agent_manager()
        if not mgr.set_active(body.backend):
            raise HTTPException(
                status_code=400,
                detail=f"Unknown or unhealthy agent backend: {body.backend}. "
                       f"Available: {', '.join(b['name'] for b in mgr.list_backends())}",
            )
        # Persist to settings
        try:
            settings = load_settings()
            settings["agent_backend"] = body.backend
            save_settings(settings)
        except Exception as e:
            logger.warning(f"Failed to persist agent_backend setting: {e}")
        return {"ok": True, "backend": body.backend}

    return router
