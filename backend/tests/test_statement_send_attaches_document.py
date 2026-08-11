"""BSS-2 D-2 — the statement email carries a statement.

Static, no DB. Exercising the send would require a seeded run, a rendered
Document and R2; what is worth pinning is the WIRING, because every part of it
already existed and only the join was missing.

⚠️ WHAT WAS WRONG. `statement_pdf_service.generate_statement_document` renders a
real Document via the active `statement.professional` template and had **ZERO
CALLERS** — its own docstring said "the email-sending path in email_service
doesn't call it yet." Meanwhile `send_all_digital` called
`send_statement_email(...)` without `document_id`, so a statement email would
have gone out with **no statement in it**. Neither side was broken; the join was
absent, and nothing failed loudly because no statement has ever been sent on this
platform (0 `email.statement` rows in `document_deliveries`, PLATFORM-WIDE).

`send_statement_email` has accepted `document_id` all along, and DeliveryService
auto-fetches and attaches the PDF from it — so this is a wiring, not a build.
"""
from __future__ import annotations

import inspect

from app.services import statement_service


def _send_src() -> str:
    return inspect.getsource(statement_service.send_all_digital)


class TestTheJoinExists:
    def test_the_send_generates_a_document(self):
        assert "generate_statement_document" in _send_src(), (
            "the renderer is unwired again — a statement email would carry no "
            "statement"
        )

    def test_the_document_id_is_passed_to_the_email(self):
        """Generating without passing it would render a Document nobody
        attaches — the zero-caller state with extra steps."""
        assert "document_id=document_id" in _send_src()

    def test_the_renderer_still_exists_and_is_callable(self):
        from app.services import statement_pdf_service

        assert callable(statement_pdf_service.generate_statement_document)

    def test_the_email_path_still_accepts_a_document_id(self):
        """The whole reason this is small. If the parameter is ever dropped,
        the call above becomes a TypeError at send time — on a monthly workflow,
        which is the worst cadence to discover it."""
        from app.services.email_service import email_service

        sig = inspect.signature(email_service.send_statement_email)
        assert "document_id" in sig.parameters


class TestTheGuardIsPresent:
    """⚠️ NOT DEFENSIVE PADDING — the loop's only `db.commit()` is AFTER it."""

    def test_the_render_is_guarded(self):
        """`generate_statement_document` raises DocumentRenderError on template,
        PDF or R2 failure. Unguarded, one raise aborts the sweep and rolls back
        the per-item ledger for every customer already processed — the exact
        failure shape D-3 exists to fix. This guard is why D-2 does not ship
        that hazard while D-3 is pending."""
        src = _send_src()
        assert "try:" in src and "except Exception" in src
        assert "generate_statement_document" in src.split("try:")[1].split("except")[0], (
            "the render call moved outside the try — a render failure can now "
            "abort the whole sweep"
        )

    def test_a_render_failure_skips_the_send(self):
        """A statement email carrying no statement is worse than no email, so a
        render failure must NOT fall through to a body-only send."""
        src = _send_src()
        after_except = src.split("except Exception")[1]
        assert "continue" in after_except.split("statement_month")[0], (
            "a render failure no longer skips the send"
        )

    def test_a_none_document_also_skips(self):
        """`generate_statement_document` RETURNS None (rather than raising) when
        the statement, customer or company row is missing — a different path
        from the exception, and equally must not send."""
        assert "document_id is None" in _send_src()


class TestTheCommitHazardIsStillOpen:
    """Records what D-2 deliberately did NOT fix, so D-3's scope stays legible
    and nobody reads the narrow guard as the whole answer."""

    def test_the_commit_is_still_outside_the_loop(self):
        """When this starts failing, D-3 has landed and this test should be
        replaced by D-3's own coverage — not deleted quietly."""
        src = _send_src()
        loop_body = src.split("for stmt in stmts:")[1]
        tail = loop_body.split("# Update run")[-1]
        assert "db.commit()" in tail, (
            "the commit moved — if D-3 landed, replace this test with D-3's "
            "per-item commit coverage rather than removing it"
        )
