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

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.services.capture.pills import BURIAL_ONLY_EQUIPMENT
from app.services.capture.schema import VAULT_FIELD_ID, resolve_schema
from app.services.capture.vault_form import form_of

# ⚠️ IMPORTED AT MODULE LEVEL ON PURPOSE, AND THIS LINE IS THE FIX FOR A SHIPPED
# DEFECT. These two were function-local inside a `try: ... except Exception:` that
# fails open, and `resolve_availability_config` was imported from
# `personalization.availability` — where it does not live. It lives in
# `personalization.enrollment`. So every call raised ImportError, the except swallowed
# it, and the personalization half of James's clause 4 cleared NOTHING, silently, from
# the day it shipped. At module level a wrong name is an ImportError at import time,
# which every test in this package trips immediately. The failure is now unexpressible
# rather than merely discouraged.
from app.services.capture import SALES_ORDER, template_for
from app.services.personalization.enrollment import resolve_availability_config
from app.services.personalization.questions import ANSWER_NONE
from app.services.product_name_resolver import build_index
from app.services.product_name_resolver import resolve as resolve_vault

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
        # ⚠️ ONLY THE DATABASE READ IS GUARDED, AND ONLY AGAINST DATABASE ERRORS. The
        # except below used to be a bare `except Exception` wrapping the imports too,
        # which is how a wrong module name became a permanently silent no-op. A bare
        # Exception here conflates two unlike things: "this tenant's availability could
        # not be read", which is a real runtime condition that must fail open, and "this
        # code is wrong", which must fail loudly. `SQLAlchemyError` covers the first and
        # lets the second through.
        # ⚠️ THE CALL SHAPE IS `typed_extraction`'s, AND THE ONE IT REPLACES COULD NOT
        # HAVE RUN. `resolve_schema` is keyword-only over
        # (vault_product_id, personalization_config, vault_form, platform_fields,
        # answers) — it takes no session, no `company_id` and no `values`. The previous
        # call passed `db` positionally plus both of those names, so it raised TypeError
        # on every invocation, which the bare `except Exception` then swallowed
        # alongside the ImportError. Two independent defects, one silence.
        #
        # ⚠️ AND THE VAULT IS A NAME HERE, NOT AN ID. Availability is keyed by
        # variant_template_id, so the name has to go through the catalogue's own
        # resolver — the same two lines `typed_extraction` uses — rather than being
        # handed to a resolver that expects an id.
        resolution = resolve_vault(build_index(db), str(vault) or None)
        resolved = resolve_schema(
            vault_product_id=resolution.variant_template_id,
            personalization_config=resolve_availability_config(db, company_id),
            vault_form=form.form,
            platform_fields=template_for(SALES_ORDER),
            answers={**after, VAULT_FIELD_ID: vault},
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
    except SQLAlchemyError:
        # ⚠️ FAILS OPEN AND CLEARS NOTHING. An availability read that cannot run is not
        # evidence that an answer no longer fits; clearing on an exception would delete
        # the director's answers because a config table was unreachable.
        #
        # ⚠️ AND THE `pragma: no cover` THAT USED TO SIT ON THIS LINE WAS LOAD-BEARING
        # IN THE WRONG DIRECTION. It told the coverage tool not to care that this branch
        # never ran under test — while in production it was the ONLY branch that ever
        # ran. An exemption from coverage on the path that fails open is an exemption
        # from noticing that the path is the whole behaviour.
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
