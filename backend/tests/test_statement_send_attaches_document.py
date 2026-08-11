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


def _code_only(src: str) -> str:
    """Source with `#` comments stripped — see the note in
    `test_statement_dispatch_durability.py`. Matching against source text also
    matches the comments explaining that text, which is how the split point
    below landed inside a comment mentioning `send_statement_email` rather than
    on the call itself."""
    return "\n".join(line.split("#")[0] for line in src.splitlines())


def _send_src() -> str:
    return _code_only(inspect.getsource(statement_service.send_all_digital))


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


class TestTheRenderFailurePathSurvives:
    """⚠️ D-2's two guard-shape tests LIVED HERE AND WERE REPLACED, not deleted.

    They pinned D-2's narrow structure — a render-only `try` with a `continue`
    on failure — which existed solely so D-2 did not ship the abort hazard while
    D-3 was pending. D-3 widened the `try` to span the whole item and routes
    failures through `_record_hard`, so both assertions became false BY DESIGN.

    Durability, classification and the terminal raise are now covered by
    `test_statement_dispatch_durability.py`. What stays here is the one property
    that belongs to D-2's subject: a render failure must never fall through to a
    body-only send, because a statement email carrying no statement is worse
    than no email.

    (One prediction was wrong and is worth recording: D-2 asserted the trailing
    `db.commit()` would move when D-3 landed. It did not — that commit writes
    the RUN row and correctly stays after the loop. D-3 added per-item commits
    beside it rather than relocating it.)
    """

    def test_a_missing_document_never_reaches_the_send(self):
        src = _send_src()
        before_send = src.split("send_statement_email")[0]
        assert "document_id is None" in before_send
        assert "raise RuntimeError" in before_send, (
            "the missing-document case no longer stops the item — a body-only "
            "statement email could now go out"
        )
