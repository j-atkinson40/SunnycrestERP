"""When a field applies, and when it is required.

⚠️ TWO SLOTS, ONE MACHINERY. A field declares `applies_when` (is it asked at all?)
and `required_when` (is leaving it unanswered a GAP?). The inventory Piece 4 was
derived from proves both are needed: it says *required when* for the dates and
*applies when* for `nameplate_date_format`. The dates are always SHOWN and become a
gap only under personalization; collapsing the two slots would hide them until
personalization was chosen, which nothing asked for.

⚠️ NODES ARE DATA, NOT CALLABLES, and that is the load-bearing choice. A callable
cannot declare its own edges, and the edges are the whole mechanism — without them
there is no dependency graph, no topological order, and no cycle check. Every node
exposes exactly two things: `depends_on` (the field ids it reads) and
`evaluate(ctx)`.

⚠️ THREE-VALUED, BECAUSE TWO VALUES LOSE THE CASE THAT MATTERS. "Any personalization
chosen" with all three questions unanswered is not FALSE — reading it as FALSE means
the dates are not required now and silently BECOME required the moment someone picks
a flag, a requirement appearing mid-flow with no explanation. It is INDETERMINATE,
and canon already names that state: *depends on an answer not yet given.*

⚠️ AVAILABILITY IS ONE NODE AMONG SIX, NOT THE MODEL. `AvailabilityOffered` reads the
licensee's config rather than the answers — but it declares
`depends_on == (VAULT_FIELD_ID,)`, because you cannot look up availability without
knowing which vault. Its *source* is external; its *dependency* is still a field. Of
the eight conditional fields, five are value-dependent and three use this node, so
value-dependence is the shape and this is the exception. A mechanism generalised from
this lookup alone would have served three cases and missed five.

A THIRD SHAPE — a tenant setting, a role, a time of day, another object's state —
costs one new node type plus one field on `ConditionContext`. Two edits, bounded. If a
proposed shape cannot be expressed that way, that is a finding about this design.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol, runtime_checkable


class Verdict(Enum):
    """⚠️ INDETERMINATE IS NOT A THIRD KIND OF FALSE. It means the condition's own
    inputs are not yet available, so no claim is being made in either direction."""

    TRUE = "true"
    FALSE = "false"
    INDETERMINATE = "indeterminate"


class Applicability(Enum):
    """The outcome of a field's `applies_when`, as the walk decides it."""

    APPLIES = "applies"
    #: Either the condition said no, or the tenant switched the field off. ⚠️ The two
    #: are merged DELIBERATELY: both mean "never asked, never missing", which is what
    #: `CaptureState.not_applicable` already reports, and a surface renders neither.
    DOES_NOT_APPLY = "does_not_apply"
    #: Cannot be decided yet — a field it depends on is applicable and unanswered.
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class ConditionContext:
    """Everything a node may read.

    ⚠️ `resolution` IS PASSED IN, NEVER RESOLVED HERE. Deriving the vault inside the
    engine would put a database-reading resolver inside what is otherwise a pure
    function over config and answers, and purity here is what lets the whole engine be
    tested without a database. `call_extraction_service.resolve_and_evaluate` is the
    one impure seam and stays that way.
    """

    answers: Mapping[str, object]
    #: field_id -> Applicability, for every field the walk has ALREADY decided.
    #: Topological order is what guarantees a node's dependencies are present here.
    decided: Mapping[str, Applicability]
    #: The product id availability is keyed on — `Resolution.variant_template_id`,
    #: which is None when the resolver found an ambiguous candidate set.
    vault_product_id: str | None
    personalization_config: dict | None


@runtime_checkable
class Condition(Protocol):
    @property
    def depends_on(self) -> tuple[str, ...]: ...
    def evaluate(self, ctx: ConditionContext) -> Verdict: ...


def _answered(ctx: ConditionContext, field_id: str) -> bool:
    """⚠️ DELEGATES TO THE ONE PLACE THAT DECIDES WHAT ANSWERED MEANS. Importing
    `is_answered` rather than re-deriving it is what stops conditions and the
    partition from disagreeing about whether `"none"` or `""` counts."""
    from app.services.capture.missing import is_answered

    return is_answered(ctx.answers.get(field_id))


def _unusable(ctx: ConditionContext, field_id: str) -> bool:
    """True when the dependency can never be answered, so the condition is settled
    rather than pending. A field the tenant switched off, or one whose own condition
    said no, is in this state."""
    return ctx.decided.get(field_id) is Applicability.DOES_NOT_APPLY


