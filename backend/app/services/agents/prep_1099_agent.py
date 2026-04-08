"""1099 Prep Agent — Phase 10.

Annual agent (run in January) that identifies vendors who received $600+
in payments during the prior calendar year, flags missing tax IDs and
W-9 tracking gaps, and produces a CPA-ready 1099 filing list.

Steps:
  1. compute_vendor_payment_totals
  2. apply_1099_eligibility
  3. flag_data_gaps
  4. generate_report
"""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import ClassVar

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.vendor import Vendor
from app.models.vendor_payment import VendorPayment
from app.models.vendor_payment_application import VendorPaymentApplication
from app.schemas.agent import (
    AgentJobType,
    AnomalyItem,
    AnomalySeverity,
    StepResult,
)
from app.services.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# IRS minimum for Form 1099-NEC
IRS_THRESHOLD = Decimal("600.00")


def mask_tax_id(tax_id: str | None) -> str:
    """Mask a tax ID for display — never show full value."""
    if not tax_id or len(tax_id) < 4:
        return "***"
    return "*" * (len(tax_id) - 4) + tax_id[-4:]


class Prep1099Agent(BaseAgent):
    """Annual agent that produces a CPA-ready 1099 filing list."""

    JOB_TYPE = AgentJobType.PREP_1099

    IRS_THRESHOLD = IRS_THRESHOLD

    STEPS: ClassVar[list[str]] = [
        "compute_vendor_payment_totals",
        "apply_1099_eligibility",
        "flag_data_gaps",
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

    # ------------------------------------------------------------------
    # STEP 1 — compute_vendor_payment_totals
    # ------------------------------------------------------------------

    def _step_compute_vendor_payment_totals(self) -> StepResult:
        period_start = self._period_start()
        period_end = self._period_end()
        period_start_dt = datetime(period_start.year, period_start.month, period_start.day, tzinfo=timezone.utc)
        period_end_dt = datetime(period_end.year, period_end.month, period_end.day, 23, 59, 59, tzinfo=timezone.utc)

        # Aggregate payment applications by vendor
        vendor_totals = (
            self.db.query(
                VendorPayment.vendor_id,
                func.sum(VendorPaymentApplication.amount_applied).label("total_paid"),
                func.count(VendorPayment.id.distinct()).label("payment_count"),
                func.min(VendorPayment.payment_date).label("first_payment_date"),
                func.max(VendorPayment.payment_date).label("last_payment_date"),
                func.max(VendorPaymentApplication.amount_applied).label("largest_single_payment"),
            )
            .join(VendorPaymentApplication, VendorPaymentApplication.payment_id == VendorPayment.id)
            .filter(
                VendorPayment.company_id == self.tenant_id,
                VendorPayment.payment_date >= period_start_dt,
                VendorPayment.payment_date <= period_end_dt,
                VendorPayment.deleted_at.is_(None),
            )
            .group_by(VendorPayment.vendor_id)
            .all()
        )

        vendors_data = []
        total_amount = Decimal("0")
        above_threshold = 0

        for row in vendor_totals:
            vendor = self.db.query(Vendor).filter(Vendor.id == row.vendor_id).first()
            vendor_name = vendor.name if vendor else "Unknown"
            total_paid = Decimal(str(row.total_paid or 0))
            total_amount += total_paid
            is_above = total_paid >= self.IRS_THRESHOLD
            if is_above:
                above_threshold += 1

            first_date = row.first_payment_date
            last_date = row.last_payment_date

            vendors_data.append({
                "vendor_id": row.vendor_id,
                "vendor_name": vendor_name,
                "total_paid": float(total_paid),
                "payment_count": row.payment_count,
                "first_payment_date": first_date.isoformat() if first_date else None,
                "last_payment_date": last_date.isoformat() if last_date else None,
                "largest_single_payment": float(Decimal(str(row.largest_single_payment or 0))),
                "above_threshold": is_above,
            })

        data = {
            "period_start": str(period_start),
            "period_end": str(period_end),
            "total_vendors_paid": len(vendors_data),
            "total_amount_paid": float(total_amount),
            "above_threshold_count": above_threshold,
            "vendors": vendors_data,
        }

        msg = (
            f"{len(vendors_data)} vendors paid in period. "
            f"{above_threshold} at or above $600 threshold. "
            f"Total paid: ${float(total_amount):,.2f}."
        )

        return StepResult(message=msg, data=data, anomalies=[])

    # ------------------------------------------------------------------
    # STEP 2 — apply_1099_eligibility
    # ------------------------------------------------------------------

    def _step_apply_1099_eligibility(self) -> StepResult:
        totals_data = self.step_results.get("compute_vendor_payment_totals", {})
        vendors = totals_data.get("vendors", [])
        anomalies: list[AnomalyItem] = []

        include_list = []
        needs_review_list = []
        below_threshold_list = []
        include_total = Decimal("0")
        needs_review_total = Decimal("0")
        filing_ready = 0
        missing_tax_id = 0

        for v in vendors:
            total_paid = Decimal(str(v["total_paid"]))
            vendor_id = v["vendor_id"]
            vendor_name = v["vendor_name"]

            if not v["above_threshold"]:
                below_threshold_list.append(v)
                continue

            # Look up vendor record for 1099 status and tax_id
            vendor = self.db.query(Vendor).filter(Vendor.id == vendor_id).first()
            is_1099 = vendor.is_1099_vendor if vendor else False
            tax_id = vendor.tax_id if vendor else None

            vendor_entry = {
                **v,
                "is_1099_vendor": is_1099,
                "tax_id_masked": mask_tax_id(tax_id),
                "has_tax_id": tax_id is not None and len(tax_id.strip()) > 0 if tax_id else False,
            }

            if is_1099:
                # INCLUDE — vendor needs a 1099
                include_list.append(vendor_entry)
                include_total += total_paid

                if vendor_entry["has_tax_id"]:
                    filing_ready += 1
                else:
                    missing_tax_id += 1
                    anomalies.append(self._make_anomaly(
                        severity=AnomalySeverity.CRITICAL,
                        anomaly_type="missing_tax_id",
                        entity_type="vendor",
                        entity_id=vendor_id,
                        description=(
                            f"{vendor_name}: requires 1099 "
                            f"(${float(total_paid):,.2f} paid) but has no "
                            f"Tax ID / EIN on file. Cannot file 1099 without this."
                        ),
                        amount=total_paid,
                    ))
            else:
                # NEEDS REVIEW — above threshold but is_1099_vendor=False
                needs_review_list.append(vendor_entry)
                needs_review_total += total_paid
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.INFO,
                    anomaly_type="missing_w9_tracking",
                    entity_type="vendor",
                    entity_id=vendor_id,
                    description=(
                        f"Vendor {vendor_name} paid ${float(total_paid):,.2f} "
                        f"has is_1099_vendor=False but no W-9 or entity type "
                        f"on record to confirm exclusion. Verify with CPA "
                        f"whether a 1099 is required."
                    ),
                ))

        data = {
            "include_count": len(include_list),
            "include_total": float(include_total),
            "needs_review_count": len(needs_review_list),
            "needs_review_total": float(needs_review_total),
            "below_threshold_count": len(below_threshold_list),
            "filing_ready_count": filing_ready,
            "missing_tax_id_count": missing_tax_id,
            "vendors_by_status": {
                "include": include_list,
                "needs_review": needs_review_list,
                "below_threshold": below_threshold_list,
            },
        }

        msg = (
            f"{len(include_list)} vendors require 1099 "
            f"(${float(include_total):,.2f} total). "
            f"{filing_ready} ready to file, "
            f"{missing_tax_id} missing Tax ID. "
            f"{len(needs_review_list)} need CPA review."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 3 — flag_data_gaps
    # ------------------------------------------------------------------

    def _step_flag_data_gaps(self) -> StepResult:
        eligibility = self.step_results.get("apply_1099_eligibility", {})
        anomalies: list[AnomalyItem] = []

        needs_review_count = eligibility.get("needs_review_count", 0)
        needs_review_total = Decimal(str(eligibility.get("needs_review_total", 0)))
        missing_tax_id_count = eligibility.get("missing_tax_id_count", 0)

        # CHECK A — Vendors above threshold never reviewed
        if needs_review_count > 0:
            anomalies.append(self._make_anomaly(
                severity=AnomalySeverity.WARNING,
                anomaly_type="vendors_not_reviewed_for_1099",
                description=(
                    f"{needs_review_count} vendors paid "
                    f"${float(needs_review_total):,.2f} above the $600 threshold "
                    f"have not been reviewed for 1099 eligibility "
                    f"(is_1099_vendor=False by default). "
                    f"Review each before filing."
                ),
                amount=needs_review_total,
            ))

        # CHECK B — Missing Tax IDs summary
        if missing_tax_id_count > 0:
            # Compute total affected
            include_vendors = eligibility.get("vendors_by_status", {}).get("include", [])
            affected_total = Decimal("0")
            for v in include_vendors:
                if not v.get("has_tax_id"):
                    affected_total += Decimal(str(v["total_paid"]))

            anomalies.append(self._make_anomaly(
                severity=AnomalySeverity.CRITICAL,
                anomaly_type="missing_tax_ids_summary",
                description=(
                    f"{missing_tax_id_count} vendors requiring 1099 are "
                    f"missing Tax ID / EIN. Collect W-9 forms before "
                    f"filing deadline."
                ),
                amount=affected_total,
            ))

        # CHECK C — No W-9 tracking infrastructure (always)
        anomalies.append(self._make_anomaly(
            severity=AnomalySeverity.INFO,
            anomaly_type="w9_tracking_not_implemented",
            description=(
                "W-9 receipt tracking is not yet implemented in Bridgeable. "
                "The system cannot confirm W-9s are on file for vendors. "
                "Recommend maintaining W-9s in your CPA's system until "
                "this feature is added."
            ),
        ))

        # CHECK D — Payments with no vendor link (orphaned)
        period_start = self._period_start()
        period_end = self._period_end()
        period_start_dt = datetime(period_start.year, period_start.month, period_start.day, tzinfo=timezone.utc)
        period_end_dt = datetime(period_end.year, period_end.month, period_end.day, 23, 59, 59, tzinfo=timezone.utc)

        orphaned = (
            self.db.query(
                func.count(VendorPayment.id),
                func.coalesce(func.sum(VendorPayment.total_amount), 0),
            )
            .filter(
                VendorPayment.company_id == self.tenant_id,
                VendorPayment.payment_date >= period_start_dt,
                VendorPayment.payment_date <= period_end_dt,
                VendorPayment.deleted_at.is_(None),
                VendorPayment.vendor_id.is_(None),
            )
            .first()
        )
        orphan_count = orphaned[0] if orphaned else 0
        orphan_total = Decimal(str(orphaned[1] or 0)) if orphaned else Decimal("0")

        if orphan_count > 0:
            anomalies.append(self._make_anomaly(
                severity=AnomalySeverity.WARNING,
                anomaly_type="orphaned_vendor_payments",
                description=(
                    f"{orphan_count} payments totaling "
                    f"${float(orphan_total):,.2f} in period have no vendor "
                    f"linked. These are excluded from 1099 totals and "
                    f"may be misclassified."
                ),
                amount=orphan_total,
            ))

        # Data quality score
        filing_ready = eligibility.get("filing_ready_count", 0)
        include_count = eligibility.get("include_count", 0)
        quality_score = filing_ready / include_count if include_count > 0 else 1.0

        data = {
            "unreviewed_vendor_count": needs_review_count,
            "missing_tax_id_count": missing_tax_id_count,
            "orphaned_payment_count": orphan_count,
            "orphaned_payment_total": float(orphan_total),
            "data_quality_score": round(quality_score, 2),
        }

        msg = (
            f"Data quality score: {quality_score:.0%}. "
            f"{missing_tax_id_count} Tax IDs missing. "
            f"{needs_review_count} vendors need eligibility review."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 4 — generate_report
    # ------------------------------------------------------------------

    def _step_generate_report(self) -> StepResult:
        totals = self.step_results.get("compute_vendor_payment_totals", {})
        eligibility = self.step_results.get("apply_1099_eligibility", {})
        gaps = self.step_results.get("flag_data_gaps", {})

        tax_year = self._period_start().year
        filing_deadline_year = tax_year + 1

        critical = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.CRITICAL)

        executive_summary = {
            "tax_year": tax_year,
            "period": f"{self._period_start()} to {self._period_end()}",
            "filing_deadline": f"January 31, {filing_deadline_year}",
            "include_count": eligibility.get("include_count", 0),
            "include_total": eligibility.get("include_total", 0),
            "filing_ready_count": eligibility.get("filing_ready_count", 0),
            "missing_tax_id_count": eligibility.get("missing_tax_id_count", 0),
            "needs_review_count": eligibility.get("needs_review_count", 0),
            "data_quality_score": gaps.get("data_quality_score", 0),
            "anomaly_count": self.job.anomaly_count,
            "critical_count": critical,
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
            executive_summary, eligibility,
        )
        self.db.commit()

        msg = (
            f"1099 prep report ready for tax year {tax_year}. "
            f"{eligibility.get('include_count', 0)} vendors requiring 1099, "
            f"{eligibility.get('filing_ready_count', 0)} ready to file."
        )

        return StepResult(message=msg, data={"report_generated": True}, anomalies=[])

    def _build_report_html(self, summary: dict, eligibility: dict) -> str:
        dry_run_badge = (
            '<span style="background:#f59e0b;color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:12px;margin-left:8px;">DRY RUN</span>'
            if self.dry_run else ""
        )

        tax_year = summary["tax_year"]
        filing_deadline_year = tax_year + 1
        today = date.today()
        deadline = date(filing_deadline_year, 1, 31)
        days_to_deadline = (deadline - today).days

        # Deadline banner styling
        if days_to_deadline <= 14:
            deadline_bg, deadline_color = "#fef2f2", "#dc2626"
        elif days_to_deadline <= 60:
            deadline_bg, deadline_color = "#fffbeb", "#92400e"
        else:
            deadline_bg, deadline_color = "#dbeafe", "#1e40af"

        deadline_html = (
            f'<div style="background:{deadline_bg};border-radius:6px;padding:12px 16px;margin-bottom:16px;">'
            f'<p style="margin:0;color:{deadline_color};font-weight:600;">'
            f'1099-NEC forms due to recipients by January 31, {filing_deadline_year}. '
            f'IRS filing deadline: January 31, {filing_deadline_year}.'
            f'</p></div>'
        )

        disclaimer_html = (
            '<div style="background:#f4f4f5;border-radius:6px;padding:12px 16px;margin-bottom:24px;">'
            '<p style="margin:0;color:#71717a;font-size:13px;">'
            'This report identifies potential 1099 obligations based on payment data in '
            'Bridgeable. Final determination of 1099 requirements should be made by your CPA. '
            'Rules vary by vendor type, payment type, and jurisdiction.'
            '</p></div>'
        )

        vendors_by_status = eligibility.get("vendors_by_status", {})

        # Ready to file table
        ready_rows = ""
        for v in vendors_by_status.get("include", []):
            if v.get("has_tax_id"):
                ready_rows += (
                    f'<tr><td>{v["vendor_name"]}</td>'
                    f'<td>{v["tax_id_masked"]}</td>'
                    f'<td style="text-align:right;">${v["total_paid"]:,.2f}</td>'
                    f'<td>{v["payment_count"]}</td>'
                    f'<td>Ready</td></tr>'
                )

        ready_html = ""
        if ready_rows:
            ready_html = f"""
            <h2 style="color:#16a34a;">Ready to File</h2>
            <p style="font-size:13px;color:#71717a;">These vendors are ready for 1099 filing.</p>
            <table><thead><tr><th>Vendor</th><th>Tax ID</th><th style="text-align:right;">Total Paid</th><th>Payments</th><th>Notes</th></tr></thead>
            <tbody>{ready_rows}</tbody></table>"""

        # Missing Tax ID table
        missing_rows = ""
        for v in vendors_by_status.get("include", []):
            if not v.get("has_tax_id"):
                missing_rows += (
                    f'<tr><td>{v["vendor_name"]}</td>'
                    f'<td style="text-align:right;">${v["total_paid"]:,.2f}</td>'
                    f'<td>Collect W-9</td></tr>'
                )

        missing_html = ""
        if missing_rows:
            missing_html = f"""
            <h2 style="color:#dc2626;">Missing Tax ID</h2>
            <p style="font-size:13px;color:#71717a;">Collect W-9 from each vendor before filing.</p>
            <table><thead><tr><th>Vendor</th><th style="text-align:right;">Total Paid</th><th>Action Required</th></tr></thead>
            <tbody>{missing_rows}</tbody></table>"""

        # Needs CPA Review table
        review_rows = ""
        for v in vendors_by_status.get("needs_review", []):
            review_rows += (
                f'<tr><td>{v["vendor_name"]}</td>'
                f'<td style="text-align:right;">${v["total_paid"]:,.2f}</td>'
                f'<td>Confirm 1099 requirement</td></tr>'
            )

        review_html = ""
        if review_rows:
            review_html = f"""
            <h2 style="color:#d97706;">Needs CPA Review</h2>
            <p style="font-size:13px;color:#71717a;">Confirm 1099 requirement with CPA.</p>
            <table><thead><tr><th>Vendor</th><th style="text-align:right;">Total Paid</th><th>Reason for Review</th></tr></thead>
            <tbody>{review_rows}</tbody></table>"""

        # Below threshold table
        below_rows = ""
        for v in vendors_by_status.get("below_threshold", []):
            below_rows += (
                f'<tr><td>{v["vendor_name"]}</td>'
                f'<td style="text-align:right;">${v["total_paid"]:,.2f}</td></tr>'
            )

        below_html = ""
        if below_rows:
            below_html = f"""
            <h2 style="color:#71717a;">Below Threshold</h2>
            <p style="font-size:13px;color:#71717a;">Below $600 threshold — no 1099 required.</p>
            <table><thead><tr><th>Vendor</th><th style="text-align:right;">Total Paid</th></tr></thead>
            <tbody>{below_rows}</tbody></table>"""

        include_count = summary.get("include_count", 0)
        include_total = summary.get("include_total", 0)
        filing_ready = summary.get("filing_ready_count", 0)
        missing_count = summary.get("missing_tax_id_count", 0)

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
            <h1>1099 Prep — Tax Year {tax_year}{dry_run_badge}</h1>
            <div class="meta">Period: {summary.get('period', '')} &middot; Generated {summary.get('generated_at', '')}</div>

            {deadline_html}
            {disclaimer_html}

            <div class="cards">
                <div class="card">
                    <div class="card-value">{include_count}</div>
                    <div class="card-label">Vendors Requiring 1099</div>
                </div>
                <div class="card">
                    <div class="card-value">${include_total:,.0f}</div>
                    <div class="card-label">Total Amount</div>
                </div>
                <div class="card">
                    <div class="card-value">{filing_ready}</div>
                    <div class="card-label">Filing Ready</div>
                </div>
                <div class="card">
                    <div class="card-value">{missing_count}</div>
                    <div class="card-label">Missing Tax ID</div>
                </div>
            </div>

            {ready_html}
            {missing_html}
            {review_html}
            {below_html}
        </div>
        </body>
        </html>
        """

    # ------------------------------------------------------------------
    # Override _assemble_report — generate_report step handles it
    # ------------------------------------------------------------------

    def _assemble_report(self) -> None:
        pass
