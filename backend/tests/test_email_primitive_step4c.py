"""Phase W-4b Layer 1 Email Step 4c — HTML sandbox + operational-action tests.

Coverage:
  - HTML sanitization: dangerous content stripped (script/iframe/on*=/
    javascript:); allowed tags preserved; cid: protocol preserved;
    style attributes filtered to safelist; tracking pixel detected.
  - Iframe srcdoc: CSP meta tag present; image-blocking style applied;
    data-blocked="true" toggled when block_external_images=True.
  - Action shape: build_quote_approval_action emits canonical shape;
    get_action_at_index handles bounds.
  - Token issuance: 256-bit URL-safe; insert with TTL; idempotent
    re-lookup; consume marks; expired raises 410; consumed raises 409.
  - commit_action: approve → Quote.status=accepted; reject →
    Quote.status=rejected; request_changes → Quote.status unchanged
    (sent stays sent); request_changes without note → 400; double
    commit → 409; cross-tenant Quote → 404.
  - API: inline-action commit (Bridgeable user); magic-link GET (returns
    contextual surface); magic-link commit (consumes token); already-
    consumed magic-link GET returns consumed=True surface; expired
    magic-link → 410; cross-tenant message via inline → 404.
  - Inbox detail surfaces actions[] + body_html_sanitized.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from cryptography.fernet import Fernet


os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _make_ctx(role_slug: str = "admin"):
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"EM4c-{suffix}",
            slug=f"em4c-{suffix}",
            is_active=True,
            vertical="manufacturing",
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name=role_slug.title(),
            slug=role_slug,
            is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@em4c.co",
            first_name="EM4c",
            last_name="User",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "user_id": user.id,
            "company_id": co.id,
            "token": token,
            "slug": co.slug,
            "role_id": role.id,
        }
    finally:
        db.close()


@pytest.fixture
def ctx():
    return _make_ctx()


@pytest.fixture
def ctx_b():
    return _make_ctx()


@pytest.fixture
def auth(ctx):
    return {
        "Authorization": f"Bearer {ctx['token']}",
        "X-Company-Slug": ctx["slug"],
    }


def _seed_quote(tenant_id, *, status="sent", total="1500.00"):
    from app.database import SessionLocal
    from app.models.quote import Quote, QuoteLine

    db = SessionLocal()
    try:
        q = Quote(
            id=str(uuid.uuid4()),
            company_id=tenant_id,
            number=f"QTE-{uuid.uuid4().hex[:6]}",
            customer_name="Hopkins Funeral Home",
            status=status,
            quote_date=datetime.now(timezone.utc),
            expiry_date=datetime.now(timezone.utc) + timedelta(days=30),
            subtotal=Decimal(total),
            tax_rate=Decimal("0.0000"),
            tax_amount=Decimal("0.00"),
            total=Decimal(total),
        )
        db.add(q)
        db.flush()
        line = QuoteLine(
            id=str(uuid.uuid4()),
            quote_id=q.id,
            description="Standard burial vault",
            quantity=Decimal("1"),
            unit_price=Decimal(total),
            line_total=Decimal(total),
        )
        db.add(line)
        db.commit()
        # Re-fetch to attach lines relationship
        return q.id
    finally:
        db.close()


def _seed_message_with_action(tenant_id, quote_id, *, status="pending"):
    """Create an EmailThread + EmailMessage with quote_approval action."""
    from app.database import SessionLocal
    from app.models.email_primitive import (
        EmailAccount,
        EmailMessage,
        EmailThread,
    )
    from app.services.email.crypto import encrypt_credentials

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        acc = EmailAccount(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            account_type="shared",
            display_name="Test",
            email_address=f"acc-{suffix}@example.com",
            provider_type="gmail",
            provider_config={},
            encrypted_credentials=encrypt_credentials({}),
            outbound_enabled=True,
        )
        db.add(acc)
        db.flush()
        thread = EmailThread(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            account_id=acc.id,
            subject="Quote QTE-X",
            participants_summary=["fh@example.com", acc.email_address],
            first_message_at=datetime.now(timezone.utc),
            last_message_at=datetime.now(timezone.utc),
            message_count=1,
        )
        db.add(thread)
        db.flush()
        action = {
            "action_type": "quote_approval",
            "action_target_type": "quote",
            "action_target_id": quote_id,
            "action_metadata": {
                "quote_amount": "1500.00",
                "quote_number": "QTE-X",
            },
            "action_status": status,
            "action_completed_at": None,
            "action_completed_by": None,
            "action_completion_metadata": None,
        }
        msg = EmailMessage(
            id=str(uuid.uuid4()),
            thread_id=thread.id,
            tenant_id=tenant_id,
            account_id=acc.id,
            provider_message_id=f"pm-{suffix}",
            sender_email=acc.email_address,
            subject="Quote",
            body_html="<p>Please review.</p>",
            body_text="Please review.",
            sent_at=datetime.now(timezone.utc),
            received_at=datetime.now(timezone.utc),
            direction="outbound",
            message_payload={"actions": [action]},
        )
        db.add(msg)
        db.commit()
        return msg.id, thread.id, acc.id
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────
# 1. HTML sanitization
# ─────────────────────────────────────────────────────────────────────


class TestHtmlSanitization:
    def test_strips_script_tags(self):
        from app.services.email.html_sanitization import sanitize_email_html

        res = sanitize_email_html("<p>Hi</p><script>alert(1)</script>")
        assert "<script" not in res.cleaned_html
        assert res.dangerous_content_detected
        assert "script" in res.stripped_summary

    def test_strips_iframe_tags(self):
        from app.services.email.html_sanitization import sanitize_email_html

        res = sanitize_email_html("<p>Hi</p><iframe src='evil'></iframe>")
        assert "<iframe" not in res.cleaned_html

    def test_strips_event_handlers(self):
        from app.services.email.html_sanitization import sanitize_email_html

        res = sanitize_email_html('<p onclick="evil()">click</p>')
        assert "onclick" not in res.cleaned_html

    def test_strips_javascript_protocol(self):
        from app.services.email.html_sanitization import sanitize_email_html

        res = sanitize_email_html('<a href="javascript:alert(1)">x</a>')
        assert "javascript:" not in res.cleaned_html

    def test_preserves_allowed_tags(self):
        from app.services.email.html_sanitization import sanitize_email_html

        res = sanitize_email_html(
            "<p><strong>Bold</strong> <em>italic</em> <a href='https://x'>link</a></p>"
        )
        assert "<strong>" in res.cleaned_html
        assert "<em>" in res.cleaned_html
        assert "https://x" in res.cleaned_html

    def test_preserves_cid_protocol_for_inline_images(self):
        from app.services.email.html_sanitization import sanitize_email_html

        res = sanitize_email_html('<img src="cid:img1">')
        assert "cid:img1" in res.cleaned_html
        assert 'data-cid="true"' in res.cleaned_html

    def test_external_images_annotated(self):
        from app.services.email.html_sanitization import sanitize_email_html

        res = sanitize_email_html('<img src="https://x.com/i.png">')
        assert 'data-external="true"' in res.cleaned_html

    def test_tracking_pixel_detected(self):
        from app.services.email.html_sanitization import sanitize_email_html

        res = sanitize_email_html(
            '<img src="https://x/p.gif" width="1" height="1">'
        )
        assert 'data-tracking="true"' in res.cleaned_html

    def test_style_attribute_filters_to_safelist(self):
        from app.services.email.html_sanitization import sanitize_email_html

        # color is allowed; expression() (IE7-era) should be stripped
        res = sanitize_email_html(
            '<p style="color: red; expression(evil())">x</p>'
        )
        assert "color" in res.cleaned_html
        assert "expression" not in res.cleaned_html

    def test_empty_input_returns_empty(self):
        from app.services.email.html_sanitization import sanitize_email_html

        # None + empty string short-circuit to fully-empty result;
        # whitespace passes through (it's valid input, no content)
        for empty in (None, ""):
            res = sanitize_email_html(empty)
            assert res.cleaned_html == ""
            assert res.cleaned_length == 0


class TestSrcdoc:
    def test_csp_present(self):
        from app.services.email.html_sanitization import build_srcdoc

        srcdoc = build_srcdoc("<p>Hi</p>")
        assert "Content-Security-Policy" in srcdoc
        assert "default-src 'none'" in srcdoc

    def test_image_blocking_marks_external_images(self):
        from app.services.email.html_sanitization import (
            build_srcdoc,
            sanitize_email_html,
        )

        cleaned = sanitize_email_html('<img src="https://x.com/i.png">').cleaned_html
        srcdoc = build_srcdoc(cleaned, block_external_images=True)
        # The img tag in the body must carry the runtime data-blocked
        # attribute (not just the CSS selector that looks for it).
        # Body section starts after the closing </head>.
        body_section = srcdoc.split("</head>", 1)[1]
        assert 'data-blocked="true"' in body_section
        # Also the image-src CSP excludes http/https in block mode
        assert "img-src cid: data:;" in srcdoc

    def test_image_unblocking_skips_marker(self):
        from app.services.email.html_sanitization import (
            build_srcdoc,
            sanitize_email_html,
        )

        cleaned = sanitize_email_html('<img src="https://x.com/i.png">').cleaned_html
        srcdoc = build_srcdoc(cleaned, block_external_images=False)
        # Body must NOT carry runtime data-blocked attribute (CSS selector
        # in <style> still references it as a rule, that's fine)
        body_section = srcdoc.split("</head>", 1)[1]
        assert 'data-blocked="true"' not in body_section
        # CSP allows external image protocols
        assert "https:" in srcdoc


# ─────────────────────────────────────────────────────────────────────
# 2. Action shape + token issuance
# ─────────────────────────────────────────────────────────────────────


class TestActionShape:
    def test_build_quote_approval_canonical_shape(self, ctx):
        from app.database import SessionLocal
        from app.models.quote import Quote
        from app.services.email.email_action_service import (
            build_quote_approval_action,
        )

        qid = _seed_quote(ctx["company_id"], total="2750.00")
        db = SessionLocal()
        try:
            q = db.query(Quote).filter(Quote.id == qid).first()
            action = build_quote_approval_action(quote=q)
        finally:
            db.close()
        assert action["action_type"] == "quote_approval"
        assert action["action_target_type"] == "quote"
        assert action["action_target_id"] == qid
        assert action["action_status"] == "pending"
        assert action["action_completed_at"] is None
        assert action["action_metadata"]["quote_amount"] == "2750.00"
        assert action["action_metadata"]["customer_name"] == "Hopkins Funeral Home"

    def test_get_action_at_index_out_of_bounds(self, ctx):
        from app.services.email.email_action_service import (
            ActionNotFound,
            get_action_at_index,
        )

        class FakeMsg:
            id = "m1"
            message_payload = {"actions": [{"action_type": "quote_approval"}]}

        with pytest.raises(ActionNotFound):
            get_action_at_index(FakeMsg(), 99)


class TestTokenIssuance:
    def test_token_format_url_safe_256_bit(self):
        from app.services.email.email_action_service import (
            generate_action_token,
        )

        tok = generate_action_token()
        assert isinstance(tok, str)
        assert len(tok) >= 40  # 256 bits → 43 chars base64
        assert "/" not in tok
        assert "=" not in tok

    def test_lookup_token_increments_click_count(self, ctx):
        from app.database import SessionLocal
        from app.services.email.email_action_service import (
            issue_action_token,
            lookup_action_token,
        )

        qid = _seed_quote(ctx["company_id"])
        msg_id, _, _ = _seed_message_with_action(ctx["company_id"], qid)
        db = SessionLocal()
        try:
            tok = issue_action_token(
                db,
                tenant_id=ctx["company_id"],
                message_id=msg_id,
                action_idx=0,
                action_type="quote_approval",
                recipient_email="fh@example.com",
            )
            db.commit()
            row1 = lookup_action_token(db, token=tok)
            db.commit()
            row2 = lookup_action_token(db, token=tok)
            db.commit()
        finally:
            db.close()
        # Lookup returns the row pre-increment, then stamps the click.
        # First lookup sees 0 (then stamps 1); second sees 1 (stamps 2).
        assert row1["click_count"] == 0
        assert row2["click_count"] == 1

    def test_lookup_invalid_raises_401(self):
        from app.database import SessionLocal
        from app.services.email.email_action_service import (
            ActionTokenInvalid,
            lookup_action_token,
        )

        db = SessionLocal()
        try:
            with pytest.raises(ActionTokenInvalid):
                lookup_action_token(db, token="nonexistent")
        finally:
            db.close()

    def test_lookup_consumed_raises_409(self, ctx):
        from app.database import SessionLocal
        from app.services.email.email_action_service import (
            ActionTokenAlreadyConsumed,
            consume_action_token,
            issue_action_token,
            lookup_action_token,
        )

        qid = _seed_quote(ctx["company_id"])
        msg_id, _, _ = _seed_message_with_action(ctx["company_id"], qid)
        db = SessionLocal()
        try:
            tok = issue_action_token(
                db,
                tenant_id=ctx["company_id"],
                message_id=msg_id,
                action_idx=0,
                action_type="quote_approval",
                recipient_email="fh@example.com",
            )
            consume_action_token(db, token=tok)
            db.commit()
            with pytest.raises(ActionTokenAlreadyConsumed):
                lookup_action_token(db, token=tok)
        finally:
            db.close()

    def test_lookup_expired_raises_410(self, ctx):
        from sqlalchemy import text

        from app.database import SessionLocal
        from app.services.email.email_action_service import (
            ActionTokenExpired,
            issue_action_token,
            lookup_action_token,
        )

        qid = _seed_quote(ctx["company_id"])
        msg_id, _, _ = _seed_message_with_action(ctx["company_id"], qid)
        db = SessionLocal()
        try:
            tok = issue_action_token(
                db,
                tenant_id=ctx["company_id"],
                message_id=msg_id,
                action_idx=0,
                action_type="quote_approval",
                recipient_email="fh@example.com",
            )
            # Backdate expiry
            db.execute(
                text(
                    # Substrate consolidation r70: table renamed
                    # email_action_tokens → platform_action_tokens.
                    "UPDATE platform_action_tokens SET expires_at = :past "
                    "WHERE token = :t"
                ),
                {
                    "past": datetime.now(timezone.utc) - timedelta(days=1),
                    "t": tok,
                },
            )
            db.commit()
            with pytest.raises(ActionTokenExpired):
                lookup_action_token(db, token=tok)
        finally:
            db.close()


# ─────────────────────────────────────────────────────────────────────
# 3. commit_action — state propagation + Quote.status updates
# ─────────────────────────────────────────────────────────────────────


class TestCommitAction:
    def _commit_helper(self, ctx, *, outcome, completion_note=None, initial_quote_status="sent"):
        from app.database import SessionLocal
        from app.models.email_primitive import EmailMessage
        from app.models.quote import Quote
        from app.services.email.email_action_service import commit_action

        qid = _seed_quote(ctx["company_id"], status=initial_quote_status)
        msg_id, _, _ = _seed_message_with_action(ctx["company_id"], qid)

        db = SessionLocal()
        try:
            msg = db.query(EmailMessage).filter(EmailMessage.id == msg_id).first()
            updated = commit_action(
                db,
                message=msg,
                action_idx=0,
                outcome=outcome,
                actor_user_id=ctx["user_id"],
                actor_email=None,
                completion_note=completion_note,
                auth_method="bridgeable",
            )
            db.commit()
            q = db.query(Quote).filter(Quote.id == qid).first()
            return updated, q.status, msg_id
        finally:
            db.close()

    def test_approve_sets_quote_accepted(self, ctx):
        updated, qstatus, _ = self._commit_helper(ctx, outcome="approve")
        assert updated["action_status"] == "approved"
        assert qstatus == "accepted"

    def test_reject_sets_quote_rejected(self, ctx):
        updated, qstatus, _ = self._commit_helper(ctx, outcome="reject")
        assert updated["action_status"] == "rejected"
        assert qstatus == "rejected"

    def test_request_changes_keeps_quote_sent(self, ctx):
        updated, qstatus, _ = self._commit_helper(
            ctx, outcome="request_changes", completion_note="please reduce price"
        )
        assert updated["action_status"] == "changes_requested"
        assert qstatus == "sent"  # unchanged

    def test_request_changes_without_note_raises_400(self, ctx):
        from app.services.email.email_action_service import ActionError

        with pytest.raises(ActionError):
            self._commit_helper(ctx, outcome="request_changes")

    def test_double_commit_raises_409(self, ctx):
        from app.database import SessionLocal
        from app.models.email_primitive import EmailMessage
        from app.services.email.email_action_service import (
            ActionAlreadyCompleted,
            commit_action,
        )

        updated, _, msg_id = self._commit_helper(ctx, outcome="approve")
        db = SessionLocal()
        try:
            msg = db.query(EmailMessage).filter(EmailMessage.id == msg_id).first()
            with pytest.raises(ActionAlreadyCompleted):
                commit_action(
                    db,
                    message=msg,
                    action_idx=0,
                    outcome="reject",
                    actor_user_id=ctx["user_id"],
                    actor_email=None,
                    auth_method="bridgeable",
                )
        finally:
            db.close()

    def test_unknown_outcome_raises_400(self, ctx):
        from app.services.email.email_action_service import ActionError

        with pytest.raises(ActionError):
            self._commit_helper(ctx, outcome="banana")


# ─────────────────────────────────────────────────────────────────────
# 4. API surface — inline + magic-link
# ─────────────────────────────────────────────────────────────────────


class TestInlineActionAPI:
    def test_commit_inline_approve(self, client, ctx, auth):
        qid = _seed_quote(ctx["company_id"])
        msg_id, _, _ = _seed_message_with_action(ctx["company_id"], qid)

        resp = client.post(
            f"/api/v1/email/messages/{msg_id}/actions/0/commit",
            json={"outcome": "approve"},
            headers=auth,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["action_status"] == "approved"
        assert body["target_status"] == "accepted"

    def test_cross_tenant_message_returns_404(self, client, ctx, ctx_b):
        # Message belongs to ctx_b but request authenticated as ctx
        qid = _seed_quote(ctx_b["company_id"])
        msg_id, _, _ = _seed_message_with_action(ctx_b["company_id"], qid)

        auth_a = {
            "Authorization": f"Bearer {ctx['token']}",
            "X-Company-Slug": ctx["slug"],
        }
        resp = client.post(
            f"/api/v1/email/messages/{msg_id}/actions/0/commit",
            json={"outcome": "approve"},
            headers=auth_a,
        )
        assert resp.status_code == 404


class TestMagicLinkAPI:
    def _issue_token(self, ctx):
        from app.database import SessionLocal
        from app.services.email.email_action_service import issue_action_token

        qid = _seed_quote(ctx["company_id"])
        msg_id, _, _ = _seed_message_with_action(ctx["company_id"], qid)
        db = SessionLocal()
        try:
            tok = issue_action_token(
                db,
                tenant_id=ctx["company_id"],
                message_id=msg_id,
                action_idx=0,
                action_type="quote_approval",
                recipient_email="fh@example.com",
            )
            db.commit()
            return tok, qid, msg_id
        finally:
            db.close()

    def test_get_magic_link_returns_contextual_surface(self, client, ctx):
        tok, qid, _ = self._issue_token(ctx)
        # No auth headers — public route
        resp = client.get(f"/api/v1/email/actions/{tok}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["action_type"] == "quote_approval"
        assert body["action_target_id"] == qid
        assert body["recipient_email"] == "fh@example.com"
        assert body["consumed"] is False

    def test_get_magic_link_invalid_token(self, client):
        resp = client.get("/api/v1/email/actions/totally-bogus")
        assert resp.status_code == 401

    def test_commit_magic_link_approve_consumes_token(self, client, ctx):
        tok, qid, _ = self._issue_token(ctx)
        resp = client.post(
            f"/api/v1/email/actions/{tok}/commit",
            json={"outcome": "approve"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["action_status"] == "approved"
        assert body["target_status"] == "accepted"

        # Second click on the consumed token: GET should return consumed=True
        resp2 = client.get(f"/api/v1/email/actions/{tok}")
        assert resp2.status_code == 200
        assert resp2.json()["consumed"] is True
        assert resp2.json()["action_status"] == "approved"

        # Second commit attempt → 409
        resp3 = client.post(
            f"/api/v1/email/actions/{tok}/commit",
            json={"outcome": "approve"},
        )
        assert resp3.status_code == 409

    def test_commit_magic_link_request_changes_requires_note(self, client, ctx):
        tok, _, _ = self._issue_token(ctx)
        resp = client.post(
            f"/api/v1/email/actions/{tok}/commit",
            json={"outcome": "request_changes"},
        )
        assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────────────
# 5. Inbox detail surfaces actions[] + body_html_sanitized
# ─────────────────────────────────────────────────────────────────────


class TestThreadDetailIncludesActions:
    def test_message_detail_carries_action_metadata(self, client, ctx, auth):
        from app.database import SessionLocal
        from app.services.email import account_service

        qid = _seed_quote(ctx["company_id"])
        msg_id, thread_id, account_id = _seed_message_with_action(
            ctx["company_id"], qid
        )

        # Grant the user read access on the account so inbox queries surface
        db = SessionLocal()
        try:
            account_service.grant_access(
                db,
                account_id=account_id,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                access_level="admin",
                actor_user_id=ctx["user_id"],
            )
            db.commit()
        finally:
            db.close()

        resp = client.get(f"/api/v1/email/threads/{thread_id}", headers=auth)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        msgs = body["messages"]
        assert len(msgs) == 1
        assert len(msgs[0]["actions"]) == 1
        assert msgs[0]["actions"][0]["action_type"] == "quote_approval"
        # body_html_sanitized exists when body_html present
        assert msgs[0]["body_html_sanitized"] is not None
        assert "Content-Security-Policy" in msgs[0]["body_html_sanitized"]
