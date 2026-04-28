"""Pulse API — Phase W-4a Commits 3 + 4.

Endpoints:
  • GET  /api/v1/pulse/composition       — Commit 3, single composed
                                            endpoint per D1
  • POST /api/v1/pulse/signals/dismiss   — Commit 4, signal tracking
                                            (Tier 2 input)
  • POST /api/v1/pulse/signals/navigate  — Commit 4, signal tracking
                                            (Tier 2 input)

Tenant + user scoped via the canonical `get_current_user` dependency.
Composition cache (5-min TTL) keyed on
`pulse:{user_id}:{work_areas_hash}:{minute_window}` per D1.
`?refresh=true` query param bypasses cache for manual reload.

Signal endpoints persist to `pulse_signals` with
standardized JSONB metadata shapes (see r61 migration docstring).
Cross-user writes are structurally impossible — both endpoints
force `user_id = current_user.id` server-side; request bodies
NEVER carry user_id or company_id.
"""
from __future__ import annotations

from dataclasses import asdict, fields, is_dataclass
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.pulse import composition_engine, signal_service
from app.services.pulse.signal_service import SignalValidationError


router = APIRouter()


def _serialize(obj: Any) -> Any:
    """Convert PulseComposition (frozen dataclasses) to a JSON-
    compatible dict. Mirrors `composition_cache._dataclass_to_dict`
    but kept local to the route module so the API contract is
    self-contained — the cache module's serialization is internal."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if is_dataclass(obj) and not isinstance(obj, type):
        return {
            f.name: _serialize(getattr(obj, f.name))
            for f in fields(obj)
        }
    if isinstance(obj, list):
        return [_serialize(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    return obj


@router.get("/composition")
def get_pulse_composition(
    refresh: bool = Query(
        default=False,
        description=(
            "Bypass the composition cache and recompute. "
            "Frontend's manual refresh affordance sets this; normal "
            "page loads omit it and rely on the 5-min TTL + work_areas-"
            "aware invalidation."
        ),
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current user's Home Pulse composition.

    Response shape (frozen dataclasses serialized to JSON):
      {
        "user_id": "...",
        "composed_at": "ISO-8601",
        "layers": [
          {
            "layer": "personal" | "operational" | "anomaly" | "activity",
            "items": [LayerItem, ...],
            "advisory": str | null,
          },
          ...
        ],
        "intelligence_streams": [IntelligenceStream, ...],
        "metadata": {
          "work_areas_used": [str, ...],
          "vertical_default_applied": bool,
          "time_of_day_signal": "morning" | "midday" | "end_of_day" | "off_hours",
        },
      }

    Tenant isolation: every layer service enforces tenant scoping
    on its own queries; `current_user.company_id` is the
    authoritative scope. Cross-tenant data cannot leak through this
    endpoint.
    """
    composition = composition_engine.compose_for_user(
        db, user=current_user, bypass_cache=refresh
    )
    return _serialize(composition)


# ── Phase W-4a Commit 4 — Signal tracking endpoints ────────────────


class _DismissSignalRequest(BaseModel):
    """Body for POST /pulse/signals/dismiss.

    `component_key` + `layer` identify the dismissed Pulse piece.
    `time_of_day` is required so Tier 2 algorithms can reason about
    "user dismissed X consistently in the morning" patterns.
    `work_areas_at_dismiss` is the snapshot of user.work_areas at
    dismiss time — enables "user dismissed X while in [area]"
    correlations.

    user_id + company_id are NOT in the body — forced server-side
    from `get_current_user`. Cross-user writes are structurally
    impossible.
    """

    component_key: str = Field(..., min_length=1, max_length=128)
    layer: str = Field(..., min_length=1, max_length=32)
    time_of_day: str = Field(..., min_length=1, max_length=32)
    work_areas_at_dismiss: list[str] | None = None


class _NavigateSignalRequest(BaseModel):
    """Body for POST /pulse/signals/navigate.

    `from_component_key` + `layer` identify the originating Pulse
    piece. `to_route` is the navigation target. `dwell_time_seconds`
    is how long the user spent on Pulse before navigating — shorter
    dwell + frequent click-through suggests strong relevance signal;
    long dwell + occasional click-through suggests browse-mode.

    user_id + company_id forced server-side as above.
    """

    from_component_key: str = Field(..., min_length=1, max_length=128)
    to_route: str = Field(..., min_length=1, max_length=1024)
    dwell_time_seconds: float = Field(..., ge=0)
    layer: str = Field(..., min_length=1, max_length=32)


def _signal_response(sig) -> dict:
    """Minimal canonical response shape — id + timestamp confirms
    persistence; metadata returned for client-side validation
    convenience."""
    return {
        "id": sig.id,
        "signal_type": sig.signal_type,
        "layer": sig.layer,
        "component_key": sig.component_key,
        "timestamp": sig.timestamp.isoformat() if sig.timestamp else None,
        "metadata": sig.signal_metadata,
    }


@router.post("/signals/dismiss", status_code=status.HTTP_201_CREATED)
def post_dismiss_signal(
    body: _DismissSignalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Persist a dismiss signal for the current user.

    Tier 2 input: a dismiss is a strong "this isn't useful right
    now" signal that drives composition de-prioritization in future
    requests. Phase W-4a captures the signal; Tier 2 algorithms
    consume it post-September.

    Tenant + user scoping forced server-side: cross-user / cross-
    tenant writes are structurally impossible (user_id + company_id
    derived from the authenticated User).
    """
    try:
        sig = signal_service.record_dismiss(
            db,
            user=current_user,
            component_key=body.component_key,
            layer=body.layer,
            time_of_day=body.time_of_day,
            work_areas_at_dismiss=body.work_areas_at_dismiss,
        )
    except SignalValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return _signal_response(sig)


@router.post("/signals/navigate", status_code=status.HTTP_201_CREATED)
def post_navigate_signal(
    body: _NavigateSignalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Persist a navigation signal for the current user.

    Tier 2 input: navigation patterns identify which Pulse pieces
    consistently lead to which routes. Future composition can offer
    those routes as quick actions on the originating piece.

    Tenant + user scoping forced server-side as above.
    """
    try:
        sig = signal_service.record_navigation(
            db,
            user=current_user,
            from_component_key=body.from_component_key,
            to_route=body.to_route,
            dwell_time_seconds=body.dwell_time_seconds,
            layer=body.layer,
        )
    except SignalValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return _signal_response(sig)
