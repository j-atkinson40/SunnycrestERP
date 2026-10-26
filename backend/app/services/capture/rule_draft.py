"""Turn "why?" and the change it was about into one plain rule sentence.

James's dispatch of 2026-10-26: "'Always' makes the model turn your words into a short
rule sentence. You confirm or edit it before it goes into the rulebook… If the model is
down, your own words become the draft."

⚠️ THE FALLBACK IS NOT AN ERROR PATH, IT IS A STATED REQUIREMENT, and clause 5 of the
dispatch verifies it: "Model key off -> own words drafted". So every failure here —
no key, no seeded prompt, a provider 401, an unparseable answer — returns None and the
caller uses the person's own words. There is no state in which the person is told the
rule could not be drafted.

⚠️ AND THE PERSON CONFIRMS WHATEVER COMES BACK. The model never writes to the rulebook;
it proposes a sentence into the reply line, which the office presses Enter on or types
over. That is the whole reason a model is acceptable here at all — nothing it says
becomes a rule without somebody reading it first.

⚠️ LEAST DATA, AND I MADE A JUDGEMENT THE DISPATCH DID NOT MAKE FOR ME. It says "least
data: no deceased names". What goes is the FIELD, the two VALUES and the person's own
REASON — and deliberately NOT the funeral home, the cemetery, or anything else from the
order. A rule is usually about a customer, so leaving the home out means a drafted rule
reads tenant-wide unless the person's own words name the home. Reported rather than
decided silently: if James wants customer-scoped rules, the home is the next variable to
add and `VARIABLE_SCHEMA` in the seed is where it goes.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

PROMPT_KEY = "opas.rulebook.draft"

#: ⚠️ A SENTENCE, NOT A PARAGRAPH. The rulebook pane shows one line per rule and the
#: next slice shows these to the model; prose would be unreadable in both places. The
#: ceiling is characters rather than tokens because it is enforced here, on the way out.
MAX_RULE = 220


def _tidy(sentence: str) -> str | None:
    """One line, trimmed, capped. None when there is nothing usable left.

    ⚠️ NEWLINES COLLAPSE RATHER THAN TRUNCATE. A model that answers with two lines has
    still answered; keeping only the first would silently drop half a rule.
    """
    text = " ".join((sentence or "").split()).strip().strip('"').strip()
    if not text:
        return None
    return text[:MAX_RULE]


def draft(
    db: Session,
    *,
    company_id: str,
    field_label: str,
    was: str,
    now: str,
    reason: str,
) -> str | None:
    """The model's one-sentence rule, or None if it cannot produce one.

    None means "use their own words", never "tell them it failed".
    """
    from app.config import settings

    if not settings.ANTHROPIC_API_KEY:
        # ⚠️ CHECKED BEFORE THE CALL, not inferred from a failure. "Model key off" is a
        # configuration fact, and clause 5 asks for it as its own verified case.
        logger.info("%s: no api key; the person's own words stand", PROMPT_KEY)
        return None
    try:
        from app.services.intelligence.intelligence_service import execute

        result = execute(
            db,
            prompt_key=PROMPT_KEY,
            variables={
                "field": field_label,
                "was": was,
                "now": now,
                "reason": reason,
            },
            company_id=company_id,
            caller_module="capture.rule_draft",
            # ⚠️ NO `override_model`. The prompt version's `model_preference` plus
            # `intelligence_model_routes` is the ONE place a model is named — a literal
            # here is the drift that cost `order_list.proposal` its first live run, when
            # a stale Haiku id 404'd minutes after its prompt was seeded.
            #
            # ⚠️ AND `persist=False`: drafting is a read on behalf of a person who has
            # not confirmed anything. An audit row would commit the caller's session
            # mid-flow, and the thing worth auditing is the RULE, which `opas_rules`
            # records with its source decision.
            persist=False,
        )
    except Exception:
        logger.warning("%s: provider error; the person's own words stand", PROMPT_KEY,
                       exc_info=True)
        return None

    # ⚠️ THE PARSED FIELD FIRST, THE TEXT AS FALLBACK — the same two-path read as
    # `order_list.proposal`, and for the reason recorded there: `intelligence_service`
    # fills `response_parsed` when the prompt sets `force_json`, Haiku fences its JSON,
    # and reading the raw text meant re-parsing something already parsed. The text path
    # survives because a prompt version edited in the playground can have `force_json`
    # switched off.
    parsed = getattr(result, "response_parsed", None)
    if isinstance(parsed, dict):
        got = _tidy(str(parsed.get("rule") or ""))
        if got:
            return got
    return _tidy(getattr(result, "response_text", "") or "")
