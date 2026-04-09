"""Annual Budget Agent — Phase 13.

Annual agent that uses prior year actuals to generate a draft budget
for the coming year. Business owner adjusts assumptions (growth rate,
cost changes) and the agent produces structured budget figures. The
output feeds Phase 9 (Budget vs. Actual) as the formal budget
comparison basis.

Steps:
  1. pull_prior_year_actuals
  2. compute_quarterly_baseline
  3. apply_growth_assumptions
  4. generate_budget_lines
  5. generate_report
"""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import ClassVar

from sqlalchemy.orm import Session

from app.schemas.agent import (
    AgentJobType,
    AnomalyItem,
    AnomalySeverity,
    StepResult,
)
from app.services.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# Default growth assumptions (overridable via job metadata)
DEFAULT_REVENUE_GROWTH_PCT = Decimal("5.0")
DEFAULT_COGS_GROWTH_PCT = Decimal("3.0")
DEFAULT_EXPENSE_GROWTH_PCT = Decimal("3.0")

MONTH_NAMES = [
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec",
]

QUARTER_MONTHS = {
    "q1": (1, 3),
    "q2": (4, 6),
    "q3": (7, 9),
    "q4": (10, 12),
}

QUARTER_LABELS = {
    "q1": "Jan–Mar",
    "q2": "Apr–Jun",
    "q3": "Jul–Sep",
    "q4": "Oct–Dec",
}


