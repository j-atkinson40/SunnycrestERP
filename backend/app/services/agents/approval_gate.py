"""Approval gate service — handles accountant review workflow for agent jobs.

Manages the approve/reject lifecycle, sends review emails with HTML reports,
and coordinates period locking on approval.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.agent import AgentJob
from app.models.user import User
from app.schemas.agent import ApprovalAction

logger = logging.getLogger(__name__)

# Job type → human-readable label
JOB_TYPE_LABELS = {
    "month_end_close": "Month-End Close",
    "ar_collections": "AR Collections Review",
    "unbilled_orders": "Unbilled Orders Audit",
    "cash_receipts_matching": "Cash Receipts Matching",
    "expense_categorization": "Expense Categorization",
    "estimated_tax_prep": "Estimated Tax Prep",
    "inventory_reconciliation": "Inventory Reconciliation",
    "budget_vs_actual": "Budget vs. Actual",
    "1099_prep": "1099 Prep",
    "year_end_close": "Year-End Close",
    "tax_package": "Tax Package",
    "annual_budget": "Annual Budget",
}

# Approval token validity
TOKEN_EXPIRY_HOURS = 72


class ApprovalGateService:
    """Manages the approval workflow for accounting agent jobs."""

    @staticmethod
    def send_review_email(
        job: AgentJob,
        token: str,
        tenant_id: str,
        db: Session,
    ) -> None:
        """Send the accountant review email with approve/reject CTAs."""
        from app.models.company import Company
        from app.services.email_service import email_service

        company = db.query(Company).filter(Company.id == tenant_id).first()
        tenant_name = company.name if company else "Your Company"

        # Build email recipients — job triggerer + any schedule notify_emails
        recipients = []
        if job.triggered_by:
            user = db.query(User).filter(User.id == job.triggered_by).first()
            if user and user.email:
                recipients.append(user.email)

        # Also notify admins with accounting role
        admins = (
            db.query(User)
            .filter(User.company_id == tenant_id, User.is_active == True)
            .all()
        )
        for admin in admins:
            if admin.email and admin.email not in recipients:
                if admin.role and admin.role.slug in ("admin", "accounting"):
                    recipients.append(admin.email)

        if not recipients:
            logger.warning("No recipients for approval email on job %s", job.id)
            return

        label = JOB_TYPE_LABELS.get(job.job_type, job.job_type)
        period_label = ""
        if job.period_start and job.period_end:
            period_label = f"{job.period_start:%B %Y}"

        subject = f"Agent Review: {label} — {period_label or 'Review Required'}"

        base_url = settings.FRONTEND_URL
        if settings.ENVIRONMENT == "production" and company and company.slug:
            base_url = f"https://{company.slug}.{settings.PLATFORM_DOMAIN}"

        approve_url = f"{base_url}/agents/{job.id}/review?action=approve&token={token}"
        reject_url = f"{base_url}/agents/{job.id}/review?action=reject&token={token}"
        review_url = f"{base_url}/agents/{job.id}/review"

        html = ApprovalGateService._build_review_email_html(
            job=job,
            label=label,
            period_label=period_label,
            tenant_name=tenant_name,
            approve_url=approve_url,
            reject_url=reject_url,
            review_url=review_url,
        )

        for recipient in recipients:
            email_service.send_email(
                to=recipient,
                subject=subject,
                html_body=html,
                from_name=f"Bridgeable ({tenant_name})",
            )

        logger.info(
            "Approval email sent for job %s to %d recipients",
            job.id, len(recipients),
        )

    @staticmethod
    def process_approval(
        token: str,
        action: ApprovalAction,
        db: Session,
    ) -> AgentJob:
        """Process an approve or reject action via token.

        Token is single-use and expires after 72 hours.
        """
        job = (
            db.query(AgentJob)
            .filter(AgentJob.approval_token == token)
            .first()
        )
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid or already-used approval token",
            )

        # Check expiry
        if job.created_at:
            created = job.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            expiry = created + timedelta(hours=TOKEN_EXPIRY_HOURS)
            if datetime.now(timezone.utc) > expiry:
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="Approval token has expired (72-hour limit)",
                )

        # Must be awaiting approval
        if job.status != "awaiting_approval":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Job is not awaiting approval (current status: {job.status})",
            )

        # Null out token (single-use)
        job.approval_token = None

        if action.action == "approve":
            return ApprovalGateService._process_approve(job, action, db)
        else:
            return ApprovalGateService._process_reject(job, action, db)

    # Job types that use simplified approval (no period lock, no statement run)
    SIMPLE_APPROVAL_TYPES = {
        "ar_collections",       # TODO Phase 3b: trigger email sends for approved collection drafts
        "unbilled_orders",      # TODO Phase 4b: on approval, optionally create draft invoices for HIGH urgency orders
        "cash_receipts_matching",
        "expense_categorization",
        "estimated_tax_prep",   # TODO Phase 7b: on approval, optionally create a VendorBill draft for the estimated tax payment amount so it appears in AP
    }

    @staticmethod
    def _process_approve(
        job: AgentJob, action: ApprovalAction, db: Session
    ) -> AgentJob:
        """Handle approval: lock period, mark complete.

        For month_end_close jobs, also triggers statement generation
        and auto-approves unflagged statement items.

        For weekly agents (ar_collections, unbilled_orders, cash_receipts_matching),
        uses simplified approval — no period lock, no statement run.
        """
        from app.services.agents.period_lock import PeriodAlreadyLockedError, PeriodLockService

        job.status = "approved"
        job.approved_at = datetime.now(timezone.utc)
        # approved_by will be set by the route if user is authenticated
        db.flush()

        # Simplified approval path for weekly agents
        if job.job_type in ApprovalGateService.SIMPLE_APPROVAL_TYPES:
            # Expense categorization: write high-confidence categories on approval
            if job.job_type == "expense_categorization" and not job.dry_run:
                ApprovalGateService._apply_expense_categories(job, db)

            job.status = "complete"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(job)
            logger.info("Job %s approved and completed (simple path)", job.id)
            return job

        # Month-end close: generate statement run on approval
        if job.job_type == "month_end_close" and not job.dry_run and job.period_start and job.period_end:
            ApprovalGateService._trigger_statement_run(job, db)

        # Lock the period (skip if dry_run)
        if not job.dry_run and job.period_start and job.period_end:
            try:
                label = JOB_TYPE_LABELS.get(job.job_type, job.job_type)
                PeriodLockService.lock_period(
                    db=db,
                    tenant_id=job.tenant_id,
                    period_start=job.period_start,
                    period_end=job.period_end,
                    agent_job_id=job.id,
                    locked_by=job.approved_by,
                    reason=f"{label} approved",
                )
            except PeriodAlreadyLockedError:
                logger.info("Period already locked for job %s — skipping", job.id)

        job.status = "complete"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)

        logger.info("Job %s approved and completed", job.id)
        return job

    @staticmethod
    def _trigger_statement_run(job: AgentJob, db: Session) -> None:
        """Generate statement run and auto-approve unflagged items on month-end close approval."""
        from app.models.agent_anomaly import AgentAnomaly
        from app.models.statement import CustomerStatement, StatementRun
        from app.services.statement_generation_service import (
            approve_item,
            generate_statement_run,
        )

        try:
            # Check for existing statement run conflict from step data
            steps = (job.report_payload or {}).get("steps", {})
            cs_data = steps.get("customer_statements", {})
            existing_run_id = cs_data.get("existing_statement_run_id")

            if existing_run_id:
                existing_run = db.query(StatementRun).filter(StatementRun.id == existing_run_id).first()
                if existing_run and existing_run.status not in ("draft", "failed"):
                    # Link to existing run instead of creating a new one
                    payload = dict(job.report_payload or {})
                    payload["statement_run_id"] = str(existing_run.id)
                    payload["statement_run_status"] = existing_run.status
                    payload["statement_run_note"] = "Linked to existing run (conflict detected)"
                    job.report_payload = payload
                    db.flush()
                    logger.info("Linked job %s to existing statement run %s", job.id, existing_run.id)
                    return

            # Generate statement run
            user_id = str(job.approved_by) if job.approved_by else str(job.triggered_by or "")
            statement_run = generate_statement_run(
                db=db,
                tenant_id=str(job.tenant_id),
                user_id=user_id,
                period_start=job.period_start,
                period_end=job.period_end,
            )

            # Auto-approve unflagged items — skip customers with unresolved CRITICAL anomalies
            critical_customer_ids = set()
            critical_anomalies = (
                db.query(AgentAnomaly)
                .filter(
                    AgentAnomaly.agent_job_id == job.id,
                    AgentAnomaly.severity == "critical",
                    AgentAnomaly.entity_type == "customer",
                    AgentAnomaly.resolved == False,
                )
                .all()
            )
            for a in critical_anomalies:
                if a.entity_id:
                    critical_customer_ids.add(a.entity_id)

            # Get all statement items for this run
            statement_items = (
                db.query(CustomerStatement)
                .filter(CustomerStatement.run_id == statement_run.id)
                .all()
            )

            auto_approved = 0
            for item in statement_items:
                if item.customer_id not in critical_customer_ids:
                    approve_item(
                        db=db,
                        item_id=item.id,
                        tenant_id=str(job.tenant_id),
                        user_id=user_id,
                        note="Auto-approved by month-end close agent",
                    )
                    auto_approved += 1

            # Store link in report_payload
            payload = dict(job.report_payload or {})
            payload["statement_run_id"] = str(statement_run.id)
            payload["statement_run_status"] = statement_run.status
            payload["statement_items_auto_approved"] = auto_approved
            payload["statement_items_total"] = len(statement_items)
            job.report_payload = payload
            db.flush()

            logger.info(
                "Statement run %s created for job %s. %d/%d items auto-approved.",
                statement_run.id, job.id, auto_approved, len(statement_items),
            )

        except Exception as e:
            logger.error("Failed to trigger statement run for job %s: %s", job.id, e)
            payload = dict(job.report_payload or {})
            payload["statement_run_error"] = str(e)
            job.report_payload = payload
            db.flush()

    @staticmethod
    def _apply_expense_categories(job: AgentJob, db: Session) -> None:
        """Write high-confidence expense categories to VendorBillLines on approval.

        Only updates lines classified with confidence >= 0.85 that also have
        a valid GL mapping. NEEDS_REVIEW lines are NOT written.
        TODO Phase 6b: add per-line approval endpoint so reviewer can
        confirm/override individual categorizations before posting.
        """
        from app.models.vendor_bill_line import VendorBillLine

        payload = job.report_payload or {}
        steps = payload.get("steps", {})
        gl_data = steps.get("map_to_gl_accounts", {})
        mappings = gl_data.get("mappings", [])

        updated = 0
        for m in mappings:
            if m.get("mapping_status") == "mapped":
                line = db.query(VendorBillLine).filter(VendorBillLine.id == m["line_id"]).first()
                if line:
                    line.expense_category = m["proposed_category"]
                    updated += 1

        if updated:
            db.flush()
            logger.info(
                "Expense categorization job %s: updated %d vendor bill lines",
                job.id, updated,
            )

    @staticmethod
    def _process_reject(
        job: AgentJob, action: ApprovalAction, db: Session
    ) -> AgentJob:
        """Handle rejection: record reason, do NOT lock period."""
        job.status = "rejected"
        job.rejection_reason = action.rejection_reason or "No reason provided"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)

        logger.info("Job %s rejected: %s", job.id, job.rejection_reason)
        return job

    @staticmethod
    def generate_review_html(job: AgentJob) -> str:
        """Generate the full HTML review report from job.report_payload.

        Used in both the email and the platform review page.
        """
        payload = job.report_payload or {}
        label = JOB_TYPE_LABELS.get(job.job_type, job.job_type)
        period_label = ""
        if job.period_start:
            period_label = f"{job.period_start:%B %d, %Y} – {job.period_end:%B %d, %Y}" if job.period_end else str(job.period_start)

        anomalies = payload.get("anomalies", [])
        steps = payload.get("steps", {})

        # Build anomaly rows
        anomaly_html = ""
        if anomalies:
            for a in anomalies:
                sev = a.get("severity", "info")
                badge_color = {"critical": "#dc2626", "warning": "#d97706", "info": "#2563eb"}.get(sev, "#6b7280")
                raw_amount = a.get("amount")
                amount_str = f"${float(raw_amount):,.2f}" if raw_amount is not None else ""
                anomaly_html += f"""
                <tr>
                    <td><span style="background:{badge_color};color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;">{sev}</span></td>
                    <td>{a.get('anomaly_type', '')}</td>
                    <td>{a.get('description', '')}</td>
                    <td style="text-align:right;">{amount_str}</td>
                </tr>"""
        else:
            anomaly_html = '<tr><td colspan="4" style="text-align:center;color:#16a34a;padding:16px;">No anomalies found</td></tr>'

        # Build step summary
        step_html = ""
        for name, data in steps.items():
            step_html += f"<li><strong>{name}</strong>: {data if isinstance(data, str) else 'completed'}</li>"

        # Build run log
        run_log_html = ""
        for entry in (job.run_log or []):
            status_color = "#16a34a" if entry.get("status") == "complete" else "#dc2626"
            duration = f"{entry.get('duration_ms', 0)}ms" if entry.get("duration_ms") else ""
            run_log_html += f"""
            <tr>
                <td>{entry.get('step_number', '')}</td>
                <td>{entry.get('step_name', '')}</td>
                <td style="color:{status_color};">{entry.get('status', '')}</td>
                <td>{duration}</td>
                <td>{entry.get('message', '')}</td>
            </tr>"""

        dry_run_badge = '<span style="background:#f59e0b;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;margin-left:8px;">DRY RUN</span>' if job.dry_run else ""

        return f"""
        <!DOCTYPE html>
        <html>
        <head><style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #18181b; margin: 0; padding: 24px; background: #f4f4f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background: #fff; border-radius: 8px; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,.1); }}
            h1 {{ font-size: 22px; margin: 0 0 4px; }}
            .meta {{ color: #71717a; font-size: 14px; margin-bottom: 24px; }}
            .cards {{ display: flex; gap: 12px; margin-bottom: 24px; }}
            .card {{ flex: 1; background: #f4f4f5; border-radius: 6px; padding: 16px; text-align: center; }}
            .card-value {{ font-size: 24px; font-weight: 700; }}
            .card-label {{ font-size: 12px; color: #71717a; margin-top: 4px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
            th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #e4e4e7; font-size: 14px; }}
            th {{ background: #f4f4f5; font-weight: 600; }}
            h2 {{ font-size: 16px; margin: 24px 0 8px; }}
        </style></head>
        <body>
        <div class="container">
            <h1>{label}{dry_run_badge}</h1>
            <div class="meta">{period_label} &middot; Generated {payload.get('generated_at', '')}</div>

            <div class="cards">
                <div class="card">
                    <div class="card-value">{job.anomaly_count}</div>
                    <div class="card-label">Anomalies</div>
                </div>
                <div class="card">
                    <div class="card-value">{len(steps)}</div>
                    <div class="card-label">Steps Completed</div>
                </div>
            </div>

            <h2>Anomalies</h2>
            <table>
                <thead><tr><th>Severity</th><th>Type</th><th>Description</th><th style="text-align:right;">Amount</th></tr></thead>
                <tbody>{anomaly_html}</tbody>
            </table>

            <h2>Steps</h2>
            <ul>{step_html or '<li>No step data available</li>'}</ul>

            <h2>Run Log</h2>
            <table>
                <thead><tr><th>#</th><th>Step</th><th>Status</th><th>Duration</th><th>Message</th></tr></thead>
                <tbody>{run_log_html or '<tr><td colspan="5">No log entries</td></tr>'}</tbody>
            </table>
        </div>
        </body>
        </html>
        """

    @staticmethod
    def _build_review_email_html(
        job: AgentJob,
        label: str,
        period_label: str,
        tenant_name: str,
        approve_url: str,
        reject_url: str,
        review_url: str,
    ) -> str:
        """Build the HTML email body for the approval review."""
        anomaly_count = job.anomaly_count
        critical_count = sum(
            1 for a in (job.report_payload or {}).get("anomalies", [])
            if a.get("severity") == "critical"
        )

        anomaly_summary = ""
        if anomaly_count > 0:
            anomaly_summary = f"""
            <div style="background:#fef3c7;border-radius:6px;padding:16px;margin:16px 0;">
                <p style="margin:0;font-weight:600;color:#92400e;">
                    {anomaly_count} anomal{'y' if anomaly_count == 1 else 'ies'} found
                    {f'({critical_count} critical)' if critical_count else ''}
                </p>
            </div>"""
        else:
            anomaly_summary = """
            <div style="background:#dcfce7;border-radius:6px;padding:16px;margin:16px 0;">
                <p style="margin:0;font-weight:600;color:#166534;">No anomalies found</p>
            </div>"""

        dry_run_note = ""
        if job.dry_run:
            dry_run_note = """
            <div style="background:#fef9c3;border:1px solid #fde68a;border-radius:6px;padding:12px;margin:16px 0;">
                <p style="margin:0;font-size:13px;color:#854d0e;">
                    <strong>Dry Run:</strong> No changes were committed. This is a read-only preview.
                </p>
            </div>"""

        return f"""
        <!DOCTYPE html>
        <html>
        <head><style>
            body {{ margin:0; padding:0; background:#f4f4f5; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }}
            .wrapper {{ max-width:600px; margin:32px auto; background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,.1); }}
            .header {{ background:#09090b; padding:24px 32px; }}
            .header-title {{ color:#fff; font-size:18px; font-weight:600; margin:0; }}
            .header-sub {{ color:#a1a1aa; font-size:13px; margin:4px 0 0; }}
            .body {{ padding:32px; }}
            .body p {{ margin:0 0 16px; line-height:1.6; font-size:15px; color:#3f3f46; }}
            .btn {{ display:inline-block; padding:14px 32px; border-radius:6px; font-size:15px; font-weight:600; text-decoration:none; margin-right:12px; }}
            .btn-approve {{ background:#16a34a; color:#fff !important; }}
            .btn-reject {{ background:#fff; color:#dc2626 !important; border:2px solid #dc2626; }}
            .footer {{ border-top:1px solid #e4e4e7; padding:20px 32px; background:#fafafa; }}
            .footer p {{ margin:0; font-size:12px; color:#71717a; }}
        </style></head>
        <body>
        <div class="wrapper">
            <div class="header">
                <p class="header-title">Bridgeable</p>
                <p class="header-sub">Agent Review Required — {tenant_name}</p>
            </div>
            <div class="body">
                <p><strong>{label}</strong> for <strong>{period_label}</strong> has completed and requires your review.</p>
                {dry_run_note}
                {anomaly_summary}
                <p style="margin:24px 0;">
                    <a href="{approve_url}" class="btn btn-approve">Approve &amp; Lock Period</a>
                    <a href="{reject_url}" class="btn btn-reject">Reject</a>
                </p>
                <p style="font-size:13px;color:#71717a;">
                    <a href="{review_url}" style="color:#2563eb;">View full report in Bridgeable</a>
                </p>
            </div>
            <div class="footer">
                <p>This approval link expires in 72 hours. If you did not expect this email, contact {tenant_name}.</p>
            </div>
        </div>
        </body>
        </html>
        """
