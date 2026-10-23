"""Read the record nobody reads: has a prompt been failing for over an hour?

⚠️ THIS IS THE "EVIDENCE EXISTED WITHIN THE HOUR" FIX (James, 2026-10-23).
`intelligence_executions` recorded the dead Anthropic key honestly as `api_error` from
2026-10-22 17:00:01 onward. It kept recording it for 42 hours. Nothing read the table, so
36 briefings went out degraded and nobody knew. The data was never the problem.

⚠️ IT ASKS "ANY SUCCESS?", NOT "ANY FAILURE?", AND THAT IS THE WHOLE DESIGN. A single
failure is ordinary — a 529 overload, a parse miss, a rate limit. 15 `overloaded_error`
rows and 44 schema misses are in this table across six months and none of them is an
incident. What is NOT ordinary is a prompt key that has been ATTEMPTED and has not
SUCCEEDED ONCE in the window. That is the shape a dead credential makes and a transient
hiccup does not.

⚠️ AND IT IS PER PROMPT KEY, not global. A global check is silent whenever any one prompt
still works — exactly the saturation CLAUDE.md describes, where a channel cannot report a
new failure because something else is already green.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

#: ⚠️ 90 MINUTES FOR AN "OVER AN HOUR" RULE, DELIBERATELY. The briefing prompts run
#: hourly, so a 60-minute window can hold exactly one attempt — and one failed attempt is
#: not yet a pattern. 90 minutes guarantees at least two attempt opportunities for an
#: hourly prompt before anything is claimed.
WINDOW_MINUTES = 90


@dataclass(frozen=True)
class FailingPrompt:
    prompt_key: str
    failures: int
    statuses: str
    first_at: str
    last_at: str


def failing_prompts(
    db: Session,
    *,
    window_minutes: int = WINDOW_MINUTES,
    as_of: str | None = None,
) -> list[FailingPrompt]:
    """Prompt keys attempted in the window with ZERO successes.

    ⚠️ `COALESCE(prompt_key, '(unknown)')` BECAUSE A FAILURE CAN PRECEDE RESOLUTION. The
    42 `TypeError` rows from August carry a NULL `model_used` and some rows can carry no
    resolvable prompt; dropping them would hide the loudest failures this table has ever
    held.

    ⚠️ `as_of` EXISTS SO THIS CHECK CAN BE PROVED TO SPEAK, AND IT WAS ADDED FOR EXACTLY
    THAT REASON. Run against `now()` it returns "all clear", which is the same output a
    broken query gives — CLAUDE.md's absent signal. Pointed at 2026-10-22 18:00 it must
    name the three prompts that were failing then. A check whose only observed output is
    silence is not yet an instrument.
    """
    rows = db.execute(
        text(
            """
            SELECT COALESCE(p.prompt_key, '(unknown)') AS k,
                   count(*) AS attempts,
                   sum(CASE WHEN e.status = 'success' THEN 1 ELSE 0 END) AS wins,
                   string_agg(DISTINCT e.status, ',') AS statuses,
                   min(e.created_at)::text AS first_at,
                   max(e.created_at)::text AS last_at
            FROM intelligence_executions e
            LEFT JOIN intelligence_prompts p ON p.id = e.prompt_id
            WHERE e.created_at > CAST(COALESCE(:as_of, now()::text) AS timestamptz)
                                 - make_interval(mins => :w)
              AND e.created_at <= CAST(COALESCE(:as_of, now()::text) AS timestamptz)
            GROUP BY 1
            HAVING sum(CASE WHEN e.status = 'success' THEN 1 ELSE 0 END) = 0
            ORDER BY 2 DESC
            """
        ),
        {"w": window_minutes, "as_of": as_of},
    ).fetchall()
    return [
        FailingPrompt(r.k, int(r.attempts), r.statuses or "", r.first_at, r.last_at)
        for r in rows
    ]


def format_report(failing: list[FailingPrompt], *, window_minutes: int = WINDOW_MINUTES) -> str:
    if not failing:
        return f"No prompt has failed every attempt in the last {window_minutes} minutes."
    lines = [
        f"{len(failing)} prompt(s) attempted in the last {window_minutes} minutes with "
        f"NO success:",
        "",
    ]
    for f in failing:
        lines.append(f"  {f.prompt_key}: {f.failures} attempt(s), all failed "
                     f"[{f.statuses}]")
        lines.append(f"      {f.first_at} .. {f.last_at}")
    lines.append("")
    lines.append("A prompt that never succeeds across a whole window is a credential or "
                 "configuration problem, not a transient one.")
    return "\n".join(lines)