@dataclass(frozen=True)
class Always:
    """Unconditional. `required_when=Always()` replaces the old `required=True`."""

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ()

    def evaluate(self, ctx: ConditionContext) -> Verdict:
        return Verdict.TRUE


@dataclass(frozen=True)
class Never:
    """⚠️ PROMPTED, NEVER REQUIRED. `eta` is asked for and may go unanswered without
    blocking approval — it lands in `unanswered_optional`, which `is_complete`
    ignores."""

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ()

    def evaluate(self, ctx: ConditionContext) -> Verdict:
        return Verdict.FALSE


@dataclass(frozen=True)
class EqualsValue:
    """`service_location_other` applies when `service_location == "other"`."""

    field_id: str
    value: object

    @property
    def depends_on(self) -> tuple[str, ...]:
        return (self.field_id,)

    def evaluate(self, ctx: ConditionContext) -> Verdict:
        if _unusable(ctx, self.field_id):
            return Verdict.FALSE
        if not _answered(ctx, self.field_id):
            return Verdict.INDETERMINATE
        return Verdict.TRUE if ctx.answers.get(self.field_id) == self.value else Verdict.FALSE


@dataclass(frozen=True)
class NotEqualsValue:
    """`eta` applies when `service_location != "graveside"`.

    ⚠️ AN UNUSABLE DEPENDENCY READS FALSE, NOT TRUE, and the asymmetry is deliberate.
    If a tenant switched `service_location` off, "not graveside" is unknowable — and
    prompting for a procession ETA on an order that may be graveside invents a
    question. Not applying is the choice that claims less.
    """

    field_id: str
    value: object

    @property
    def depends_on(self) -> tuple[str, ...]:
        return (self.field_id,)

    def evaluate(self, ctx: ConditionContext) -> Verdict:
        if _unusable(ctx, self.field_id):
            return Verdict.FALSE
        if not _answered(ctx, self.field_id):
            return Verdict.INDETERMINATE
        return Verdict.TRUE if ctx.answers.get(self.field_id) != self.value else Verdict.FALSE


@dataclass(frozen=True)
class AnswerIn:
    """`legacy_print_name` applies when `personalization` is one of the print answers.

    ⚠️ A SET, NOT A CHAIN OF `EqualsValue`. R1 (2026-10-07) collapsed three
    personalization questions into one with seven answers, and three of the new
    detail fields each hang off a SUBSET of those answers rather than off a single
    value: the print name applies to the one legacy answer, the vinyl symbol to the
    two answers that carry vinyl, the date format to the four that carry text. An
    `Or(EqualsValue(...), EqualsValue(...))` would express the same thing and would
    need an `Or` — which nothing else wants, and which would then be the one
    combinator anyone reaches for.

    ⚠️ SAME THREE-VALUED DISCIPLINE AS `EqualsValue`, and it is not inherited by
    writing `in`: an unusable dependency reads FALSE, an unanswered one reads
    INDETERMINATE. The second is the one that matters here — before the director has
    said what personalization they want, "does the print name apply" is not FALSE,
    it is not yet knowable, and FALSE would drop the field into `not_applicable`
    where a surface renders nothing and never revisits it.
    """

    field_id: str
    values: frozenset

    @property
    def depends_on(self) -> tuple[str, ...]:
        return (self.field_id,)

    def evaluate(self, ctx: ConditionContext) -> Verdict:
        if _unusable(ctx, self.field_id):
            return Verdict.FALSE
        if not _answered(ctx, self.field_id):
            return Verdict.INDETERMINATE
        return (
            Verdict.TRUE if ctx.answers.get(self.field_id) in self.values
            else Verdict.FALSE
        )


