"""Pulse composition defaults per (vertical, role_slug).

Phase B Session 1 introduces this module as infrastructure-only. It
defines:

  - `PulseComposition` dataclass with the four-layer Pulse structure
    (Personal / Operational / Anomaly / Activity) per PLATFORM_
    ARCHITECTURE.md §3.3.
  - `HOME_PULSE_COMPOSITIONS: dict[(vertical, role_slug),
    PulseComposition]` — the role-defaulted composition the Phase D
    Pulse engine will consume as the baseline when composing a user's
    Home Space Pulse.

Status: **infrastructure shell, not consumed yet.** Phase D builds
the React Pulse composition engine that reads from this dict and
renders the composed surface. Phase B Session 1 ships this file so
the (manufacturing, dispatcher) composition exists from day one —
when Phase D lands, dispatchers get their Funeral Schedule
composition without a separate migration.

**Consistent with SPACES_PLAN.md §2:** role-context differentiation
lives in Pulse composition defaults on Home, NOT in separate Spaces.
The existing `SEED_TEMPLATES` dict in `registry.py` (which seeds 13
per-role Spaces) is NOT stripped by Phase B — Phase D owns that
transition. Phase B adds the new-shape data alongside the old-shape
data; neither consumes the other.

**Not coupled to Phase D engine internals.** The `PulseComponentSpec`
dataclass is a forward-compatible descriptor: component_key +
params. The Phase D engine knows how to render each component_key;
this file only declares which components appear in which layer for
which role.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


# Verticals that can have HOME_PULSE_COMPOSITIONS entries. Matches
# the `company.vertical` enum — adding a vertical here requires
# also adding composition entries for every role in that vertical.
Vertical = Literal["funeral_home", "manufacturing", "cemetery", "crematory"]


PulseLayer = Literal["personal", "learning", "operational", "anomaly", "activity"]


@dataclass(frozen=True)
class PulseComponentSpec:
    """One composition entry — tells the Phase D engine what to render
    and how to scope it.

    `component_key` identifies the widget/renderer (e.g.
    `"funeral_schedule"`, `"briefing_card"`, `"saved_view"`). The
    engine maintains a registry mapping component_key → React
    component. Unknown keys render as a muted "Component not yet
    available" placeholder so the platform degrades gracefully as
    new components ship.

    `params` are the component's render-time parameters. Convention:
    saved-view components pass `{"seed_key": "saved_view_seed:..."}`;
    query-bound components pass whatever filter/date/id the engine
    needs to resolve the scope.
    """

    component_key: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PulseComposition:
    """The default four-layer Pulse composition for one (vertical,
    role_slug) combination. Phase D overlays per-user customizations
    on top of this baseline via observe-and-offer + explicit user
    drag-drop rearrangement.

    Layer shape intentionally matches PA §3.3:
      - personal:    your work, your decisions waiting
      - operational: today's rhythm
      - anomaly:     what's unusual, what needs attention
      - activity:    recent changes

    `learning` is a fifth layer reserved for My Stuff Space (per
    SPACES_PLAN §3.14 platform-learning scope). Home Space
    compositions should leave `learning` empty; the schema includes
    it so one dataclass serves both surfaces.
    """

    personal: tuple[PulseComponentSpec, ...] = ()
    operational: tuple[PulseComponentSpec, ...] = ()
    anomaly: tuple[PulseComponentSpec, ...] = ()
    activity: tuple[PulseComponentSpec, ...] = ()
    learning: tuple[PulseComponentSpec, ...] = ()


# ── Helpers — shorthand constructors to keep the dict below readable


def _saved_view(seed_key: str, **params: Any) -> PulseComponentSpec:
    """Reference a seeded saved view by its stable seed key. Resolved
    at render time against the caller's own saved views + any shared
    with their role. See `saved_views/seed.py` for seed-key format
    (`saved_view_seed:{role_slug}:{template_id}`)."""
    return PulseComponentSpec(
        component_key="saved_view",
        params={"seed_key": seed_key, **params},
    )


def _widget(component_key: str, **params: Any) -> PulseComponentSpec:
    return PulseComponentSpec(component_key=component_key, params=params)


# ── HOME_PULSE_COMPOSITIONS ───────────────────────────────────────────
# One entry per (vertical, role_slug). Adding a vertical × role
# combination here is all that's required to ship a Pulse default
# for that combo; Phase D wires the rendering.
#
# Lookup semantics (for Phase D reference):
#   1. Look up (company.vertical, user.role.slug).
#   2. If no entry, fall back to (vertical, None) vertical-wide default.
#   3. If still none, fall back to FALLBACK_HOME_PULSE.
#
# User overrides are stored separately in
# User.preferences.home_pulse_overrides and merged on top at render
# time.


HOME_PULSE_COMPOSITIONS: dict[tuple[str, str], PulseComposition] = {}


# ── (manufacturing, dispatcher) ──────────────────────────────────────
# Phase B Session 1 demo hero composition. Dispatcher's Home Pulse
# centers on the three-day Funeral Schedule widget with supporting
# context. (Phase 3.3.1 rename: previously "dispatch_monitor"; the
# widget is "Funeral Schedule" — "Monitor" is the architectural noun
# for Pulse's purpose, not a component name.)

HOME_PULSE_COMPOSITIONS[("manufacturing", "dispatcher")] = PulseComposition(
    personal=(
        # Morning briefing surfaces the dispatcher's day: what's
        # finalized, what's still draft, what needs attention.
        _widget("briefing_card", flavor="dispatch"),
        # Count of deliveries awaiting driver assignment across all
        # open days.
        _widget("pending_dispatch_count"),
        # Triage queue — any dispatcher-targeted triage items.
        _widget("my_triage_pending"),
    ),
    operational=(
        # THE HERO — the three-day Funeral Schedule. Drives most of
        # the page. Phase B ships this as a standalone route
        # (`/dispatch/funeral-schedule`) with this component_key
        # also registered for Phase D composition.
        _widget("funeral_schedule", days=3),
        # Saved-view shortcuts for the dispatcher — show up
        # underneath the schedule as "deeper lists."
        _saved_view(
            "saved_view_seed:dispatcher:pending_dispatch",
            label="Needs a driver",
        ),
        _saved_view(
            "saved_view_seed:dispatcher:this_weeks_deliveries",
            label="This week",
        ),
        _saved_view(
            "saved_view_seed:dispatcher:ancillary_pending",
            label="Ancillary pickup/drop",
        ),
        _saved_view(
            "saved_view_seed:dispatcher:direct_ship_pending",
            label="Direct ship",
        ),
        # Driver roster summary — count available drivers + brief
        # service-type breakdown. No capacity metric per user scope
        # decision.
        _widget("driver_roster_summary"),
    ),
    anomaly=(
        # Deliveries for past dates still in draft (missed
        # finalization — shouldn't happen normally).
        _widget("overdue_draft_schedules"),
        # Deliveries scheduled but without a driver assigned past the
        # normal assignment window.
        _widget("unassigned_near_deadline"),
        # Cross-tenant coordination issues — when manufacturer is
        # expecting info from an FH that hasn't arrived.
        _widget("delivery_coordination_anomalies"),
    ),
    activity=(
        # Recent schedule state transitions (finalized, reverted).
        _widget("recent_schedule_events"),
        # Recent driver status updates (clock-in, route-started,
        # delivery-completed).
        _widget("recent_driver_activity"),
    ),
)


# ── Lookup helpers (used by tests + future Phase D engine) ───────────


def get_home_pulse_composition(
    vertical: str | None,
    role_slug: str | None,
) -> PulseComposition | None:
    """Look up the default Pulse composition for a (vertical, role)
    combination.

    Returns None if no entry matches. Callers should fall back to
    `FALLBACK_HOME_PULSE` or render an explicit empty state. Phase D
    engine must handle None gracefully.
    """
    if vertical is None or role_slug is None:
        return None
    return HOME_PULSE_COMPOSITIONS.get((vertical, role_slug))


# Fallback composition for users whose (vertical, role) isn't
# explicitly seeded. Minimal, not zero — briefing + tasks only.
FALLBACK_HOME_PULSE = PulseComposition(
    personal=(
        _widget("briefing_card"),
        _widget("my_triage_pending"),
    ),
    operational=(),
    anomaly=(),
    activity=(),
)
