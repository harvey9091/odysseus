"""
agent_backend.py — Agent backend abstraction layer.

Defines the interface that all agent backends must implement.
The existing OpenCode agent (agent_loop.py) and the new Hermes agent
both implement this interface, allowing seamless runtime switching.

SSE Event Contract (all backends MUST yield these):
  - data: {"delta": "text"}                          (text chunks)
  - data: {"thinking": true, "delta": "..."}          (reasoning tokens)
  - data: {"type": "tool_start", "tool": "...", ...}  (before tool execution)
  - data: {"type": "tool_output", "tool": "...", ...} (after tool execution)
  - data: {"type": "agent_step", "round": N}          (next agent round)
  - data: {"type": "web_sources", "data": [...]}      (web search results)
  - data: {"type": "metrics", "data": {...}}          (final metrics)
  - data: {"type": "fallback", ...}                   (fallback model used)
  - data: {"type": "message_saved", "id": "..."}      (message persisted)
  - data: [DONE]                                      (end of stream)
"""

import abc
import logging
from typing import AsyncGenerator, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class AgentBackend(abc.ABC):
    """Abstract base class for agent backends.

    All agent implementations (OpenCode, Hermes, future backends) must
    subclass this and implement the required methods.
    """

    # Unique identifier for this backend (used in settings, API, env vars)
    name: str = ""

    # Human-readable display name shown in the UI
    display_name: str = ""

    # Short description of the backend's capabilities
    description: str = ""

    def __init__(self):
        self._initialized = False

    @abc.abstractmethod
    async def stream(
        self,
        endpoint_url: str,
        model: str,
        messages: List[Dict],
        *,
        headers: Optional[Dict] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        prompt_type: Optional[str] = None,
        max_rounds: int = 20,
        max_tool_calls: int = 0,
        context_length: int = 0,
        active_document=None,
        session_id: Optional[str] = None,
        disabled_tools: Optional[Set[str]] = None,
        owner: Optional[str] = None,
        relevant_tools: Optional[Set[str]] = None,
        fallbacks: Optional[List[tuple]] = None,
        _is_teacher_run: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Stream agent responses as SSE events.

        This is the main entry point called by chat_routes.py when
        chat_mode == 'agent'. Must yield SSE-formatted strings.

        Args mirror src/agent_loop.py:stream_agent_loop() exactly so the
        OpenCode backend can delegate directly.
        """
        ...

    @abc.abstractmethod
    async def initialize(self) -> None:
        """Called once at app startup. Set up connections, warm caches, etc."""
        ...

    @abc.abstractmethod
    async def shutdown(self) -> None:
        """Called at app shutdown. Clean up resources."""
        ...

    @abc.abstractmethod
    def is_healthy(self) -> bool:
        """Return True if the backend is ready to handle requests."""
        ...

    def get_info(self) -> Dict:
        """Return backend metadata for the API/UI."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "healthy": self.is_healthy(),
        }


class OpenCodeBackend(AgentBackend):
    """The existing Odysseus agent system (agent_loop.py).

    Named "OpenCode" in the UI for consistency with the project's
    acknowledgments, though it is a fully custom implementation inspired
    by opencode patterns.
    """

    name = "opencode"
    display_name = "OpenCode"
    description = (
        "Built-in multi-round agent with 60+ tools: shell, python, web search, "
        "file I/O, documents, email, calendar, memory, skills, MCP, and more. "
        "Supports both fenced-code-block and native function calling."
    )

    def __init__(self):
        super().__init__()

    async def stream(
        self,
        endpoint_url: str,
        model: str,
        messages: List[Dict],
        *,
        headers: Optional[Dict] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        prompt_type: Optional[str] = None,
        max_rounds: int = 20,
        max_tool_calls: int = 0,
        context_length: int = 0,
        active_document=None,
        session_id: Optional[str] = None,
        disabled_tools: Optional[Set[str]] = None,
        owner: Optional[str] = None,
        relevant_tools: Optional[Set[str]] = None,
        fallbacks: Optional[List[tuple]] = None,
        _is_teacher_run: bool = False,
    ) -> AsyncGenerator[str, None]:
        from src.agent_loop import stream_agent_loop

        async for chunk in stream_agent_loop(
            endpoint_url,
            model,
            messages,
            headers=headers,
            temperature=temperature,
            max_tokens=max_tokens,
            prompt_type=prompt_type,
            max_rounds=max_rounds,
            max_tool_calls=max_tool_calls,
            context_length=context_length,
            active_document=active_document,
            session_id=session_id,
            disabled_tools=disabled_tools,
            owner=owner,
            relevant_tools=relevant_tools,
            fallbacks=fallbacks,
            _is_teacher_run=_is_teacher_run,
        ):
            yield chunk

    async def initialize(self) -> None:
        # OpenCode uses the existing app startup (MCP, tool index, etc.)
        # No additional initialization needed.
        self._initialized = True
        logger.info("OpenCode agent backend ready")

    async def shutdown(self) -> None:
        self._initialized = False

    def is_healthy(self) -> bool:
        return self._initialized


