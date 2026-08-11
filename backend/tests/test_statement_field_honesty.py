"""BSS-2 — two statement fields that lied, found while wiring D-2.

Static, no DB. Both bugs survived because NOTHING HAS EVER BEEN SENT on this
platform — 0 `statement_runs`, 0 `customer_statements`, 0 `email.statement`
deliveries [PLATFORM-WIDE]. Neither would have survived a single real send.

BUG 1 — every statement email would have said "Monthly".
`send_all_digital` read `hasattr(stmt, "period_month")`, but the columns are
`statement_period_month` / `statement_period_year`. The attribute does not exist,
so the ternary took its else branch on EVERY row and the month rendered as the
literal string "Monthly". **The first customer to receive a statement would have
found it.** This is the guessed-attribute-name class — the same one that produced
nine or ten catches this week — and the first instance of it that would have
reached a customer rather than a database error.

BUG 2 — a timestamp asserting a document that did not exist.
`generate_statement` stamped `statement_pdf_generated_at` while rendering
nothing, and `statement_pdf_url` was left null. A column claiming a PDF, beside a
URL column that was always empty. The stamp now lives in
`statement_pdf_service.generate_statement_document`, next to the URL it is paired
with, so the two are written together and only when both are true.

⚠️ `ready` IS UNCHANGED. It still means "balances computed and sendable", not
"has a document" — two live endpoints consume it, and redefining a value mid-arc
is the failure D-1 was gated to avoid.
"""
from __future__ import annotations

import inspect
import re

from app.services import statement_pdf_service, statement_service


def _fn_source(module, needle: str) -> str:
    """Return the source of the function containing `needle`.

    Located by CONTENT rather than by name: the first version of this check
    guessed the function name, `inspect.getsource` returned nothing, and the
    assertions passed vacuously against an empty string. A check that cannot
    fail is not a check.
    """
    src = inspect.getsource(module)
    for m in re.finditer(r"^def ([a-z_]+)\(", src, re.M):
        body = src[m.start():]
        nxt = re.search(r"^def ", body[1:], re.M)
        body = body[: nxt.start() + 1] if nxt else body
        if needle in body:
            return body
    raise AssertionError(f"no function in {module.__name__} contains {needle!r}")


class TestTheMonthIsTheRealMonth:
    def test_the_send_reads_the_columns_that_exist(self):
        src = inspect.getsource(statement_service.send_all_digital)
        assert "stmt.statement_period_month" in src
        assert "stmt.statement_period_year" in src

    def test_the_nonexistent_attribute_is_gone(self):
        src = inspect.getsource(statement_service.send_all_digital)
        assert 'hasattr(stmt, "period_month")' not in src, (
            "the hasattr guard is back; it is always False and every statement "
            "email renders its month as the literal string 'Monthly'"
        )

    def test_the_attribute_really_does_not_exist(self):
        """Pins WHY the guard was wrong rather than just that it went. If a
        `period_month` synonym is ever added, this fails and the fix should be
        reconsidered rather than silently double-covered."""
        from app.models.statement import CustomerStatement

        assert not hasattr(CustomerStatement, "period_month")
        assert hasattr(CustomerStatement, "statement_period_month")


class TestTheTimestampFollowsTheDocument:
    def test_the_balances_path_no_longer_stamps_it(self):
        body = _fn_source(statement_service, 'stmt.status = "ready"')
        assert "statement_pdf_generated_at = datetime" not in body, (
            "the false stamp is back — this function renders no PDF, so the "
            "column would again assert a document that does not exist"
        )

    def test_ready_is_still_set_there(self):
        """The fix must remove the false claim WITHOUT changing what `ready`
        means. Two live endpoints select on it."""
        body = _fn_source(statement_service, 'stmt.status = "ready"')
        assert 'stmt.status = "ready"' in body

    def test_the_renderer_stamps_both_fields_together(self):
        """They describe one event. Written apart, they drift — which is how one
        of them ended up always-null while the other was always-set."""
        src = inspect.getsource(statement_pdf_service.generate_statement_document)
        assert "statement_pdf_url" in src
        assert "statement_pdf_generated_at" in src


class TestBothSurvivedForTheSameReason:
    def test_no_statement_has_ever_been_sent(self):
        """Documented, not asserted against the DB — this is the CONDITION that
        let both bugs live, and it stops being true the first time a statement
        goes out. Recorded so the next reader knows why two obvious defects sat
        in a live codebase: nothing exercised them."""
        doc = __import__(__name__).__doc__ or ""
        assert "NOTHING HAS EVER BEEN SENT" in doc
