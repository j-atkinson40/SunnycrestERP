"""What is answered and what is still missing — deterministically, server-side.

⚠️ THE MODEL DOES NOT DECIDE WHAT AN ORDER REQUIRES. It pulls values out of the
transcript; this compares those values against the schema. The seeded prompt
used to ask the model for "field names that were NOT mentioned and are needed
for a complete order", which put the one judgment that must be reliable in the
least reliable component — a flag that cannot be trusted to fire, cannot be
trusted not to fire spuriously, and cannot be tested. Ruled 2026-09-22, `The
model extracts; the server decides what is missing`.

⚠️ FOUR OUTCOMES, AND THE FOURTH WAS ADDED 2026-10-05 BECAUSE IT WAS FALLING OUT.
A field is answered, or missing, or UNANSWERED-BUT-OPTIONAL, or IT DOES NOT APPLY.
The last two are absent from `missing` rather than reported there: a Monticello
order at a licensee offering no personalization on the Monticello must not report
personalization as missing, and an optional field nobody mentioned is not a gap.

⚠️ THE SETS EXHAUST THE RESOLVED SCHEMA, AND THAT IS NOW AN INVARIANT RATHER THAN
AN ACCIDENT. Until 2026-10-05 three sets appeared to partition the fields — but
only because EVERY template field was required. `evaluate` adds an unanswered
field to `missing` only when it is required, so the moment optional fields existed
(`date_of_birth`, `date_of_death`, `cemetery_equipment`) they landed in NO SET:
not answered, not missing, not inapplicable. A consumer reading `CaptureState`
could not see them at all.

⚠️ AND THAT WAS THE THIRD TIME THIS TYPE DESCRIBED LESS THAN `evaluate` KNEW.
`answered` was computed and discarded until r197; NOT_CONFIGURED is computed by
`resolve_schema` and still discarded here; optional-unanswered fell out entirely.
Each time a consumer re-derived from the resolved schema instead — which is two
sources of truth about field state at the server, immediately after the same
duplication was removed at the client. The row layer's workaround (reading
`ResolvedField` directly) stays correct and is no longer the only way to see this
one.

⚠️ `none` IS AN ANSWER. It clears the requirement. Absence of the key, or a
`None` value, is unanswered. Those two are different and the difference is the
whole ruling: `{"nameplate_cover_emblem": "none"}` is answered, `{}` is not.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.capture.conditions import Applicability, Verdict
from app.services.capture.schema import (
    PLATFORM_DEFAULT_FIELDS,
    FieldDefinition,
    ResolvedField,
    TenantCaptureConfig,
    resolve_schema,
    applicability_map,
)
from app.services.personalization.questions import ANSWER_NONE


class UnpermittedAnswer(ValueError):
    """An answer the vault does not permit was supplied for a question.

    ⚠️ Raised rather than silently treated as unanswered. A vault that permits
    only `cover_emblem_only` and receives `nameplate_and_cover_emblem` has been
    given a contradiction, and folding that into "missing" would report it as a
    gap in the conversation rather than as a conflict with the catalog.
    """


@dataclass(frozen=True)
class CaptureState:
    """The answer to "where is this order up to?".

    ⚠️ FIVE SETS AS OF 2026-10-06 — THIS SAID FOUR, AND THE CLAIM WAS PART OF THE
    CHANGE. The original read: *"THE FOUR SETS EXHAUST THE RESOLVED SCHEMA AND ARE
    DISJOINT. Every field the schema resolved appears in exactly one, and
    `not_applicable` covers the platform fields the schema dropped."* That was true
    until conditions could be INDETERMINATE.

    The five still EXHAUST and are still DISJOINT. Every field in the template appears
    in exactly one. A field in none of them is a defect in `evaluate`, not a state.
    """

    answered: tuple[str, ...]
    #: Required, applicable, unanswered. The reported gap.
    missing: tuple[str, ...]
    #: ⚠️ OPTIONAL, APPLICABLE, UNANSWERED — added 2026-10-05, when it stopped
    #: being empty. Not a gap, so never in `missing`; not an answer, so never in
    #: `answered`. It needs its own name because "absent from all three sets" is
    #: indistinguishable from "the engine forgot about it", and a surface that
    #: renders a row per field has to know the difference.
    unanswered_optional: tuple[str, ...]
    #: Fields that do not apply to this vault at this tenant. Reported
    #: separately so a caller can tell "nothing to ask" from "not asked yet";
    #: the capture list renders neither.
    not_applicable: tuple[str, ...]
    #: ⚠️ APPLICABILITY NOT YET DECIDABLE — added 2026-10-06 with Piece 4. Canon's
    #: name for it: *depends on an answer not yet given.*
    #:
    #: A field lands here when its `applies_when` reads INDETERMINATE: something it
    #: depends on is applicable and unanswered. It is NOT `not_applicable` — we have
    #: not established that it does not apply — and it cannot be `answered` or
    #: `missing`, because we do not yet know whether it is even asked.
    #:
    #: ⚠️ BY RULING, these are NOT RENDERED AND NOT COUNTED on the capture surface
    #: until the condition resolves. No design shows the state, and a row that
    #: appears once its question becomes real invents nothing. The set exists so the
    #: engine can tell "this vault does not offer it" from "we cannot know yet",
    #: which before today were the same silence.
    #:
    #: ⚠️ A field whose REQUIRED_WHEN is indeterminate does NOT land here — it is
    #: applicable and unanswered, so it goes to `unanswered_optional`. Only
    #: applicability lands here. See `evaluate`.
    indeterminate: tuple[str, ...] = ()

    @property
    def is_complete(self) -> bool:
        """⚠️ UNCHANGED, DELIBERATELY. Completeness is about gaps, and an
        unanswered OPTIONAL field is not one. Folding `unanswered_optional` in
        here would make every order incomplete until someone answered three
        fields the design does not require."""
        return not self.missing

    @property
    def all_field_ids(self) -> tuple[str, ...]:
        """⚠️ EXISTS SO THE EXHAUSTIVENESS CLAIM IS TESTABLE RATHER THAN ASSERTED IN
        PROSE. The docstring above says the five sets exhaust and are disjoint; a test
        compares this against the template and against the sum of the five lengths."""
        return (
            self.answered
            + self.missing
            + self.unanswered_optional
            + self.not_applicable
            + self.indeterminate
        )


def is_answered(value: object) -> bool:
    """⚠️ THE ONE PLACE THAT DECIDES WHAT ANSWERED MEANS.

    - absent key or `None`  -> unanswered
    - `"none"`              -> ANSWERED (the family declined; that is an answer)
    - empty string / blank  -> unanswered (whitespace is not a decision)
    - anything else         -> answered
    """
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def evaluate(
    extracted: dict[str, object],
    *,
    vault_product_id: str | None,
    personalization_config: dict | None = None,
    tenant_config: TenantCaptureConfig | None = None,
    platform_fields: tuple[FieldDefinition, ...] = PLATFORM_DEFAULT_FIELDS,
) -> CaptureState:
    """Compare extracted values against the resolved schema.

    `extracted` is whatever the model produced, keyed by field id. Keys it does
    not know about are ignored rather than rejected: the schema decides what an
    order requires, so an extra key is noise, not an error.
    """
    applicable = resolve_schema(
        vault_product_id=vault_product_id,
        personalization_config=personalization_config,
        tenant_config=tenant_config,
        platform_fields=platform_fields,
        answers=extracted,
    )
    applicable_ids = {f.field_id for f in applicable}

    answered: list[str] = []
    missing: list[str] = []
    unanswered_optional: list[str] = []

    for resolved in applicable:
        value = extracted.get(resolved.field_id)
        if not is_answered(value):
            # ⚠️ BOTH BRANCHES APPEND. The optional arm used to `continue`
            # silently, which is how optional fields came to belong to no set.
            #
            # ⚠️ `resolved.required` IS NOW THE LIVE VERDICT, and INDETERMINATE reads
            # False — so a field whose requirement is not yet decidable goes to
            # `unanswered_optional` and CANNOT BLOCK APPROVAL. That is deliberate: the
            # dependency it is waiting on is itself unanswered and therefore already
            # in `missing`, so reporting this one too would report one gap twice.
            if resolved.required:
                missing.append(resolved.field_id)
            else:
                unanswered_optional.append(resolved.field_id)
            continue
        _reject_unpermitted(resolved, value)
        answered.append(resolved.field_id)

    # ⚠️ THE ABSENT FIELDS ARE SPLIT, NOT LUMPED. This used to be "everything the
    # schema did not return is not_applicable", which was right while applicability
    # was two-valued. A field whose condition cannot be evaluated yet is also absent
    # from `applicable`, and calling it not_applicable would assert we had established
    # it does not apply.
    applicability = applicability_map(
        vault_product_id=vault_product_id,
        personalization_config=personalization_config,
        tenant_config=tenant_config,
        platform_fields=platform_fields,
        answers=extracted,
    )
    not_applicable = tuple(
        f.field_id for f in platform_fields
        if f.field_id not in applicable_ids
        and applicability.get(f.field_id) is not Applicability.INDETERMINATE
    )
    indeterminate = tuple(
        f.field_id for f in platform_fields
        if f.field_id not in applicable_ids
        and applicability.get(f.field_id) is Applicability.INDETERMINATE
    )
    return CaptureState(
        answered=tuple(answered),
        missing=tuple(missing),
        unanswered_optional=tuple(unanswered_optional),
        not_applicable=not_applicable,
        indeterminate=indeterminate,
    )


def _reject_unpermitted(resolved: ResolvedField, value: object) -> None:
    """Guard a conditional answer against the vault's permitted set.

    ⚠️ ONLY WHEN THE VAULT CONFIGURED THE QUESTION. An empty `permitted_answers`
    means NOT_CONFIGURED — the licensee has said nothing, so nothing is
    contradicted and any answer stands. Guarding there would turn "we have not
    set this up yet" into "that answer is wrong", which is the exact confusion
    the three-state reader exists to prevent.
    """
    if not resolved.definition.is_conditional:
        return
    if not resolved.permitted_answers:
        return
    if value == ANSWER_NONE:
        # Declining is permitted wherever the question is asked at all.
        return
    if value not in resolved.permitted_answers:
        raise UnpermittedAnswer(
            f"{resolved.field_id}={value!r} is not permitted on this vault; "
            f"permitted: {sorted(resolved.permitted_answers)} (plus "
            f"{ANSWER_NONE!r})"
        )
