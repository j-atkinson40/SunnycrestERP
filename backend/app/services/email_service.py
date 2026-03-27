"""Email delivery service via Resend.

Test mode: if RESEND_API_KEY is not set or equals "test", emails are logged
to the console rather than sent. This allows local development without
consuming API quota.
"""

import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------

_BASE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
  <style>
    body {{ margin: 0; padding: 0; background: #f4f4f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #18181b; }}
    .wrapper {{ max-width: 600px; margin: 32px auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.1); }}
    .header {{ background: #09090b; padding: 24px 32px; }}
    .header-title {{ color: #ffffff; font-size: 18px; font-weight: 600; margin: 0; letter-spacing: -0.3px; }}
    .header-sub {{ color: #a1a1aa; font-size: 13px; margin: 4px 0 0; }}
    .body {{ padding: 32px; }}
    .body p {{ margin: 0 0 16px; line-height: 1.6; font-size: 15px; color: #3f3f46; }}
    .body p:last-child {{ margin-bottom: 0; }}
    .cta {{ display: inline-block; margin: 24px 0; padding: 12px 24px; background: #09090b; color: #ffffff !important; text-decoration: none; border-radius: 6px; font-size: 14px; font-weight: 500; }}
    .footer {{ border-top: 1px solid #e4e4e7; padding: 20px 32px; background: #fafafa; }}
    .footer p {{ margin: 0; font-size: 12px; color: #71717a; line-height: 1.5; }}
    .divider {{ height: 1px; background: #e4e4e7; margin: 24px 0; }}
    .highlight-box {{ background: #f4f4f5; border-radius: 6px; padding: 16px 20px; margin: 16px 0; }}
    .highlight-box p {{ color: #3f3f46; margin: 0; }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <p class="header-title">Bridgeable</p>
      <p class="header-sub">{header_sub}</p>
    </div>
    <div class="body">
      {body_content}
    </div>
    <div class="footer">
      <p>{footer_text}</p>
    </div>
  </div>
</body>
</html>
"""


def _wrap_html(subject: str, header_sub: str, body_content: str, footer_text: str) -> str:
    return _BASE_HTML.format(
        subject=subject,
        header_sub=header_sub,
        body_content=body_content,
        footer_text=footer_text,
    )


def _collections_html(
    customer_name: str,
    subject: str,
    body: str,
    tenant_name: str,
) -> str:
    paragraphs = "".join(f"<p>{line}</p>" for line in body.split("\n\n") if line.strip())
    body_content = f"""
      <p>Dear {customer_name},</p>
      {paragraphs}
      <div class="divider"></div>
      <p style="font-size:13px;color:#71717a;">
        This message was sent on behalf of <strong>{tenant_name}</strong>.
        Please reply directly to this email to reach their team.
      </p>
    """
    return _wrap_html(
        subject=subject,
        header_sub=f"Message from {tenant_name}",
        body_content=body_content,
        footer_text=f"You are receiving this because you have an outstanding account with {tenant_name}.",
    )


def _statement_html(
    customer_name: str,
    tenant_name: str,
    statement_month: str,
) -> str:
    body_content = f"""
      <p>Dear {customer_name},</p>
      <p>Your monthly account statement from <strong>{tenant_name}</strong> for <strong>{statement_month}</strong> is ready.</p>
      <div class="highlight-box">
        <p>Your statement is attached to this email as a PDF. Please review it at your earliest convenience.</p>
      </div>
      <p>If you have any questions about your account balance or charges, please contact {tenant_name} directly.</p>
    """
    return _wrap_html(
        subject=f"Your {statement_month} Statement — {tenant_name}",
        header_sub=f"Monthly Statement from {tenant_name}",
        body_content=body_content,
        footer_text=f"This statement was sent on behalf of {tenant_name} via Bridgeable. Contact {tenant_name} with any billing questions.",
    )


def _invitation_html(name: str, tenant_name: str, invite_url: str) -> str:
    body_content = f"""
      <p>Hi {name},</p>
      <p>You've been invited to join <strong>{tenant_name}</strong> on Bridgeable — the platform built for the Wilbert licensee network.</p>
      <p>Click the button below to accept your invitation and set up your account:</p>
      <a href="{invite_url}" class="cta">Accept Invitation</a>
      <p style="font-size:13px;color:#71717a;">This invitation link will expire in 7 days. If you did not expect this invitation, you can safely ignore this email.</p>
    """
    return _wrap_html(
        subject=f"You've been invited to {tenant_name} on Bridgeable",
        header_sub="Platform Invitation",
        body_content=body_content,
        footer_text="You are receiving this because someone at your organization invited you to Bridgeable.",
    )


def _accountant_invitation_html(
    tenant_name: str,
    migration_url: str,
    expires_days: int,
) -> str:
    body_content = f"""
      <p>Hi,</p>
      <p>Your client <strong>{tenant_name}</strong> is migrating their accounting data to Bridgeable and needs your help to get started.</p>
      <p>Please click the button below to access the secure data migration portal:</p>
      <a href="{migration_url}" class="cta">Open Data Migration Portal</a>
      <div class="highlight-box">
        <p>This link is unique to your client and will expire in <strong>{expires_days} days</strong>. You do not need to create an account — the link grants you direct access.</p>
      </div>
      <p>If you have any questions, please contact the Bridgeable support team at <a href="mailto:{settings.SUPPORT_EMAIL}">{settings.SUPPORT_EMAIL}</a>.</p>
    """
    return _wrap_html(
        subject=f"Accounting Data Migration — {tenant_name}",
        header_sub=f"Action Required: {tenant_name} Data Migration",
        body_content=body_content,
        footer_text=f"This invitation was generated on behalf of {tenant_name}. This link is confidential — do not share it.",
    )


def _alert_digest_html(tenant_name: str, alerts: list[dict]) -> str:
    items = ""
    for alert in alerts:
        title = alert.get("title", "")
        summary = alert.get("summary", alert.get("description", ""))
        items += f"""
        <div class="highlight-box" style="margin-bottom:12px;">
          <p style="font-weight:600;margin-bottom:4px;">{title}</p>
          <p style="font-size:14px;">{summary}</p>
        </div>
        """
    body_content = f"""
      <p>Here is your daily action summary for <strong>{tenant_name}</strong>. The following items require your attention:</p>
      {items}
      <p>Log in to Bridgeable to review and act on these items.</p>
    """
    count = len(alerts)
    return _wrap_html(
        subject=f"{count} item{'s' if count != 1 else ''} require your attention — {tenant_name}",
        header_sub=f"Daily Action Digest for {tenant_name}",
        body_content=body_content,
        footer_text="You are receiving this digest because you have active alerts in Bridgeable.",
    )


# ---------------------------------------------------------------------------
# EmailService
# ---------------------------------------------------------------------------

class EmailService:
    """Send transactional emails via Resend. Falls back to console logging
    when RESEND_API_KEY is not configured or equals 'test'."""

    def _is_test_mode(self) -> bool:
        key = getattr(settings, "RESEND_API_KEY", "")
        return not key or key == "test"

    def _from_address(self, from_name: str | None = None) -> str:
        name = from_name or getattr(settings, "FROM_NAME", "Bridgeable")
        addr = getattr(settings, "FROM_EMAIL", "noreply@getbridgeable.com")
        return f"{name} <{addr}>"

    def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        from_name: str | None = None,
        reply_to: str | None = None,
        attachments: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Send a single email. Never raises — returns success/failure dict."""
        if self._is_test_mode():
            logger.info("[EMAIL] To: %s | Subject: %s", to, subject)
            return {"success": True, "message_id": "test-mode"}

        try:
            import resend  # type: ignore

            resend.api_key = settings.RESEND_API_KEY

            params: dict[str, Any] = {
                "from": self._from_address(from_name),
                "to": [to],
                "subject": subject,
                "html": html_body,
            }
            if reply_to:
                params["reply_to"] = reply_to
            if attachments:
                params["attachments"] = attachments

            response = resend.Emails.send(params)
            return {"success": True, "message_id": response.get("id", "")}

        except Exception as exc:
            logger.error("Email delivery failed to %s: %s", to, exc)
            return {"success": False, "message_id": ""}

    def send_collections_email(
        self,
        customer_email: str,
        customer_name: str,
        subject: str,
        body: str,
        tenant_name: str,
        reply_to_email: str,
    ) -> dict[str, Any]:
        """Send a collections sequence email on behalf of a tenant."""
        html = _collections_html(customer_name, subject, body, tenant_name)
        return self.send_email(
            to=customer_email,
            subject=subject,
            html_body=html,
            from_name=f"{tenant_name} via Bridgeable",
            reply_to=reply_to_email,
        )

    def send_statement_email(
        self,
        customer_email: str,
        customer_name: str,
        tenant_name: str,
        statement_month: str,
        pdf_attachment: bytes | None = None,
    ) -> dict[str, Any]:
        """Send a monthly statement notification, with optional PDF attachment."""
        subject = f"Your {statement_month} Statement — {tenant_name}"
        html = _statement_html(customer_name, tenant_name, statement_month)

        attachments = None
        if pdf_attachment:
            import base64
            attachments = [{
                "filename": f"statement-{statement_month.lower().replace(' ', '-')}.pdf",
                "content": base64.b64encode(pdf_attachment).decode(),
            }]

        return self.send_email(
            to=customer_email,
            subject=subject,
            html_body=html,
            from_name=f"{tenant_name} via Bridgeable",
            attachments=attachments,
        )

    def send_user_invitation(
        self,
        email: str,
        name: str,
        tenant_name: str,
        invite_url: str,
    ) -> dict[str, Any]:
        """Send a new user platform invitation."""
        subject = f"You've been invited to {tenant_name} on Bridgeable"
        html = _invitation_html(name, tenant_name, invite_url)
        return self.send_email(
            to=email,
            subject=subject,
            html_body=html,
            reply_to=settings.SUPPORT_EMAIL,
        )

    def send_accountant_invitation(
        self,
        email: str,
        tenant_name: str,
        migration_url: str,
        expires_days: int = 7,
    ) -> dict[str, Any]:
        """Send an accountant data migration invitation."""
        subject = f"Accounting Data Migration — {tenant_name}"
        html = _accountant_invitation_html(tenant_name, migration_url, expires_days)
        return self.send_email(
            to=email,
            subject=subject,
            html_body=html,
            reply_to=settings.SUPPORT_EMAIL,
        )

    def send_agent_alert_digest(
        self,
        email: str,
        tenant_name: str,
        alerts: list[dict],
    ) -> dict[str, Any]:
        """Send a daily digest of action_required alerts. No-ops if list is empty."""
        if not alerts:
            return {"success": True, "message_id": "skipped-empty"}
        count = len(alerts)
        subject = f"{count} item{'s' if count != 1 else ''} require your attention — {tenant_name}"
        html = _alert_digest_html(tenant_name, alerts)
        return self.send_email(
            to=email,
            subject=subject,
            html_body=html,
        )


# Singleton instance
email_service = EmailService()
