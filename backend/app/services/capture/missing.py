"""What is answered and what is still missing — deterministically, server-side.

⚠️ THE MODEL DOES NOT DECIDE WHAT AN ORDER REQUIRES. It pulls values out of the
transcript; this compares those values against the schema. The seeded prompt
used to ask the model for "field names that were NOT mentioned and are needed
for a complete order", which put the one judgment that must be reliable in the
least reliable component — a flag that cannot be trusted to fire, cannot be
trusted not to fire spuriously, and cannot be tested. Ruled 2026-09-22, `The
model extracts; the server decides what is missing`.

⚠️ THREE OUTCOMES, NOT TWO. A field is answered, or missing, or IT DOES NOT
APPLY — and the third is absent from both sets rather than reported as missing.
A Monticello order at a licensee that offers no personalization on the Monticello
must not report personalization as missing; there is nothing to ask.

⚠️ `none` IS AN ANSWER. It clears the requirement. Absence of the key, or a
`None` value, is unanswered. Those two are different and the difference is the
whole ruling: `{"nameplate_cover_emblem": "none"}` is answered, `{}` is not.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.capture.schema import (
    PLATFORM_DEFAULT_FIELDS,
    FieldDefinition,
    ResolvedField,
    TenantCaptureConfig,
    resolve_schema,
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
    """The answer to "where is this order up to?"."""

    answered: tuple[str, ...]
    missing: tuple[str, ...]
    #: Fields that do not apply to this vault at this tenant. Reported
    #: separately so a caller can tell "nothing to ask" from "not asked yet";
    #: the capture list renders neither.
    not_applicable: tuple[str, ...]

    @property
    def is_complete(self) -> bool:
        return not self.missing


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
    )
    applicable_ids = {f.field_id for f in applicable}

    answered: list[str] = []
    missing: list[str] = []

    for resolved in applicable:
        value = extracted.get(resolved.field_id)
        if not is_answered(value):
            if resolved.required:
                missing.append(resolved.field_id)
            continue
        _reject_unpermitted(resolved, value)
        answered.append(resolved.field_id)

    not_applicable = tuple(
        f.field_id for f in platform_fields if f.field_id not in applicable_ids
    )
    return CaptureState(
        answered=tuple(answered),
        missing=tuple(missing),
        not_applicable=not_applicable,
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
