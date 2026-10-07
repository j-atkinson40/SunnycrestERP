"""A fake licensee whose vaults cover every availability case.

⚠️ FIXTURES, NOT SUNNYCREST. Sunnycrest's real catalog is an onboarding task and
is not a dependency of the capture schema. Building against it would couple this
work to a spreadsheet that is still being settled, and would test one licensee's
configuration rather than the shape of the problem.

⚠️ DERIVED FROM THE QUESTION LAYER, NOT TYPED OUT. Answer ids come from
`questions.py` so a fixture cannot name an answer that does not exist — the
failure this closes is a test that passes against a value the system could never
produce (CLAUDE.md §11, *fixtures modelled on the implementation*).

⚠️ RESHAPED 2026-10-07 FOR R1 — ONE QUESTION, NOT THREE. Availability is now keyed
`{product_id: {"personalization": [answers]}}`. `VAULT_ALL_THREE` was renamed to
`VAULT_EVERY_ANSWER`: "all three" counted questions that no longer exist, and a
fixture whose name describes the superseded model is the stale-count defect wearing
a test's clothes.

The six vaults, and what each one is for. ⚠️ THE MIDDLE TWO ARE MODELLED ON REAL
VAULTS FROM THE ORDERING PORTAL (R7), so the fixture exercises shapes a licensee
actually has rather than shapes only a test has:

    VAULT_EVERY_ANSWER       every answer permitted — the 17 portal vaults that
                             carry `wilbertPersonalizationFields`
    VAULT_SALUTE_SHAPED      nameplate and/or emblem, no print, no vinyl — Salute®
                             and the Salute® urn vault
    VAULT_CONTINENTAL_SHAPED nameplate only, NO emblem — Continental®, and the one
                             vault R2 deliberately excludes from `cover_emblem_only`
    VAULT_ONE_ANSWER         one permitted answer — the narrow case
    VAULT_OFFERS_NONE        the question present and empty — NOT_OFFERED, which is
                             the 7 portal vaults with `hasPersonalization: false`
    VAULT_UNCONFIGURED       absent from `availability` entirely — NOT_CONFIGURED
"""
from __future__ import annotations

from app.services.personalization.questions import (
    ANSWER_COVER_EMBLEM_ONLY,
    ANSWER_LEGACY_PRINT,
    ANSWER_LIFES_REFLECTIONS,
    ANSWER_NAMEPLATE_AND_COVER_EMBLEM,
    ANSWER_NAMEPLATE_AND_LIFES_REFLECTIONS,
    ANSWER_NAMEPLATE_ONLY,
    PERSONALIZATION_QUESTION,
    QUESTION_PERSONALIZATION,
)

VAULT_EVERY_ANSWER = "vault-every-answer"
VAULT_SALUTE_SHAPED = "vault-salute-shaped"
VAULT_CONTINENTAL_SHAPED = "vault-continental-shaped"
VAULT_ONE_ANSWER = "vault-one-answer"
VAULT_OFFERS_NONE = "vault-offers-none"
VAULT_UNCONFIGURED = "vault-unconfigured"
VAULT_PARTIAL_CONFIG = "vault-partial-config"

#: ⚠️ DERIVED FROM THE QUESTION, NOT LISTED. `PERSONALIZATION_QUESTION.answers`
#: excludes `none` by construction, and `none` must never appear in a stored
#: permitted set — `Availability.permits` grants it wherever the question is asked.
#: Listing the six by hand here would be a copy able to drift from the answer set,
#: and would also be the place someone eventually adds `none` by mistake.
_EVERY_ANSWER: list[str] = list(PERSONALIZATION_QUESTION.answers)

#: Every vault the fixture licensee has an opinion about. `VAULT_UNCONFIGURED`
#: is deliberately NOT here — its absence is the case it tests.
FIXTURE_PERSONALIZATION_CONFIG: dict = {
    "options": {},  # the pre-r185 key, untouched — present to prove it is ignored
    "availability": {
        VAULT_EVERY_ANSWER: {QUESTION_PERSONALIZATION: _EVERY_ANSWER},
        # Salute permits an emblem WITHOUT a nameplate. Under three questions this
        # was the combination the re-key existed to keep expressible; under one it
        # is simply one of three permitted answers, and no exclusion rule is
        # written anywhere — the print and vinyl answers are ABSENT rather than
        # forbidden, which is R1's whole argument.
        VAULT_SALUTE_SHAPED: {
            QUESTION_PERSONALIZATION: [
                ANSWER_NAMEPLATE_ONLY,
                ANSWER_COVER_EMBLEM_ONLY,
                ANSWER_NAMEPLATE_AND_COVER_EMBLEM,
            ]
        },
        # ⚠️ THE R2 EXCLUSION, AS A FIXTURE. R2 permits `cover_emblem_only` on every
        # vault that offers cover emblems — Continental does not offer one, so it
        # gets `nameplate_only` and nothing else. This vault is the positive control
        # on the exclusion: if availability were built as "emblem-only everywhere",
        # this fixture is what goes red.
        VAULT_CONTINENTAL_SHAPED: {
            QUESTION_PERSONALIZATION: [ANSWER_NAMEPLATE_ONLY]
        },
        VAULT_ONE_ANSWER: {QUESTION_PERSONALIZATION: [ANSWER_LEGACY_PRINT]},
        VAULT_OFFERS_NONE: {QUESTION_PERSONALIZATION: []},
        # ⚠️ PRESENT IN `availability`, BUT THE QUESTION KEY IS ABSENT. Under three
        # questions this state arose by itself — a licensee who configured one
        # question and not the others. With one question it has to be constructed,
        # and it still needs testing, because `read_availability` distinguishes
        # "product absent" from "question absent for a present product" and both
        # read NOT_CONFIGURED for different reasons. Without this fixture the
        # second branch (`availability.py:91-92`) would have no test at all.
        VAULT_PARTIAL_CONFIG: {},
    },
}

