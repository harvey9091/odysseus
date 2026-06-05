"""
agent_manager.py — Agent provider manager.

Manages registration, selection, and runtime switching between agent
backends (OpenCode, Hermes, future providers). Thread-safe singleton
accessed via get_agent_manager().

Settings integration:
  - `agent_backend` in data/settings.json (persisted selection)
  - AGENT_BACKEND env var (initial default / override)

Usage:
    from src.agent_manager import get_agent_manager
    mgr = get_agent_manager()
    backend = mgr.get_active_backend()
    async for chunk in backend.stream(url, model, messages, ...):
        ...
"""

import asyncio
import logging
import os
import threading
from typing import Dict, List, Optional

from src.agent_backend import AgentBackend, OpenCodeBackend, HermesBackend, LeadHunterBackend

logger = logging.getLogger(__name__)

_agent_manager: Optional["AgentManager"] = None
_agent_manager_lock = threading.Lock()


class AgentManager:
    """Registry and lifecycle manager for agent backends."""

    # Default backend when nothing is configured
    DEFAULT_BACKEND = "opencode"

    def __init__(self):
        self._backends: Dict[str, AgentBackend] = {}
        self._active_name: str = self.DEFAULT_BACKEND
        self._lock = threading.Lock()
        self._started = False

    # ── Registration ──

    def register(self, backend: AgentBackend) -> None:
        """Register an agent backend. Replaces existing if same name."""
        with self._lock:
            self._backends[backend.name] = backend
            logger.info(f"Registered agent backend: {backend.name} ({backend.display_name})")

    def unregister(self, name: str) -> None:
        """Remove a backend from the registry."""
        with self._lock:
            self._backends.pop(name, None)

    # ── Selection ──

    def get_active_backend(self) -> AgentBackend:
        """Return the currently active agent backend.

        Falls back to OpenCode if the selected backend is unavailable.
        """
        with self._lock:
            backend = self._backends.get(self._active_name)
            if backend and backend.is_healthy():
                return backend
            # Fallback to OpenCode
            fallback = self._backends.get(self.DEFAULT_BACKEND)
            if fallback and fallback.is_healthy():
                return fallback
            # Last resort: return any healthy backend
            for b in self._backends.values():
                if b.is_healthy():
                    return b
            # Nothing healthy — return active anyway (will error on use)
            return backend or fallback

    def get_active_name(self) -> str:
        """Return the name of the currently active backend."""
        with self._lock:
            return self._active_name

    def set_active(self, name: str) -> bool:
        """Switch the active agent backend. Returns True if successful."""
        with self._lock:
            if name not in self._backends:
                logger.warning(f"Cannot switch to unknown agent backend: {name}")
                return False
            backend = self._backends[name]
            if not backend.is_healthy():
                logger.warning(f"Cannot switch to unhealthy agent backend: {name}")
                return False
            old = self._active_name
            self._active_name = name
            if old != name:
                logger.info(f"Switched agent backend: {old} → {name}")
            return True

    def force_set_active(self, name: str) -> None:
        """Force-switch to a backend regardless of health (for fallback scenarios)."""
        with self._lock:
            self._active_name = name

    # ── Query ──

    def list_backends(self) -> List[Dict]:
        """Return metadata for all registered backends."""
        with self._lock:
            result = []
            for name, backend in sorted(self._backends.items()):
                info = backend.get_info()
                info["active"] = (name == self._active_name)
                result.append(info)
            return result

    def get_backend(self, name: str) -> Optional[AgentBackend]:
        """Get a specific backend by name."""
        with self._lock:
            return self._backends.get(name)

    # ── Lifecycle ──

    async def start(self) -> None:
        """Initialize all registered backends. Called at app startup."""
        if self._started:
            return
        self._started = True

        # Determine initial active backend from env/settings
        env_backend = os.getenv("AGENT_BACKEND", "").strip().lower()
        if env_backend and env_backend in self._backends:
            self._active_name = env_backend
        else:
            try:
                from src.settings import get_setting
                saved = (get_setting("agent_backend") or "").strip().lower()
                if saved and saved in self._backends:
                    self._active_name = saved
            except Exception:
                pass

        # Initialize all backends
        for name, backend in self._backends.items():
            try:
                await backend.initialize()
                logger.info(f"Agent backend initialized: {name}")
            except Exception as e:
                logger.warning(f"Agent backend {name} failed to initialize: {e}")

        active = self.get_active_backend()
        logger.info(f"Agent manager started — active backend: {active.display_name}")

    async def stop(self) -> None:
        """Shutdown all backends. Called at app shutdown."""
        for name, backend in self._backends.items():
            try:
                await backend.shutdown()
            except Exception as e:
                logger.warning(f"Agent backend {name} shutdown error: {e}")
        self._started = False
        logger.info("Agent manager stopped")


def get_agent_manager() -> AgentManager:
    """Return the process-wide AgentManager singleton."""
    global _agent_manager
    if _agent_manager is None:
        with _agent_manager_lock:
            if _agent_manager is None:
                _agent_manager = AgentManager()
    return _agent_manager


def setup_default_backends() -> None:
    """Register the built-in agent backends.

    Called during app initialization (app.py). Sets up OpenCode, Hermes,
    and LeadHunter with Hermes configured to fall back to OpenCode when unavailable.
    """
    mgr = get_agent_manager()

    # OpenCode — always available
    opencode = OpenCodeBackend()
    mgr.register(opencode)

    # Hermes — optional, falls back to OpenCode
    hermes = HermesBackend()
    hermes.set_fallback(opencode)
    mgr.register(hermes)

    # LeadHunter — lead discovery and Listmonk sync
    leadhunter = LeadHunterBackend()
    leadhunter.set_fallback(opencode)
    mgr.register(leadhunter)

    logger.info(
        f"Default agent backends registered: "
        f"{', '.join(b['display_name'] for b in mgr.list_backends())}"
    )
