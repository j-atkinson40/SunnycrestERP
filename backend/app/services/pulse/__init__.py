"""Phase W-4a Pulse package — Home Space's intelligence-composed surface.

Per BRIDGEABLE_MASTER §3.26 + DESIGN_LANGUAGE §13.

Package layout:
  • types.py          — shared dataclasses (LayerItem, LayerContent)
  • personal_layer_service.py    — Personal layer composition (tasks,
                                    approvals, mentions stubbed for W-4b)
  • operational_layer_service.py — Operational layer composition (per
                                    work_areas → widget mapping)
  • anomaly_layer_service.py     — Anomaly layer (agent_anomalies +
                                    computed risks)
  • activity_layer_service.py    — Activity layer (recent_activity +
                                    system events; comms stubbed for W-4b)
  • composition_engine.py        — Phase W-4a Commit 3 (orchestrates the
                                    four layer services into a cached
                                    Pulse response per user)

Each layer service exports a `compose_for_user(db, user, ...)` function
that returns a `LayerContent` shape with structured items + metadata.
The composition engine (Commit 3) calls all four in parallel and
assembles the Pulse response.

Tenant isolation discipline (canon from Phase W-3a anomalies widget +
Phase 8e.1 affinity): every query filters by `company_id ==
user.company_id` explicitly. Cross-tenant data must never leak through
Pulse, which surfaces signals to users in their own tenant context only.
"""

from app.services.pulse.types import (
    IntelligenceStream,
    LayerContent,
    LayerItem,
    LayerName,
    PulseComposition,
    PulseCompositionMetadata,
    ReferencedItem,
    TimeOfDaySignal,
)

__all__ = [
    "IntelligenceStream",
    "LayerContent",
    "LayerItem",
    "LayerName",
    "PulseComposition",
    "PulseCompositionMetadata",
    "ReferencedItem",
    "TimeOfDaySignal",
]