#: The one permitted mix, named here because more than one test wants it and it is
#: the answer most likely to be dropped by a future edit to the answer set.
FIXTURE_MIXED_ANSWER = ANSWER_NAMEPLATE_AND_LIFES_REFLECTIONS

#: An answer that carries a vinyl symbol, for the detail-field conditions.
FIXTURE_VINYL_ANSWER = ANSWER_LIFES_REFLECTIONS


#: A realistic answer per unconditional template field.
#:
#: ⚠️ A LOOKUP, NOT THE RETURN VALUE. `complete_non_personalization_answers`
#: below derives its KEYS from the template and reads values from here, so the
#: fixture cannot claim completeness it does not have.
_ANSWER_BY_FIELD: dict[str, object] = {
    "vault": "Monticello",
    "funeral_home": "Hopkins Funeral Home",
    "deceased_name": "John Michael Smith",
    "cemetery": "St. Mary's",
    # Added with the field, 2026-10-07 (R4). The town is what makes a shared
    # cemetery name an answer — "St. Mary's" exists in several of these towns.
    "cemetery_city": "Auburn",
    "burial_date": "2026-10-01",
    # Added with the field, 2026-10-07 (R4). ⚠️ DELIBERATELY NOT `burial_date`'s
    # value: the service is at a church in the morning and the burial is at the
    # cemetery afterwards, so a fixture that gave both the same date would pass
    # whether or not the engine kept them as two facts.
    "service_date": "2026-09-30",
    "service_time": "10:00",
    "grave_location": "Section 4, Lot 12",
    # One of the column's four enum values ('church', 'funeral_home',
    # 'graveside', 'other'). Added with the field, 2026-10-05.
    "service_location": "church",
    # Added with the Dates row, 2026-10-05. Strings because the capture layer
    # takes whatever the extractor produced; parsing is the adapter's job.
    "date_of_birth": "1948-03-14",
    "date_of_death": "2026-09-14",
    # A product reference. "Full setup" is the prototype's own value.
    "cemetery_equipment": "Full setup",
}


def complete_non_personalization_answers() -> dict[str, object]:
    """Every platform field that is not a personalization question, answered.

    Lets a test isolate the conditional behaviour: whatever comes back missing
    is a personalization question, because nothing else is left unanswered.

    ⚠️ DERIVED FROM THE TEMPLATE, AND IT RAISES ON AN UNKNOWN FIELD. This used
    to be a hardcoded dict of eight entries under exactly the docstring above —
    a universal claim that silently became false the moment the template grew.
    Adding `service_location` on 2026-10-05 turned seven tests red, all of them
    testing personalization rather than this fixture, because "complete" had
    quietly changed meaning underneath them.

    Deriving the keys makes the claim true by construction. Raising on a field
    with no entry in `_ANSWER_BY_FIELD` is the part that matters: the next field
    added to the template gets a loud, specific failure naming what to supply,
    instead of seven confusing ones somewhere else. A fixture that defaulted
    would have been worse than the hardcoded version — it would answer new
    fields with something nobody chose.

    ⚠️ IT FIRED AGAIN ON 2026-10-07 AND THAT IS THE SECOND TIME IT HAS PAID FOR
    ITSELF. R4 added `cemetery_city` and `service_date`; the raise named both,
    specifically, before any personalization test had a chance to fail confusingly.
    `nameplate_date_format` LEFT this dict in the same change — it is conditional
    now (it hangs off the personalization answer), so the loop skips it and an entry
    here would have been dead weight nobody would have noticed.
    """
    from app.services.capture import SALES_ORDER, template_for

    out: dict[str, object] = {}
    for f in template_for(SALES_ORDER):
        if f.is_conditional:
            continue
        if f.field_id not in _ANSWER_BY_FIELD:
            raise AssertionError(
                f"the capture template gained unconditional field "
                f"{f.field_id!r} ({f.label!r}) and this fixture has no answer "
                f"for it. Add one to _ANSWER_BY_FIELD in tests/_capture_fixtures.py "
                f"— do not let it default, or every 'nothing is missing' test "
                f"starts asserting something nobody chose."
            )
        out[f.field_id] = _ANSWER_BY_FIELD[f.field_id]
    return out
