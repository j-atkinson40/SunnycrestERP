"""BSS-2 D-3 — the statement ledger survives a failure, and normal states don't fail the run.

Static, no DB. Exercising the sweep needs a seeded run, a rendered Document and
R2; what is worth pinning is the SHAPE, because the shape is the whole fix.

⚠️ THE DEFECT, WHICH IS WORSE THAN "THE RUN STOPS".
The loop already continued past a failed item. What it did NOT do was commit per
item — and `send_statement_email` has `try:`/`finally:` with **no `except`** (the
`finally` only closes a session). So a delivery exception PROPAGATED, aborted the
sweep, and the single trailing commit never ran. Every statement already marked
`sent`, with `sent_at` and `email_sent_to` written, rolled back.

**The customers received their statements and the ledger said nobody did.**
The scope is DURABILITY, not resilience.

⚠️ THE SOFT / HARD LINE. `success: False` is the provider ANSWERING; an exception
is the provider or transport NOT answering, which is our problem.

    SOFT — recorded per item, does NOT fail the run
      no email address        → `skipped`   (a paper-statement customer)
      delivery returned False → `failed`    (the provider answered: no)
    HARD — recorded per item, DOES fail the run after the sweep
      render raised · render returned no document · the send raised

⚠️ "NO EMAIL" MUST BE SOFT, and the numbers make it concrete rather than
theoretical: 6 of 11 statement-cohort customers have no address [PLATFORM-WIDE],
concentrated at **testco 3-of-3**. Classified hard, that tenant's statement run
fails EVERY MONTH FOREVER on a normal configuration — the arc's own pathology,
created by the arc.
"""
from __future__ import annotations

import inspect

from app.services import statement_service


def _code_only(src: str) -> str:
    """Source with `#` comments removed.

    ⚠️ NOT COSMETIC. These tests match against source text, and comment PROSE
    matches as readily as code — which broke two of them on the first run: the
    split point `send_statement_email` first occurs inside a comment describing
    it, and an assertion that the else-branch contains no `raise` tripped on the
    words "a later raise cannot unwrite…". A source-scraping test that reads its
    own explanatory comments is measuring documentation, not behaviour.

    Line-based rather than tokenised, because `inspect.getsource` of an indented
    block does not round-trip through `tokenize.untokenize`. Safe here: no `#`
    appears inside a string literal in this function.
    """
    return "\n".join(line.split("#")[0] for line in src.splitlines())


def _src() -> str:
    return _code_only(inspect.getsource(statement_service.send_all_digital))


def _loop_body() -> str:
    raw = inspect.getsource(statement_service.send_all_digital)
    return _code_only(raw.split("for stmt in stmts:")[1].split("# Update run")[0])


class TestTheLedgerSurvives:
    def test_state_is_committed_inside_the_loop(self):
        """THE FIX. Without this, one raise unwrites every delivery that already
        happened."""
        assert "db.commit()" in _loop_body(), (
            "per-item commits are gone — a raise now discards the whole ledger"
        )

    def test_the_send_is_inside_the_try(self):
        """The send was the UNGUARDED half. Guarding only the render (D-2's
        interim shape) leaves the actual hazard open."""
        body = _loop_body()
        guarded = body.split("try:")[1].split("except Exception")[0]
        assert "send_statement_email" in guarded

    def test_hard_failures_roll_back_before_re_fetching(self):
        """Plaid's shape, and the reason for it: the exception may have left the
        session dirty and the ORM object stale, so writing through the existing
        identity map could fail or silently write nothing."""
        src = _src()
        helper = src.split("def _record_hard")[1].split("for stmt in stmts:")[0]
        assert "db.rollback()" in helper
        assert "db.get(CustomerStatement" in helper
        assert helper.index("db.rollback()") < helper.index("db.get(CustomerStatement"), (
            "the re-fetch must come AFTER the rollback"
        )
        assert "db.commit()" in helper, "the hard-failure state is not durable"


class TestTheSoftHardSplit:
    def test_no_email_is_skipped_not_failed(self):
        """6 of 11 cohort customers have none; testco is 3 of 3. A hard
        classification fails that tenant's run every month forever."""
        body = _loop_body()
        assert 'stmt.status = "skipped"' in body
        no_email_branch = body.split("if not email:")[1].split("continue")[0]
        assert '"skipped"' in no_email_branch
        assert '"failed"' not in no_email_branch, (
            "a customer with no email address is a paper-statement customer, "
            "not a failure"
        )

    def test_skipped_is_a_status_the_run_completion_check_already_reads(self):
        """Not a new status — it was consumed at the run-completion check and
        written by nothing. A soft slot built and never used."""
        whole = inspect.getsource(statement_service)
        assert '"sent", "skipped", "failed"' in whole

    def test_a_provider_rejection_does_not_raise(self):
        """SOFT. The provider answered. Per the Plaid precedent a routine
        external condition must not turn a monthly run red forever — the item
        state is the signal."""
        body = _loop_body()
        else_branch = body.split('if result["success"]:')[1]
        assert "raise" not in else_branch.split("except Exception")[0], (
            "a delivery rejection now raises — one full mailbox would fail the "
            "whole run"
        )

    def test_hard_failures_are_tracked_separately_from_soft_ones(self):
        src = _src()
        assert "hard_failures" in src
        assert "skipped = 0" in src and "failed = 0" in src, (
            "soft outcomes must stay countable apart from hard ones"
        )


class TestTheTerminalRaise:
    def test_it_raises_only_when_a_hard_failure_occurred(self):
        assert "if hard_failures:" in _src()

    def test_it_comes_after_the_run_row_is_committed(self):
        """The run must reflect reality before the failure surfaces.

        ⚠️ Located by the LAST `raise RuntimeError`, not the first. My initial
        check used `.index(...)` and found the missing-document raise INSIDE the
        loop, reporting the ordering as wrong when it was correct. A name- or
        first-match-based lookup that lands on the wrong occurrence is silent.
        """
        src = _src()
        terminal_raise = src.rindex("raise RuntimeError")
        last_commit = src.rindex("db.commit()")
        assert terminal_raise > last_commit

    def test_the_message_says_the_ledger_is_intact(self):
        """Whoever reads this in a failed run needs to know the per-item state
        is trustworthy — otherwise the first instinct is to re-run and
        double-send."""
        src = _src()
        assert "per-item state is committed" in src

    def test_the_return_reports_skipped(self):
        """A caller that sees only sent/failed cannot tell a paper-statement
        cohort from a broken one."""
        assert '"skipped": skipped' in _src()
