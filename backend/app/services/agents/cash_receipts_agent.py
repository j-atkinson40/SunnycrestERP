"""Cash Receipts Matching Agent — Phase 5.

Weekly agent that reviews incoming payments, attempts to auto-match
them to open invoices, and surfaces unmatched payments for manual
resolution.

Steps:
  1. collect_unmatched_payments — find payments without invoice applications
  2. attempt_auto_match — rule-based matching (exact amount, partial, etc.)
  3. flag_unresolvable — escalate stale unmatched payments
  4. generate_report — executive summary + HTML report
"""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from itertools import combinations
from typing import ClassVar

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.customer_payment import CustomerPayment, CustomerPaymentApplication
from app.models.invoice import Invoice
from app.schemas.agent import (
    AgentJobType,
    AnomalyItem,
    AnomalySeverity,
    StepResult,
)
from app.services.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class CashReceiptsAgent(BaseAgent):
    """Weekly cash receipts matching and reconciliation agent."""

    JOB_TYPE = AgentJobType.CASH_RECEIPTS_MATCHING

    STEPS: ClassVar[list[str]] = [
        "collect_unmatched_payments",
        "attempt_auto_match",
        "flag_unresolvable",
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
    # STEP 1 — collect_unmatched_payments
    # ------------------------------------------------------------------

    def _step_collect_unmatched_payments(self) -> StepResult:
        today = date.today()

        # All non-deleted payments for this tenant
        all_payments = (
            self.db.query(CustomerPayment)
            .filter(
                CustomerPayment.company_id == self.tenant_id,
                CustomerPayment.deleted_at.is_(None),
            )
            .all()
        )

        unmatched = []
        for p in all_payments:
            # Check if this payment has any applications
            app_count = (
                self.db.query(CustomerPaymentApplication)
                .filter(CustomerPaymentApplication.payment_id == p.id)
                .count()
            )
            if app_count > 0:
                continue

            customer = (
                self.db.query(Customer)
                .filter(Customer.id == p.customer_id)
                .first()
            )
            customer_name = customer.name if customer else "Unknown"

            pay_date = p.payment_date.date() if hasattr(p.payment_date, "date") else p.payment_date
            days_since = (today - pay_date).days if pay_date else 0

            unmatched.append({
                "payment_id": p.id,
                "customer_id": p.customer_id,
                "customer_name": customer_name,
                "payment_date": str(pay_date) if pay_date else None,
                "amount": float(Decimal(str(p.total_amount or 0))),
                "payment_method": p.payment_method,
                "reference_number": p.reference_number,
                "days_since_received": max(days_since, 0),
            })

        # Also collect all open invoices for step 2
        open_invoices = (
            self.db.query(Invoice)
            .filter(
                Invoice.company_id == self.tenant_id,
                Invoice.status.notin_(["paid", "void", "write_off", "draft"]),
            )
            .all()
        )

        self._open_invoices = open_invoices
        open_inv_total = sum(
            Decimal(str(inv.total or 0)) - Decimal(str(inv.amount_paid or 0))
            for inv in open_invoices
        )

        unmatched_total = sum(Decimal(str(p["amount"])) for p in unmatched)

        data = {
            "unmatched_count": len(unmatched),
            "unmatched_total": float(unmatched_total),
            "open_invoice_count": len(open_invoices),
            "open_invoice_total": float(open_inv_total),
            "payments": unmatched,
        }

        msg = (
            f"{len(unmatched)} unmatched payments totaling "
            f"${float(unmatched_total):,.2f}. "
            f"{len(open_invoices)} open invoices totaling "
            f"${float(open_inv_total):,.2f}."
        )

        return StepResult(message=msg, data=data, anomalies=[])

    # ------------------------------------------------------------------
    # STEP 2 — attempt_auto_match
    # ------------------------------------------------------------------

    def _step_attempt_auto_match(self) -> StepResult:
        collect_data = self.step_results.get("collect_unmatched_payments", {})
        payments = collect_data.get("payments", [])
        anomalies: list[AnomalyItem] = []

        open_invoices = getattr(self, "_open_invoices", [])

        # Build invoice lookup helpers
        inv_by_customer: dict[str, list] = {}
        all_inv_list = []
        for inv in open_invoices:
            balance = Decimal(str(inv.total or 0)) - Decimal(str(inv.amount_paid or 0))
            if balance <= 0:
                continue
            entry = {
                "invoice_id": inv.id,
                "invoice_number": inv.number,
                "customer_id": inv.customer_id,
                "balance_due": balance,
                "invoice_obj": inv,
            }
            all_inv_list.append(entry)
            if inv.customer_id not in inv_by_customer:
                inv_by_customer[inv.customer_id] = []
            inv_by_customer[inv.customer_id].append(entry)

        matches = []
        confident_matches = 0
        confident_total = Decimal(0)
        possible_matches = 0
        possible_total = Decimal(0)
        unresolvable = 0
        unresolvable_total = Decimal(0)

        for pay in payments:
            pay_amount = Decimal(str(pay["amount"]))
            pay_cid = pay["customer_id"]
            match_result = None

            # RULE 1 — Exact amount + same customer
            same_cust_invoices = inv_by_customer.get(pay_cid, [])
            exact_same = [
                inv for inv in same_cust_invoices
                if abs(inv["balance_due"] - pay_amount) <= Decimal("0.01")
            ]
            if len(exact_same) == 1:
                match_result = {
                    "payment_id": pay["payment_id"],
                    "payment_amount": float(pay_amount),
                    "customer_name": pay["customer_name"],
                    "match_type": "CONFIDENT_MATCH",
                    "suggested_invoice_id": exact_same[0]["invoice_id"],
                    "suggested_invoice_number": exact_same[0]["invoice_number"],
                    "confidence": "high",
                }
                confident_matches += 1
                confident_total += pay_amount

                # Apply match if not dry run
                if not self.dry_run:
                    self.guard_write()
                    inv_obj = exact_same[0]["invoice_obj"]
                    import uuid
                    app = CustomerPaymentApplication(
                        id=str(uuid.uuid4()),
                        payment_id=pay["payment_id"],
                        invoice_id=inv_obj.id,
                        amount_applied=pay_amount,
                    )
                    self.db.add(app)
                    inv_obj.amount_paid = Decimal(str(inv_obj.amount_paid or 0)) + pay_amount
                    if inv_obj.amount_paid >= Decimal(str(inv_obj.total or 0)):
                        inv_obj.status = "paid"
                        inv_obj.paid_at = datetime.now(timezone.utc)
                    self.db.flush()

            # RULE 2 — Exact amount, any customer
            if not match_result:
                exact_any = [
                    inv for inv in all_inv_list
                    if abs(inv["balance_due"] - pay_amount) <= Decimal("0.01")
                ]
                if len(exact_any) == 1:
                    match_result = {
                        "payment_id": pay["payment_id"],
                        "payment_amount": float(pay_amount),
                        "customer_name": pay["customer_name"],
                        "match_type": "POSSIBLE_MATCH",
                        "suggested_invoice_id": exact_any[0]["invoice_id"],
                        "suggested_invoice_number": exact_any[0]["invoice_number"],
                        "confidence": "medium",
                    }
                    possible_matches += 1
                    possible_total += pay_amount
                    anomalies.append(self._make_anomaly(
                        severity=AnomalySeverity.INFO,
                        anomaly_type="payment_possible_match",
                        entity_type="payment",
                        entity_id=pay["payment_id"],
                        description=(
                            f"Payment of ${float(pay_amount):,.2f} from "
                            f"{pay['customer_name']} on {pay['payment_date']} "
                            f"may match Invoice #{exact_any[0]['invoice_number']} "
                            f"(${float(exact_any[0]['balance_due']):,.2f}). Confirm match."
                        ),
                        amount=pay_amount,
                    ))

            # RULE 3 — Partial amount, same customer (subset sum)
            if not match_result:
                candidates = [
                    inv for inv in same_cust_invoices
                    if inv["balance_due"] <= pay_amount
                ]
                # Cap at 10 candidates
                candidates = candidates[:10]
                found_subset = False

                for r in range(1, len(candidates) + 1):
                    if found_subset:
                        break
                    for combo in combinations(candidates, r):
                        combo_total = sum(inv["balance_due"] for inv in combo)
                        if abs(combo_total - pay_amount) <= Decimal("0.01"):
                            inv_nums = ", ".join(inv["invoice_number"] for inv in combo)
                            match_result = {
                                "payment_id": pay["payment_id"],
                                "payment_amount": float(pay_amount),
                                "customer_name": pay["customer_name"],
                                "match_type": "POSSIBLE_MATCH",
                                "suggested_invoice_id": combo[0]["invoice_id"],
                                "suggested_invoice_number": inv_nums,
                                "confidence": "medium",
                            }
                            possible_matches += 1
                            possible_total += pay_amount
                            anomalies.append(self._make_anomaly(
                                severity=AnomalySeverity.INFO,
                                anomaly_type="payment_possible_match",
                                entity_type="payment",
                                entity_id=pay["payment_id"],
                                description=(
                                    f"Payment of ${float(pay_amount):,.2f} from "
                                    f"{pay['customer_name']} may match invoices "
                                    f"{inv_nums} (combined ${float(combo_total):,.2f}). "
                                    f"Confirm match."
                                ),
                                amount=pay_amount,
                            ))
                            found_subset = True
                            break

            # RULE 4 — No match
            if not match_result:
                match_result = {
                    "payment_id": pay["payment_id"],
                    "payment_amount": float(pay_amount),
                    "customer_name": pay["customer_name"],
                    "match_type": "UNRESOLVABLE",
                    "suggested_invoice_id": None,
                    "suggested_invoice_number": None,
                    "confidence": "low",
                }
                unresolvable += 1
                unresolvable_total += pay_amount

            matches.append(match_result)

        data = {
            "confident_matches": confident_matches,
            "confident_match_total": float(confident_total),
            "possible_matches": possible_matches,
            "possible_match_total": float(possible_total),
            "unresolvable": unresolvable,
            "unresolvable_total": float(unresolvable_total),
            "matches": matches,
        }

        msg = (
            f"{confident_matches} auto-matched "
            f"(${float(confident_total):,.2f}), "
            f"{possible_matches} need confirmation, "
            f"{unresolvable} unresolvable."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 3 — flag_unresolvable
    # ------------------------------------------------------------------

    def _step_flag_unresolvable(self) -> StepResult:
        match_data = self.step_results.get("attempt_auto_match", {})
        collect_data = self.step_results.get("collect_unmatched_payments", {})
        matches = match_data.get("matches", [])
        payments = collect_data.get("payments", [])
        anomalies: list[AnomalyItem] = []

        # Build payment lookup for days_since_received
        pay_lookup = {p["payment_id"]: p for p in payments}

        stale_count = 0
        stale_total = Decimal(0)
        recent_count = 0
        unmatched_total = Decimal(0)

        for m in matches:
            if m["match_type"] != "UNRESOLVABLE":
                continue

            pay_info = pay_lookup.get(m["payment_id"], {})
            days = pay_info.get("days_since_received", 0)
            amount = Decimal(str(m["payment_amount"]))
            customer_name = m["customer_name"]
            unmatched_total += amount

            if days > 30:
                stale_count += 1
                stale_total += amount
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.CRITICAL,
                    anomaly_type="payment_unmatched_stale",
                    entity_type="payment",
                    entity_id=m["payment_id"],
                    description=(
                        f"Payment of ${float(amount):,.2f} from "
                        f"{customer_name} received {days} days ago "
                        f"cannot be matched to any open invoice."
                    ),
                    amount=amount,
                ))
            else:
                recent_count += 1
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.WARNING,
                    anomaly_type="payment_unmatched_recent",
                    entity_type="payment",
                    entity_id=m["payment_id"],
                    description=(
                        f"Payment of ${float(amount):,.2f} from "
                        f"{customer_name} received {days} days ago "
                        f"has no matching invoice."
                    ),
                    amount=amount,
                ))

        # Check unmatched ratio vs total AR
        total_ar = Decimal(str(collect_data.get("open_invoice_total", 0)))
        unmatched_ratio = 0.0
        high_ratio_flagged = False
        if total_ar > 0:
            unmatched_ratio = float(unmatched_total / total_ar * 100)
            if unmatched_ratio > 10:
                high_ratio_flagged = True
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.WARNING,
                    anomaly_type="high_unmatched_ratio",
                    description=(
                        f"Unmatched payments (${float(unmatched_total):,.2f}) "
                        f"represent {unmatched_ratio:.1f}% of total AR. "
                        f"Cash application may be falling behind."
                    ),
                    amount=unmatched_total,
                ))

        data = {
            "stale_unmatched_count": stale_count,
            "stale_unmatched_total": float(stale_total),
            "recent_unmatched_count": recent_count,
            "unmatched_ratio_pct": round(unmatched_ratio, 1),
            "high_ratio_flagged": high_ratio_flagged,
        }

        msg = (
            f"{stale_count} stale unmatched payments "
            f"(${float(stale_total):,.2f}). "
            f"{recent_count} recent. "
            f"Unmatched ratio: {unmatched_ratio:.1f}% of AR."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 4 — generate_report
    # ------------------------------------------------------------------

    def _step_generate_report(self) -> StepResult:
        collect_data = self.step_results.get("collect_unmatched_payments", {})
        match_data = self.step_results.get("attempt_auto_match", {})
        flag_data = self.step_results.get("flag_unresolvable", {})

        confident = match_data.get("confident_matches", 0)
        confident_total = match_data.get("confident_match_total", 0)
        possible = match_data.get("possible_matches", 0)
        unresolv = match_data.get("unresolvable", 0)
        needs_action = possible + unresolv

        critical = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.CRITICAL)
        warning = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.WARNING)
        info = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.INFO)

        executive_summary = {
            "report_date": date.today().isoformat(),
            "unmatched_count": collect_data.get("unmatched_count", 0),
            "unmatched_total": collect_data.get("unmatched_total", 0),
            "confident_matches": confident,
            "confident_match_total": confident_total,
            "possible_matches": possible,
            "unresolvable": unresolv,
            "anomaly_count": self.job.anomaly_count,
            "critical_anomaly_count": critical,
            "warning_anomaly_count": warning,
            "info_anomaly_count": info,
            "dry_run": self.dry_run,
            "generated_at": datetime.now(timezone.utc).isoformat(),
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

        self.job.report_payload["report_html"] = self._build_report_html(
            executive_summary, match_data,
        )
        self.db.commit()

        msg = (
            f"Cash receipts report ready. "
            f"{confident} auto-matched, {needs_action} need manual attention."
        )

        return StepResult(message=msg, data={"report_generated": True}, anomalies=[])

    def _build_report_html(self, summary: dict, match_data: dict) -> str:
        unmatched_count = summary.get("unmatched_count", 0)
        confident = summary.get("confident_matches", 0)
        possible = summary.get("possible_matches", 0)
        unresolv = summary.get("unresolvable", 0)

        dry_run_badge = (
            '<span style="background:#f59e0b;color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:12px;margin-left:8px;">DRY RUN</span>'
            if self.dry_run else ""
        )

        # Match results table
        matches = match_data.get("matches", [])
        row_colors = {
            "CONFIDENT_MATCH": "background:#f0fdf4;",
            "POSSIBLE_MATCH": "background:#fffbeb;",
            "UNRESOLVABLE": "background:#fef2f2;",
        }
        badge_colors = {
            "CONFIDENT_MATCH": "#16a34a",
            "POSSIBLE_MATCH": "#d97706",
            "UNRESOLVABLE": "#dc2626",
        }

        match_rows = ""
        for m in matches:
            mt = m.get("match_type", "UNRESOLVABLE")
            row_bg = row_colors.get(mt, "")
            badge_color = badge_colors.get(mt, "#6b7280")
            conf = m.get("confidence", "low")
            match_rows += (
                f'<tr style="{row_bg}">'
                f'<td>{m.get("payment_id", "")[:8]}...</td>'
                f'<td>{m.get("customer_name", "")}</td>'
                f'<td style="text-align:right;">${m.get("payment_amount", 0):,.2f}</td>'
                f'<td><span style="background:{badge_color};color:#fff;padding:2px 8px;'
                f'border-radius:4px;font-size:12px;">{mt.replace("_", " ")}</span></td>'
                f'<td>{m.get("suggested_invoice_number", "") or "—"}</td>'
                f'<td>{conf}</td></tr>'
            )

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
            <h1>Cash Receipts Matching{dry_run_badge}</h1>
            <div class="meta">{period_label} &middot; Generated {summary.get('generated_at', '')}</div>

            <div class="cards">
                <div class="card">
                    <div class="card-value">{unmatched_count}</div>
                    <div class="card-label">Unmatched Payments</div>
                </div>
                <div class="card">
                    <div class="card-value">{confident}</div>
                    <div class="card-label">Auto-Matched</div>
                </div>
                <div class="card">
                    <div class="card-value">{possible}</div>
                    <div class="card-label">Need Confirmation</div>
                </div>
                <div class="card">
                    <div class="card-value">{unresolv}</div>
                    <div class="card-label">Unresolvable</div>
                </div>
            </div>

            <h2>Match Results</h2>
            <table>
                <thead><tr><th>Payment</th><th>Customer</th><th style="text-align:right;">Amount</th><th>Match Type</th><th>Invoice</th><th>Confidence</th></tr></thead>
                <tbody>{match_rows or '<tr><td colspan="6" style="text-align:center;color:#16a34a;">No unmatched payments</td></tr>'}</tbody>
            </table>
        </div>
        </body>
        </html>
        """

    # ------------------------------------------------------------------
    # Override _assemble_report — generate_report step handles it
    # ------------------------------------------------------------------

    def _assemble_report(self) -> None:
        pass