class HermesBackend(AgentBackend):
    """Hermes agent backend — external agent service integration.

    Connects to a Hermes agent service via HTTP/SSE. The service can run:
    - As a local subprocess (HERMES_URL=http://localhost:8200)
    - As a Docker sidecar container
    - As a remote service on another host

    If HERMES_URL is not configured, the backend gracefully degrades to
    the OpenCode agent so the app always works.
    """

    name = "hermes"
    display_name = "Hermes"
    description = (
        "Hermes agent — external agent service with autonomous planning, "
        "multi-step reasoning, and tool orchestration. Connects via HTTP/SSE."
    )

    def __init__(self, url: Optional[str] = None, api_key: Optional[str] = None):
        super().__init__()
        import os
        self._url = url or os.getenv("HERMES_URL", "").rstrip("/")
        self._api_key = api_key or os.getenv("HERMES_API_KEY", "")
        self._fallback_backend: Optional[AgentBackend] = None

    def set_fallback(self, backend: AgentBackend) -> None:
        """Set a fallback backend to use when Hermes is unavailable."""
        self._fallback_backend = backend

    async def stream(
        self,
        endpoint_url: str,
        model: str,
        messages: List[Dict],
        *,
        headers: Optional[Dict] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        prompt_type: Optional[str] = None,
        max_rounds: int = 20,
        max_tool_calls: int = 0,
        context_length: int = 0,
        active_document=None,
        session_id: Optional[str] = None,
        disabled_tools: Optional[Set[str]] = None,
        owner: Optional[str] = None,
        relevant_tools: Optional[Set[str]] = None,
        fallbacks: Optional[List[tuple]] = None,
        _is_teacher_run: bool = False,
    ) -> AsyncGenerator[str, None]:
        if not self._url or not self.is_healthy():
            # Hermes unavailable — fall back to OpenCode silently
            if self._fallback_backend and self._fallback_backend.is_healthy():
                logger.warning("Hermes unavailable, falling back to OpenCode agent")
                async for chunk in self._fallback_backend.stream(
                    endpoint_url, model, messages,
                    headers=headers, temperature=temperature,
                    max_tokens=max_tokens, prompt_type=prompt_type,
                    max_rounds=max_rounds, max_tool_calls=max_tool_calls,
                    context_length=context_length, active_document=active_document,
                    session_id=session_id, disabled_tools=disabled_tools,
                    owner=owner, relevant_tools=relevant_tools,
                    fallbacks=fallbacks, _is_teacher_run=_is_teacher_run,
                ):
                    yield chunk
                return

        # Hermes is available — proxy to the external service
        import httpx
        import json

        payload = {
            "endpoint_url": endpoint_url,
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "max_rounds": max_rounds,
            "max_tool_calls": max_tool_calls,
            "session_id": session_id,
            "owner": owner,
        }
        if headers:
            payload["headers"] = headers
        if disabled_tools:
            payload["disabled_tools"] = list(disabled_tools)
        if relevant_tools:
            payload["relevant_tools"] = list(relevant_tools)

        req_headers = {"Content-Type": "application/json"}
        if self._api_key:
            req_headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream(
                    "POST",
                    f"{self._url}/v1/agent/stream",
                    json=payload,
                    headers=req_headers,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            yield line
        except Exception as e:
            logger.error(f"Hermes stream error: {e}")
            # On error, fall back to OpenCode
            if self._fallback_backend and self._fallback_backend.is_healthy():
                logger.info("Falling back to OpenCode after Hermes error")
                async for chunk in self._fallback_backend.stream(
                    endpoint_url, model, messages,
                    headers=headers, temperature=temperature,
                    max_tokens=max_tokens, prompt_type=prompt_type,
                    max_rounds=max_rounds, max_tool_calls=max_tool_calls,
                    context_length=context_length, active_document=active_document,
                    session_id=session_id, disabled_tools=disabled_tools,
                    owner=owner, relevant_tools=relevant_tools,
                    fallbacks=fallbacks, _is_teacher_run=_is_teacher_run,
                ):
                    yield chunk
            else:
                import json as _json
                yield f'data: {_json.dumps({"delta": f"Hermes agent error: {e}. Please switch to OpenCode agent in Settings."})}\n\n'
                yield 'data: [DONE]\n\n'

    async def initialize(self) -> None:
        self._initialized = True
        if self._url:
            logger.info(f"Hermes agent backend configured (url={self._url})")
        else:
            logger.info("Hermes agent backend registered (no URL set — will use OpenCode fallback)")

    async def shutdown(self) -> None:
        self._initialized = False

    def is_healthy(self) -> bool:
        # Hermes is "healthy" if it's initialized, even without a URL.
        # When no URL is set, stream() will silently fall back to OpenCode.
        # This prevents "Hermes not running" errors in the UI.
        return self._initialized

    def get_info(self) -> Dict:
        info = super().get_info()
        info["url"] = self._url or None
        info["has_fallback"] = self._fallback_backend is not None
        return info


class LeadHunterBackend(AgentBackend):
    """LeadHunter agent backend — lead discovery and email marketing.

    Provides capabilities for discovering Product Hunt and beta startups,
    scoring leads, syncing to Listmonk, and campaign analytics.
    """

    name = "leadhunter"
    display_name = "LeadHunter"
    description = (
        "LeadHunter agent — discover startups from Product Hunt and beta platforms, "
        "score leads, sync to Listmonk, and track campaign analytics."
    )

    def __init__(self):
        super().__init__()
        self._service: Optional[Any] = None
        self._fallback_backend: Optional[AgentBackend] = None

    def set_fallback(self, backend: AgentBackend) -> None:
        """Set a fallback backend to use when LeadHunter is unavailable."""
        self._fallback_backend = backend

    async def initialize(self) -> None:
        logger.info("LeadHunter initializing")
        from services.leadhunter import get_lead_hunter_service
        self._service = get_lead_hunter_service()
        await self._service.initialize()
        self._initialized = True
        logger.info("LeadHunter initialized and healthy")

    async def shutdown(self) -> None:
        if self._service:
            await self._service.shutdown()
        self._initialized = False

    def is_healthy(self) -> bool:
        return self._initialized and self._service is not None

    async def stream(
        self,
        endpoint_url: str,
        model: str,
        messages: List[Dict],
        *,
        headers: Optional[Dict] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        prompt_type: Optional[str] = None,
        max_rounds: int = 20,
        max_tool_calls: int = 0,
        context_length: int = 0,
        active_document=None,
        session_id: Optional[str] = None,
        disabled_tools: Optional[Set[str]] = None,
        owner: Optional[str] = None,
        relevant_tools: Optional[Set[str]] = None,
        fallbacks: Optional[List[tuple]] = None,
        _is_teacher_run: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Stream LeadHunter agent responses.

        Delegates to fallback backend but restricts to LeadHunter tools only.
        """
        if not self._initialized or not self._service:
            if self._fallback_backend and self._fallback_backend.is_healthy():
                lead_tools = {
                    "discover_producthunt_leads", "discover_beta_leads", "score_leads",
                    "sync_to_listmonk", "campaign_metrics", "export_leads",
                }
                import json as _json
                yield f'data: {_json.dumps({"delta": "LeadHunter unavailable, using fallback"})}\n\n'
                async for chunk in self._fallback_backend.stream(
                    endpoint_url, model, messages,
                    headers=headers, temperature=temperature,
                    max_tokens=max_tokens, prompt_type=prompt_type,
                    max_rounds=max_rounds, max_tool_calls=max_tool_calls,
                    context_length=context_length, active_document=active_document,
                    session_id=session_id, disabled_tools=disabled_tools,
                    owner=owner, relevant_tools=lead_tools if relevant_tools is None else relevant_tools | lead_tools,
                    fallbacks=fallbacks, _is_teacher_run=_is_teacher_run,
                ):
                    yield chunk
                return
            import json as _json
            yield f'data: {_json.dumps({"delta": "LeadHunter agent not initialized"})}\n\n'
            yield 'data: [DONE]\n\n'
            return

        lead_tools = {
            "discover_producthunt_leads", "discover_beta_leads", "score_leads",
            "sync_to_listmonk", "campaign_metrics", "export_leads",
        }

        filtered_tools = lead_tools if disabled_tools is None else (disabled_tools - lead_tools)

        from src.agent_loop import stream_agent_loop
        async for chunk in stream_agent_loop(
            endpoint_url,
            model,
            messages,
            headers=headers,
            temperature=temperature,
            max_tokens=max_tokens,
            prompt_type=prompt_type,
            max_rounds=max_rounds,
            max_tool_calls=max_tool_calls,
            context_length=context_length,
            active_document=active_document,
            session_id=session_id,
            disabled_tools=filtered_tools,
            owner=owner,
            relevant_tools=lead_tools if relevant_tools is None else relevant_tools | lead_tools,
            fallbacks=fallbacks,
            _is_teacher_run=_is_teacher_run,
        ):
            yield chunk

    def get_info(self) -> Dict:
        info = super().get_info()
        if self._service:
            info["stats"] = self._service.get_stats()
        return info
