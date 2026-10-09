"""Registry of what NOVA can really do right now.

This is the single source of truth behind ``GET /system/capabilities``: a capability
that is not built, not configured or not reachable is reported as such, never implied.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Literal

from pydantic import BaseModel

CapabilityStatus = Literal["available", "degraded", "unavailable", "not_implemented"]

CAPABILITY_IDS: tuple[str, ...] = (
    "chat.local",
    "chat.cloud",
    "research.search",
    "research.fetch",
    "image.generate",
    "agent.fs",
    "agent.exec",
    "agent.git",
    "voice.stt",
    "voice.tts",
)

_logger = logging.getLogger("nova_core.capabilities")


class CapabilityState(BaseModel):
    id: str
    status: CapabilityStatus
    reason: str | None = None
    detail: str | None = None


Probe = Callable[[], Awaitable[CapabilityState]]


class CapabilityRegistry:
    def __init__(self) -> None:
        # Insertion-ordered; registering an existing id keeps its position.
        self._probes: dict[str, Probe] = {}

    def register(self, capability_id: str, probe: Probe) -> None:
        self._probes[capability_id] = probe

    def declare_not_implemented(self, capability_id: str) -> None:
        async def probe() -> CapabilityState:
            return CapabilityState(id=capability_id, status="not_implemented")

        self.register(capability_id, probe)

    async def snapshot(self) -> list[CapabilityState]:
        states: list[CapabilityState] = []
        for capability_id, probe in self._probes.items():
            try:
                state = (await probe()).model_copy(update={"id": capability_id})
            except Exception:
                _logger.exception("capability probe failed", extra={"capability": capability_id})
                state = CapabilityState(
                    id=capability_id, status="unavailable", reason="probe_failed"
                )
            states.append(state)
        return states
