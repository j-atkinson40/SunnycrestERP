"""Year-End Close Agent — Phase 11.

Annual agent that runs the full December month-end close (inherited from
MonthEndCloseAgent) then executes five additional year-end steps. Produces
a complete annual financial close package and triggers the December statement
run on approval.

Inherits all 8 steps from MonthEndCloseAgent then adds:
  9.  full_year_summary
  10. depreciation_review
  11. accruals_review
  12. inventory_valuation
  13. retained_earnings_summary
"""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import ClassVar

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.agent import AgentJob
from app.models.inventory_item import InventoryItem
from app.models.journal_entry import JournalEntry, JournalEntryLine
from app.models.product import Product
from app.schemas.agent import (
    AgentJobType,
    AnomalyItem,
    AnomalySeverity,
    StepResult,
)
from app.services.agents.month_end_close_agent import MonthEndCloseAgent

logger = logging.getLogger(__name__)

# Depreciation monthly variance threshold (20%)
DEPRECIATION_VARIANCE_PCT = Decimal("20.0")

# Budget variance threshold (15%)
BUDGET_VARIANCE_THRESHOLD = Decimal("15.0")

# Accrual pattern keywords
ACCRUAL_KEYWORDS = [
    "accrued", "accrual", "prepaid", "deferred", "unbilled", "unearned",
]

# Distribution pattern keywords
DISTRIBUTION_KEYWORDS = [
    "distribution", "dividend", "owner draw", "owner withdrawal", "draw",
]


