"""Seed the managed prompt that drafts a rulebook sentence.

James's dispatch of 2026-10-26: "'Always' makes the model turn your words into a short
rule sentence. You confirm or edit it before it goes into the rulebook."

⚠️ IDEMPOTENT BY CONTENT, NOT BY COUNT, and the distinction is not academic here — it is
the defect this family of seeds already shipped once. `seed_opas_order_list_prompt`
skipped whenever more than one version existed, which made it a one-shot seed that
believed it was idempotent: from its own second update onward, "an admin edited this" and
"I have run twice" were the same observation. v3 never landed and every dated question on
production was refused for fifteen minutes. This file compares the NEWEST version's
content with what it would write, which is a question a count cannot answer.

⚠️ AND NOTHING BREAKS IF IT NEVER RUNS. `rule_draft.draft` returns None on an unseeded
prompt exactly as it does on a dead key, and the caller falls back to the person's own
words — which the dispatch asks for as its own verified case. An unseeded prompt makes
the feature quieter, not broken, which is the right failure for a prompt that only ever
proposes something a person then confirms.

Run:
    cd backend && DATABASE_URL=<url> python -m scripts.seed_opas_rulebook_prompt
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models.intelligence import IntelligencePrompt, IntelligencePromptVersion

logger = logging.getLogger(__name__)

PROMPT_KEY = "opas.rulebook.draft"

SYSTEM_PROMPT = (
    "You turn one correction into one rule sentence for a burial vault "
    "manufacturer's office.\n"
    "\n"
    "The office changed a field on an order after the system filled it in, and said "
    "why. Write the standing rule their words imply, as ONE short sentence in their "
    "own register — plain, specific, no hedging.\n"
    "\n"
    "HARD RULES:\n"
    "  1. ONE sentence. No preamble, no explanation, no second sentence.\n"
    "  2. Use only what you are given. You do not know the deceased, the funeral "
    "home, the cemetery or the date, and you must not invent any of them.\n"
    "  3. If their reason is specific to this one order and implies no standing rule, "
    "say so by returning their reason as the sentence, unchanged. Do NOT manufacture a "
    "general rule out of a one-off.\n"
    "  4. Do not promise behaviour. Write what should be TRUE, not what the system "
    "will do — 'Hopkins takes the Continental', not 'I will always pick the "
    "Continental'.\n"
    "  5. Return JSON: {\"rule\": \"<the sentence>\"}. Nothing else.\n"
    "\n"
    "EXAMPLES\n"
    "  field=Vault was='Monticello Burial Vault' now='Continental Burial Vault'\n"
    "  reason='they always take the continental for a veteran'\n"
    "  -> {\"rule\": \"Veterans take the Continental rather than the Monticello.\"}\n"
    "\n"
    "  field=Service time was='10:00' now='11:00'\n"
    "  reason='the church is never free before eleven'\n"
    "  -> {\"rule\": \"Services at the church start no earlier than 11:00.\"}\n"
    "\n"
    "  field=Vault was='Monticello Burial Vault' now='Venetian Burial Vault'\n"
    "  reason='the family asked for it on the phone this morning'\n"
    "  -> {\"rule\": \"The family asked for it on the phone this morning.\"}\n"
)

USER_TEMPLATE = (
    "field={{ field }}\n"
    "was={{ was }}\n"
    "now={{ now }}\n"
    "reason={{ reason }}\n"
)

VARIABLE_SCHEMA = {
    "type": "object",
    "properties": {
        "field": {"type": "string"},
        "was": {"type": "string"},
        "now": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["field", "was", "now", "reason"],
}

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {"rule": {"type": "string"}},
    "required": ["rule"],
}

CHANGELOG = (
    "v1 — the rulebook's first slice (James, 2026-10-26). Drafts one sentence from a "
    "change plus the person's reason; the person confirms or edits it before it is "
    "stored. Deliberately NOT sent: the deceased name, the funeral home, the cemetery "
    "and the date — 'least data: no deceased names' in the dispatch, read as the "
    "narrowest set that still produces a sentence. Rule 3 exists because the common "
    "case is a one-off: a model that generalises every correction would fill the "
    "rulebook with rules nobody meant, and the office would stop reading it."
)


def _matches(version: IntelligencePromptVersion) -> bool:
    return (
        version.system_prompt == SYSTEM_PROMPT
        and version.user_template == USER_TEMPLATE
    )


def _new_version(prompt: IntelligencePrompt, number: int) -> IntelligencePromptVersion:
    return IntelligencePromptVersion(
        prompt_id=prompt.id,
        version_number=number,
        system_prompt=SYSTEM_PROMPT,
        user_template=USER_TEMPLATE,
        variable_schema=VARIABLE_SCHEMA,
        response_schema=RESPONSE_SCHEMA,
        # ⚠️ ONE PLACE NAMES A MODEL. `simple` resolves through
        # `intelligence_model_routes`, which is updatable without a deploy; a literal in
        # the caller is the drift that 404'd the order-list door's first live run.
        model_preference="simple",
        # The same reason as the order-list prompt: one correction must draft the same
        # sentence twice, or the office cannot tell an edit of theirs from the model
        # changing its mind.
        temperature=0.0,
        # One sentence. A larger ceiling buys nothing and pays for prose.
        max_tokens=200,
        force_json=True,
        supports_streaming=False,
        supports_tool_use=False,
        status="active",
        changelog=CHANGELOG,
        activated_at=datetime.now(timezone.utc),
    )


def seed(db) -> str:
    """Returns one of: created, noop, upgraded, reactivated."""
    prompt = (
        db.query(IntelligencePrompt)
        .filter(
            IntelligencePrompt.company_id.is_(None),
            IntelligencePrompt.prompt_key == PROMPT_KEY,
        )
        .first()
    )
    if prompt is None:
        prompt = IntelligencePrompt(
            company_id=None,
            prompt_key=PROMPT_KEY,
            display_name="Opas — draft a rulebook sentence",
            description=(
                "Called when the office answers Opas's \"why?\" and chooses Always. "
                "Turns the change plus their reason into ONE sentence, which they "
                "confirm or edit before it is stored in opas_rules. Never writes "
                "anything itself; a failure of any kind falls back to the person's own "
                "words, which the dispatch requires as a verified case."
            ),
            domain="opas",
            caller_module="capture.rule_draft",
            is_active=True,
        )
        db.add(prompt)
        db.flush()
        db.add(_new_version(prompt, 1))
        return "created"

    versions = (
        db.query(IntelligencePromptVersion)
        .filter(IntelligencePromptVersion.prompt_id == prompt.id)
        .order_by(IntelligencePromptVersion.version_number)
        .all()
    )
    # ⚠️ CONTENT, NEVER COUNT — see the module docstring for what counting cost.
    live = [v for v in versions if v.status == "active"]
    newest = max(versions, key=lambda v: v.version_number) if versions else None

    if newest is not None and _matches(newest):
        if newest.status != "active":
            for other in live:
                other.status = "retired"
            newest.status = "active"
            newest.activated_at = datetime.now(timezone.utc)
            return "reactivated"
        return "noop"

    if newest is None:
        db.add(_new_version(prompt, 1))
        return "created"

    for other in live:
        other.status = "retired"
        logger.warning(
            "%s: superseding v%d (was active) with v%d. The old row is RETAINED as "
            "'retired' and can be reactivated in the playground.",
            PROMPT_KEY, other.version_number, newest.version_number + 1,
        )
    db.add(_new_version(prompt, newest.version_number + 1))
    return "upgraded"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    db = SessionLocal()
    try:
        outcome = seed(db)
        db.commit()
        logger.info("%s: %s", PROMPT_KEY, outcome)
        return 0
    except Exception:
        db.rollback()
        logger.exception("seeding %s failed; nothing written", PROMPT_KEY)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
