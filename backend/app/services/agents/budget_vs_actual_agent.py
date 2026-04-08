"""Budget vs. Actual Agent — Phase 9.

Quarterly agent that compares actual financial performance against the
prior year same period (budget proxy) and flags variances worth
investigating.  As formal budgets are built (Phase 13), this agent will
compare against those instead.

Steps:
  1. get_current_period_actuals — income statement for job period + YTD
  2. get_comparison_period — formal budget > prior year > prior quarter > none
  3. compute_variances — summary + GL-line level variance analysis
  4. generate_report — executive summary + HTML report
"""

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import ClassVar

from sqlalchemy.orm import Session

from app.models.agent import AgentJob
from app.schemas.agent import (
    AgentJobType,
    AnomalyItem,
    AnomalySeverity,
    StepResult,
)
from app.services.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# Flag any metric that varies > 15% from comparison
VARIANCE_THRESHOLD_PCT = 15.0


class BudgetVsActualAgent(BaseAgent):
    """Quarterly agent that compares actual vs budget/prior period."""

    JOB_TYPE = AgentJobType.BUDGET_VS_ACTUAL

    STEPS: ClassVar[list[str]] = [
        "get_current_period_actuals",
        "get_comparison_period",
        "compute_variances",
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

    def _period_start(self) -> date:
        return self.job.period_start

    def _period_end(self) -> date:
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

    @staticmethod
    def _extract_income_data(income_stmt: dict) -> dict:
        """Normalize income statement output to consistent structure."""
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

    # ------------------------------------------------------------------
    # STEP 1 — get_current_period_actuals
    # ------------------------------------------------------------------

    def _step_get_current_period_actuals(self) -> StepResult:
        from app.services.financial_report_service import get_income_statement

        period_start = self._period_start()
        period_end = self._period_end()

        # Period income statement
        period_stmt = get_income_statement(
            self.db, self.tenant_id, period_start, period_end,
        )
        period_data = self._extract_income_data(period_stmt)

        # YTD income statement (Jan 1 of current year to period_end)
        ytd_start = date(period_start.year, 1, 1)
        ytd_stmt = get_income_statement(
            self.db, self.tenant_id, ytd_start, period_end,
        )
        ytd_data = self._extract_income_data(ytd_stmt)

        data = {
            "period_label": f"{period_start} to {period_end}",
            "period": period_data,
            "ytd": ytd_data,
        }

        rev = period_data["total_revenue"]
        net = period_data["net_income"]
        margin = period_data["net_margin_pct"]

        msg = (
            f"Period: Revenue ${rev:,.2f}, "
            f"Net Income ${net:,.2f} "
            f"({margin:.1f}% margin)."
        )

        return StepResult(message=msg, data=data, anomalies=[])

    # ------------------------------------------------------------------
    # STEP 2 — get_comparison_period
    # ------------------------------------------------------------------

    def _step_get_comparison_period(self) -> StepResult:
        from app.services.financial_report_service import get_income_statement

        period_start = self._period_start()
        period_end = self._period_end()
        anomalies: list[AnomalyItem] = []

        # OPTION A — Formal budget (Phase 13)
        formal_budget = (
            self.db.query(AgentJob)
            .filter(
                AgentJob.tenant_id == self.tenant_id,
                AgentJob.job_type == "annual_budget",
                AgentJob.status == "complete",
            )
            .first()
        )

        if formal_budget and formal_budget.report_payload:
            # Extract budget figures for the matching quarter
            budget_data = self._extract_budget_for_period(
                formal_budget.report_payload, period_start, period_end,
            )
            if budget_data:
                data = {
                    "comparison_type": "formal_budget",
                    "comparison_label": "Budget",
                    "comparison_period_label": f"FY{period_start.year} Budget",
                    "comparison": budget_data,
                }
                return StepResult(
                    message=f"Comparison basis: formal_budget (FY{period_start.year} Budget).",
                    data=data, anomalies=[],
                )

        # OPTION B — Prior year same period
        prior_start = date(period_start.year - 1, period_start.month, period_start.day)
        prior_end = date(period_end.year - 1, period_end.month, period_end.day)

        prior_stmt = get_income_statement(
            self.db, self.tenant_id, prior_start, prior_end,
        )
        prior_data = self._extract_income_data(prior_stmt)

        # Check if prior year has any data
        if prior_data["total_revenue"] != 0 or prior_data["total_expenses"] != 0:
            period_label = f"{prior_start} to {prior_end}"
            data = {
                "comparison_type": "prior_year_same_period",
                "comparison_label": f"Prior Year ({prior_start.year})",
                "comparison_period_label": period_label,
                "comparison": prior_data,
            }
            return StepResult(
                message=f"Comparison basis: prior_year_same_period ({period_label}).",
                data=data, anomalies=[],
            )

        # OPTION C — Prior quarter
        # Compute the most recent completed quarter before this period
        q_month = ((period_start.month - 1) // 3) * 3 + 1
        q_start = date(period_start.year, q_month, 1)
        if q_start >= period_start:
            # Go back one quarter
            if q_month == 1:
                pq_start = date(period_start.year - 1, 10, 1)
                pq_end = date(period_start.year - 1, 12, 31)
            else:
                pq_month = q_month - 3
                pq_start = date(period_start.year, pq_month, 1)
                # End of prior quarter
                pq_end = q_start - timedelta(days=1)
        else:
            pq_start = q_start
            pq_end = date(period_start.year, q_month + 2, 28)  # approximate
            if q_month + 2 in (3, 12):
                pq_end = date(period_start.year, q_month + 2, 31)

        pq_stmt = get_income_statement(
            self.db, self.tenant_id, pq_start, pq_end,
        )
        pq_data = self._extract_income_data(pq_stmt)

        if pq_data["total_revenue"] != 0 or pq_data["total_expenses"] != 0:
            period_label = f"{pq_start} to {pq_end}"
            data = {
                "comparison_type": "prior_quarter",
                "comparison_label": f"Prior Quarter ({pq_start:%b}–{pq_end:%b %Y})",
                "comparison_period_label": period_label,
                "comparison": pq_data,
            }
            return StepResult(
                message=f"Comparison basis: prior_quarter ({period_label}).",
                data=data, anomalies=[],
            )

        # OPTION D — No comparison available
        anomalies.append(self._make_anomaly(
            severity=AnomalySeverity.INFO,
            anomaly_type="budget_no_comparison_basis",
            description=(
                "No budget or prior period data available for comparison. "
                "This report shows actuals only."
            ),
        ))

        data = {
            "comparison_type": "none",
            "comparison_label": "No Comparison",
            "comparison_period_label": "N/A",
            "comparison": None,
        }

        return StepResult(
            message="No comparison basis available.",
            data=data, anomalies=anomalies,
        )

    @staticmethod
    def _extract_budget_for_period(
        budget_payload: dict, period_start: date, period_end: date,
    ) -> dict | None:
        """Extract budget figures for the matching quarter from an annual budget report.

        Returns None if no matching quarter data is found.
        """
        # Annual budget report_payload stores quarterly breakdowns
        steps = budget_payload.get("steps", {})
        quarters = steps.get("quarterly_breakdown", {})
        if not quarters:
            return None

        # Try to find matching quarter
        quarter_num = (period_start.month - 1) // 3 + 1
        q_key = f"Q{quarter_num}"
        q_data = quarters.get(q_key)
        if not q_data:
            return None

        return q_data

    # ------------------------------------------------------------------
    # STEP 3 — compute_variances
    # ------------------------------------------------------------------

    def _step_compute_variances(self) -> StepResult:
        comparison_data = self.step_results.get("get_comparison_period", {})
        comparison_type = comparison_data.get("comparison_type", "none")

        if comparison_type == "none":
            return StepResult(
                message="No comparison data.",
                data={"variances_computed": False},
                anomalies=[],
            )

        actuals_data = self.step_results.get("get_current_period_actuals", {})
        period = actuals_data.get("period", {})
        comparison = comparison_data.get("comparison", {})
        comparison_label = comparison_data.get("comparison_label", "Comparison")
        anomalies: list[AnomalyItem] = []

        # Summary-level variances
        # Metrics where HIGHER actual is favorable
        favorable_when_higher = {"total_revenue", "gross_profit", "net_income"}
        # Metrics where LOWER actual is favorable
        favorable_when_lower = {"total_cogs", "total_expenses"}

        metrics = [
            ("Revenue", "total_revenue"),
            ("COGS", "total_cogs"),
            ("Gross Profit", "gross_profit"),
            ("Expenses", "total_expenses"),
            ("Net Income", "net_income"),
        ]

        summary_variances = []
        favorable_count = 0
        unfavorable_count = 0
        flagged_count = 0

        for label, key in metrics:
            actual = Decimal(str(period.get(key, 0)))
            comp = Decimal(str(comparison.get(key, 0)))
            variance_amount = actual - comp

            if comp != 0:
                variance_pct = float((actual - comp) / abs(comp) * 100)
            else:
                variance_pct = None

            # Determine favorable direction
            if key in favorable_when_higher:
                is_favorable = actual >= comp
            else:
                is_favorable = actual <= comp

            flagged = variance_pct is not None and abs(variance_pct) > VARIANCE_THRESHOLD_PCT

            if is_favorable:
                favorable_count += 1
            else:
                unfavorable_count += 1

            if flagged:
                flagged_count += 1
                severity = (
                    AnomalySeverity.WARNING if abs(variance_pct) < 25
                    else AnomalySeverity.CRITICAL
                )
                direction = "favorable" if is_favorable else "unfavorable"
                anomalies.append(self._make_anomaly(
                    severity=severity,
                    anomaly_type="budget_variance_significant",
                    description=(
                        f"{label}: actual ${float(actual):,.2f} vs {comparison_label} "
                        f"${float(comp):,.2f}. "
                        f"Variance: {variance_pct:+.1f}% ({direction})."
                    ),
                    amount=abs(variance_amount),
                ))

            summary_variances.append({
                "metric": label,
                "actual": float(actual),
                "comparison": float(comp),
                "variance_amount": float(variance_amount),
                "variance_pct": round(variance_pct, 1) if variance_pct is not None else None,
                "is_favorable": is_favorable,
                "flagged": flagged,
            })

        # GL line-level variances
        line_variances = []
        actual_lines = (
            period.get("revenue_lines", [])
            + period.get("cogs_lines", [])
            + period.get("expense_lines", [])
        )
        comp_lines = (
            comparison.get("revenue_lines", [])
            + comparison.get("cogs_lines", [])
            + comparison.get("expense_lines", [])
        )

        # Build lookup by account_number
        comp_by_acct: dict[str, dict] = {}
        for cl in comp_lines:
            acct_num = cl.get("account_number", "")
            if acct_num:
                comp_by_acct[acct_num] = cl

        for al in actual_lines:
            acct_num = al.get("account_number", "")
            acct_name = al.get("account_name", "")
            actual_amt = Decimal(str(al.get("amount", 0)))

            comp_line = comp_by_acct.get(acct_num, {})
            comp_amt = Decimal(str(comp_line.get("amount", 0)))

            if comp_amt == 0 and actual_amt == 0:
                continue

            line_var_amt = actual_amt - comp_amt
            if comp_amt != 0:
                line_var_pct = float((actual_amt - comp_amt) / abs(comp_amt) * 100)
            else:
                line_var_pct = None

            # Revenue accounts (4000-series) favorable when higher
            # COGS (5000) and expense (6000) favorable when lower
            if acct_num.startswith("4"):
                line_favorable = actual_amt >= comp_amt
            else:
                line_favorable = actual_amt <= comp_amt

            line_flagged = line_var_pct is not None and abs(line_var_pct) > VARIANCE_THRESHOLD_PCT

            if line_flagged:
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.INFO,
                    anomaly_type="budget_line_variance",
                    description=(
                        f"GL {acct_num} {acct_name}: ${float(actual_amt):,.2f} actual vs "
                        f"${float(comp_amt):,.2f} {comparison_label}. "
                        f"({line_var_pct:+.1f}%)"
                    ),
                    amount=abs(line_var_amt),
                ))

            line_variances.append({
                "gl_account_number": acct_num,
                "gl_account_name": acct_name,
                "actual": float(actual_amt),
                "comparison": float(comp_amt),
                "variance_amount": float(line_var_amt),
                "variance_pct": round(line_var_pct, 1) if line_var_pct is not None else None,
                "is_favorable": line_favorable,
                "flagged": line_flagged,
            })

        data = {
            "variances_computed": True,
            "summary_variances": summary_variances,
            "line_variances": line_variances,
            "favorable_count": favorable_count,
            "unfavorable_count": unfavorable_count,
            "flagged_count": flagged_count,
        }

        msg = (
            f"{favorable_count} favorable variances, "
            f"{unfavorable_count} unfavorable. "
            f"{flagged_count} exceed {VARIANCE_THRESHOLD_PCT}% threshold."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 4 — generate_report
    # ------------------------------------------------------------------

    def _step_generate_report(self) -> StepResult:
        actuals = self.step_results.get("get_current_period_actuals", {})
        comp_data = self.step_results.get("get_comparison_period", {})
        variance_data = self.step_results.get("compute_variances", {})

        period = actuals.get("period", {})
        comparison_type = comp_data.get("comparison_type", "none")
        comparison_label = comp_data.get("comparison_label", "No Comparison")

        # Revenue variance pct
        rev_var_pct = None
        ni_var_pct = None
        comp_revenue = None
        if variance_data.get("variances_computed"):
            for sv in variance_data.get("summary_variances", []):
                if sv["metric"] == "Revenue":
                    rev_var_pct = sv["variance_pct"]
                    comp_revenue = sv["comparison"]
                elif sv["metric"] == "Net Income":
                    ni_var_pct = sv["variance_pct"]

        # Quarter label
        q_num = (self._period_start().month - 1) // 3 + 1
        quarter_label = f"Q{q_num} {self._period_start().year}"

        critical = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.CRITICAL)

        executive_summary = {
            "period": f"{self._period_start()} to {self._period_end()}",
            "quarter_label": quarter_label,
            "comparison_type": comparison_type,
            "comparison_label": comparison_label,
            "actual_revenue": period.get("total_revenue", 0),
            "actual_net_income": period.get("net_income", 0),
            "actual_net_margin_pct": period.get("net_margin_pct", 0),
            "comparison_revenue": comp_revenue,
            "revenue_variance_pct": rev_var_pct,
            "net_income_variance_pct": ni_var_pct,
            "favorable_variances": variance_data.get("favorable_count", 0),
            "unfavorable_variances": variance_data.get("unfavorable_count", 0),
            "flagged_variances": variance_data.get("flagged_count", 0),
            "anomaly_count": self.job.anomaly_count,
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
            executive_summary, actuals, comp_data, variance_data,
        )
        self.db.commit()

        msg = (
            f"Budget vs. Actual report ready. "
            f"{quarter_label}, comparison: {comparison_label}."
        )

        return StepResult(message=msg, data={"report_generated": True}, anomalies=[])

    def _build_report_html(
        self,
        summary: dict,
        actuals: dict,
        comp_data: dict,
        variance_data: dict,
    ) -> str:
        dry_run_badge = (
            '<span style="background:#f59e0b;color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:12px;margin-left:8px;">DRY RUN</span>'
            if self.dry_run else ""
        )

        period_label = ""
        if self.job.period_start:
            period_label = (
                f"{self.job.period_start:%B %d, %Y} – {self.job.period_end:%B %d, %Y}"
                if self.job.period_end else str(self.job.period_start)
            )

        comparison_type = comp_data.get("comparison_type", "none")
        comparison_label = comp_data.get("comparison_label", "No Comparison")

        # Comparison basis banner
        banner_colors = {
            "formal_budget": ("#dcfce7", "#166534"),
            "prior_year_same_period": ("#dbeafe", "#1e40af"),
            "prior_quarter": ("#fffbeb", "#92400e"),
            "none": ("#f4f4f5", "#71717a"),
        }
        bg, text_color = banner_colors.get(comparison_type, ("#f4f4f5", "#71717a"))
        banner_html = (
            f'<div style="background:{bg};border-radius:6px;padding:12px 16px;margin-bottom:24px;">'
            f'<p style="margin:0;color:{text_color};font-weight:600;">'
            f'Comparison Basis: {comparison_label}</p></div>'
        )

        # Summary variance table
        variance_rows = ""
        if variance_data.get("variances_computed"):
            for sv in variance_data.get("summary_variances", []):
                var_pct = sv.get("variance_pct")
                var_pct_str = f"{var_pct:+.1f}%" if var_pct is not None else "—"
                fav = sv.get("is_favorable", True)
                arrow = "↑" if fav else "↓"
                color = "#16a34a" if fav else "#dc2626"
                flagged_style = 'background:#fef2f2;' if sv.get("flagged") and not fav else ""

                variance_rows += (
                    f'<tr style="{flagged_style}">'
                    f'<td><strong>{sv["metric"]}</strong></td>'
                    f'<td style="text-align:right;">${sv["actual"]:,.2f}</td>'
                    f'<td style="text-align:right;">${sv["comparison"]:,.2f}</td>'
                    f'<td style="text-align:right;">${sv["variance_amount"]:,.2f}</td>'
                    f'<td style="text-align:right;color:{color};">{arrow} {var_pct_str}</td>'
                    f'<td style="color:{color};">{"Favorable" if fav else "Unfavorable"}</td></tr>'
                )
        else:
            variance_rows = (
                '<tr><td colspan="6" style="text-align:center;color:#71717a;">'
                'No comparison data available</td></tr>'
            )

        # GL line detail
        line_rows = ""
        if variance_data.get("variances_computed"):
            lines = sorted(
                variance_data.get("line_variances", []),
                key=lambda x: abs(x.get("variance_pct") or 0),
                reverse=True,
            )
            for lv in lines:
                var_pct = lv.get("variance_pct")
                var_pct_str = f"{var_pct:+.1f}%" if var_pct is not None else "—"
                fav = lv.get("is_favorable", True)
                color = "#16a34a" if fav else "#dc2626"
                flagged_marker = " *" if lv.get("flagged") else ""

                line_rows += (
                    f'<tr><td>{lv["gl_account_number"]} {lv["gl_account_name"]}</td>'
                    f'<td style="text-align:right;">${lv["actual"]:,.2f}</td>'
                    f'<td style="text-align:right;">${lv["comparison"]:,.2f}</td>'
                    f'<td style="text-align:right;">${lv["variance_amount"]:,.2f}</td>'
                    f'<td style="text-align:right;color:{color};">{var_pct_str}{flagged_marker}</td>'
                    f'<td style="color:{color};">{"OK" if fav else "Review"}</td></tr>'
                )

        # Metric cards
        period = actuals.get("period", {})
        actual_rev = period.get("total_revenue", 0)
        actual_gp = period.get("gross_profit", 0)
        actual_ni = period.get("net_income", 0)
        actual_margin = period.get("net_margin_pct", 0)

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
            <h1>Budget vs. Actual{dry_run_badge}</h1>
            <div class="meta">{summary.get('quarter_label', '')} &middot; {period_label} &middot; Generated {summary.get('generated_at', '')}</div>

            {banner_html}

            <div class="cards">
                <div class="card">
                    <div class="card-value">${actual_rev:,.0f}</div>
                    <div class="card-label">Revenue</div>
                </div>
                <div class="card">
                    <div class="card-value">${actual_gp:,.0f}</div>
                    <div class="card-label">Gross Profit</div>
                </div>
                <div class="card">
                    <div class="card-value">${actual_ni:,.0f}</div>
                    <div class="card-label">Net Income</div>
                </div>
                <div class="card">
                    <div class="card-value">{actual_margin:.1f}%</div>
                    <div class="card-label">Net Margin</div>
                </div>
            </div>

            <h2>Summary Variances</h2>
            <table>
                <thead><tr><th>Metric</th><th style="text-align:right;">Actual</th><th style="text-align:right;">{comparison_label}</th><th style="text-align:right;">Variance $</th><th style="text-align:right;">Variance %</th><th>Status</th></tr></thead>
                <tbody>{variance_rows}</tbody>
            </table>

            <h2>GL Account Detail</h2>
            <table>
                <thead><tr><th>GL Account</th><th style="text-align:right;">Actual</th><th style="text-align:right;">{comparison_label}</th><th style="text-align:right;">Variance $</th><th style="text-align:right;">Variance %</th><th>Status</th></tr></thead>
                <tbody>{line_rows or '<tr><td colspan="6" style="text-align:center;">No GL line data</td></tr>'}</tbody>
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
