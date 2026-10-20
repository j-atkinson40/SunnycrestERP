"""Optional model door. It may return a question. It may not return a total.

Called only after the rules have already declined the phrase. No API key, or no
managed prompt, means the model is down: this returns None and the unrecognized
hint stands. Any failure returns None for the same reason — a timeout must not
become a guess.

The call goes through Intelligence (`opas.order_list.interpret`), seeded by
`scripts/seed_opas_order_list_prompt.py`.

⚠️ THE PROMPT WAS UNSEEDED UNTIL 2026-10-20 AND THIS DOOR HAD THEREFORE NEVER
OPENED. Measured on production that day: zero rows in `intelligence_prompts`
for this key, and zero of 5,565 `intelligence_executions` from
`order_list.proposal`. Everything here was correct, tested, and unreachable —
the shape CLAUDE.md §11 calls complete machinery behind an unprovisioned
entrance. The seed is the entrance.

⚠️ THE VARIABLES ARE THE LEAST THE MODEL NEEDS, BY RULING (James, 2026-10-20),
AND `model_context` IS WHERE THAT IS DECIDED. They used to be `today` and
`phrase` alone, which is less than the model needs — a question naming a
funeral home has to name it as the records spell it, because `stage.matches`
compares substrings. So the three name lists travel and nothing else does.
**No deceased name is ever sent from here**; see `model_context`'s docstring
for why that is structural rather than a policy.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.services.order_list.question import Interpretation, accept_model_text

PROMPT_KEY = "opas.order_list.interpret"


def propose(
    phrase: str,
    today: date,
    db: Session | None = None,
    company_id: str | None = None,
) -> Interpretation | None:
    if db is None or not phrase.strip():
        return None
    from app.config import settings

    # ⚠️ DEFENSIVE, NOT LOAD-BEARING, AND A BREAK TEST SAID SO. Removing this turns
    # nothing red: the Anthropic client raises on a missing key and the `except` below
    # returns `None` anyway. What it uniquely buys is that NO CALL IS ATTEMPTED — no
    # round trip, and no stack trace in the log for a tenant that simply has no key
    # configured. The test asserts that, rather than the return value both paths share.
    if not settings.ANTHROPIC_API_KEY:
        return None
    try:
        from app.services.intelligence.intelligence_service import execute

        from app.services.order_list import model_context

        context = model_context.build(db, company_id or "", phrase, today)
        result = execute(
            db,
            prompt_key=PROMPT_KEY,
            variables=context.as_variables(),
            company_id=company_id,
            caller_module="order_list.proposal",
            override_model="claude-haiku-4-5-20250514",
            # Asking is a read. An audit row would commit the caller's session.
            persist=False,
        )
        raw = result.response_text or ""
    except Exception:
        return None
    return accept_model_text(raw)
