"""Estimated Tax Prep Agent — Phase 7.

Quarterly agent that uses get_income_statement() to compute taxable income,
looks up applicable tax rates, estimates quarterly federal and state tax
liability, and produces a payment summary for CPA review.

This agent is purely informational — no financial writes on approval.

Steps:
  1. compute_income_statement — period + YTD income via financial_report_service
  2. annualize_income — project full-year income from YTD actuals
  3. compute_tax_liability — look up rates, estimate quarterly payments
  4. assess_prior_payments — find any prior estimated tax payments
  5. generate_report — executive summary + HTML report with disclaimer
"""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import ClassVar

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.agent import AgentJob
from app.models.journal_entry import JournalEntry, JournalEntryLine
from app.models.tax import TaxRate, TaxJurisdiction
from app.models.vendor_bill import VendorBill
from app.models.vendor_bill_line import VendorBillLine
from app.schemas.agent import (
    AgentJobType,
    AnomalyItem,
    AnomalySeverity,
    StepResult,
)
from app.services.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# Federal estimated tax due dates (month, day)
FEDERAL_DUE_DATES = [
    (4, 15),   # Q1: April 15
    (6, 15),   # Q2: June 15
    (9, 15),   # Q3: September 15
    (1, 15),   # Q4: January 15 (next year)
]

# Conservative federal effective rate range for small business planning
FEDERAL_RATE_LOW = Decimal("0.20")   # 20%
FEDERAL_RATE_HIGH = Decimal("0.25")  # 25%


