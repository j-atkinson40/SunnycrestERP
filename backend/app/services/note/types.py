"""Standing-set types.

Per DECISIONS 2026-09-04 ("The note has two registers, and only one of them is
composed"). The standing set is the register that is CONFIGURED — positionally
stable, always present, never ordered or selected by Intelligence, because
composition destroys the positional memory that makes a standing line cheap to
use.

Prose fragments are the other register and live in `app/services/fragments/`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

#: DECISIONS 2026-09-04: "Standing set is capped at 7 per role... Most roles
#: will sit well below it; a role approaching 7 is a signal about that role's
#: design, not grounds to raise the cap."
#:
#: ⚠️ THE CAP IS FROM 2026-09-04. THE ADMISSION TEST IS NOT, AND THIS DOCSTRING
#: QUOTED THE SUPERSEDED ONE UNTIL 2026-09-11. It read "referenced most days
#: rather than useful sometimes"; the test was TIGHTENED 2026-09-09 and
#: `note/registry.py` carries the live one — NEEDS CHECKING AGAINST SOMETHING IN
#: THE USER'S HAND AT AN UNPREDICTABLE MOMENT. The difference is kind, not
#: strictness: anything looked at on a rhythm is a report.
#:
#: The tightening landed in the neighbouring file and this one kept asking the
#: old question. Quote the cap here; point at registry.py for the test, so there
#: is one copy of a thing that has already changed once.
#:
#: ⚠️ ENFORCED LIVE FROM THIS COMMIT, not deferred as unreachable. Measured
#: 2026-09-04: all 18 production users have zero `work_areas`, so every user
#: currently resolves through the vertical-default fallback whose largest set is
#: 5. But a user selecting all five populated work areas resolves 8, and
#: `OperatorOnboardingFlow` can write work_areas today. The first person through
#: onboarding is the person who breaks it.
MAX_STANDING_ENTRIES = 7

#: A standing line's target is ALWAYS a peek. Per DECISIONS 2026-09-04 ("A
#: standing line never opens a Focus directly"): the set's value is that every
#: entry costs the same, and one heavyweight click hidden among seven cheap ones
#: destroys that in a single instance.
StandingTargetSurface = Literal["peek"]


class StandingSetError(ValueError):
    """A standing set violated the register's rules. Raised at CONFIGURATION
    time, not at render — a bad set must fail where someone is editing it, not
    silently truncate in front of a reader."""


@dataclass(frozen=True)
class StandingEntry:
    """One line in the standing set.

    Positionally stable: entries do not reorder, do not appear, and do not
    disappear. Position IS the affordance — a user who has stopped reading the
    labels and simply hits the third one is relying on that.
    """

    entry_id: str
    label: str

    #: What the line opens. Type-level and always a peek; the peek layer itself
    #: is session 3, so this is DECLARED AND NOT WIRED. A standing line renders
    #: today as a labelled entry with a live count and no open behaviour.
    #: Deliberately not stubbed: a placeholder interaction would have to be
    #: removed, and removing an interaction users have learned is worse than
    #: never shipping it.
    target_surface: StandingTargetSurface = "peek"
    target_key: str = ""

    #: How the live count is resolved, or None for a line that carries no count.
    #: ⚠️ COUNTS ARE OF DISTINCT SUBJECTS, never of raw rows — see
    #: `counts.resolve_count`. A count is a fact the user reads; a badge is a
    #: demand. No colour escalation, no growth to catch the eye, no red.
    count_source: str | None = None

    #: ⚠️ HELD FOR SESSION 5 (operator review, 2026-09-09): a `99+` CAP.
    #: A count that keeps growing is a number that starts competing for
    #: attention, which is the growth-to-catch-the-eye this register already
    #: refuses in the note above. Capping the display is the obvious answer and
    #: it is a rendering decision that belongs with owner/backup routing and
    #: Pulse retirement, not bolted on here. Recorded so it is a decision taken
    #: rather than a default inherited.
    #:
    #: Free-form, register-opaque.
    metadata: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "label": self.label,
            "target_surface": self.target_surface,
            "target_key": self.target_key,
            "count_source": self.count_source,
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "StandingEntry":
        return cls(
            entry_id=str(d["entry_id"]),
            label=str(d.get("label", "")),
            target_surface="peek",
            target_key=str(d.get("target_key", "")),
            count_source=d.get("count_source"),
            metadata=d.get("metadata") or {},
        )


#: ⚠️ WHY THIS EXISTS. The rule "a failed count renders as no count, never zero"
#: is right, and taken alone it made two different states indistinguishable from
#: outside: an entry that HAS no count and an entry whose count FAILED both
#: rendered as nothing. An operator reviewing the surface could not tell a
#: deliberate blank from three silent failures — the absent-signal problem
#: appearing in the UI itself.
#:
#: So the payload distinguishes them even though the reader may not need to:
#:   "absent"      — the entry declares no count_source. Nothing to show.
#:   "ok"          — resolved. `count` is the number.
#:   "unavailable" — a count_source was declared and resolution FAILED.
#:                   Still never rendered as zero; zero is a claim.
CountState = Literal["absent", "ok", "unavailable"]


@dataclass(frozen=True)
class ResolvedStandingEntry:
    """An entry with its count resolved, ready to render."""

    entry: StandingEntry
    #: None for both "absent" and "unavailable" — see `state` to tell them apart.
    count: int | None
    #: Which tier this entry came from: "role" | "tenant" | "user".
    tier: str
    state: CountState = "absent"
