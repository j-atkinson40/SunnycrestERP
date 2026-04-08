"""AR Collections Agent — Phase 3.

Weekly agent that reviews outstanding AR, classifies customers into
collection tiers, drafts collection emails via Claude, and generates
a report for human review before anything is sent.

Steps:
  1. build_ar_snapshot — age all open invoices per customer
  2. classify_customers — tier assignment + anomalies
  3. draft_communications — Claude-generated collection emails
  4. generate_report — executive summary + HTML report
"""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import ClassVar

import anthropic

from sqlalchemy.orm import Session

from app.config import settings
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.schemas.agent import (
    AgentJobType,
    AnomalyItem,
    AnomalySeverity,
    StepResult,
)
from app.services.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# Collection tier thresholds (days past due)
TIER_CURRENT_MAX = 30
TIER_FOLLOW_UP_MAX = 60
TIER_ESCALATE_MAX = 90

FALLBACK_TEMPLATE = (
    "Dear [Contact Name],\n\n"
    "This is a reminder that your account has an outstanding balance "
    "of ${amount}. Please remit payment at your earliest convenience "
    "or contact us to discuss your account.\n\n"
    "[FALLBACK — review before sending]\n\n"
    "Sincerely,\n"
    "Accounts Receivable Team, Sunnycrest Vault"
)