@dataclass(frozen=True)
class AnyAnswered:
    """"Any personalization is chosen" — the predicate five of the eight hang off.

    ⚠️ THREE CASES, AND GETTING ANY ONE WRONG BREAKS A REQUIREMENT:

    1. All applicable fields answered, every answer in `ignoring` (i.e. all `"none"`)
       -> FALSE. `"none"` IS an answer; the family declined. The dates are not
       required and `nameplate_date_format` does not apply.
    2. Some applicable field unanswered -> INDETERMINATE. Not FALSE: see the module
       docstring on requirements appearing mid-flow.
    3. NO field applies — the vault offers none of the three -> FALSE, settled.
       There is nothing to choose, so this is not pending.

    ⚠️ CASE 3 IS WHY THE QUANTIFIER IS OVER *APPLICABLE* FIELDS AND WHY TOPOLOGICAL
    ORDER IS LOAD-BEARING: the three questions' applicability must be decided before
    this runs. A flat two-pass design cannot guarantee that and gets case 3 wrong.
    """

    field_ids: tuple[str, ...]
    ignoring: frozenset[str] = frozenset()

    @property
    def depends_on(self) -> tuple[str, ...]:
        return self.field_ids

    def evaluate(self, ctx: ConditionContext) -> Verdict:
        live = [f for f in self.field_ids if not _unusable(ctx, f)]
        if not live:
            return Verdict.FALSE                      # case 3
        pending = False
        for f in live:
            # ⚠️ ANSWERED IS CHECKED FIRST, AND THE ORDER IS A BUG FIX. This read
            # `if decided[f] is INDETERMINATE: pending = True; continue` BEFORE looking
            # at the answer, so a field that had been ANSWERED was skipped whenever its
            # own applicability was still unknown.
            #
            # The case that found it: a director answers `legacy_print` before the
            # vault resolves. Applicability of that question is INDETERMINATE (no
            # product to read availability against) — but the answer exists, and an
            # ANSWER IS POSITIVE EVIDENCE REGARDLESS of whether we can yet confirm the
            # question applied. Under the old order "any personalization chosen" stayed
            # INDETERMINATE, so `nameplate_date_format` never appeared and the dates
            # never became required, for an order that plainly had personalization.
            #
            # Found by `test_nameplate_date_format_is_the_mirror_image`, not by review.
            if _answered(ctx, f):
                if ctx.answers.get(f) not in self.ignoring:
                    return Verdict.TRUE
                continue          # answered "none" — settled, contributes nothing
            pending = True
        return Verdict.INDETERMINATE if pending else Verdict.FALSE


@dataclass(frozen=True)
class AvailabilityOffered:
    """The three personalization questions apply when the resolved vault offers them.

    ⚠️ AMBIGUITY READS INDETERMINATE, NOT NOT_OFFERED, and that is a correctness gain
    over what shipped. The resolver returns *a candidate set plus a discriminator,
    never a best match*, so `variant_template_id` is None when two vaults match. Today
    ambiguity and "no vault named yet" and "this vault does not offer it" all produce
    the same silence; here only the last one is FALSE.
    """

    question_id: str

    @property
    def depends_on(self) -> tuple[str, ...]:
        from app.services.capture.schema import VAULT_FIELD_ID

        return (VAULT_FIELD_ID,)

    def evaluate(self, ctx: ConditionContext) -> Verdict:
        from app.services.personalization.availability import (
            AvailabilityState,
            read_availability,
        )

        if ctx.vault_product_id is None:
            return Verdict.INDETERMINATE
        availability = read_availability(
            ctx.personalization_config, ctx.vault_product_id, self.question_id
        )
        if availability.state is AvailabilityState.NOT_OFFERED:
            return Verdict.FALSE
        # ⚠️ OFFERED and NOT_CONFIGURED both apply. NOT_CONFIGURED means nobody has
        # said, and the answer to "nobody has said" is to ask.
        return Verdict.TRUE


class CyclicConditions(Exception):
    """⚠️ RAISED, NEVER TIE-BROKEN. A cycle is a template defect. Picking an order
    silently would make it unobservable, and the field that lost the tie would read
    as INDETERMINATE forever with nothing pointing at the cause."""


def topological_order(
    field_ids: tuple[str, ...], edges: Mapping[str, tuple[str, ...]]
) -> tuple[str, ...]:
    """Fields ordered so every dependency precedes its dependents.

    `edges[f]` are the fields `f` READS, so they must come first. Dependencies on
    fields outside `field_ids` — a tenant switched one off entirely — are ignored
    rather than raising: the node handles the absence through `decided`.

    ⚠️ Kahn's algorithm with the ORIGINAL ORDER preserved among ready nodes, so the
    platform field order survives wherever conditions do not force a change. An
    arbitrary order here would make the capture list's sequence depend on dict
    iteration.
    """
    present = set(field_ids)
    remaining = {f: [d for d in edges.get(f, ()) if d in present] for f in field_ids}
    out: list[str] = []
    while remaining:
        ready = [f for f in field_ids if f in remaining and not remaining[f]]
        if not ready:
            raise CyclicConditions(
                "conditions form a cycle among: " + ", ".join(sorted(remaining))
            )
        for f in ready:
            out.append(f)
            del remaining[f]
        for deps in remaining.values():
            deps[:] = [d for d in deps if d not in out]
    return tuple(out)
