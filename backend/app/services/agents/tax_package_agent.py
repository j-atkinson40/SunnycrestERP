"""Tax Package Compilation Agent — Phase 12.

Annual agent that gathers outputs from all completed agents for a given
tax year and assembles a single organized packet for the CPA. This is the
capstone of the entire accounting agent suite — it turns 12 months of agent
work into one clean handoff document.

This agent is READ-ONLY. It does not run any calculations itself. It only
gathers, organizes, and presents data that other agents have already
produced and approved.

Steps:
  1. collect_agent_outputs
  2. assess_completeness
  3. compile_financial_statements
  4. compile_supporting_schedules
  5. generate_report
"""

import calendar
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import ClassVar

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.agent import AgentJob
from app.models.agent_anomaly import AgentAnomaly
from app.models.user import User
from app.schemas.agent import (
    AgentJobType,
    AnomalyItem,
    AnomalySeverity,
    StepResult,
)
from app.services.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# Expected agent types for a complete tax package
REQUIRED_AGENTS = {"year_end_close", "1099_prep"}
RECOMMENDED_AGENTS = {
    "month_end_close",       # x12 ideally
    "estimated_tax_prep",    # x4 ideally
    "inventory_reconciliation",
}
OPTIONAL_AGENTS = {
    "budget_vs_actual",
    "annual_budget",
    "expense_categorization",
}

# Readiness score weights
REQUIRED_WEIGHT = Decimal("0.6")
RECOMMENDED_WEIGHT = Decimal("0.4")

# Schedule labels
SCHEDULE_LABELS = {
    "schedule_a_1099": "Schedule A — 1099 Vendor List",
    "schedule_b_tax_estimates": "Schedule B — Estimated Tax Payments",
    "schedule_c_inventory": "Schedule C — Inventory Schedule",
    "schedule_d_ar_aging": "Schedule D — AR Aging Detail",
    "schedule_e_budget_vs_actual": "Schedule E — Budget vs. Actual Summary",
    "schedule_f_anomaly_summary": "Schedule F — Data Quality Notes",
}


