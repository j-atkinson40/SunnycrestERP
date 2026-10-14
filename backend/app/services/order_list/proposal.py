"""Optional model door. It may return a question. It may not return a total.

Called only after the rules have already declined the phrase. No API key, or no
managed prompt, means the model is down: this returns None and the unrecognized
hint stands. Any failure returns None for the same reason — a timeout must not
become a guess.

The call goes through Intelligence (`opas.order_list.interpret`). That prompt
is not seeded here. Until it exists, an unrecognized phrase stays unrecognized,
and the questions the rules already know do not need it. Variables the prompt
receives: `today` (YYYY-MM-DD) and `phrase`.
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

    if not settings.ANTHROPIC_API_KEY:
        return None
    try:
        from app.services.intelligence.intelligence_service import execute

        result = execute(
            db,
            prompt_key=PROMPT_KEY,
            variables={"today": today.isoformat(), "phrase": phrase},
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
