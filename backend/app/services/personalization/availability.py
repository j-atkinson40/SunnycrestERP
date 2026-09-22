"""What a licensee permits on a vault — per licensee, per vault, per question.

⚠️ THE DEFECT THIS CLOSES. `PersonalizationConfigService.get_config` returns
`{"error": "No active enrollment found", "options": []}` when a tenant has no
enrollment, and `get_applicable_options_for_product` turns that into `[]`. Every
caller reads `[]` as "nothing offered". Measured on production 2026-09-22:
`wilbert_program_enrollments` holds ZERO rows, so every product of every tenant
currently answers "no personalization offered" — indistinguishable from a true
negative, and wrong for every vault that does offer something.

NOT CONFIGURED IS NOT NOT OFFERED. A licensee who has said nothing has said
nothing. Only a licensee who has said "none" has said none.

⚠️ THIS READER ANSWERS AVAILABILITY. IT DOES NOT VALIDATE STORED ORDERS. The one
personalization record on production is an emblem on a vault the ordering portal
says takes no personalization; that contradiction is a data correction belonging
to the seeding work, and nothing here may fail because of it. There is
deliberately no `validate_record_against_availability` in this module.

THE STORED SHAPE — ADDITIVE, NO SCHEMA MIGRATION

A new key inside the existing `wilbert_program_enrollments.personalization_config`
JSONB. The existing `options` key is untouched, so nothing that reads it changes
and nothing needs a column:

    personalization_config = {
      "options": { ... unchanged ... },
      "availability": {
        "<product_id>": {
          "<question_id>": ["<permitted answer>", ...]
        }
      }
    }

Read as three states, which is the whole reason for the shape:

    product id absent from "availability"      -> NOT_CONFIGURED
    question absent for a present product      -> NOT_CONFIGURED (partial config)
    question present, empty list               -> NOT_OFFERED
    question present, non-empty list           -> OFFERED, with those answers

⚠️ An empty list is the ONLY way to say "not offered", and it has to be written
deliberately. That is what makes silence distinguishable from refusal.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .questions import ANSWER_NONE, question

AVAILABILITY_KEY = "availability"


class AvailabilityState(str, Enum):
    OFFERED = "offered"
    NOT_OFFERED = "not_offered"
    NOT_CONFIGURED = "not_configured"


@dataclass(frozen=True)
class Availability:
    state: AvailabilityState
    #: Permitted answers, excluding `none`, which is always permitted.
    permitted_answers: tuple[str, ...] = ()

    @property
    def is_offered(self) -> bool:
        return self.state is AvailabilityState.OFFERED

    def permits(self, answer: str) -> bool:
        """⚠️ `none` is permitted wherever the question is asked at all — a
        family may always decline. It is never listed in the stored set."""
        if answer == ANSWER_NONE:
            return self.state is AvailabilityState.OFFERED
        return answer in self.permitted_answers


def read_availability(
    personalization_config: dict | None, product_id: str, question_id: str
) -> Availability:
    """The three-state answer. Never raises on missing configuration."""
    question(question_id)              # unknown question is a programming error
    config = personalization_config or {}
    by_product = config.get(AVAILABILITY_KEY) or {}

    product = by_product.get(product_id)
    if product is None:
        return Availability(AvailabilityState.NOT_CONFIGURED)

    if question_id not in product:
        return Availability(AvailabilityState.NOT_CONFIGURED)

    permitted = tuple(product.get(question_id) or ())
    if not permitted:
        return Availability(AvailabilityState.NOT_OFFERED)
    return Availability(AvailabilityState.OFFERED, permitted)


def read_all(
    personalization_config: dict | None, product_id: str
) -> dict[str, Availability]:
    """Every question's state for one product."""
    from .questions import QUESTIONS

    return {
        q.question_id: read_availability(
            personalization_config, product_id, q.question_id
        )
        for q in QUESTIONS
    }