class AnnualBudgetAgent(BaseAgent):
    """Annual agent that generates a draft budget from prior year actuals."""

    JOB_TYPE = AgentJobType.ANNUAL_BUDGET

    DEFAULT_REVENUE_GROWTH_PCT = DEFAULT_REVENUE_GROWTH_PCT
    DEFAULT_COGS_GROWTH_PCT = DEFAULT_COGS_GROWTH_PCT
    DEFAULT_EXPENSE_GROWTH_PCT = DEFAULT_EXPENSE_GROWTH_PCT

    STEPS: ClassVar[list[str]] = [
        "pull_prior_year_actuals",
        "compute_quarterly_baseline",
        "apply_growth_assumptions",
        "generate_budget_lines",
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

    def _get_assumptions(self) -> dict:
        """Load growth assumptions from job metadata or use defaults."""
        payload = self.job.report_payload or {}
        assumptions = payload.get("assumptions")
        if assumptions:
            return {
                "revenue_growth_pct": Decimal(str(assumptions.get("revenue_growth_pct", self.DEFAULT_REVENUE_GROWTH_PCT))),
                "cogs_growth_pct": Decimal(str(assumptions.get("cogs_growth_pct", self.DEFAULT_COGS_GROWTH_PCT))),
                "expense_growth_pct": Decimal(str(assumptions.get("expense_growth_pct", self.DEFAULT_EXPENSE_GROWTH_PCT))),
                "source": "user_provided",
            }
        return {
            "revenue_growth_pct": self.DEFAULT_REVENUE_GROWTH_PCT,
            "cogs_growth_pct": self.DEFAULT_COGS_GROWTH_PCT,
            "expense_growth_pct": self.DEFAULT_EXPENSE_GROWTH_PCT,
            "source": "defaults",
        }

    @staticmethod
    def _extract_income_data(income_stmt: dict) -> dict:
        """Normalize income statement to consistent Decimal-based structure."""
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
    # STEP 1 — pull_prior_year_actuals
    # ------------------------------------------------------------------

    def _step_pull_prior_year_actuals(self) -> StepResult:
        from app.services.financial_report_service import get_income_statement

        budget_year = self._period_start().year
        prior_year = budget_year - 1
        anomalies: list[AnomalyItem] = []

        # Full prior year
        prior_start = date(prior_year, 1, 1)
        prior_end = date(prior_year, 12, 31)
        annual_stmt = get_income_statement(
            self.db, self.tenant_id, prior_start, prior_end,
        )
        annual_data = self._extract_income_data(annual_stmt)

        # Quarterly breakdown
        quarterly = {}
        q_dates = [
            ("q1", date(prior_year, 1, 1), date(prior_year, 3, 31)),
            ("q2", date(prior_year, 4, 1), date(prior_year, 6, 30)),
            ("q3", date(prior_year, 7, 1), date(prior_year, 9, 30)),
            ("q4", date(prior_year, 10, 1), date(prior_year, 12, 31)),
        ]
        for q_key, q_start, q_end in q_dates:
            q_stmt = get_income_statement(
                self.db, self.tenant_id, q_start, q_end,
            )
            quarterly[q_key] = self._extract_income_data(q_stmt)

        data_available = (
            annual_data["total_revenue"] != 0
            or annual_data["total_expenses"] != 0
        )

        if not data_available:
            anomalies.append(self._make_anomaly(
                severity=AnomalySeverity.WARNING,
                anomaly_type="budget_no_prior_year_data",
                description=(
                    f"No financial data found for {prior_year}. Budget will be "
                    f"based on available partial data or manual entry required."
                ),
            ))

        data = {
            "prior_year": prior_year,
            "budget_year": budget_year,
            "annual": annual_data,
            "quarterly": quarterly,
            "data_available": data_available,
        }

        rev = annual_data["total_revenue"]
        net = annual_data["net_income"]

        msg = (
            f"Prior year {prior_year} actuals: Revenue ${rev:,.2f}, "
            f"Net Income ${net:,.2f}. Quarterly breakdown loaded."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 2 — compute_quarterly_baseline
    # ------------------------------------------------------------------

    def _step_compute_quarterly_baseline(self) -> StepResult:
        prior = self.step_results.get("pull_prior_year_actuals", {})
        annual = prior.get("annual", {})
        quarterly = prior.get("quarterly", {})

        def compute_shares(metric: str) -> dict:
            annual_total = Decimal(str(annual.get(metric, 0)))
            if annual_total == 0:
                return {"q1": 0.25, "q2": 0.25, "q3": 0.25, "q4": 0.25}
            shares = {}
            for q in ["q1", "q2", "q3", "q4"]:
                q_val = Decimal(str(quarterly.get(q, {}).get(metric, 0)))
                shares[q] = float(q_val / annual_total)
            return shares

        rev_shares = compute_shares("total_revenue")
        cogs_shares = compute_shares("total_cogs")
        exp_shares = compute_shares("total_expenses")

        annual_rev = Decimal(str(annual.get("total_revenue", 0)))
        annual_ni = Decimal(str(annual.get("net_income", 0)))

        avg_monthly_rev = float(annual_rev / 12) if annual_rev else 0.0
        avg_monthly_ni = float(annual_ni / 12)

        # Best and worst quarter by revenue
        q_revs = {q: quarterly.get(q, {}).get("total_revenue", 0) for q in ["q1", "q2", "q3", "q4"]}
        best_q = max(q_revs, key=q_revs.get)
        worst_q = min(q_revs, key=q_revs.get)

        # Seasonality variance
        if float(annual_rev) > 0:
            seasonality_var = (q_revs[best_q] - q_revs[worst_q]) / float(annual_rev) * 100
        else:
            seasonality_var = 0.0

        data = {
            "revenue_quarterly_shares": rev_shares,
            "cogs_quarterly_shares": cogs_shares,
            "expense_quarterly_shares": exp_shares,
            "average_monthly_revenue": avg_monthly_rev,
            "average_monthly_net_income": avg_monthly_ni,
            "best_revenue_quarter": best_q.upper(),
            "worst_revenue_quarter": worst_q.upper(),
            "seasonality_variance_pct": round(seasonality_var, 1),
        }

        msg = (
            f"Quarterly baseline computed. Seasonality variance: "
            f"{seasonality_var:.1f}%. Best quarter: {best_q.upper()}, "
            f"worst: {worst_q.upper()}."
        )

        return StepResult(message=msg, data=data, anomalies=[])

    # ------------------------------------------------------------------
    # STEP 3 — apply_growth_assumptions
    # ------------------------------------------------------------------

    def _step_apply_growth_assumptions(self) -> StepResult:
        prior = self.step_results.get("pull_prior_year_actuals", {})
        annual = prior.get("annual", {})
        assumptions = self._get_assumptions()
        anomalies: list[AnomalyItem] = []

        rev_growth = assumptions["revenue_growth_pct"]
        cogs_growth = assumptions["cogs_growth_pct"]
        exp_growth = assumptions["expense_growth_pct"]

        prior_rev = Decimal(str(annual.get("total_revenue", 0)))
        prior_cogs = Decimal(str(annual.get("total_cogs", 0)))
        prior_gp = Decimal(str(annual.get("gross_profit", 0)))
        prior_exp = Decimal(str(annual.get("total_expenses", 0)))
        prior_ni = Decimal(str(annual.get("net_income", 0)))

        budget_rev = (prior_rev * (1 + rev_growth / 100)).quantize(Decimal("0.01"), ROUND_HALF_UP)
        budget_cogs = (prior_cogs * (1 + cogs_growth / 100)).quantize(Decimal("0.01"), ROUND_HALF_UP)
        budget_gp = budget_rev - budget_cogs
        budget_exp = (prior_exp * (1 + exp_growth / 100)).quantize(Decimal("0.01"), ROUND_HALF_UP)
        budget_ni = budget_gp - budget_exp

        budget_gm_pct = float(budget_gp / budget_rev * 100) if budget_rev else 0.0
        budget_nm_pct = float(budget_ni / budget_rev * 100) if budget_rev else 0.0

        if budget_ni < 0:
            anomalies.append(self._make_anomaly(
                severity=AnomalySeverity.WARNING,
                anomaly_type="budget_projects_loss",
                description=(
                    f"With current assumptions, budget projects a net loss of "
                    f"${float(abs(budget_ni)):,.2f}. Consider adjusting growth "
                    f"rates or expense targets."
                ),
                amount=abs(budget_ni),
            ))

        # Apply growth to GL account lines
        budget_lines = []
        for line in annual.get("revenue_lines", []):
            prior_amt = Decimal(str(line.get("amount", 0)))
            budget_amt = (prior_amt * (1 + rev_growth / 100)).quantize(Decimal("0.01"), ROUND_HALF_UP)
            budget_lines.append({
                "gl_account_number": line.get("account_number", ""),
                "gl_account_name": line.get("account_name", ""),
                "line_type": "revenue",
                "prior_amount": float(prior_amt),
                "growth_pct": float(rev_growth),
                "budget_amount": float(budget_amt),
            })
        for line in annual.get("cogs_lines", []):
            prior_amt = Decimal(str(line.get("amount", 0)))
            budget_amt = (prior_amt * (1 + cogs_growth / 100)).quantize(Decimal("0.01"), ROUND_HALF_UP)
            budget_lines.append({
                "gl_account_number": line.get("account_number", ""),
                "gl_account_name": line.get("account_name", ""),
                "line_type": "cogs",
                "prior_amount": float(prior_amt),
                "growth_pct": float(cogs_growth),
                "budget_amount": float(budget_amt),
            })
        for line in annual.get("expense_lines", []):
            prior_amt = Decimal(str(line.get("amount", 0)))
            budget_amt = (prior_amt * (1 + exp_growth / 100)).quantize(Decimal("0.01"), ROUND_HALF_UP)
            budget_lines.append({
                "gl_account_number": line.get("account_number", ""),
                "gl_account_name": line.get("account_name", ""),
                "line_type": "expense",
                "prior_amount": float(prior_amt),
                "growth_pct": float(exp_growth),
                "budget_amount": float(budget_amt),
            })

        data = {
            "assumptions_used": {
                "revenue_growth_pct": float(rev_growth),
                "cogs_growth_pct": float(cogs_growth),
                "expense_growth_pct": float(exp_growth),
                "source": assumptions["source"],
            },
            "prior_year_annual": {
                "revenue": float(prior_rev),
                "cogs": float(prior_cogs),
                "gross_profit": float(prior_gp),
                "expenses": float(prior_exp),
                "net_income": float(prior_ni),
            },
            "budget_year_annual": {
                "revenue": float(budget_rev),
                "cogs": float(budget_cogs),
                "gross_profit": float(budget_gp),
                "expenses": float(budget_exp),
                "net_income": float(budget_ni),
                "gross_margin_pct": round(budget_gm_pct, 1),
                "net_margin_pct": round(budget_nm_pct, 1),
            },
            "budget_lines": budget_lines,
        }

        budget_year = self._period_start().year
        msg = (
            f"Budget year {budget_year} projected: Revenue "
            f"${float(budget_rev):,.2f} (+{float(rev_growth):.1f}%), "
            f"Net Income ${float(budget_ni):,.2f} "
            f"({budget_nm_pct:.1f}% margin)."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 4 — generate_budget_lines
    # ------------------------------------------------------------------

    def _step_generate_budget_lines(self) -> StepResult:
        baseline = self.step_results.get("compute_quarterly_baseline", {})
        growth = self.step_results.get("apply_growth_assumptions", {})
        budget_annual = growth.get("budget_year_annual", {})
        budget_lines_raw = growth.get("budget_lines", [])
        budget_year = self._period_start().year

        rev_shares = baseline.get("revenue_quarterly_shares", {"q1": 0.25, "q2": 0.25, "q3": 0.25, "q4": 0.25})
        cogs_shares = baseline.get("cogs_quarterly_shares", {"q1": 0.25, "q2": 0.25, "q3": 0.25, "q4": 0.25})
        exp_shares = baseline.get("expense_quarterly_shares", {"q1": 0.25, "q2": 0.25, "q3": 0.25, "q4": 0.25})

        annual_rev = Decimal(str(budget_annual.get("revenue", 0)))
        annual_cogs = Decimal(str(budget_annual.get("cogs", 0)))
        annual_gp = Decimal(str(budget_annual.get("gross_profit", 0)))
        annual_exp = Decimal(str(budget_annual.get("expenses", 0)))
        annual_ni = Decimal(str(budget_annual.get("net_income", 0)))

        # Quarterly budget using seasonal shares
        quarterly = {}
        for q in ["q1", "q2", "q3", "q4"]:
            q_rev = float((annual_rev * Decimal(str(rev_shares[q]))).quantize(Decimal("0.01"), ROUND_HALF_UP))
            q_cogs = float((annual_cogs * Decimal(str(cogs_shares[q]))).quantize(Decimal("0.01"), ROUND_HALF_UP))
            q_exp = float((annual_exp * Decimal(str(exp_shares[q]))).quantize(Decimal("0.01"), ROUND_HALF_UP))
            q_gp = q_rev - q_cogs
            q_ni = q_gp - q_exp

            quarterly[q] = {
                "revenue": q_rev,
                "cogs": q_cogs,
                "gross_profit": q_gp,
                "expenses": q_exp,
                "net_income": q_ni,
                "period": f"{QUARTER_LABELS[q]} {budget_year}",
            }

        # Also build Phase 9 compatible quarterly_breakdown (Q1, Q2, ...)
        # that _extract_budget_for_period expects
        quarterly_breakdown = {}
        for q in ["q1", "q2", "q3", "q4"]:
            q_data = quarterly[q]
            quarterly_breakdown[q.upper()] = {
                "total_revenue": q_data["revenue"],
                "total_cogs": q_data["cogs"],
                "gross_profit": q_data["gross_profit"],
                "gross_margin_pct": float(Decimal(str(q_data["gross_profit"])) / Decimal(str(q_data["revenue"])) * 100) if q_data["revenue"] else 0.0,
                "total_expenses": q_data["expenses"],
                "net_income": q_data["net_income"],
                "net_margin_pct": float(Decimal(str(q_data["net_income"])) / Decimal(str(q_data["revenue"])) * 100) if q_data["revenue"] else 0.0,
                "revenue_lines": [],
                "cogs_lines": [],
                "expense_lines": [],
            }

        # Monthly budget (divide each quarter evenly by 3)
        monthly = {}
        q_to_months = {
            "q1": ["jan", "feb", "mar"],
            "q2": ["apr", "may", "jun"],
            "q3": ["jul", "aug", "sep"],
            "q4": ["oct", "nov", "dec"],
        }
        for q, months in q_to_months.items():
            q_data = quarterly[q]
            for m in months:
                monthly[m] = {
                    "revenue": round(q_data["revenue"] / 3, 2),
                    "cogs": round(q_data["cogs"] / 3, 2),
                    "expenses": round(q_data["expenses"] / 3, 2),
                }

        # GL line budget with quarterly breakdown
        gl_lines = []
        for bl in budget_lines_raw:
            line_annual = Decimal(str(bl["budget_amount"]))
            line_type = bl["line_type"]

            if line_type == "revenue":
                shares = rev_shares
            elif line_type == "cogs":
                shares = cogs_shares
            else:
                shares = exp_shares

            gl_lines.append({
                "gl_account_number": bl["gl_account_number"],
                "gl_account_name": bl["gl_account_name"],
                "line_type": line_type,
                "annual_budget": float(line_annual),
                "q1_budget": float((line_annual * Decimal(str(shares["q1"]))).quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "q2_budget": float((line_annual * Decimal(str(shares["q2"]))).quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "q3_budget": float((line_annual * Decimal(str(shares["q3"]))).quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "q4_budget": float((line_annual * Decimal(str(shares["q4"]))).quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "monthly_budget": float((line_annual / 12).quantize(Decimal("0.01"), ROUND_HALF_UP)),
            })

        budget_structure = {
            "budget_year": budget_year,
            "annual": {
                "revenue": float(annual_rev),
                "cogs": float(annual_cogs),
                "gross_profit": float(annual_gp),
                "expenses": float(annual_exp),
                "net_income": float(annual_ni),
            },
            "quarterly": quarterly,
            "quarterly_breakdown": quarterly_breakdown,
            "monthly": monthly,
            "gl_lines": gl_lines,
        }

        data = budget_structure

        msg = (
            f"Budget lines generated: {len(gl_lines)} GL accounts across "
            f"4 quarters. Annual revenue target: ${float(annual_rev):,.2f}."
        )

        return StepResult(message=msg, data=data, anomalies=[])

    # ------------------------------------------------------------------
    # STEP 5 — generate_report
    # ------------------------------------------------------------------

    def _step_generate_report(self) -> StepResult:
        prior = self.step_results.get("pull_prior_year_actuals", {})
        growth = self.step_results.get("apply_growth_assumptions", {})
        budget_data = self.step_results.get("generate_budget_lines", {})
        assumptions = growth.get("assumptions_used", {})
        budget_annual = growth.get("budget_year_annual", {})
        budget_year = self._period_start().year
        prior_year = budget_year - 1

        critical = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.CRITICAL)

        quarterly_rev = {}
        for q in ["q1", "q2", "q3", "q4"]:
            quarterly_rev[q] = budget_data.get("quarterly", {}).get(q, {}).get("revenue", 0)

        executive_summary = {
            "budget_year": budget_year,
            "prior_year": prior_year,
            "assumptions": {
                "revenue_growth_pct": assumptions.get("revenue_growth_pct", 5.0),
                "cogs_growth_pct": assumptions.get("cogs_growth_pct", 3.0),
                "expense_growth_pct": assumptions.get("expense_growth_pct", 3.0),
            },
            "annual_revenue_target": budget_annual.get("revenue", 0),
            "annual_net_income_target": budget_annual.get("net_income", 0),
            "net_margin_target_pct": budget_annual.get("net_margin_pct", 0),
            "quarterly_revenue_targets": quarterly_rev,
            "projects_loss": budget_annual.get("net_income", 0) < 0,
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
            # Budget structure for Phase 9 queryability
            "budget": budget_data,
        }

        self.job.report_payload["report_html"] = self._build_report_html(
            executive_summary, growth, budget_data,
        )
        self.db.commit()

        msg = (
            f"Annual budget for {budget_year} ready. "
            f"Revenue target: ${budget_annual.get('revenue', 0):,.2f}."
        )

        return StepResult(message=msg, data={"report_generated": True}, anomalies=[])

    def _build_report_html(
        self, summary: dict, growth: dict, budget_data: dict,
    ) -> str:
        dry_run_badge = (
            '<span style="background:#f59e0b;color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:12px;margin-left:8px;">DRY RUN</span>'
            if self.dry_run else ""
        )

        budget_year = summary["budget_year"]
        prior_year = summary["prior_year"]
        assumptions = summary.get("assumptions", {})
        rev_growth = assumptions.get("revenue_growth_pct", 5.0)
        cogs_growth = assumptions.get("cogs_growth_pct", 3.0)
        exp_growth = assumptions.get("expense_growth_pct", 3.0)

        assumptions_html = (
            f'<div style="background:#fffbeb;border-radius:6px;padding:12px 16px;margin-bottom:24px;">'
            f'<p style="margin:0;color:#92400e;font-weight:600;">'
            f'This budget is based on {prior_year} actuals with {rev_growth:.1f}% revenue growth, '
            f'{cogs_growth:.1f}% COGS growth, and {exp_growth:.1f}% expense growth applied. '
            f'Adjust assumptions and re-run to model different scenarios.'
            f'</p></div>'
        )

        budget_annual = growth.get("budget_year_annual", {})
        prior_annual = growth.get("prior_year_annual", {})

        # Metric cards
        b_rev = budget_annual.get("revenue", 0)
        b_ni = budget_annual.get("net_income", 0)
        b_gm = budget_annual.get("gross_margin_pct", 0)
        b_nm = budget_annual.get("net_margin_pct", 0)

        # Quarterly targets table
        quarterly = budget_data.get("quarterly", {})
        q_rows = ""
        for q in ["q1", "q2", "q3", "q4"]:
            qd = quarterly.get(q, {})
            q_rows += (
                f'<tr><td>{q.upper()}</td>'
                f'<td>{qd.get("period", "")}</td>'
                f'<td style="text-align:right;">${qd.get("revenue", 0):,.2f}</td>'
                f'<td style="text-align:right;">${qd.get("gross_profit", 0):,.2f}</td>'
                f'<td style="text-align:right;">${qd.get("expenses", 0):,.2f}</td>'
                f'<td style="text-align:right;">${qd.get("net_income", 0):,.2f}</td></tr>'
            )

        # Monthly revenue table
        monthly = budget_data.get("monthly", {})
        month_headers = "".join(f"<th>{m.capitalize()}</th>" for m in MONTH_NAMES)
        _empty = {}
        month_cells = "".join(
            f'<td style="text-align:right;">${monthly.get(m, _empty).get("revenue", 0):,.0f}</td>'
            for m in MONTH_NAMES
        )

        # GL lines
        budget_lines = growth.get("budget_lines", [])
        gl_rows = ""
        for bl in budget_lines:
            change_amt = bl["budget_amount"] - bl["prior_amount"]
            gl_rows += (
                f'<tr><td>{bl["gl_account_number"]} {bl["gl_account_name"]}</td>'
                f'<td style="text-align:right;">${bl["prior_amount"]:,.2f}</td>'
                f'<td style="text-align:right;">${bl["budget_amount"]:,.2f}</td>'
                f'<td style="text-align:right;">${change_amt:,.2f}</td>'
                f'<td style="text-align:right;">{bl["growth_pct"]:+.1f}%</td></tr>'
            )

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
            <h1>Annual Budget — {budget_year}{dry_run_badge}</h1>
            <div class="meta">Based on {prior_year} actuals &middot; Generated {summary.get('generated_at', '')}</div>

            {assumptions_html}

            <div class="cards">
                <div class="card">
                    <div class="card-value">${b_rev:,.0f}</div>
                    <div class="card-label">Revenue Target</div>
                </div>
                <div class="card">
                    <div class="card-value">${b_ni:,.0f}</div>
                    <div class="card-label">Net Income Target</div>
                </div>
                <div class="card">
                    <div class="card-value">{b_gm:.1f}%</div>
                    <div class="card-label">Gross Margin</div>
                </div>
                <div class="card">
                    <div class="card-value">{b_nm:.1f}%</div>
                    <div class="card-label">Net Margin</div>
                </div>
            </div>

            <h2>Quarterly Targets</h2>
            <table>
                <thead><tr><th>Quarter</th><th>Period</th><th style="text-align:right;">Revenue</th><th style="text-align:right;">Gross Profit</th><th style="text-align:right;">Expenses</th><th style="text-align:right;">Net Income</th></tr></thead>
                <tbody>{q_rows}</tbody>
            </table>

            <h2>Monthly Revenue Targets</h2>
            <table>
                <thead><tr>{month_headers}<th>Annual</th></tr></thead>
                <tbody><tr>{month_cells}<td style="text-align:right;font-weight:700;">${b_rev:,.0f}</td></tr></tbody>
            </table>

            <h2>GL Account Budget Lines</h2>
            <table>
                <thead><tr><th>GL Account</th><th style="text-align:right;">Prior Year</th><th style="text-align:right;">Budget</th><th style="text-align:right;">Change $</th><th style="text-align:right;">Change %</th></tr></thead>
                <tbody>{gl_rows or '<tr><td colspan="5" style="text-align:center;color:#71717a;">No GL line data available</td></tr>'}</tbody>
            </table>

            <p style="margin-top:24px;padding:12px;background:#f4f4f5;border-radius:6px;font-size:13px;color:#71717a;">
                To model a different growth scenario, re-run this agent with adjusted assumptions via the API or Agent Dashboard.
            </p>
        </div>
        </body>
        </html>
        """

    # ------------------------------------------------------------------
    # Override _assemble_report — generate_report step handles it
    # ------------------------------------------------------------------

    def _assemble_report(self) -> None:
        pass
