"""Role standing-set templates — tier 1, code-declared.

⚠️ WHY THIS TIER IS CODE AND NOT A TABLE. The session-1 dispatch named the Focus
layout-state pattern for a three-tier configuration. Measured, that pattern's
tiers are `active user session → recent closed user session → tenant default` —
two user-scoped tiers plus a tenant baseline, with NO role tier. Reusing it as
named would have meant inventing one.

The role-keyed precedent that does exist is `spaces/registry.py::SEED_TEMPLATES`,
keyed on `(vertical, role_slug)` and code-declared. So the cascade composes two
in-repo patterns rather than inventing a tier:

    code role template  →  tenant override  →  user override
    (this module)          (standing_set_configs rows)

A director's standing set is a vertical design artifact, not tenant data. It
belongs on the code side of the same code-declared/config-enabled split the
fragment registry follows, where "referenced most days" is a design decision
someone argued for rather than a value a tenant drifted into.

⚠️ THE TEMPLATES BELOW ARE DELIBERATELY SPARSE. Canon's admission test is
"referenced most days", not "useful sometimes", and most roles should sit well
below the cap of 7. Session 1 seeds only what the operational layer's
decomposition actually supports; adding entries is cheap and removing them from
under a user who has learned their positions is not.
"""

from __future__ import annotations

import logging
from typing import Mapping

from app.services.note.types import (
    MAX_STANDING_ENTRIES,
    StandingEntry,
    StandingSetError,
)

logger = logging.getLogger(__name__)


def _e(entry_id: str, label: str, target_key: str, count_source: str | None = None):
    return StandingEntry(
        entry_id=entry_id,
        label=label,
        target_surface="peek",
        target_key=target_key,
        count_source=count_source,
    )


#: Keyed `(vertical, role_slug)`, exactly as `spaces` keys its seed templates.
#:
#: ⚠️ DERIVED FROM `operational_layer_service`'s VERTICAL DEFAULTS, not from its
#: work-area mapping. Measured 2026-09-04: all 18 production users have zero
#: `work_areas`, so every real user resolves through the vertical-default
#: fallback — manufacturing 5 widgets, the other three verticals 2. The
#: work-area mapping's breadth is untested because its input has never existed,
#: so seeding from it would be seeding from a path nobody has walked.
ROLE_TEMPLATES: dict[tuple[str, str], tuple[StandingEntry, ...]] = {
    ("manufacturing", "admin"): (
        _e("schedule", "Schedule", "vault_schedule"),
        _e("production", "Production", "line_status"),
        _e("today", "Today", "today"),
        _e("anomalies", "Needs attention", "anomalies", count_source="anomalies"),
    ),
    ("manufacturing", "production"): (
        _e("schedule", "Schedule", "vault_schedule"),
        _e("production", "Production", "line_status"),
        _e("today", "Today", "today"),
    ),
    ("manufacturing", "dispatcher"): (
        _e("schedule", "Schedule", "vault_schedule"),
        _e("ancillary", "Ancillary pool", "scheduling.ancillary-pool"),
        _e("today", "Today", "today"),
    ),
    ("manufacturing", "accountant"): (
        _e("anomalies", "Needs attention", "anomalies", count_source="anomalies"),
        _e("ar", "Receivables", "ar_summary"),
        _e("today", "Today", "today"),
    ),
    # The three non-manufacturing verticals share the sparse default the
    # operational layer already falls back to. Two entries, not five.
    ("funeral_home", "director"): (
        _e("today", "Today", "today"),
        _e("activity", "Recent activity", "recent_activity"),
    ),
    ("cemetery", "admin"): (
        _e("today", "Today", "today"),
        _e("activity", "Recent activity", "recent_activity"),
    ),
    ("crematory", "admin"): (
        _e("today", "Today", "today"),
        _e("activity", "Recent activity", "recent_activity"),
    ),
}

#: Every role without a template. Deliberately minimal rather than empty: a user
#: with no standing set has no positional memory to build, and the register's
#: whole value is that position means something.
FALLBACK_TEMPLATE: tuple[StandingEntry, ...] = (
    _e("today", "Today", "today"),
)


def validate_entries(entries: tuple[StandingEntry, ...] | list[StandingEntry]) -> None:
    """Enforce the register's rules. Raises rather than truncating.

    ⚠️ CLEAR ERROR, NEVER SILENT TRUNCATION. Canon caps the set at 7; truncating
    to fit would drop the eighth entry without telling the person configuring it,
    and they would discover it by noticing something missing — which is exactly
    the failure mode the cap exists to prevent.
    """
    entries = list(entries)

    if len(entries) > MAX_STANDING_ENTRIES:
        raise StandingSetError(
            f"A standing set may hold at most {MAX_STANDING_ENTRIES} entries; "
            f"this one has {len(entries)}. The cap is not a rendering limit — "
            "canon treats a role approaching 7 as a signal about that role's "
            "design. Decide which entries are referenced MOST DAYS and drop the "
            "rest; they are not lost, they are reachable by peek and by prose."
        )

    seen: set[str] = set()
    for e in entries:
        if not e.entry_id or not e.entry_id.strip():
            raise StandingSetError("Every standing entry needs an entry_id.")
        if e.entry_id in seen:
            raise StandingSetError(
                f"Duplicate standing entry {e.entry_id!r}. Entries are "
                "positionally stable, so two lines with one id have no stable "
                "position between them."
            )
        seen.add(e.entry_id)

        # A standing line's target is always a peek — refused at the door
        # rather than validated after, the way subject_kind is.
        if e.target_surface != "peek":
            raise StandingSetError(
                f"{e.entry_id}: a standing line's target must be a peek, not "
                f"{e.target_surface!r}. Per canon it may never open a Focus "
                "directly: the set's value is that every entry costs the same, "
                "and one heavyweight click hidden among cheap ones destroys "
                "that in a single instance. Focus entrances come from prose "
                "fragments, or from inside a peek."
            )


def template_for(vertical: str | None, role_slug: str | None) -> tuple[StandingEntry, ...]:
    """Tier 1. Returns the fallback when the pair has no template."""
    key = (vertical or "", role_slug or "")
    return ROLE_TEMPLATES.get(key, FALLBACK_TEMPLATE)


def all_templates() -> Mapping[tuple[str, str], tuple[StandingEntry, ...]]:
    return dict(ROLE_TEMPLATES)
