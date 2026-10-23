"""A short briefing says why it is short.

⚠️ MEASURED ON PRODUCTION (James, 2026-10-23). The Anthropic key died mid-rotation at
2026-10-22 ~17:00 UTC. For the next 42 hours, 36 briefings were generated:

    after  the key died:  narrative 29–61 chars,   cost $0.00
    before the key died:  narrative 356–528 chars, cost $0.002–0.005

None was empty. None failed. Every count in them was correct. What none of them said was
that the writing model had been skipped — so a director read a one-line briefing with no
way to tell it from a quiet day. `_fallback_content`'s own docstring claimed it was "kept
factual so it never misleads", and every word in it was factual; it misled by OMISSION.
"""
from __future__ import annotations

import pytest

from app.services.briefings.generator import DEGRADED_PREFIX, _fallback_content
from app.services.briefings.types import BriefingDataContext


def _ctx(**kw):
    """A context with just the fields the stub reads."""
    base = dict(
        user_first_name="James", day_of_week="Friday", today_events=[],
        queue_summaries=[], overnight_calls={},
    )
    base.update(kw)

    class C:
        def __init__(self, d):
            for k, v in d.items():
                setattr(self, k, v)

        def __getattr__(self, _n):
            return None

    return C(base)


def test_a_degraded_briefing_SAYS_SO_in_the_prose():
    narrative, _sections = _fallback_content(_ctx(), "morning", reason="api_error")
    assert DEGRADED_PREFIX in narrative, narrative
    # ⚠️ IT LEADS. A note at the end is read after the reader has already taken the short
    # narrative for the whole briefing.
    assert narrative.startswith(DEGRADED_PREFIX), narrative


def test_it_also_says_so_IN_THE_SECTIONS():
    """⚠️ TWO RENDERINGS, SO TWO PLACES. A surface that shows `structured_sections`
    rather than the prose would otherwise display a degraded briefing with no sign of it
    — a degradation visible in one rendering is invisible in the other."""
    _n, sections = _fallback_content(_ctx(), "evening", reason="api_error")
    assert sections.degraded_note is not None
    assert DEGRADED_PREFIX in sections.degraded_note
    # the reason travels, so a reader can tell a dead key from a schema miss
    assert "api_error" in sections.degraded_note


def test_a_NON_degraded_stub_stays_silent():
    """⚠️ THE CONTROL, AND WITHOUT IT THE TESTS ABOVE PASS FOR A STUB THAT ALWAYS
    APOLOGISES. The stub is also reached on paths that are not model failures; claiming
    the model was unavailable there would be a false statement in the other direction.
    """
    narrative, sections = _fallback_content(_ctx(), "morning")
    assert DEGRADED_PREFIX not in narrative, narrative
    assert sections.degraded_note is None


def test_the_counts_are_still_there_alongside_the_notice():
    """The notice is added, not substituted. A degraded briefing still carries whatever
    the data context knew — that was the one thing the old stub got right."""
    narrative, _s = _fallback_content(
        _ctx(today_events=[1, 2, 3],
             queue_summaries=[{"pending_count": 4}]),
        "morning", reason="api_error",
    )
    assert DEGRADED_PREFIX in narrative
    assert "3 events" in narrative
    assert "4 item" in narrative


@pytest.mark.parametrize("reason", ["api_error", "unparseable response", "empty narrative"])
def test_every_fallback_path_carries_a_reason(reason):
    """⚠️ THREE PATHS REACH THE STUB, NOT ONE. A provider failure, an unparseable
    response, and an empty narrative — and the two shape failures are the ones that have
    actually been happening: 44 `briefing.evening` responses have omitted
    `structured_sections` since May 2026. All three now say so.
    """
    narrative, sections = _fallback_content(_ctx(), "evening", reason=reason)
    assert narrative.startswith(DEGRADED_PREFIX)
    assert reason in (sections.degraded_note or "")


def test_the_generator_passes_a_reason_at_every_fallback_call_site():
    """⚠️ READ OUT OF THE SOURCE, because the call sites are what a break test showed to
    be unpinned: removing `reason=status` from the generator left every other test green.
    """
    import ast
    import inspect

    from app.services.briefings import generator

    tree = ast.parse(inspect.getsource(generator))
    calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "_fallback_content"
    ]
    assert len(calls) >= 3, f"expected 3 fallback call sites, found {len(calls)}"
    for c in calls:
        kw = {k.arg for k in c.keywords}
        assert "reason" in kw, ast.dump(c)[:160]