class TaxPackageAgent(BaseAgent):
    """Annual agent that compiles a CPA-ready tax package from all agent outputs."""

    JOB_TYPE = AgentJobType.TAX_PACKAGE

    STEPS: ClassVar[list[str]] = [
        "collect_agent_outputs",
        "assess_completeness",
        "compile_financial_statements",
        "compile_supporting_schedules",
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

    def _tax_year(self) -> int:
        return self.job.period_start.year

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
    # STEP 1 — collect_agent_outputs
    # ------------------------------------------------------------------

    def _step_collect_agent_outputs(self) -> StepResult:
        year = self._tax_year()
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)

        completed_jobs = (
            self.db.query(AgentJob)
            .filter(
                AgentJob.tenant_id == self.tenant_id,
                AgentJob.status == "complete",
                AgentJob.period_start >= year_start,
                AgentJob.period_end <= year_end,
            )
            .order_by(AgentJob.completed_at.desc())
            .all()
        )

        # Group by job_type — keep most recent for each
        agents_found: dict[str, dict] = {}
        month_end_closes: dict[int, dict] = {}

        for job in completed_jobs:
            jt = job.job_type
            entry = {
                "job_id": job.id,
                "period": f"{job.period_start} to {job.period_end}",
                "approved_at": job.approved_at.isoformat() if job.approved_at else None,
                "anomaly_count": job.anomaly_count,
            }

            if jt == "month_end_close":
                month = job.period_start.month if job.period_start else None
                if month and month not in month_end_closes:
                    month_end_closes[month] = entry
            elif jt not in agents_found:
                agents_found[jt] = entry

        # Determine months missing
        months_found = sorted(month_end_closes.keys())
        months_missing = [m for m in range(1, 13) if m not in months_found]

        # Check required completeness
        required_complete = all(
            jt in agents_found for jt in REQUIRED_AGENTS
        )

        # Check recommended — count items met
        recommended_met = 0
        recommended_total = 5  # 12 months + 4 tax quarters + inventory
        if len(months_found) == 12:
            recommended_met += 1
        # Count estimated tax prep quarters
        est_tax_jobs = (
            self.db.query(AgentJob)
            .filter(
                AgentJob.tenant_id == self.tenant_id,
                AgentJob.status == "complete",
                AgentJob.job_type == "estimated_tax_prep",
                AgentJob.period_start >= year_start,
                AgentJob.period_end <= year_end,
            )
            .count()
        )
        if est_tax_jobs >= 4:
            recommended_met += 1
        if "inventory_reconciliation" in agents_found:
            recommended_met += 1
        # Additional recommended items
        if len(months_found) >= 6:
            recommended_met += 1  # partial credit for some months
        if est_tax_jobs >= 2:
            recommended_met += 1  # partial credit

        data = {
            "tax_year": year,
            "agents_found": agents_found,
            "month_end_closes": month_end_closes,
            "month_end_closes_found": len(months_found),
            "months_missing": months_missing,
            "required_complete": required_complete,
            "recommended_met": recommended_met,
            "recommended_total": recommended_total,
        }

        req_status = "complete" if required_complete else "INCOMPLETE"
        rec_status = f"{recommended_met}/{recommended_total}"

        msg = (
            f"Tax year {year}: found {len(agents_found) + len(month_end_closes)} "
            f"completed agent outputs. {len(months_found)}/12 months closed. "
            f"Required: {req_status}. Recommended: {rec_status}."
        )

        return StepResult(message=msg, data=data, anomalies=[])

    # ------------------------------------------------------------------
    # STEP 2 — assess_completeness
    # ------------------------------------------------------------------

    def _step_assess_completeness(self) -> StepResult:
        collected = self.step_results.get("collect_agent_outputs", {})
        agents_found = collected.get("agents_found", {})
        year = self._tax_year()
        anomalies: list[AnomalyItem] = []

        critical_gaps = 0
        warning_gaps = 0
        info_gaps = 0

        # CRITICAL: Year-end close
        if "year_end_close" not in agents_found:
            critical_gaps += 1
            anomalies.append(self._make_anomaly(
                severity=AnomalySeverity.CRITICAL,
                anomaly_type="tax_package_missing_year_end_close",
                description=(
                    f"Year-end close has not been completed for {year}. "
                    f"Annual financial statements are not available."
                ),
            ))

        # CRITICAL: 1099 prep
        if "1099_prep" not in agents_found:
            critical_gaps += 1
            anomalies.append(self._make_anomaly(
                severity=AnomalySeverity.CRITICAL,
                anomaly_type="tax_package_missing_1099_prep",
                description=(
                    f"1099 prep has not been run for {year}. "
                    f"Vendor filing list is not available."
                ),
            ))

        # WARNING: Months not closed
        months_found = collected.get("month_end_closes_found", 0)
        months_missing = collected.get("months_missing", [])
        if months_found < 12:
            warning_gaps += 1
            month_names = ", ".join(
                calendar.month_abbr[m] for m in months_missing
            )
            anomalies.append(self._make_anomaly(
                severity=AnomalySeverity.WARNING,
                anomaly_type="tax_package_months_not_closed",
                description=(
                    f"Only {months_found}/12 months have completed month-end "
                    f"closes. Months missing: {month_names}. Financial "
                    f"statements may be incomplete."
                ),
            ))

        # WARNING: Estimated tax prep quarters
        est_count = (
            self.db.query(AgentJob)
            .filter(
                AgentJob.tenant_id == self.tenant_id,
                AgentJob.status == "complete",
                AgentJob.job_type == "estimated_tax_prep",
                AgentJob.period_start >= date(year, 1, 1),
                AgentJob.period_end <= date(year, 12, 31),
            )
            .count()
        )
        if est_count < 4:
            warning_gaps += 1
            anomalies.append(self._make_anomaly(
                severity=AnomalySeverity.WARNING,
                anomaly_type="tax_package_missing_tax_estimates",
                description=(
                    f"Not all quarterly tax estimate reports are available "
                    f"for {year}. Found {est_count}/4 quarters."
                ),
            ))

        # INFO: Optional agents
        for agent_type, label in [
            ("inventory_reconciliation", "Inventory Reconciliation"),
            ("budget_vs_actual", "Budget vs. Actual"),
            ("annual_budget", "Annual Budget"),
        ]:
            if agent_type not in agents_found:
                info_gaps += 1
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.INFO,
                    anomaly_type=f"tax_package_missing_{agent_type}",
                    description=(
                        f"{label} has not been completed for {year}. "
                        f"This is optional but recommended."
                    ),
                ))

        # Readiness score
        required_met = sum(1 for jt in REQUIRED_AGENTS if jt in agents_found)
        required_total = len(REQUIRED_AGENTS)
        recommended_met = collected.get("recommended_met", 0)
        recommended_total = collected.get("recommended_total", 5)

        required_score = Decimal(str(required_met)) / Decimal(str(required_total)) if required_total else Decimal("1")
        recommended_score = Decimal(str(recommended_met)) / Decimal(str(recommended_total)) if recommended_total else Decimal("1")
        readiness_score = float(
            required_score * REQUIRED_WEIGHT + recommended_score * RECOMMENDED_WEIGHT
        )

        data = {
            "readiness_score": round(readiness_score, 2),
            "required_met": required_met,
            "required_total": required_total,
            "recommended_met": recommended_met,
            "recommended_total": recommended_total,
            "gaps": [a.model_dump(mode="json") for a in anomalies],
        }

        msg = (
            f"Tax package readiness: {readiness_score:.0%}. "
            f"{critical_gaps} critical gaps, {warning_gaps} warnings."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 3 — compile_financial_statements
    # ------------------------------------------------------------------

    def _step_compile_financial_statements(self) -> StepResult:
        collected = self.step_results.get("collect_agent_outputs", {})
        agents_found = collected.get("agents_found", {})
        year = self._tax_year()

        income_statement = None
        quarterly = None
        ar_aging = None
        inventory_value = None

        # Try year-end close first
        ye_info = agents_found.get("year_end_close")
        if ye_info:
            ye_job = self.db.query(AgentJob).filter(
                AgentJob.id == ye_info["job_id"]
            ).first()
            if ye_job and ye_job.report_payload:
                steps = ye_job.report_payload.get("steps", {})
                fys = steps.get("full_year_summary", {})
                income_statement = fys.get("annual_income_statement")
                quarterly = fys.get("quarterly_breakdown")
                ar_data = steps.get("ar_aging_snapshot", {})
                if ar_data:
                    ar_aging = ar_data
                inv_step = steps.get("inventory_valuation", {})
                if inv_step:
                    inventory_value = inv_step.get("total_inventory_value", 0)

        # Supplement inventory from dedicated agent if available
        inv_info = agents_found.get("inventory_reconciliation")
        if inv_info:
            inv_job = self.db.query(AgentJob).filter(
                AgentJob.id == inv_info["job_id"]
            ).first()
            if inv_job and inv_job.report_payload:
                inv_steps = inv_job.report_payload.get("steps", {})
                snapshot = inv_steps.get("snapshot_current_inventory", {})
                if snapshot:
                    inventory_value = snapshot.get("total_inventory_value", inventory_value)

        total_ar = None
        if ar_aging:
            total_ar = ar_aging.get("total_ar", 0)

        rev = 0
        net = 0
        if income_statement:
            rev = income_statement.get("total_revenue", 0)
            net = income_statement.get("net_income", 0)

        financial_statements = {
            "income_statement": {
                "annual": income_statement,
                "quarterly": quarterly,
            } if income_statement else None,
            "balance_sheet_components": {
                "accounts_receivable": total_ar,
                "inventory_value": inventory_value,
                "note": (
                    "Full balance sheet requires CPA input for fixed assets, "
                    "liabilities, and equity accounts."
                ),
            },
            "ar_aging_snapshot": ar_aging,
        }

        data = financial_statements

        if income_statement:
            msg = (
                f"Financial statements compiled from year-end close data. "
                f"Revenue: ${rev:,.2f}, Net Income: ${net:,.2f}."
            )
        else:
            msg = "Financial statements unavailable — year-end close not complete."

        return StepResult(message=msg, data=data, anomalies=[])

    # ------------------------------------------------------------------
    # STEP 4 — compile_supporting_schedules
    # ------------------------------------------------------------------

    def _step_compile_supporting_schedules(self) -> StepResult:
        collected = self.step_results.get("collect_agent_outputs", {})
        agents_found = collected.get("agents_found", {})
        year = self._tax_year()

        schedules_available = []
        schedules_missing = []

        # Schedule A — 1099 Vendor List
        schedule_a = None
        prep_info = agents_found.get("1099_prep")
        if prep_info:
            prep_job = self.db.query(AgentJob).filter(
                AgentJob.id == prep_info["job_id"]
            ).first()
            if prep_job and prep_job.report_payload:
                steps = prep_job.report_payload.get("steps", {})
                eligibility = steps.get("apply_1099_eligibility", {})
                vendors_by_status = eligibility.get("vendors_by_status", {})
                schedule_a = {
                    "include_count": eligibility.get("include_count", 0),
                    "include_total": eligibility.get("include_total", 0),
                    "vendors": vendors_by_status.get("include", []),
                    "needs_review": vendors_by_status.get("needs_review", []),
                }
                schedules_available.append("schedule_a_1099")
        if not schedule_a:
            schedules_missing.append("schedule_a_1099")

        # Schedule B — Estimated Tax Payments
        schedule_b = None
        est_jobs = (
            self.db.query(AgentJob)
            .filter(
                AgentJob.tenant_id == self.tenant_id,
                AgentJob.status == "complete",
                AgentJob.job_type == "estimated_tax_prep",
                AgentJob.period_start >= date(year, 1, 1),
                AgentJob.period_end <= date(year, 12, 31),
            )
            .order_by(AgentJob.period_start)
            .all()
        )
        if est_jobs:
            quarters = []
            for ej in est_jobs:
                rp = ej.report_payload or {}
                es = rp.get("executive_summary", {})
                quarters.append({
                    "period": f"{ej.period_start} to {ej.period_end}",
                    "taxable_income": es.get("taxable_income_annualized", 0),
                    "quarterly_estimate_low": es.get("quarterly_estimate_low", 0),
                    "quarterly_estimate_high": es.get("quarterly_estimate_high", 0),
                })
            schedule_b = {"quarters_found": len(est_jobs), "quarters": quarters}
            schedules_available.append("schedule_b_tax_estimates")
        else:
            schedules_missing.append("schedule_b_tax_estimates")

        # Schedule C — Inventory
        schedule_c = None
        ye_info = agents_found.get("year_end_close")
        if ye_info:
            ye_job = self.db.query(AgentJob).filter(
                AgentJob.id == ye_info["job_id"]
            ).first()
            if ye_job and ye_job.report_payload:
                inv_data = ye_job.report_payload.get("steps", {}).get("inventory_valuation", {})
                if inv_data:
                    schedule_c = {
                        "total_value": inv_data.get("total_inventory_value", 0),
                        "products_valued": inv_data.get("products_valued", 0),
                        "products_no_cost": inv_data.get("products_no_cost", 0),
                        "lines": inv_data.get("inventory_lines", []),
                    }
                    schedules_available.append("schedule_c_inventory")
        if not schedule_c:
            # Try dedicated inventory agent
            inv_info = agents_found.get("inventory_reconciliation")
            if inv_info:
                inv_job = self.db.query(AgentJob).filter(
                    AgentJob.id == inv_info["job_id"]
                ).first()
                if inv_job and inv_job.report_payload:
                    snap = inv_job.report_payload.get("steps", {}).get("snapshot_current_inventory", {})
                    if snap:
                        schedule_c = {
                            "total_value": snap.get("total_inventory_value", 0),
                            "products_valued": snap.get("total_items", 0),
                            "products_no_cost": 0,
                            "lines": snap.get("items", []),
                        }
                        schedules_available.append("schedule_c_inventory")
        if not schedule_c:
            schedules_missing.append("schedule_c_inventory")

        # Schedule D — AR Aging
        schedule_d = None
        if ye_info:
            ye_job = self.db.query(AgentJob).filter(
                AgentJob.id == ye_info["job_id"]
            ).first()
            if ye_job and ye_job.report_payload:
                ar_data = ye_job.report_payload.get("steps", {}).get("ar_aging_snapshot", {})
                if ar_data:
                    schedule_d = ar_data
                    schedules_available.append("schedule_d_ar_aging")
        if not schedule_d:
            schedules_missing.append("schedule_d_ar_aging")

        # Schedule E — Budget vs Actual
        schedule_e = None
        bva_info = agents_found.get("budget_vs_actual")
        if bva_info:
            bva_job = self.db.query(AgentJob).filter(
                AgentJob.id == bva_info["job_id"]
            ).first()
            if bva_job and bva_job.report_payload:
                es = bva_job.report_payload.get("executive_summary", {})
                schedule_e = {
                    "comparison_basis": es.get("comparison_basis", "unknown"),
                    "total_revenue_actual": es.get("total_revenue_actual", 0),
                    "total_revenue_comparison": es.get("total_revenue_comparison", 0),
                    "net_income_actual": es.get("net_income_actual", 0),
                }
                schedules_available.append("schedule_e_budget_vs_actual")
        if not schedule_e:
            schedules_missing.append("schedule_e_budget_vs_actual")

        # Schedule F — Anomaly Summary (always available)
        all_job_ids = [v["job_id"] for v in agents_found.values()]
        # Include month-end close job ids
        month_closes = collected.get("month_end_closes", {})
        for mc in month_closes.values():
            all_job_ids.append(mc["job_id"])

        schedule_f = {"total_anomalies": 0, "critical_count": 0, "warning_count": 0, "by_type": []}
        if all_job_ids:
            unresolved = (
                self.db.query(AgentAnomaly)
                .filter(
                    AgentAnomaly.agent_job_id.in_(all_job_ids),
                    AgentAnomaly.severity.in_(["critical", "warning"]),
                )
                .all()
            )
            type_counts: dict[str, dict] = {}
            for a in unresolved:
                key = a.anomaly_type
                if key not in type_counts:
                    type_counts[key] = {"type": key, "count": 0, "resolved": 0}
                type_counts[key]["count"] += 1
                if a.resolved:
                    type_counts[key]["resolved"] += 1

            critical_count = sum(1 for a in unresolved if a.severity == "critical")
            warning_count = sum(1 for a in unresolved if a.severity == "warning")

            schedule_f = {
                "total_anomalies": len(unresolved),
                "critical_count": critical_count,
                "warning_count": warning_count,
                "by_type": list(type_counts.values()),
            }

        schedules_available.append("schedule_f_anomaly_summary")

        data = {
            "schedules_available": schedules_available,
            "schedules_missing": schedules_missing,
            "schedule_a_1099": schedule_a,
            "schedule_b_tax_estimates": schedule_b,
            "schedule_c_inventory": schedule_c,
            "schedule_d_ar_aging": schedule_d,
            "schedule_e_budget_vs_actual": schedule_e,
            "schedule_f_anomaly_summary": schedule_f,
        }

        msg = (
            f"{len(schedules_available)}/6 supporting schedules compiled. "
            f"{len(schedules_missing)} unavailable due to missing agent runs."
        )

        return StepResult(message=msg, data=data, anomalies=[])

    # ------------------------------------------------------------------
    # STEP 5 — generate_report
    # ------------------------------------------------------------------

    def _step_generate_report(self) -> StepResult:
        collected = self.step_results.get("collect_agent_outputs", {})
        completeness = self.step_results.get("assess_completeness", {})
        financials = self.step_results.get("compile_financial_statements", {})
        schedules = self.step_results.get("compile_supporting_schedules", {})

        year = self._tax_year()
        readiness_score = completeness.get("readiness_score", 0)

        # Extract key figures
        income_stmt = (financials.get("income_statement") or {}).get("annual")
        total_revenue = income_stmt.get("total_revenue", 0) if income_stmt else None
        net_income = income_stmt.get("net_income", 0) if income_stmt else None
        total_ar = (financials.get("balance_sheet_components") or {}).get("accounts_receivable")
        inventory_value = (financials.get("balance_sheet_components") or {}).get("inventory_value")

        schedule_a = schedules.get("schedule_a_1099")
        vendors_1099 = schedule_a.get("include_count", 0) if schedule_a else None

        schedule_f = schedules.get("schedule_f_anomaly_summary", {})
        unresolved_critical = schedule_f.get("critical_count", 0)

        critical = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.CRITICAL)

        # Approved by name
        approved_by_name = None
        if self.job.approved_by:
            user = self.db.query(User).filter(User.id == self.job.approved_by).first()
            if user:
                approved_by_name = f"{user.first_name} {user.last_name}"

        executive_summary = {
            "tax_year": year,
            "readiness_score": readiness_score,
            "required_complete": collected.get("required_complete", False),
            "month_end_closes_found": collected.get("month_end_closes_found", 0),
            "schedules_available": len(schedules.get("schedules_available", [])),
            "total_revenue": total_revenue,
            "net_income": net_income,
            "total_ar": total_ar,
            "inventory_value": inventory_value,
            "vendors_requiring_1099": vendors_1099,
            "unresolved_critical_anomalies": unresolved_critical,
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

        report_html = self._build_report_html(
            executive_summary, financials, schedules, approved_by_name,
        )
        payload = dict(self.job.report_payload)
        payload["report_html"] = report_html
        self.job.report_payload = payload
        self.db.commit()

        msg = (
            f"Tax package for {year} compiled. "
            f"Readiness: {readiness_score:.0%}. "
            f"{self.job.anomaly_count} anomalies."
        )

        return StepResult(message=msg, data={"report_generated": True}, anomalies=[])

    def _build_report_html(
        self,
        summary: dict,
        financials: dict,
        schedules: dict,
        approved_by_name: str | None,
    ) -> str:
        year = summary["tax_year"]
        readiness = summary["readiness_score"]
        dry_run_badge = (
            '<span style="background:#f59e0b;color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:12px;margin-left:8px;">DRY RUN</span>'
            if self.dry_run else ""
        )

        # Readiness badge
        if readiness >= 0.9:
            readiness_bg, readiness_color = "#dcfce7", "#166534"
        elif readiness >= 0.7:
            readiness_bg, readiness_color = "#fffbeb", "#92400e"
        else:
            readiness_bg, readiness_color = "#fef2f2", "#dc2626"

        # Company name
        from app.models.company import Company
        company = self.db.query(Company).filter(Company.id == self.tenant_id).first()
        company_name = company.name if company else "Company"

        reviewed_by = approved_by_name or "Pending approval"
        generated_at = summary.get("generated_at", "")

        # Cover page
        cover_html = f"""
        <div style="text-align:center;padding:48px 0 32px;">
            <h1 style="font-size:28px;margin:0;">{company_name}</h1>
            <h2 style="font-size:22px;color:#71717a;margin:8px 0;">Tax Package — {year}{dry_run_badge}</h2>
            <p style="color:#71717a;margin:16px 0;">Prepared by Bridgeable Accounting Agents</p>
            <p style="color:#71717a;">Generated {generated_at}</p>
            <p style="color:#71717a;">Reviewed by: {reviewed_by}</p>
            <div style="display:inline-block;background:{readiness_bg};color:{readiness_color};padding:8px 24px;border-radius:8px;margin-top:16px;font-weight:700;font-size:18px;">
                Readiness: {readiness:.0%}
            </div>
        </div>
        """

        # TOC
        available_schedules = schedules.get("schedules_available", [])
        toc_items = "<li>Financial Statements</li>"
        for sched_key in available_schedules:
            label = SCHEDULE_LABELS.get(sched_key, sched_key)
            toc_items += f"<li>{label}</li>"
        schedule_f = schedules.get("schedule_f_anomaly_summary", {})
        if schedule_f.get("total_anomalies", 0) > 0:
            toc_items += "<li>Data Quality Notes</li>"

        toc_html = f"""
        <h2>Table of Contents</h2>
        <ol style="font-size:14px;line-height:2;">{toc_items}</ol>
        """

        # Section 1 — Financial Statements
        income_stmt = (financials.get("income_statement") or {}).get("annual")
        fs_html = "<h2>1. Financial Statements</h2>"
        if income_stmt:
            rev = income_stmt.get("total_revenue", 0)
            cogs = income_stmt.get("total_cogs", 0)
            gp = income_stmt.get("gross_profit", 0)
            exp = income_stmt.get("total_expenses", 0)
            ni = income_stmt.get("net_income", 0)
            fs_html += f"""
            <h3>Income Statement — Full Year {year}</h3>
            <table>
                <thead><tr><th>Line Item</th><th style="text-align:right;">Amount</th></tr></thead>
                <tbody>
                    <tr><td>Total Revenue</td><td style="text-align:right;">${rev:,.2f}</td></tr>
                    <tr><td>Cost of Goods Sold</td><td style="text-align:right;">${cogs:,.2f}</td></tr>
                    <tr><td style="font-weight:600;">Gross Profit</td><td style="text-align:right;font-weight:600;">${gp:,.2f}</td></tr>
                    <tr><td>Operating Expenses</td><td style="text-align:right;">${exp:,.2f}</td></tr>
                    <tr style="border-top:2px solid #18181b;"><td style="font-weight:700;">Net Income</td><td style="text-align:right;font-weight:700;">${ni:,.2f}</td></tr>
                </tbody>
            </table>
            """

            # Quarterly breakdown
            quarterly = (financials.get("income_statement") or {}).get("quarterly")
            if quarterly:
                q_rows = ""
                for q in ["q1", "q2", "q3", "q4"]:
                    qd = quarterly.get(q, {})
                    q_rows += (
                        f'<tr><td>{q.upper()}</td>'
                        f'<td style="text-align:right;">${qd.get("total_revenue", 0):,.2f}</td>'
                        f'<td style="text-align:right;">${qd.get("gross_profit", 0):,.2f}</td>'
                        f'<td style="text-align:right;">${qd.get("net_income", 0):,.2f}</td></tr>'
                    )
                fs_html += f"""
                <h3>Quarterly Breakdown</h3>
                <table>
                    <thead><tr><th>Quarter</th><th style="text-align:right;">Revenue</th><th style="text-align:right;">Gross Profit</th><th style="text-align:right;">Net Income</th></tr></thead>
                    <tbody>{q_rows}</tbody>
                </table>
                """

            # Balance sheet components
            bsc = financials.get("balance_sheet_components", {})
            ar_val = bsc.get("accounts_receivable")
            inv_val = bsc.get("inventory_value")
            fs_html += f"""
            <h3>Balance Sheet Components</h3>
            <table>
                <tbody>
                    <tr><td>Accounts Receivable</td><td style="text-align:right;">{"${:,.2f}".format(ar_val) if ar_val is not None else "N/A"}</td></tr>
                    <tr><td>Inventory Value</td><td style="text-align:right;">{"${:,.2f}".format(inv_val) if inv_val is not None else "N/A"}</td></tr>
                </tbody>
            </table>
            <p style="font-size:13px;color:#71717a;">{bsc.get("note", "")}</p>
            """
        else:
            fs_html += '<p style="color:#dc2626;">Financial statements unavailable — year-end close not complete.</p>'

        # Section 2 — Supporting Schedules
        sched_html = "<h2>2. Supporting Schedules</h2>"

        # Schedule A
        schedule_a = schedules.get("schedule_a_1099")
        if schedule_a:
            vendor_rows = ""
            for v in schedule_a.get("vendors", []):
                vendor_rows += (
                    f'<tr><td>{v.get("vendor_name", "")}</td>'
                    f'<td>{v.get("tax_id_masked", "***")}</td>'
                    f'<td style="text-align:right;">${v.get("total_paid", 0):,.2f}</td></tr>'
                )
            sched_html += f"""
            <h3>Schedule A — 1099 Vendor List</h3>
            <p style="font-size:13px;color:#71717a;">{schedule_a.get("include_count", 0)} vendors requiring 1099, total ${schedule_a.get("include_total", 0):,.2f}</p>
            <table>
                <thead><tr><th>Vendor</th><th>Tax ID</th><th style="text-align:right;">Total Paid</th></tr></thead>
                <tbody>{vendor_rows or '<tr><td colspan="3">No vendors</td></tr>'}</tbody>
            </table>
            """
        else:
            sched_html += '<h3>Schedule A — 1099 Vendor List</h3><p style="color:#71717a;">Not available — 1099 prep not completed.</p>'

        # Schedule F — always show if anomalies exist
        if schedule_f.get("total_anomalies", 0) > 0:
            anomaly_rows = ""
            for bt in schedule_f.get("by_type", []):
                anomaly_rows += (
                    f'<tr><td>{bt["type"]}</td>'
                    f'<td style="text-align:right;">{bt["count"]}</td>'
                    f'<td style="text-align:right;">{bt["resolved"]}</td></tr>'
                )
            sched_html += f"""
            <h3>Schedule F — Data Quality Notes</h3>
            <p style="font-size:13px;color:#71717a;">
                The following data quality issues were identified during the year.
                Items marked unresolved should be reviewed with your CPA.
            </p>
            <table>
                <thead><tr><th>Anomaly Type</th><th style="text-align:right;">Count</th><th style="text-align:right;">Resolved</th></tr></thead>
                <tbody>{anomaly_rows}</tbody>
            </table>
            """

        # Footer
        footer_html = f"""
        <div style="border-top:1px solid #e4e4e7;margin-top:32px;padding-top:16px;">
            <p style="font-size:12px;color:#71717a;">
                Generated by Bridgeable. This package was prepared from automated
                accounting agent outputs that were reviewed and approved by {reviewed_by}.
                Final tax determination is the responsibility of your CPA.
            </p>
        </div>
        """

        return f"""
        <!DOCTYPE html>
        <html>
        <head><style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #18181b; margin: 0; padding: 24px; background: #f4f4f5; }}
            .container {{ max-width: 900px; margin: 0 auto; background: #fff; border-radius: 8px; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,.1); }}
            h1 {{ font-size: 28px; margin: 0 0 4px; }}
            h2 {{ font-size: 18px; margin: 32px 0 12px; border-bottom: 2px solid #18181b; padding-bottom: 4px; }}
            h3 {{ font-size: 15px; margin: 20px 0 8px; color: #3f3f46; }}
            .meta {{ color: #71717a; font-size: 14px; margin-bottom: 24px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
            th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #e4e4e7; font-size: 14px; }}
            th {{ background: #f4f4f5; font-weight: 600; }}
        </style></head>
        <body>
        <div class="container">
            {cover_html}
            {toc_html}
            {fs_html}
            {sched_html}
            {footer_html}
        </div>
        </body>
        </html>
        """

    # ------------------------------------------------------------------
    # Override _assemble_report — generate_report step handles it
    # ------------------------------------------------------------------

    def _assemble_report(self) -> None:
        pass
