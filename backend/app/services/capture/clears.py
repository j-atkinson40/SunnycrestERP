"""When an answer changes, what no longer fits — and the one line that says why.

James's dispatch of 2026-10-27, clause 4:

> Changing an answer clears what no longer fits (urn after burial clears equipment;
> a vault without that personalization clears it) and says why in one line in the
> pane footer.

⚠️ IT CLEARS `resolutions`, NOT `values`, AND THAT IS THE WHOLE MECHANISM. Under
whole-text capture `values` is rebuilt from the text on every read, so clearing a
value there is undone by the next keystroke. A picked answer is a RESOLUTION — the
director's decision about the text, which outlives every re-read of it — so an answer
that no longer fits has to be removed from there or it comes straight back.

⚠️ AND IT ONLY EVER CLEARS WHAT THE DIRECTOR PICKED. A value the extractor read out of
the text is not cleared: the words are still in the bar, the director can see them, and
deleting a reading of visible text would make the pane disagree with the sentence above
it. If the text says "full equipment" and the vault becomes an urn vault, that is a
CONFLICT to show, not an answer to silently drop.

⚠️ THE NOTE IS NOT STORED. It is returned by the answer that caused the clearing and
held by the pane until the next answer — the same arrangement as
`completion_attempt`, and for the same reason: it is the answer to "what just
happened", not a property of the order. A column for it would mean a stale sentence
surviving a reload and explaining a change the director made yesterday.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.capture.pills import BURIAL_ONLY_EQUIPMENT
from app.services.capture.schema import VAULT_FIELD_ID
from app.services.capture.vault_form import form_of
from app.services.personalization.questions import ANSWER_NONE

EQUIPMENT_FIELD_ID = "cemetery_equipment"


def _label_for(db: Session, company_id: str, field_id: str, value: str) -> str:
    """A cleared answer is named the way the office reads it, never by its id.

    ⚠️ THE SAME RULE AS ROWS AND PILLS. James ruled on 2026-10-12 that enum fields
    store ids and labels come from the schema — the Service row had shown
    `funeral_home` raw. A note saying "lowering_device_and_grass cleared" would be the
    same defect in a sentence.
    """
    from app.services.capture.schema import PLATFORM_DEFAULT_FIELDS

    for definition in PLATFORM_DEFAULT_FIELDS:
        if definition.field_id == field_id:
            return definition.label_for(value)
    return str(value)


def clear_what_no_longer_fits(
    db: Session,
    *,
    company_id: str,
    resolutions: dict,
    changed_field: str,
) -> tuple[dict, str | None]:
    """Resolutions after the change, and the one line explaining what went.

    Returns the dict unchanged and `None` when everything still fits, which is the
    ordinary case — so a caller can store the result either way.

    ⚠️ ONE LINE EVEN WHEN TWO THINGS GO, by ruling ("says why in one line"). Two
    sentences in a footer is a log; the office needs to know that something was
    cleared and why, and the pane already shows WHICH rows emptied.
    """
    after = dict(resolutions)
    gone: list[str] = []
    reason: str | None = None

    if changed_field != VAULT_FIELD_ID:
        return after, None

    vault = after.get(VAULT_FIELD_ID)
    if not vault:
        return after, None

    form = form_of(db, tenant_id=company_id, vault=vault)

    # ── the urn rule ────────────────────────────────────────────────────────────────
    # ⚠️ ONLY WHEN THE NEW VAULT IS A CREMATION, not whenever the vault changes.
    # Monticello -> Continental are both burial vaults and the equipment still fits;
    # clearing on every vault change would make the office re-answer a question whose
    # answer did not become wrong.
    equipment = after.get(EQUIPMENT_FIELD_ID)
    if form.is_cremation and equipment in BURIAL_ONLY_EQUIPMENT:
        label = _label_for(db, company_id, EQUIPMENT_FIELD_ID, str(equipment))
        del after[EQUIPMENT_FIELD_ID]
        gone.append(label)
        reason = f"{label} cleared: an urn vault means a cremation setup."

    # ── the personalization rule ────────────────────────────────────────────────────
    # ⚠️ READ OFF `permitted_answers`, WHICH IS THE CATALOGUE'S ANSWER. "A vault
    # without that personalization" is not a judgement this module makes — it is
    # `platform_personalization_availability`, resolved by `resolve_schema` against the
    # new vault. Hard-coding which vaults take a Legacy print would be a second
    # catalogue.
    #
    # ⚠️ AN EMPTY `permitted_answers` CLEARS NOTHING. Its own docstring says empty means
    # "any answer the question defines is acceptable" — most licensees are not
    # configured — so treating empty as "nothing permitted" would wipe every
    # personalization answer on every tenant that has not been set up.
    dropped_personalization: list[str] = []
    try:
        from app.services.capture.schema import resolve_schema
        from app.services.personalization.availability import (
            resolve_availability_config,
        )

        resolved = resolve_schema(
            db,
            company_id=company_id,
            values={**after, VAULT_FIELD_ID: vault},
            personalization_config=resolve_availability_config(db, company_id),
        )
        for field in resolved:
            field_id = field.definition.field_id
            answer = after.get(field_id)
            if answer is None or answer == ANSWER_NONE:
                continue
            if not field.permitted_answers:
                continue
            if answer in field.permitted_answers:
                continue
            label = _label_for(db, company_id, field_id, str(answer))
            del after[field_id]
            dropped_personalization.append(label)
    except Exception:  # pragma: no cover - availability is optional per tenant
        # ⚠️ FAILS OPEN AND CLEARS NOTHING. An availability read that cannot run is not
        # evidence that an answer no longer fits; clearing on an exception would delete
        # the director's answers because a config table was unreachable.
        dropped_personalization = []

    if dropped_personalization:
        gone.extend(dropped_personalization)
        named = ", ".join(dropped_personalization)
        short = str(vault)
        sentence = f"{named} cleared: the {short} doesn’t offer it."
        # ⚠️ THE EQUIPMENT REASON WINS WHEN BOTH FIRE, because the kind of service
        # changing is the larger fact and the one the director just caused. The pane
        # shows both rows emptied either way.
        reason = reason or sentence

    return after, (reason if gone else None)