class EstimatedTaxPrepAgent(BaseAgent):
    """Quarterly estimated tax prep report for CPA review."""

    JOB_TYPE = AgentJobType.ESTIMATED_TAX_PREP

    STEPS: ClassVar[list[str]] = [
        "compute_income_statement",
        "annualize_income",
        "compute_tax_liability",
        "assess_prior_payments",
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

    def _period_start(self):
        return self.job.period_start

    def _period_end(self):
        return self.job.period_end

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

    def _compute_quarters_elapsed(self, period_end: date) -> int:
        """How many complete quarters have passed since Jan 1 of the period_end year."""
        if period_end >= date(period_end.year, 12, 31):
            return 4
        if period_end >= date(period_end.year, 9, 30):
            return 3
        if period_end >= date(period_end.year, 6, 30):
            return 2
        if period_end >= date(period_end.year, 3, 31):
            return 1
        return 0

    def _get_current_quarter(self, d: date) -> int:
        """Return 1-4 for the quarter containing date d."""
        return (d.month - 1) // 3 + 1

    def _get_next_due_date(self, period_end: date) -> date:
        """Return the next federal estimated tax due date after period_end."""
        year = period_end.year
        for month, day in FEDERAL_DUE_DATES:
            if month == 1:
                # Q4 due date is in the NEXT year
                due = date(year + 1, month, day)
            else:
                due = date(year, month, day)
            if due > period_end:
                return due
        # Fallback: next year Q1
        return date(year + 1, 4, 15)

    # ------------------------------------------------------------------
    # STEP 1 — compute_income_statement
    # ------------------------------------------------------------------

    def _step_compute_income_statement(self) -> StepResult:
        from app.services.financial_report_service import get_income_statement

        ps, pe = self._period_start(), self._period_end()
        anomalies: list[AnomalyItem] = []

        # Period income statement
        period_result = get_income_statement(
            db=self.db,
            tenant_id=self.tenant_id,
            period_start=ps,
            period_end=pe,
        )

        period_revenue = Decimal(str(period_result.get("total_revenue", 0)))
        period_cogs = Decimal(str(period_result.get("total_cogs", 0)))
        period_gross_profit = Decimal(str(period_result.get("gross_profit", 0)))
        period_expenses = Decimal(str(period_result.get("total_expenses", 0)))
        period_net_income = Decimal(str(period_result.get("net_income", 0)))

        # YTD income statement (Jan 1 of period_end year through period_end)
        ytd_start = date(pe.year, 1, 1)
        ytd_result = get_income_statement(
            db=self.db,
            tenant_id=self.tenant_id,
            period_start=ytd_start,
            period_end=pe,
        )

        ytd_revenue = Decimal(str(ytd_result.get("total_revenue", 0)))
        ytd_net_income = Decimal(str(ytd_result.get("net_income", 0)))

        quarters_elapsed = self._compute_quarters_elapsed(pe)

        quarter_num = self._get_current_quarter(pe)
        period_label = f"Q{quarter_num} {pe.year}"

        data = {
            "period_revenue": float(period_revenue),
            "period_cogs": float(period_cogs),
            "period_gross_profit": float(period_gross_profit),
            "period_operating_expenses": float(period_expenses),
            "period_net_income": float(period_net_income),
            "ytd_revenue": float(ytd_revenue),
            "ytd_net_income": float(ytd_net_income),
            "period_label": period_label,
            "quarters_elapsed": quarters_elapsed,
        }

        msg = (
            f"Period net income: ${period_net_income:,.2f}. "
            f"YTD net income: ${ytd_net_income:,.2f}."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 2 — annualize_income
    # ------------------------------------------------------------------

    def _step_annualize_income(self) -> StepResult:
        anomalies: list[AnomalyItem] = []
        income_data = self.step_results.get("compute_income_statement", {})

        quarters_elapsed = income_data.get("quarters_elapsed", 0)
        ytd_net_income = Decimal(str(income_data.get("ytd_net_income", 0)))
        period_net_income = Decimal(str(income_data.get("period_net_income", 0)))

        if quarters_elapsed > 0:
            annualized = (ytd_net_income / quarters_elapsed * 4).quantize(
                Decimal("0.01"), ROUND_HALF_UP
            )
            method = "ytd_extrapolation"
        else:
            annualized = (period_net_income * 4).quantize(
                Decimal("0.01"), ROUND_HALF_UP
            )
            method = "single_period"
            anomalies.append(self._make_anomaly(
                severity=AnomalySeverity.INFO,
                anomaly_type="tax_estimate_rough",
                description=(
                    "Less than one full quarter of data available. "
                    "Tax estimate is a rough projection only."
                ),
            ))

        federal_low = (annualized * FEDERAL_RATE_LOW).quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )
        federal_high = (annualized * FEDERAL_RATE_HIGH).quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )

        data = {
            "quarters_elapsed": quarters_elapsed,
            "ytd_net_income": float(ytd_net_income),
            "annualized_net_income": float(annualized),
            "annualization_method": method,
            "federal_estimate_low": float(federal_low),
            "federal_estimate_high": float(federal_high),
        }

        msg = (
            f"Annualized net income: ${annualized:,.2f} "
            f"based on {quarters_elapsed} quarter(s) of data. "
            f"Federal tax estimate: ${federal_low:,.2f}–${federal_high:,.2f}."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 3 — compute_tax_liability
    # ------------------------------------------------------------------

    def _step_compute_tax_liability(self) -> StepResult:
        anomalies: list[AnomalyItem] = []
        annualize_data = self.step_results.get("annualize_income", {})
        annualized = Decimal(str(annualize_data.get("annualized_net_income", 0)))

        pe = self._period_end()
        next_due = self._get_next_due_date(pe)
        days_until_due = (next_due - date.today()).days

        # Federal estimates (from annualize step)
        federal_low = Decimal(str(annualize_data.get("federal_estimate_low", 0)))
        federal_high = Decimal(str(annualize_data.get("federal_estimate_high", 0)))
        federal_quarterly_low = (federal_low / 4).quantize(Decimal("0.01"), ROUND_HALF_UP)
        federal_quarterly_high = (federal_high / 4).quantize(Decimal("0.01"), ROUND_HALF_UP)

        # Look up state/local tax rates for this tenant
        tax_rates_data = []
        state_quarterly = None

        rates = (
            self.db.query(TaxRate)
            .filter(
                TaxRate.tenant_id == self.tenant_id,
                TaxRate.is_active == True,
            )
            .all()
        )

        if not rates:
            anomalies.append(self._make_anomaly(
                severity=AnomalySeverity.WARNING,
                anomaly_type="no_tax_rates_configured",
                description=(
                    "No tax rates found for this tenant. State tax estimate "
                    "cannot be computed. Configure tax rates in "
                    "Settings → Tax Rates to enable accurate estimates."
                ),
            ))
        else:
            for rate in rates:
                # rate_percentage is stored as a percentage (e.g. 8.0 = 8%)
                pct = Decimal(str(rate.rate_percentage))
                decimal_rate = pct / 100
                annual_liability = (annualized * decimal_rate).quantize(
                    Decimal("0.01"), ROUND_HALF_UP
                )
                quarterly_payment = (annual_liability / 4).quantize(
                    Decimal("0.01"), ROUND_HALF_UP
                )
                tax_rates_data.append({
                    "jurisdiction_name": rate.rate_name,
                    "jurisdiction_type": "state",
                    "rate": float(pct),
                    "annual_liability_estimate": float(annual_liability),
                    "quarterly_payment_estimate": float(quarterly_payment),
                })
                if state_quarterly is None:
                    state_quarterly = quarterly_payment
                else:
                    state_quarterly += quarterly_payment

        total_quarterly_low = federal_quarterly_low + (state_quarterly or Decimal(0))
        total_quarterly_high = federal_quarterly_high + (state_quarterly or Decimal(0))

        data = {
            "jurisdiction_found": len(rates) > 0 if rates else False,
            "tax_rates": tax_rates_data,
            "federal_quarterly_low": float(federal_quarterly_low),
            "federal_quarterly_high": float(federal_quarterly_high),
            "state_quarterly": float(state_quarterly) if state_quarterly else None,
            "total_quarterly_low": float(total_quarterly_low),
            "total_quarterly_high": float(total_quarterly_high),
            "next_due_date": next_due.isoformat(),
            "days_until_due": days_until_due,
        }

        msg = (
            f"Estimated quarterly payment: "
            f"${total_quarterly_low:,.2f}–${total_quarterly_high:,.2f}. "
            f"Next due: {next_due} ({days_until_due} days)."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 4 — assess_prior_payments
    # ------------------------------------------------------------------

    def _step_assess_prior_payments(self) -> StepResult:
        anomalies: list[AnomalyItem] = []
        pe = self._period_end()
        year_start = date(pe.year, 1, 1)

        # Look for tax-related journal entries (tax liability accounts)
        prior_payments = []
        total_paid = Decimal(0)

        # Check journal entries with "tax" in description or gl_account_name
        tax_entries = (
            self.db.query(JournalEntry, JournalEntryLine)
            .join(JournalEntryLine, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .filter(
                JournalEntry.tenant_id == self.tenant_id,
                JournalEntry.status == "posted",
                JournalEntry.entry_date >= year_start,
                JournalEntry.entry_date <= pe,
                func.lower(JournalEntryLine.gl_account_name).contains("tax"),
                JournalEntryLine.debit_amount > 0,
            )
            .all()
        )

        for entry, line in tax_entries:
            amt = Decimal(str(line.debit_amount))
            total_paid += amt
            prior_payments.append({
                "date": entry.entry_date.isoformat() if entry.entry_date else None,
                "amount": float(amt),
                "description": entry.description or line.description or "Tax payment",
            })

        # Also check vendor bills with tax-related expense_category
        tax_bills = (
            self.db.query(VendorBill, VendorBillLine)
            .join(VendorBillLine, VendorBill.id == VendorBillLine.bill_id)
            .filter(
                VendorBill.company_id == self.tenant_id,
                VendorBill.deleted_at.is_(None),
                func.date(VendorBill.bill_date) >= year_start,
                func.date(VendorBill.bill_date) <= pe,
                func.lower(VendorBillLine.expense_category).contains("tax"),
            )
            .all()
        )

        for bill, line in tax_bills:
            amt = Decimal(str(line.amount))
            total_paid += amt
            bill_date = bill.bill_date
            if hasattr(bill_date, "date"):
                bill_date = bill_date.date()
            prior_payments.append({
                "date": bill_date.isoformat() if bill_date else None,
                "amount": float(amt),
                "description": line.description or "Tax payment (vendor bill)",
            })

        prior_found = len(prior_payments) > 0

        if not prior_found:
            anomalies.append(self._make_anomaly(
                severity=AnomalySeverity.INFO,
                anomaly_type="no_tax_payment_tracking",
                description=(
                    "No estimated tax payment records found. If payments "
                    "have been made, they may not be categorized in a way "
                    "the system can identify. Verify with your CPA."
                ),
            ))

        # Compute remaining liability estimate
        tax_data = self.step_results.get("compute_tax_liability", {})
        quarters_elapsed = self.step_results.get("compute_income_statement", {}).get("quarters_elapsed", 0)
        total_quarterly_low = Decimal(str(tax_data.get("total_quarterly_low", 0)))
        ytd_liability_estimate = total_quarterly_low * quarters_elapsed if quarters_elapsed > 0 else None

        remaining = None
        on_track = None
        if ytd_liability_estimate is not None:
            remaining = float(ytd_liability_estimate - total_paid)
            on_track = total_paid >= ytd_liability_estimate

        data = {
            "prior_payments_found": prior_found,
            "prior_payments_total": float(total_paid),
            "prior_payments": prior_payments,
            "remaining_ytd_estimate": remaining,
            "on_track": on_track,
            "tracking_note": None if prior_found else "No tax payment records found in journal entries or vendor bills.",
        }

        if prior_found:
            msg = f"Prior estimated tax payments this year: ${total_paid:,.2f}."
        else:
            msg = "No estimated tax payment records found. Manual verification recommended."

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 5 — generate_report
    # ------------------------------------------------------------------

    def _step_generate_report(self) -> StepResult:
        income_data = self.step_results.get("compute_income_statement", {})
        annualize_data = self.step_results.get("annualize_income", {})
        tax_data = self.step_results.get("compute_tax_liability", {})
        payments_data = self.step_results.get("assess_prior_payments", {})

        critical = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.CRITICAL)
        warning = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.WARNING)
        info = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.INFO)

        pe = self._period_end()
        quarter_num = self._get_current_quarter(pe)

        executive_summary = {
            "period": f"{self._period_start()} to {self._period_end()}",
            "quarter_label": f"Q{quarter_num} {pe.year}",
            "period_net_income": income_data.get("period_net_income", 0),
            "annualized_net_income": annualize_data.get("annualized_net_income", 0),
            "federal_quarterly_low": tax_data.get("federal_quarterly_low", 0),
            "federal_quarterly_high": tax_data.get("federal_quarterly_high", 0),
            "state_quarterly": tax_data.get("state_quarterly"),
            "total_quarterly_low": tax_data.get("total_quarterly_low", 0),
            "total_quarterly_high": tax_data.get("total_quarterly_high", 0),
            "next_due_date": tax_data.get("next_due_date"),
            "days_until_due": tax_data.get("days_until_due", 0),
            "prior_payments_ytd": payments_data.get("prior_payments_total", 0),
            "anomaly_count": self.job.anomaly_count,
            "dry_run": self.dry_run,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        report_html = self._build_report_html(executive_summary, income_data, tax_data, payments_data)

        self.job.report_payload = {
            "job_type": self.job.job_type,
            "period_start": str(self.job.period_start),
            "period_end": str(self.job.period_end),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": self.dry_run,
            "anomaly_count": self.job.anomaly_count,
            "executive_summary": executive_summary,
            "steps": {k: v for k, v in self.step_results.items()},
            "anomalies": [a.model_dump(mode="json") for a in self.anomalies],
            "report_html": report_html,
        }
        self.db.commit()

        msg = (
            f"Report ready. {self.job.anomaly_count} anomalies "
            f"({critical} critical, {warning} warning, {info} info). "
            f"Ready for CPA review."
        )

        return StepResult(message=msg, data={"report_generated": True}, anomalies=[])

    def _build_report_html(
        self, summary: dict, income_data: dict, tax_data: dict, payments_data: dict
    ) -> str:
        ps = self._period_start()
        pe = self._period_end()
        dry_run_badge = (
            '<span style="background:#f59e0b;color:#fff;padding:2px 8px;border-radius:4px;'
            'font-size:12px;margin-left:8px;">DRY RUN</span>'
            if self.dry_run else ""
        )

        # Due date urgency
        days_until = summary.get("days_until_due", 999)
        due_card_bg = "#fef2f2" if days_until < 14 else "#f4f4f5"
        due_card_color = "#dc2626" if days_until < 14 else "#18181b"

        # Disclaimer
        disclaimer = """
        <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:6px;padding:16px;margin-bottom:24px;">
            <p style="margin:0;font-size:13px;color:#1e40af;line-height:1.5;">
                <strong>Important:</strong> This is an estimate for planning purposes only.
                It is not tax advice. Consult your CPA before making any tax payments.
                Effective tax rates vary based on deductions, credits, and other factors
                not captured here.
            </p>
        </div>
        """

        # Metric cards
        total_low = summary.get("total_quarterly_low", 0)
        total_high = summary.get("total_quarterly_high", 0)
        cards_html = f"""
        <div class="cards">
            <div class="card">
                <div class="card-value">${summary.get('period_net_income', 0):,.0f}</div>
                <div class="card-label">Period Net Income</div>
            </div>
            <div class="card">
                <div class="card-value">${summary.get('annualized_net_income', 0):,.0f}</div>
                <div class="card-label">Annualized Income</div>
            </div>
            <div class="card">
                <div class="card-value">${total_low:,.0f}–${total_high:,.0f}</div>
                <div class="card-label">Quarterly Estimate</div>
            </div>
            <div class="card" style="background:{due_card_bg};">
                <div class="card-value" style="color:{due_card_color};">{summary.get('next_due_date', 'N/A')}</div>
                <div class="card-label">Next Due Date ({days_until} days)</div>
            </div>
        </div>
        """

        # Income breakdown
        income_html = f"""
        <h2>Income Breakdown</h2>
        <table>
            <thead><tr><th></th><th style="text-align:right;">Period</th><th style="text-align:right;">YTD</th></tr></thead>
            <tbody>
                <tr><td>Revenue</td><td style="text-align:right;">${income_data.get('period_revenue', 0):,.2f}</td>
                    <td style="text-align:right;">${income_data.get('ytd_revenue', 0):,.2f}</td></tr>
                <tr><td>COGS</td><td style="text-align:right;">${income_data.get('period_cogs', 0):,.2f}</td>
                    <td style="text-align:right;">—</td></tr>
                <tr><td>Gross Profit</td><td style="text-align:right;">${income_data.get('period_gross_profit', 0):,.2f}</td>
                    <td style="text-align:right;">—</td></tr>
                <tr><td>Operating Expenses</td><td style="text-align:right;">${income_data.get('period_operating_expenses', 0):,.2f}</td>
                    <td style="text-align:right;">—</td></tr>
                <tr style="font-weight:700;border-top:2px solid #18181b;">
                    <td>Net Income</td><td style="text-align:right;">${income_data.get('period_net_income', 0):,.2f}</td>
                    <td style="text-align:right;">${income_data.get('ytd_net_income', 0):,.2f}</td></tr>
            </tbody>
        </table>
        """

        # Tax estimate breakdown
        tax_rows = ""
        for tr in tax_data.get("tax_rates", []):
            tax_rows += f"""
            <tr>
                <td>{tr['jurisdiction_name']}</td>
                <td>{tr['rate']}%</td>
                <td style="text-align:right;">${tr['annual_liability_estimate']:,.2f}</td>
                <td style="text-align:right;">${tr['quarterly_payment_estimate']:,.2f}</td>
            </tr>"""

        fed_low = tax_data.get("federal_quarterly_low", 0)
        fed_high = tax_data.get("federal_quarterly_high", 0)
        tax_rows += f"""
        <tr>
            <td>Federal (estimated range)</td>
            <td>20–25%</td>
            <td style="text-align:right;">${summary.get('federal_quarterly_low', 0) * 4:,.2f}–${summary.get('federal_quarterly_high', 0) * 4:,.2f}</td>
            <td style="text-align:right;">${fed_low:,.2f}–${fed_high:,.2f}</td>
        </tr>"""

        tax_html = f"""
        <h2>Tax Estimate Breakdown</h2>
        <table>
            <thead><tr><th>Jurisdiction</th><th>Rate</th><th style="text-align:right;">Annual Est.</th><th style="text-align:right;">Quarterly Est.</th></tr></thead>
            <tbody>
                {tax_rows}
                <tr style="font-weight:700;border-top:2px solid #18181b;">
                    <td>Total</td><td></td><td></td>
                    <td style="text-align:right;">${total_low:,.2f}–${total_high:,.2f}</td>
                </tr>
            </tbody>
        </table>
        """

        # Payment timeline
        pe_val = self._period_end()
        year = pe_val.year
        current_q = self._get_current_quarter(pe_val)
        timeline_items = ""
        for q, (m, d) in enumerate(FEDERAL_DUE_DATES, 1):
            due_year = year + 1 if m == 1 else year
            due_str = f"{due_year}-{m:02d}-{d:02d}"
            is_current = q == current_q
            style = "background:#2563eb;color:#fff;padding:4px 8px;border-radius:4px;" if is_current else ""
            marker = " ← Current" if is_current else ""
            timeline_items += f'<li><span style="{style}">Q{q}: {due_str}{marker}</span></li>'

        timeline_html = f"""
        <h2>Payment Timeline</h2>
        <ul style="list-style:none;padding:0;">{timeline_items}</ul>
        """

        # Prior payments
        prior_html = ""
        prior_payments = payments_data.get("prior_payments", [])
        if prior_payments:
            rows = ""
            for pp in prior_payments:
                rows += f"""
                <tr>
                    <td>{pp['date'] or 'N/A'}</td>
                    <td style="text-align:right;">${pp['amount']:,.2f}</td>
                    <td>{pp['description']}</td>
                </tr>"""
            prior_html = f"""
            <h2>Prior Payments This Year</h2>
            <table>
                <thead><tr><th>Date</th><th style="text-align:right;">Amount</th><th>Description</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
            """
        else:
            prior_html = """
            <h2>Prior Payments This Year</h2>
            <p style="color:#71717a;font-size:14px;">No estimated tax payment records found.</p>
            """

        # CPA notes section
        cpa_notes = """
        <h2>CPA Notes</h2>
        <div style="background:#f4f4f5;border:1px dashed #d4d4d8;border-radius:6px;padding:24px;min-height:80px;">
            <p style="margin:0;color:#a1a1aa;font-size:13px;font-style:italic;">
                Space for accountant notes during review...
            </p>
        </div>
        """

        return f"""
        <!DOCTYPE html>
        <html>
        <head><style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #18181b; margin: 0; padding: 24px; background: #f4f4f5; }}
            .container {{ max-width: 900px; margin: 0 auto; background: #fff; border-radius: 8px; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,.1); }}
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
            <h1>Estimated Tax Prep — {summary.get('quarter_label', '')}{dry_run_badge}</h1>
            <div class="meta">{ps} to {pe} &middot; Generated {summary['generated_at']}</div>
            {disclaimer}
            {cards_html}
            {income_html}
            {tax_html}
            {timeline_html}
            {prior_html}
            {cpa_notes}
        </div>
        </body>
        </html>
        """

    # ------------------------------------------------------------------
    # Override _assemble_report — generate_report step handles it
    # ------------------------------------------------------------------

    def _assemble_report(self) -> None:
        """Skip default assembly — generate_report step already built report_payload."""
        pass
