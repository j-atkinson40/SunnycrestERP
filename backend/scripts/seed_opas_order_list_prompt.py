"""Seed `opas.order_list.interpret` — the prompt the Opas model door has never had.

James's dispatch of 2026-10-20, step 3: "Turn on the existing model door
(order_list/proposal.py, accept_model_text): seed its prompt on production."

⚠️ THE DOOR HAS BEEN COMPLETE AND UNREACHABLE. `order_list/proposal.py` and
`question.accept_model_text` already implement rules-first, engine-decides, None-on-any-
failure, and are tested. Measured on production 2026-10-20: ZERO rows in
`intelligence_prompts` for this key, and ZERO of 5,565 `intelligence_executions` from
`order_list.proposal`. This script is the only missing piece.

Option A idempotent seed (Phase 6 / 8b / 8d.1 / R-6.1a / R-6.2a):

  - no existing prompt                → create + v1 active
  - exactly 1 version matching spec   → no-op
  - exactly 1 version differing       → deactivate v1, create v2
  - several versions (admin edits)    → SKIP with a warning, touch nothing

⚠️ IT SEEDS A PLATFORM PROMPT (`company_id IS NULL`), not a per-tenant one. The question
vocabulary is the same for every manufacturer; what differs per tenant is the NAME LISTS,
and those arrive as variables at call time from `model_context`, not baked into a prompt.

Run:
    cd backend && DATABASE_URL=<url> python -m scripts.seed_opas_order_list_prompt
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

PROMPT_KEY = "opas.order_list.interpret"

# ⚠️ EVERY RULE IN THIS PROMPT IS ALSO ENFORCED BY `accept_model_text`, DELIBERATELY. A
# prompt is a request and a validator is a decision; the prompt exists so the model
# usually complies, and the validator exists because sometimes it will not. If the two
# ever disagree, the validator wins and the request is refused — which is what "the
# engine decides" means.
SYSTEM_PROMPT = (
    "You turn one typed phrase from a burial-vault manufacturer's order bar into one "
    "JSON object describing WHICH ORDERS the person is asking about. You never answer "
    "the question yourself.\n"
    "\n"
    "Return ONLY a JSON object. No prose, no code fence.\n"
    "\n"
    "SHAPE A — you understood the phrase:\n"
    '  {"question": {...}}\n'
    "\n"
    "SHAPE B — the phrase could mean two or three different things:\n"
    '  {"unsure": true, "picks": [{"label": "<what the person would recognise>", '
    '"question": {...}}, ...]}\n'
    "\n"
    "The question object may contain ONLY these keys, all optional:\n"
    "  funeral_home   string — MUST be copied exactly from the Funeral homes list below\n"
    "  cemetery       string — MUST be copied exactly from the Cemeteries list below\n"
    "  vault          string — MUST be copied exactly from the Vaults list below\n"
    "  decedent       string — a surname, taken from the phrase itself\n"
    "  when_phrase    string — the DATE WORDS from the phrase, copied as the person "
    "said them: 'next week', 'thursday', 'this month', 'coming up', 'oct 28'. Never a "
    "date. Never a range. The system resolves it against Today.\n"
    "  delivered      true | false\n"
    "  invoiced       true | false\n"
    "  going_out      true — the person means orders still COMING UP: service date "
    "today or later. Not 'not yet delivered'. An order whose service date has passed "
    "is never coming up, whatever its status.\n"
    "  title          string — a short heading for the answer\n"
    "\n"
    "HARD RULES. Breaking any of these means your answer is thrown away:\n"
    "  1. NEVER return a number, a count, a total, an amount, a sum, or any row of "
    "data. You describe a filter; the system runs it and reads the records.\n"
    "  2. NEVER return SQL or a query of any kind.\n"
    "  3. Use ONLY the keys listed above. An unknown key voids the whole answer.\n"
    "  4. A name you were not given does not exist. If the phrase names a funeral home, "
    "cemetery or vault that is not in the lists below, do not invent a value for that "
    "field — leave it out, or use shape B to ask.\n"
    "  5. NEVER COMPUTE A DATE. You do not return `service_from`, `service_to` or "
    "`when_label` — those keys void the whole answer. Put the person's own date words "
    "in `when_phrase` and let the system do the arithmetic. Asked the same question "
    "twice you must return the same words; working out a calendar is not your job.\n"
    "  6. If you are not confident, prefer shape B with two or three picks over a "
    "guess. Asking is always acceptable; guessing is not.\n"
    "\n"
    "Today is {{today}} — given so you can tell past from future, NOT so you can "
    "compute a span.\n"
    "Funeral homes: {{funeral_homes}}\n"
    "Cemeteries: {{cemeteries}}\n"
    "Vaults: {{vaults}}\n"
    "Lists truncated: {{truncated}} — if yes, a name you were not shown may still "
    "exist, so prefer shape B over assuming it does not.\n"
    "\n"
    "⚠️ You are given NO decedent names, on purpose. A surname in a question comes from "
    "the phrase the person typed, never from a list."
)

USER_TEMPLATE = "{{phrase}}"

VARIABLE_SCHEMA = {
    "today": {"type": "string", "required": True},
    "phrase": {"type": "string", "required": True},
    "funeral_homes": {"type": "string", "required": True},
    "cemeteries": {"type": "string", "required": True},
    "vaults": {"type": "string", "required": True},
    "truncated": {"type": "string", "required": True},
}

# ⚠️ ADVISORY ONLY. `accept_model_text` is the gate; this documents the shape for the
# prompt playground and for anyone reading the row.
RESPONSE_SCHEMA = {
    "type": "object",
    "oneOf": [
        {"required": ["question"]},
        {"required": ["unsure", "picks"]},
    ],
}

CHANGELOG = (
    "v3 — dates never come from the model (James, 2026-10-23). The model returns the "
    "person's own date WORDS in `when_phrase`; `order_list/when.resolve_when` turns "
    "them into a window against the tenant's local today. Found by measuring: "
    "'anything for hopkins next week' returned service_from 2026-10-26 on one run and "
    "2026-10-30 on another, ninety minutes apart, with today = 2026-10-23 — so the "
    "second was a week out. Both answered 0 orders, so nothing looked wrong. A "
    "resolved date is a computed value and hard rule 1 already forbade those; the "
    "exemption was habit, not a decision. `service_from`/`service_to`/`when_label` are "
    "now REFUSED outright in a model payload, the same treatment a payload carrying "
    "`sql` gets.\n"
    "v2 — `going_out` is a DATE, not a delivery state (James, 2026-10-23). v1 told the "
    "model it meant 'orders not yet delivered', which is what the matcher in stage.py "
    "also believed. The door's first real answer on production — 'anything going to st "
    "marys coming up?' — was read correctly and then filtered wrongly: it returned "
    "SO-2026-0001, dated a week earlier, because a draft has never been delivered. The "
    "matcher is fixed in the same commit; this line is the other half, so the prompt "
    "and the code describe the same filter.\n"
    "v1 — first seeding of the Opas order-list model door (James, 2026-10-20). The door "
    "in order_list/proposal.py and the validator in question.accept_model_text shipped "
    "earlier and had never been reachable: zero rows for this key on production. "
    "Variables carry the tenant's funeral home, cemetery and vault NAMES and nothing "
    "else — no decedent names, by ruling."
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
        # ⚠️ `simple` ROUTES TO HAIKU, which is what `proposal.py` also pins with
        # `override_model`. Two places name a model; the route is what the playground
        # and any future caller read, and the override is what this caller enforces.
        model_preference="simple",
        # ⚠️ 0.0, NOT THE ROUTE'S 0.2. The same phrase must produce the same question
        # twice, or a cache is unsafe and a test set is unscoreable.
        temperature=0.0,
        # A question object is small. A larger ceiling buys nothing and pays for prose.
        max_tokens=400,
        force_json=True,
        supports_streaming=False,
        supports_tool_use=False,
        status="active",
        changelog=CHANGELOG,
        activated_at=datetime.now(timezone.utc),
    )


def seed(db) -> str:
    """Returns one of: created, noop, upgraded, skipped-multi."""
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
            display_name="Opas — interpret an order-list phrase",
            description=(
                "The model door behind the Opas bar. Called ONLY when the deterministic "
                "rules in order_list/question.py decline a phrase. Returns one "
                "OrderQuestion, or asks with two or three picks. Every answer is "
                "validated by question.accept_model_text, which refuses non-JSON, any "
                "banned key at any depth, and anything failing OrderQuestion — and "
                "None means the rules' answer stands."
            ),
            domain="opas",
            caller_module="order_list.proposal",
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
    if len(versions) > 1:
        # ⚠️ SKIP, DO NOT MERGE. More than one version means someone edited this prompt
        # through the admin playground, and a seed that overwrote that would silently
        # throw away a person's work.
        logger.warning(
            "%s has %d versions — an admin has edited it. Skipping.",
            PROMPT_KEY, len(versions),
        )
        return "skipped-multi"
    if len(versions) == 1 and _matches(versions[0]):
        if not versions[0].status == "active":
            versions[0].status = "active"
            versions[0].activated_at = datetime.now(timezone.utc)
            return "created"
        return "noop"
    if len(versions) == 1:
        versions[0].status = "retired"
        db.add(_new_version(prompt, versions[0].version_number + 1))
        return "upgraded"
    db.add(_new_version(prompt, 1))
    return "created"


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
