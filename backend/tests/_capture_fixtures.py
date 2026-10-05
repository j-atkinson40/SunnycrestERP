"""A fake licensee whose vaults cover every availability case.

⚠️ FIXTURES, NOT SUNNYCREST. Sunnycrest's real catalog is an onboarding task and
is not a dependency of the capture schema. Building against it would couple this
work to a spreadsheet that is still being settled, and would test one licensee's
configuration rather than the shape of the problem.

⚠️ DERIVED FROM THE QUESTION LAYER, NOT TYPED OUT. Answer ids come from
`questions.py` so a fixture cannot name an answer that does not exist — the
failure this closes is a test that passes against a value the system could never
produce (CLAUDE.md §11, *fixtures modelled on the implementation*).

The five vaults, and what each one is for:

    VAULT_ALL_THREE     every question offered, every answer permitted
    VAULT_ONE_ANSWER    one question, one permitted answer — the narrow case
    VAULT_SALUTE_SHAPED cover_emblem_only, which is the answer the re-key nearly
                        modelled away; the premium vaults cannot express it
    VAULT_OFFERS_NONE   every question present and empty — NOT_OFFERED
    VAULT_UNCONFIGURED  absent from `availability` entirely — NOT_CONFIGURED
"""
from __future__ import annotations

from app.services.personalization.questions import (
    ANSWER_COVER_EMBLEM_ONLY,
    ANSWER_LEGACY_CUSTOM_SERIES,
    ANSWER_LEGACY_SERIES,
    ANSWER_NAMEPLATE_AND_COVER_EMBLEM,
    ANSWER_NAMEPLATE_ONLY,
    QUESTION_LEGACY_PRINT,
    QUESTION_LIFES_REFLECTIONS,
    QUESTION_NAMEPLATE_COVER_EMBLEM,
    VINYL_ANSWERS,
)

VAULT_ALL_THREE = "vault-all-three"
VAULT_ONE_ANSWER = "vault-one-answer"
VAULT_SALUTE_SHAPED = "vault-salute-shaped"
VAULT_OFFERS_NONE = "vault-offers-none"
VAULT_UNCONFIGURED = "vault-unconfigured"

#: Every vault the fixture licensee has an opinion about. `VAULT_UNCONFIGURED`
#: is deliberately NOT here — its absence is the case it tests.
FIXTURE_PERSONALIZATION_CONFIG: dict = {
    "options": {},  # the pre-r185 key, untouched — present to prove it is ignored
    "availability": {
        VAULT_ALL_THREE: {
            QUESTION_LEGACY_PRINT: [
                ANSWER_LEGACY_SERIES,
                ANSWER_LEGACY_CUSTOM_SERIES,
            ],
            QUESTION_NAMEPLATE_COVER_EMBLEM: [
                ANSWER_NAMEPLATE_ONLY,
                ANSWER_COVER_EMBLEM_ONLY,
                ANSWER_NAMEPLATE_AND_COVER_EMBLEM,
            ],
            QUESTION_LIFES_REFLECTIONS: list(VINYL_ANSWERS),
        },
        VAULT_ONE_ANSWER: {
            QUESTION_LEGACY_PRINT: [ANSWER_LEGACY_SERIES],
            QUESTION_NAMEPLATE_COVER_EMBLEM: [],
            QUESTION_LIFES_REFLECTIONS: [],
        },
        # Salute permits an emblem WITHOUT a nameplate; the premium vaults do
        # not. This is the combination the single-question re-key exists to
        # keep expressible.
        VAULT_SALUTE_SHAPED: {
            QUESTION_NAMEPLATE_COVER_EMBLEM: [ANSWER_COVER_EMBLEM_ONLY],
            # The other two questions are absent -> NOT_CONFIGURED, which is a
            # partial configuration and is a real state, not an oversight.
        },
        VAULT_OFFERS_NONE: {
            QUESTION_LEGACY_PRINT: [],
            QUESTION_NAMEPLATE_COVER_EMBLEM: [],
            QUESTION_LIFES_REFLECTIONS: [],
        },
    },
}


#: A realistic answer per unconditional template field.
#:
#: ⚠️ A LOOKUP, NOT THE RETURN VALUE. `complete_non_personalization_answers`
#: below derives its KEYS from the template and reads values from here, so the
#: fixture cannot claim completeness it does not have.
_ANSWER_BY_FIELD: dict[str, object] = {
    "vault": "Monticello",
    "funeral_home": "Hopkins Funeral Home",
    "deceased_name": "John Michael Smith",
    "vault_size": "standard adult",
    "cemetery": "St. Mary's",
    "burial_date": "2026-10-01",
    "burial_time": "10:00",
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