class ARCollectionsAgent(BaseAgent):
    """Weekly AR collections review and draft communication agent."""

    JOB_TYPE = AgentJobType.AR_COLLECTIONS

    STEPS: ClassVar[list[str]] = [
        "build_ar_snapshot",
        "classify_customers",
        "draft_communications",
        "generate_report",
    ]

    def run_step(self, step_name: str) -> StepResult:
        handler = getattr(self, f"_step_{step_name}", None)
        if not handler:
            raise ValueError(f"Unknown step: {step_name}")
        return handler()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_anomaly(
        self,
        severity: AnomalySeverity,
        anomaly_type: str,
        description: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
        amount: Decimal | None = None,
    ) -> AnomalyItem:
        return AnomalyItem(
            severity=severity,
            anomaly_type=anomaly_type,
            description=description,
            entity_type=entity_type,
            entity_id=entity_id,
            amount=amount,
        )

    # ------------------------------------------------------------------
    # STEP 1 — build_ar_snapshot
    # ------------------------------------------------------------------

    def _step_build_ar_snapshot(self) -> StepResult:
        today = date.today()

        open_invoices = (
            self.db.query(Invoice)
            .filter(
                Invoice.company_id == self.tenant_id,
                Invoice.status.notin_(["paid", "void", "write_off"]),
            )
            .all()
        )

        # Build per-customer summaries
        customer_map: dict[str, dict] = {}

        for inv in open_invoices:
            cid = inv.customer_id
            if cid not in customer_map:
                customer = (
                    self.db.query(Customer)
                    .filter(Customer.id == cid)
                    .first()
                )
                customer_map[cid] = {
                    "customer_id": cid,
                    "customer_name": customer.name if customer else "Unknown",
                    "total_outstanding": Decimal(0),
                    "invoice_count": 0,
                    "oldest_invoice_date": None,
                    "oldest_days_outstanding": 0,
                    "invoices": [],
                }

            balance_due = Decimal(str(inv.total or 0)) - Decimal(str(inv.amount_paid or 0))
            if balance_due <= 0:
                continue

            due_ref = inv.due_date or inv.invoice_date
            if due_ref:
                due_date_only = due_ref.date() if hasattr(due_ref, "date") else due_ref
                days_out = (today - due_date_only).days
            else:
                days_out = 0
                due_date_only = None

            inv_date = inv.invoice_date.date() if inv.invoice_date and hasattr(inv.invoice_date, "date") else inv.invoice_date

            entry = customer_map[cid]
            entry["total_outstanding"] += balance_due
            entry["invoice_count"] += 1
            entry["invoices"].append({
                "invoice_id": inv.id,
                "invoice_number": inv.number,
                "invoice_date": str(inv_date) if inv_date else None,
                "due_date": str(due_date_only) if due_date_only else None,
                "amount": float(Decimal(str(inv.total or 0))),
                "balance_due": float(balance_due),
                "days_outstanding": max(days_out, 0),
                "status": inv.status,
            })

            if entry["oldest_invoice_date"] is None or (inv_date and inv_date < entry["oldest_invoice_date"]):
                entry["oldest_invoice_date"] = inv_date

            if days_out > entry["oldest_days_outstanding"]:
                entry["oldest_days_outstanding"] = max(days_out, 0)

        # Convert to list and compute totals
        customers = []
        total_ar = Decimal(0)
        total_invoice_count = 0

        for cid, data in customer_map.items():
            if data["total_outstanding"] <= 0:
                continue
            data["total_outstanding"] = float(data["total_outstanding"])
            if data["oldest_invoice_date"]:
                data["oldest_invoice_date"] = str(data["oldest_invoice_date"])
            customers.append(data)
            total_ar += Decimal(str(data["total_outstanding"]))
            total_invoice_count += data["invoice_count"]

        result_data = {
            "snapshot_date": today.isoformat(),
            "total_ar": float(total_ar),
            "customer_count": len(customers),
            "total_invoice_count": total_invoice_count,
            "customers": customers,
        }

        msg = (
            f"AR snapshot: ${float(total_ar):,.2f} outstanding "
            f"across {len(customers)} customers, "
            f"{total_invoice_count} open invoices."
        )

        return StepResult(message=msg, data=result_data, anomalies=[])

    # ------------------------------------------------------------------
    # STEP 2 — classify_customers
    # ------------------------------------------------------------------

    def _step_classify_customers(self) -> StepResult:
        snapshot = self.step_results.get("build_ar_snapshot", {})
        customers = snapshot.get("customers", [])
        anomalies: list[AnomalyItem] = []

        current_count = current_total = 0
        follow_up_count = follow_up_total = 0
        escalate_count = escalate_total = 0
        critical_count = critical_total = 0

        classified = []

        for cust in customers:
            oldest_days = cust.get("oldest_days_outstanding", 0)
            total_out = Decimal(str(cust["total_outstanding"]))
            cname = cust["customer_name"]
            cid = cust["customer_id"]

            if oldest_days <= TIER_CURRENT_MAX:
                tier = "CURRENT"
                current_count += 1
                current_total += float(total_out)
            elif oldest_days <= TIER_FOLLOW_UP_MAX:
                tier = "FOLLOW_UP"
                follow_up_count += 1
                follow_up_total += float(total_out)
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.INFO,
                    anomaly_type="collections_follow_up",
                    entity_type="customer",
                    entity_id=cid,
                    description=(
                        f"{cname} has ${float(total_out):,.2f} outstanding, "
                        f"oldest invoice {oldest_days} days past due."
                    ),
                    amount=total_out,
                ))
            elif oldest_days <= TIER_ESCALATE_MAX:
                tier = "ESCALATE"
                escalate_count += 1
                escalate_total += float(total_out)
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.WARNING,
                    anomaly_type="collections_escalate",
                    entity_type="customer",
                    entity_id=cid,
                    description=(
                        f"{cname} has ${float(total_out):,.2f} outstanding, "
                        f"oldest invoice {oldest_days} days past due."
                    ),
                    amount=total_out,
                ))
            else:
                tier = "CRITICAL"
                critical_count += 1
                critical_total += float(total_out)
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.CRITICAL,
                    anomaly_type="collections_critical",
                    entity_type="customer",
                    entity_id=cid,
                    description=(
                        f"{cname} has ${float(total_out):,.2f} outstanding, "
                        f"oldest invoice {oldest_days} days past due."
                    ),
                    amount=total_out,
                ))

            classified.append({
                "customer_id": cid,
                "customer_name": cname,
                "tier": tier,
                "total_outstanding": float(total_out),
                "oldest_days": oldest_days,
                "invoice_count": cust["invoice_count"],
            })

        action_count = follow_up_count + escalate_count + critical_count
        action_total = follow_up_total + escalate_total + critical_total

        data = {
            "current_count": current_count,
            "current_total": current_total,
            "follow_up_count": follow_up_count,
            "follow_up_total": follow_up_total,
            "escalate_count": escalate_count,
            "escalate_total": escalate_total,
            "critical_count": critical_count,
            "critical_total": critical_total,
            "action_required_count": action_count,
            "action_required_total": action_total,
            "classified_customers": classified,
        }

        msg = (
            f"{action_count} customers need collection action: "
            f"{critical_count} critical, {escalate_count} escalate, "
            f"{follow_up_count} follow-up. "
            f"Total at risk: ${action_total:,.2f}."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 3 — draft_communications
    # ------------------------------------------------------------------

    def _step_draft_communications(self) -> StepResult:
        classify_data = self.step_results.get("classify_customers", {})
        snapshot_data = self.step_results.get("build_ar_snapshot", {})
        classified = classify_data.get("classified_customers", [])

        # Build customer_id → invoices lookup
        invoice_lookup: dict[str, list[dict]] = {}
        for cust in snapshot_data.get("customers", []):
            invoice_lookup[cust["customer_id"]] = cust.get("invoices", [])

        drafts = []
        drafts_generated = 0
        drafts_failed = 0

        for cust in classified:
            if cust["tier"] == "CURRENT":
                continue

            customer_invoices = invoice_lookup.get(cust["customer_id"], [])
            invoice_lines = "\n".join(
                f"  - Invoice #{inv['invoice_number']}: "
                f"${inv['balance_due']:,.2f} due {inv.get('due_date', 'N/A')} "
                f"({inv['days_outstanding']} days past due)"
                for inv in customer_invoices
            )

            subject = (
                f"Outstanding Balance — {cust['customer_name']} "
                f"— {cust['invoice_count']} Invoice(s)"
            )

            body = self._generate_draft_email(
                customer_name=cust["customer_name"],
                total_outstanding=cust["total_outstanding"],
                invoice_count=cust["invoice_count"],
                oldest_days=cust["oldest_days"],
                tier=cust["tier"],
                invoice_lines=invoice_lines,
            )

            if body is None:
                # Fallback template
                body = FALLBACK_TEMPLATE.replace(
                    "${amount}", f"{cust['total_outstanding']:,.2f}"
                )
                drafts_failed += 1
            else:
                drafts_generated += 1

            drafts.append({
                "customer_id": cust["customer_id"],
                "customer_name": cust["customer_name"],
                "tier": cust["tier"],
                "total_outstanding": cust["total_outstanding"],
                "subject": subject,
                "body": body,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            })

        total_generated = drafts_generated + drafts_failed

        data = {
            "drafts_generated": drafts_generated,
            "drafts_failed": drafts_failed,
            "communications": drafts,
        }

        msg = (
            f"{total_generated} collection email drafts generated. "
            f"{drafts_failed} fallback templates used. "
            f"Review before sending."
        )

        return StepResult(message=msg, data=data, anomalies=[])

    def _generate_draft_email(
        self,
        customer_name: str,
        total_outstanding: float,
        invoice_count: int,
        oldest_days: int,
        tier: str,
        invoice_lines: str,
    ) -> str | None:
        """Call Claude to draft a collection email. Returns None on failure."""
        if not settings.ANTHROPIC_API_KEY:
            logger.warning("No ANTHROPIC_API_KEY — using fallback template")
            return None

        system_prompt = (
            "You are a professional accounts receivable specialist for a "
            "burial vault manufacturer. Draft a collection email that is firm "
            "but respectful. The funeral home industry is relationship-driven "
            "— tone must preserve the business relationship while clearly "
            "communicating urgency. Never be aggressive or threatening. "
            "Sign as 'Accounts Receivable Team, Sunnycrest Vault'."
        )

        user_prompt = f"""Draft a collection email for:

Customer: {customer_name}
Total Outstanding: ${total_outstanding:,.2f}
Number of Open Invoices: {invoice_count}
Oldest Invoice: {oldest_days} days past due
Collection Tier: {tier}

Outstanding invoices:
{invoice_lines}

Tone guidance by tier:
FOLLOW_UP (31-60 days): Friendly reminder, assume oversight, offer to answer questions.
ESCALATE (61-90 days): Firm but professional, reference previous communications, request immediate attention, provide payment options.
CRITICAL (90+ days): Urgent, clear consequences if unresolved, request immediate contact, but remain professional.

Return ONLY the email body (no subject line). Start with 'Dear [Contact Name],' as a placeholder — do not fill in a real name."""

        try:
            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=400,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return message.content[0].text
        except Exception as e:
            logger.warning("Claude API call failed for %s: %s", customer_name, e)
            return None

    # ------------------------------------------------------------------
    # STEP 4 — generate_report
    # ------------------------------------------------------------------

    def _step_generate_report(self) -> StepResult:
        snapshot_data = self.step_results.get("build_ar_snapshot", {})
        classify_data = self.step_results.get("classify_customers", {})
        draft_data = self.step_results.get("draft_communications", {})

        action_count = classify_data.get("action_required_count", 0)
        action_total = classify_data.get("action_required_total", 0)
        drafts_ready = len(draft_data.get("communications", []))

        critical = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.CRITICAL)
        warning = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.WARNING)
        info = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.INFO)

        executive_summary = {
            "snapshot_date": snapshot_data.get("snapshot_date"),
            "total_ar": snapshot_data.get("total_ar", 0),
            "action_required_count": action_count,
            "action_required_total": action_total,
            "critical_count": classify_data.get("critical_count", 0),
            "critical_total": classify_data.get("critical_total", 0),
            "escalate_count": classify_data.get("escalate_count", 0),
            "follow_up_count": classify_data.get("follow_up_count", 0),
            "drafts_ready": drafts_ready,
            "anomaly_count": self.job.anomaly_count,
            "critical_anomaly_count": critical,
            "warning_anomaly_count": warning,
            "info_anomaly_count": info,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": self.dry_run,
        }

        self.step_results["generate_report"] = {"report_generated": True}

        self.job.report_payload = {
            "job_type": self.job.job_type,
            "period_start": str(self.job.period_start) if self.job.period_start else None,
            "period_end": str(self.job.period_end) if self.job.period_end else None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": self.dry_run,
            "anomaly_count": self.job.anomaly_count,
            "executive_summary": executive_summary,
            "steps": {k: v for k, v in self.step_results.items()},
            "anomalies": [a.model_dump(mode="json") for a in self.anomalies],
        }

        # Generate HTML
        self.job.report_payload["report_html"] = self._build_report_html(
            executive_summary, classify_data, draft_data,
        )
        self.db.commit()

        msg = (
            f"Collections report ready. {action_count} customers, "
            f"{drafts_ready} draft emails awaiting your review."
        )

        return StepResult(message=msg, data={"report_generated": True}, anomalies=[])

    def _build_report_html(
        self,
        summary: dict,
        classify_data: dict,
        draft_data: dict,
    ) -> str:
        total_ar = summary.get("total_ar", 0)
        action_count = summary.get("action_required_count", 0)
        critical_count = summary.get("critical_count", 0)
        drafts_ready = summary.get("drafts_ready", 0)

        dry_run_badge = (
            '<span style="background:#f59e0b;color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:12px;margin-left:8px;">DRY RUN</span>'
            if self.dry_run else ""
        )

        # Tier breakdown table
        tiers = [
            ("CURRENT", classify_data.get("current_count", 0), classify_data.get("current_total", 0)),
            ("FOLLOW_UP", classify_data.get("follow_up_count", 0), classify_data.get("follow_up_total", 0)),
            ("ESCALATE", classify_data.get("escalate_count", 0), classify_data.get("escalate_total", 0)),
            ("CRITICAL", classify_data.get("critical_count", 0), classify_data.get("critical_total", 0)),
        ]
        tier_colors = {"CURRENT": "#16a34a", "FOLLOW_UP": "#2563eb", "ESCALATE": "#d97706", "CRITICAL": "#dc2626"}

        tier_rows = ""
        for tier_name, count, total in tiers:
            color = tier_colors[tier_name]
            tier_rows += (
                f'<tr><td><span style="background:{color};color:#fff;padding:2px 8px;'
                f'border-radius:4px;font-size:12px;">{tier_name}</span></td>'
                f'<td>{count}</td><td style="text-align:right;">${total:,.2f}</td></tr>'
            )

        # Draft sections
        drafts_html = ""
        for draft in draft_data.get("communications", []):
            tier = draft.get("tier", "")
            color = tier_colors.get(tier, "#6b7280")
            body_escaped = draft.get("body", "").replace("\n", "<br>")
            drafts_html += f"""
            <div style="border:1px solid #e4e4e7;border-radius:6px;padding:16px;margin:12px 0;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <strong>{draft.get('customer_name', '')}</strong>
                    <span style="background:{color};color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;">{tier}</span>
                </div>
                <div style="font-size:13px;color:#71717a;margin-bottom:8px;">
                    Outstanding: ${draft.get('total_outstanding', 0):,.2f}
                </div>
                <div style="background:#f9fafb;border-radius:4px;padding:12px;font-size:14px;line-height:1.6;">
                    {body_escaped}
                </div>
                <div style="margin-top:8px;font-size:12px;color:#a1a1aa;">
                    Email sending is not yet enabled — drafts are for review only.
                </div>
            </div>"""

        period_label = ""
        if self.job.period_start:
            period_label = (
                f"{self.job.period_start:%B %d, %Y} – {self.job.period_end:%B %d, %Y}"
                if self.job.period_end else str(self.job.period_start)
            )

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
            <h1>AR Collections Review{dry_run_badge}</h1>
            <div class="meta">{period_label} &middot; Generated {summary.get('generated_at', '')}</div>

            <div class="cards">
                <div class="card">
                    <div class="card-value">${total_ar:,.0f}</div>
                    <div class="card-label">Total AR</div>
                </div>
                <div class="card">
                    <div class="card-value">{action_count}</div>
                    <div class="card-label">Action Required</div>
                </div>
                <div class="card">
                    <div class="card-value">{critical_count}</div>
                    <div class="card-label">Critical</div>
                </div>
                <div class="card">
                    <div class="card-value">{drafts_ready}</div>
                    <div class="card-label">Drafts Ready</div>
                </div>
            </div>

            <h2>Tier Breakdown</h2>
            <table>
                <thead><tr><th>Tier</th><th>Customers</th><th style="text-align:right;">Total</th></tr></thead>
                <tbody>{tier_rows}</tbody>
            </table>

            <h2>Draft Communications</h2>
            {drafts_html or '<p style="color:#71717a;">No drafts generated — all customers are current.</p>'}
        </div>
        </body>
        </html>
        """

    # ------------------------------------------------------------------
    # Override _assemble_report — generate_report step handles it
    # ------------------------------------------------------------------

    def _assemble_report(self) -> None:
        pass
