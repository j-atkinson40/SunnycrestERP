"""Optional model door. It may return a question. It may not return a total.

Called only after the rules have already declined the phrase. No API key means
the model is down: this returns None and the unrecognized hint stands. Any
failure returns None for the same reason — a timeout must not become a guess.
"""
from __future__ import annotations

from datetime import date

from app.services.order_list.question import Interpretation, accept_model_text

_SYSTEM = """You turn one question about funeral-home vault orders into JSON.
You do not write SQL. You do not compute counts, totals, or money.
Allowed keys inside "question": funeral_home, cemetery, vault, decedent,
service_from, service_to, when_label, delivered, invoiced, going_out,
about_money, title, surface.
Dates are YYYY-MM-DD. about_money is true only when the question is about a
customer, a product, or invoices.
If you are not sure which thing a name refers to, respond with
{"unsure": true, "picks": [{"label": "short label", "question": { ... }}]}
with at most four picks. Otherwise respond with {"question": { ... }}.
JSON only."""


def propose(phrase: str, today: date) -> Interpretation | None:
    from app.config import settings

    if not settings.ANTHROPIC_API_KEY or not phrase.strip():
        return None
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=8.0)
        message = client.messages.create(
            model="claude-haiku-4-5-20250514",
            max_tokens=400,
            system=_SYSTEM,
            messages=[{
                "role": "user",
                "content": f"Today is {today.isoformat()}. Question: {phrase}",
            }],
        )
        raw = "".join(getattr(block, "text", "") or "" for block in (message.content or []))
    except Exception:
        return None
    return accept_model_text(raw)