class YearEndCloseAgent(MonthEndCloseAgent):
    """Annual agent that runs December month-end close + year-end steps."""

    JOB_TYPE = AgentJobType.YEAR_END_CLOSE

    STEPS: ClassVar[list[str]] = MonthEndCloseAgent.STEPS + [
        "full_year_summary",
        "depreciation_review",
        "accruals_review",
        "inventory_valuation",
        "retained_earnings_summary",
    ]

    # ------------------------------------------------------------------
    # Override execute to validate December period
    # ------------------------------------------------------------------

    def execute(self) -> AgentJob:
        self._load_job()

        ps = self.job.period_start
        pe = self.job.period_end
        if (
            ps.month != 12 or pe.month != 12
            or ps.day != 1 or pe.day != 31
            or ps.year != pe.year
        ):
            self.job.status = "failed"
            self.job.error_message = (
                "YearEndCloseAgent requires period Dec 1 – Dec 31. "
                "Use MonthEndCloseAgent for other months."
            )
            self.job.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            return self.job

        # Reset job so parent execute() can re-load cleanly
        return super().execute()

    # ------------------------------------------------------------------
    # Override run_step to dispatch year-end steps
    # ------------------------------------------------------------------

    def run_step(self, step_name: str) -> StepResult:
        if step_name in MonthEndCloseAgent.STEPS:
            return super().run_step(step_name)
        handler = getattr(self, f"_step_{step_name}", None)
        if not handler:
            raise ValueError(f"Unknown step: {step_name}")
        return handler()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _close_year(self) -> int:
        return self.job.period_start.year

    def _extract_income_data(self, income_stmt: dict) -> dict:
        """Normalize income statement to consistent structure."""
        total_rev = Decimal(str(income_stmt.get("total_revenue", 0)))
        total_cogs = Decimal(str(income_stmt.get("total_cogs", 0)))
        gross_profit = Decimal(str(income_stmt.get("gross_profit", 0)))
        total_exp = Decimal(str(income_stmt.get("total_expenses", 0)))
        net_income = Decimal(str(income_stmt.get("net_income", 0)))
        gross_margin = float(income_stmt.get("gross_margin_percent", 0))
        net_margin = float(net_income / total_rev * 100) if total_rev else 0.0

        return {
            "total_revenue": float(total_rev),
            "total_cogs": float(total_cogs),
            "gross_profit": float(gross_profit),
            "gross_margin_pct": gross_margin,
            "total_expenses": float(total_exp),
            "net_income": float(net_income),
            "net_margin_pct": round(net_margin, 1),
            "revenue_lines": income_stmt.get("revenue", []),
            "cogs_lines": income_stmt.get("cogs", []),
            "expense_lines": income_stmt.get("expenses", []),
        }

    def _compute_variance(self, actual: float, comparison: float, metric: str) -> dict:
        """Compute variance with favorable-direction logic."""
        if comparison == 0:
            return {
                "metric": metric,
                "actual": actual,
                "comparison": comparison,
                "variance_amount": actual,
                "variance_pct": None,
                "favorable": None,
            }
        variance_amount = actual - comparison
        variance_pct = (variance_amount / abs(comparison)) * 100

        # Favorable direction: revenue/gross_profit/net_income ABOVE is favorable;
        # COGS/expenses BELOW is favorable
        favorable_above = metric in (
            "total_revenue", "gross_profit", "net_income",
        )
        if favorable_above:
            favorable = variance_amount >= 0
        else:
            favorable = variance_amount <= 0

        return {
            "metric": metric,
            "actual": actual,
            "comparison": comparison,
            "variance_amount": variance_amount,
            "variance_pct": round(variance_pct, 1),
            "favorable": favorable,
        }

    # ------------------------------------------------------------------
    # STEP 9 — full_year_summary
    # ------------------------------------------------------------------

    def _step_full_year_summary(self) -> StepResult:
        from app.services.financial_report_service import get_income_statement

        year = self._close_year()
        anomalies: list[AnomalyItem] = []

        # Full year income statement
        annual_stmt = get_income_statement(
            self.db, self.tenant_id, date(year, 1, 1), date(year, 12, 31),
        )
        annual_data = self._extract_income_data(annual_stmt)

        # Quarterly breakdown
        quarterly = {}
        q_dates = [
            ("q1", date(year, 1, 1), date(year, 3, 31)),
            ("q2", date(year, 4, 1), date(year, 6, 30)),
            ("q3", date(year, 7, 1), date(year, 9, 30)),
            ("q4", date(year, 10, 1), date(year, 12, 31)),
        ]
        for q_key, q_start, q_end in q_dates:
            q_stmt = get_income_statement(
                self.db, self.tenant_id, q_start, q_end,
            )
            quarterly[q_key] = self._extract_income_data(q_stmt)

        # Compare vs approved Annual Budget (if exists)
        vs_budget = {"available": False, "variances": []}
        budget_job = (
            self.db.query(AgentJob)
            .filter(
                AgentJob.tenant_id == self.tenant_id,
                AgentJob.job_type == "annual_budget",
                AgentJob.status == "complete",
                AgentJob.period_start >= date(year, 1, 1),
                AgentJob.period_end <= date(year, 12, 31),
            )
            .order_by(AgentJob.completed_at.desc())
            .first()
        )
        if budget_job and budget_job.report_payload:
            budget_data = budget_job.report_payload.get("budget", {})
            budget_annual = budget_data.get("annual", {})
            if budget_annual:
                vs_budget["available"] = True
                for metric in ["revenue", "cogs", "gross_profit", "expenses", "net_income"]:
                    budget_key = metric
                    actual_key = f"total_{metric}" if metric not in ("gross_profit", "net_income") else metric
                    actual_val = annual_data.get(actual_key, 0)
                    budget_val = budget_annual.get(budget_key, 0)
                    var = self._compute_variance(actual_val, budget_val, actual_key)
                    vs_budget["variances"].append(var)

                    if var["variance_pct"] is not None and abs(var["variance_pct"]) > float(BUDGET_VARIANCE_THRESHOLD):
                        anomalies.append(self._make_anomaly(
                            severity=AnomalySeverity.WARNING,
                            anomaly_type="yearend_budget_variance",
                            description=(
                                f"{actual_key}: full year actual "
                                f"${actual_val:,.2f} vs budget "
                                f"${budget_val:,.2f} "
                                f"({var['variance_pct']:+.1f}%). "
                                f"Review with CPA."
                            ),
                            amount=Decimal(str(abs(var["variance_amount"]))),
                        ))

        # Compare vs prior year
        vs_prior_year = {"available": False, "prior_year": year - 1, "variances": []}
        prior_stmt = get_income_statement(
            self.db, self.tenant_id, date(year - 1, 1, 1), date(year - 1, 12, 31),
        )
        prior_data = self._extract_income_data(prior_stmt)
        if prior_data["total_revenue"] != 0 or prior_data["total_expenses"] != 0:
            vs_prior_year["available"] = True
            for metric in ["total_revenue", "total_cogs", "gross_profit", "total_expenses", "net_income"]:
                actual_val = annual_data.get(metric, 0)
                prior_val = prior_data.get(metric, 0)
                var = self._compute_variance(actual_val, prior_val, metric)
                vs_prior_year["variances"].append(var)

        rev = annual_data["total_revenue"]
        net = annual_data["net_income"]
        margin = annual_data["net_margin_pct"]

        budget_note = "No budget comparison"
        if vs_budget["available"]:
            rev_var = next(
                (v for v in vs_budget["variances"] if v["metric"] == "total_revenue"),
                None,
            )
            if rev_var and rev_var["variance_pct"] is not None:
                budget_note = f"Vs budget: {rev_var['variance_pct']:+.1f}% revenue"

        data = {
            "year": year,
            "annual_income_statement": annual_data,
            "quarterly_breakdown": quarterly,
            "vs_budget": vs_budget,
            "vs_prior_year": vs_prior_year,
        }

        msg = (
            f"Full year {year}: Revenue ${rev:,.2f}, "
            f"Net Income ${net:,.2f} ({margin:.1f}% margin). "
            f"{budget_note}."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 10 — depreciation_review
    # ------------------------------------------------------------------

    def _step_depreciation_review(self) -> StepResult:
        year = self._close_year()
        anomalies: list[AnomalyItem] = []

        # Find depreciation-related journal entry lines
        depr_lines = (
            self.db.query(JournalEntryLine)
            .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
            .filter(
                JournalEntry.tenant_id == self.tenant_id,
                JournalEntry.entry_date >= date(year, 1, 1),
                JournalEntry.entry_date <= date(year, 12, 31),
                JournalEntry.status != "voided",
                or_(
                    JournalEntryLine.gl_account_name.ilike("%depreciation%"),
                    JournalEntryLine.gl_account_name.ilike("%amortization%"),
                    (
                        JournalEntryLine.gl_account_number.like("6%")
                        & JournalEntryLine.description.ilike("%deprec%")
                    ),
                ),
            )
            .all()
        )

        total_depr = Decimal("0")
        monthly_amounts: dict[int, Decimal] = {m: Decimal("0") for m in range(1, 13)}
        account_totals: dict[str, dict] = {}

        for line in depr_lines:
            amt = Decimal(str(line.debit_amount or 0))
            total_depr += amt

            # Get month from parent entry
            entry = self.db.query(JournalEntry).filter(
                JournalEntry.id == line.journal_entry_id
            ).first()
            if entry:
                monthly_amounts[entry.entry_date.month] += amt

            acct_key = line.gl_account_number or "unknown"
            if acct_key not in account_totals:
                account_totals[acct_key] = {
                    "gl_account_number": line.gl_account_number or "",
                    "gl_account_name": line.gl_account_name or "",
                    "total": Decimal("0"),
                }
            account_totals[acct_key]["total"] += amt

        review_needed = False
        irregular_months: list[int] = []

        if total_depr == 0:
            review_needed = True
            anomalies.append(self._make_anomaly(
                severity=AnomalySeverity.WARNING,
                anomaly_type="yearend_no_depreciation",
                description=(
                    "No depreciation entries found for the year. If the business "
                    "owns depreciable assets, depreciation may not have been "
                    "recorded. Verify with CPA."
                ),
            ))
        else:
            monthly_avg = total_depr / 12
            for month in range(1, 13):
                if month == 12:
                    continue  # December often has true-ups
                amt = monthly_amounts[month]
                if monthly_avg > 0:
                    variance_pct = abs(amt - monthly_avg) / monthly_avg * 100
                    if variance_pct > float(DEPRECIATION_VARIANCE_PCT):
                        irregular_months.append(month)

            if irregular_months:
                review_needed = True
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.INFO,
                    anomaly_type="yearend_depreciation_irregular",
                    description=(
                        f"Depreciation entries are irregular — monthly amounts "
                        f"vary significantly. Expected ~${float(monthly_avg):,.2f}/month. "
                        f"Verify depreciation schedule with CPA."
                    ),
                ))

        monthly_depr = [
            {"month": m, "amount": float(monthly_amounts[m])} for m in range(1, 13)
        ]
        depr_accounts = [
            {
                "gl_account_number": v["gl_account_number"],
                "gl_account_name": v["gl_account_name"],
                "total": float(v["total"]),
            }
            for v in account_totals.values()
        ]

        data = {
            "total_depreciation_posted": float(total_depr),
            "monthly_depreciation": monthly_depr,
            "depreciation_accounts": depr_accounts,
            "irregular_months": irregular_months,
            "review_needed": review_needed,
        }

        if total_depr == 0:
            msg = "No depreciation entries found. CPA review recommended."
        else:
            monthly_avg_f = float(total_depr / 12)
            irregular_note = (
                f"{len(irregular_months)} months with irregular amounts."
                if irregular_months
                else "Monthly amounts are consistent."
            )
            msg = (
                f"Total depreciation posted: ${float(total_depr):,.2f} "
                f"(${monthly_avg_f:,.2f}/month avg). {irregular_note}"
            )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 11 — accruals_review
    # ------------------------------------------------------------------

    def _step_accruals_review(self) -> StepResult:
        year = self._close_year()
        anomalies: list[AnomalyItem] = []

        # Find accrual-pattern entries in December
        dec_start = date(year, 12, 1)
        dec_end = date(year, 12, 31)

        accrual_lines = (
            self.db.query(JournalEntryLine)
            .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
            .filter(
                JournalEntry.tenant_id == self.tenant_id,
                JournalEntry.entry_date >= dec_start,
                JournalEntry.entry_date <= dec_end,
                JournalEntry.status != "voided",
                or_(
                    *[
                        or_(
                            JournalEntryLine.description.ilike(f"%{kw}%"),
                            JournalEntryLine.gl_account_name.ilike(f"%{kw}%"),
                        )
                        for kw in ACCRUAL_KEYWORDS
                    ]
                ),
            )
            .all()
        )

        entries = []
        accrual_total = Decimal("0")
        no_reversal_count = 0

        for line in accrual_lines:
            entry = self.db.query(JournalEntry).filter(
                JournalEntry.id == line.journal_entry_id
            ).first()
            if not entry:
                continue

            amt = Decimal(str(line.debit_amount or 0)) + Decimal(str(line.credit_amount or 0))
            accrual_total += amt

            # Check for reversing entry in January of next year
            jan_start = date(year + 1, 1, 1)
            jan_end = date(year + 1, 1, 31)

            has_reversal = False
            reversal_entries = (
                self.db.query(JournalEntry)
                .filter(
                    JournalEntry.tenant_id == self.tenant_id,
                    JournalEntry.entry_date >= jan_start,
                    JournalEntry.entry_date <= jan_end,
                    JournalEntry.is_reversal == True,
                    JournalEntry.reversal_of_entry_id == entry.id,
                )
                .first()
            )
            if reversal_entries:
                has_reversal = True

            if not has_reversal:
                no_reversal_count += 1
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.INFO,
                    anomaly_type="yearend_accrual_no_reversal",
                    description=(
                        f"Accrual entry '{entry.description}' "
                        f"(${float(amt):,.2f}) in December has no "
                        f"reversing entry in January. Verify "
                        f"with CPA if reversal is needed."
                    ),
                    amount=amt,
                ))

            entries.append({
                "date": entry.entry_date.isoformat(),
                "description": entry.description,
                "gl_account": line.gl_account_name or line.gl_account_number or "",
                "amount": float(amt),
                "has_reversal": has_reversal,
            })

        if not entries:
            anomalies.append(self._make_anomaly(
                severity=AnomalySeverity.INFO,
                anomaly_type="yearend_no_accruals",
                description=(
                    "No accrual entries found in December. Common year-end "
                    "accruals include: accrued wages, accrued interest, "
                    "prepaid expenses, and unbilled revenue. "
                    "Verify with CPA that all accruals are recorded."
                ),
            ))

        data = {
            "accrual_entries_found": len(entries),
            "accrual_total": float(accrual_total),
            "entries": entries,
            "no_reversal_count": no_reversal_count,
        }

        if entries:
            msg = (
                f"{len(entries)} accrual entries found totaling "
                f"${float(accrual_total):,.2f}. {no_reversal_count} may "
                f"need reversing entries."
            )
        else:
            msg = "No accrual entries found in December. CPA review recommended."

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 12 — inventory_valuation
    # ------------------------------------------------------------------

    def _step_inventory_valuation(self) -> StepResult:
        year = self._close_year()
        anomalies: list[AnomalyItem] = []

        inventory_items = (
            self.db.query(InventoryItem)
            .join(Product, InventoryItem.product_id == Product.id)
            .filter(
                InventoryItem.company_id == self.tenant_id,
                Product.is_inventory_tracked == True,
            )
            .all()
        )

        total_value = Decimal("0")
        total_units = 0
        products_valued = 0
        products_no_cost = 0
        zero_cost_units = 0
        inventory_lines = []

        for item in inventory_items:
            product = self.db.query(Product).filter(Product.id == item.product_id).first()
            if not product:
                continue

            on_hand = item.quantity_on_hand or 0
            total_units += on_hand
            cost_price = Decimal(str(product.cost_price)) if product.cost_price else None
            cost_available = cost_price is not None and cost_price > 0

            if cost_available:
                item_value = Decimal(str(on_hand)) * cost_price
                total_value += item_value
                products_valued += 1
            else:
                item_value = Decimal("0")
                if on_hand > 0:
                    products_no_cost += 1
                    zero_cost_units += on_hand
                    anomalies.append(self._make_anomaly(
                        severity=AnomalySeverity.WARNING,
                        anomaly_type="yearend_inventory_no_cost",
                        entity_type="inventory_item",
                        entity_id=item.id,
                        description=(
                            f"{product.name}: {on_hand} units on hand but no "
                            f"cost price set. Cannot compute inventory value. "
                            f"Set cost_price on product for accurate balance sheet."
                        ),
                    ))

            inventory_lines.append({
                "product_name": product.name,
                "sku": product.sku or "",
                "quantity_on_hand": on_hand,
                "unit_cost": float(cost_price) if cost_available else None,
                "total_value": float(item_value),
                "cost_available": cost_available,
            })

        if total_value == 0 and total_units > 0:
            anomalies.append(self._make_anomaly(
                severity=AnomalySeverity.WARNING,
                anomaly_type="yearend_inventory_value_zero",
                description=(
                    "Year-end inventory value computes to $0 but units are on "
                    "hand. Cost prices may not be set. Verify with CPA for "
                    "balance sheet."
                ),
            ))

        data = {
            "snapshot_date": date(year, 12, 31).isoformat(),
            "total_inventory_value": float(total_value),
            "products_valued": products_valued,
            "products_no_cost": products_no_cost,
            "zero_cost_units_on_hand": zero_cost_units,
            "inventory_lines": inventory_lines,
        }

        msg = (
            f"Year-end inventory: {len(inventory_lines)} products, "
            f"{total_units} units, total value "
            f"${float(total_value):,.2f}. {products_no_cost} products "
            f"missing cost price."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 13 — retained_earnings_summary
    # ------------------------------------------------------------------

    def _step_retained_earnings_summary(self) -> StepResult:
        year = self._close_year()
        anomalies: list[AnomalyItem] = []

        # Net income from full_year_summary
        fys = self.step_results.get("full_year_summary", {})
        net_income = Decimal(str(
            fys.get("annual_income_statement", {}).get("net_income", 0)
        ))

        # Find distributions for the year
        dist_lines = (
            self.db.query(JournalEntryLine)
            .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
            .filter(
                JournalEntry.tenant_id == self.tenant_id,
                JournalEntry.entry_date >= date(year, 1, 1),
                JournalEntry.entry_date <= date(year, 12, 31),
                JournalEntry.status != "voided",
                or_(
                    *[
                        or_(
                            JournalEntryLine.description.ilike(f"%{kw}%"),
                            JournalEntryLine.gl_account_name.ilike(f"%{kw}%"),
                        )
                        for kw in DISTRIBUTION_KEYWORDS
                    ]
                ),
            )
            .all()
        )

        distributions = Decimal("0")
        distribution_entries = []
        for line in dist_lines:
            entry = self.db.query(JournalEntry).filter(
                JournalEntry.id == line.journal_entry_id
            ).first()
            amt = Decimal(str(line.debit_amount or 0))
            distributions += amt
            if entry:
                distribution_entries.append({
                    "date": entry.entry_date.isoformat(),
                    "description": entry.description,
                    "amount": float(amt),
                })

        # Find beginning retained earnings
        beginning_re = None
        re_lines = (
            self.db.query(JournalEntryLine)
            .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
            .filter(
                JournalEntry.tenant_id == self.tenant_id,
                JournalEntry.status != "voided",
                or_(
                    JournalEntryLine.gl_account_name.ilike("%retained%"),
                    JournalEntryLine.gl_account_name.ilike("%equity%"),
                ),
            )
            .all()
        )

        if re_lines:
            # Use net of debits and credits as beginning balance
            total_credits = sum(Decimal(str(l.credit_amount or 0)) for l in re_lines)
            total_debits = sum(Decimal(str(l.debit_amount or 0)) for l in re_lines)
            beginning_re = total_credits - total_debits

        calculation_available = beginning_re is not None
        ending_re = None
        if calculation_available:
            ending_re = beginning_re + net_income - distributions
        else:
            anomalies.append(self._make_anomaly(
                severity=AnomalySeverity.INFO,
                anomaly_type="yearend_retained_earnings_unavailable",
                description=(
                    "Beginning retained earnings balance could not be found "
                    "in journal entries. CPA will need to provide this figure "
                    "for the year-end balance sheet."
                ),
            ))

        data = {
            "net_income_for_year": float(net_income),
            "distributions_for_year": float(distributions),
            "beginning_retained_earnings": float(beginning_re) if beginning_re is not None else None,
            "ending_retained_earnings": float(ending_re) if ending_re is not None else None,
            "calculation_available": calculation_available,
            "distribution_entries": distribution_entries,
        }

        if calculation_available:
            msg = (
                f"Net income: ${float(net_income):,.2f}. "
                f"Distributions: ${float(distributions):,.2f}. "
                f"Ending retained earnings: ${float(ending_re):,.2f}."
            )
        else:
            msg = (
                f"Net income: ${float(net_income):,.2f}. Beginning retained "
                f"earnings unavailable — provide to CPA."
            )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # Override generate_report for year-end specific report
    # ------------------------------------------------------------------

    def _step_generate_report(self) -> StepResult:
        # Gather all step data
        revenue_data = self.step_results.get("revenue_summary", {})
        payments_data = self.step_results.get("reconcile_payments", {})
        aging_data = self.step_results.get("ar_aging_snapshot", {})
        statements_data = self.step_results.get("customer_statements", {})
        anomaly_data = self.step_results.get("anomaly_detection", {})
        comparison_data = self.step_results.get("prior_period_comparison", {})
        fys_data = self.step_results.get("full_year_summary", {})
        depr_data = self.step_results.get("depreciation_review", {})
        accruals_data = self.step_results.get("accruals_review", {})
        inv_data = self.step_results.get("inventory_valuation", {})
        re_data = self.step_results.get("retained_earnings_summary", {})

        critical = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.CRITICAL)
        warning = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.WARNING)
        info = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.INFO)

        year = self._close_year()
        annual_is = fys_data.get("annual_income_statement", {})

        executive_summary = {
            "year": year,
            "period": f"December {year}",
            "total_revenue": annual_is.get("total_revenue", 0),
            "net_income": annual_is.get("net_income", 0),
            "net_margin_pct": annual_is.get("net_margin_pct", 0),
            "total_ar": aging_data.get("total_ar", 0),
            "total_inventory_value": inv_data.get("total_inventory_value", 0),
            "total_depreciation": depr_data.get("total_depreciation_posted", 0),
            "accrual_entries_found": accruals_data.get("accrual_entries_found", 0),
            "ending_retained_earnings": re_data.get("ending_retained_earnings"),
            "invoice_count": revenue_data.get("invoice_count", 0),
            "anomaly_count": self.job.anomaly_count,
            "critical_anomaly_count": critical,
            "warning_anomaly_count": warning,
            "info_anomaly_count": info,
            "collection_rate_pct": anomaly_data.get("collection_rate_pct", 0),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": self.dry_run,
        }

        self.step_results["generate_report"] = {"report_generated": True}

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
        }

        from app.services.agents.approval_gate import ApprovalGateService
        self.job.report_payload["report_html"] = ApprovalGateService.generate_review_html(self.job)

        self.db.commit()

        msg = (
            f"Year-end close report ready for {year}. "
            f"{self.job.anomaly_count} anomalies "
            f"({critical} critical, {warning} warning, {info} info). "
            f"Ready for accountant review."
        )

        return StepResult(message=msg, data={"report_generated": True}, anomalies=[])
