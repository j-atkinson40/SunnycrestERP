"""Expense Categorization Agent — Phase 6.

Monthly agent that finds uncategorized or low-confidence expense lines,
classifies them using Claude Haiku (same model as AccountingAnalysisService),
maps them to GL accounts via TenantGLMapping, and surfaces anything below
the confidence threshold for human review.

Steps:
  1. find_uncategorized_expenses — scan VendorBillLines in period
  2. classify_expenses — AI classification per line
  3. map_to_gl_accounts — look up TenantGLMapping for high-confidence lines
  4. generate_report — executive summary + HTML report
"""

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import ClassVar

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting_analysis import TenantGLMapping
from app.models.agent import AgentJob
from app.models.vendor import Vendor
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

# Same model and threshold used by AccountingAnalysisService
CLASSIFICATION_MODEL = "claude-haiku-4-5-20250514"
CLASSIFICATION_MAX_TOKENS = 2048

# Platform expense categories from AccountingAnalysisService.PLATFORM_CATEGORIES
EXPENSE_CATEGORIES = [
    "vault_materials", "direct_labor", "delivery_costs", "other_cogs",
    "rent", "utilities", "insurance", "payroll", "office_supplies",
    "vehicle_expense", "repairs_maintenance", "depreciation",
    "professional_fees", "advertising", "other_expense",
]

CLASSIFICATION_SYSTEM_PROMPT = """You are an expense classification assistant for a burial vault \
manufacturing business. Given a vendor bill line item, classify it into one of these categories:

COGS: vault_materials, direct_labor, delivery_costs, other_cogs
EXPENSES: rent, utilities, insurance, payroll, office_supplies, vehicle_expense, \
repairs_maintenance, depreciation, professional_fees, advertising, other_expense

Return ONLY valid JSON:
{"category": "<category>", "confidence": <0.0-1.0>, "reasoning": "<one sentence>"}

No preamble, no markdown."""


class ExpenseCategorizationAgent(BaseAgent):
    """Finds and classifies uncategorized expense lines."""

    JOB_TYPE = AgentJobType.EXPENSE_CATEGORIZATION

    CONFIDENCE_THRESHOLD = Decimal("0.85")

    STEPS: ClassVar[list[str]] = [
        "find_uncategorized_expenses",
        "classify_expenses",
        "map_to_gl_accounts",
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

    def _get_tenant_platform_categories(self) -> set[str]:
        """Return the set of platform_category values in TenantGLMapping for this tenant."""
        rows = (
            self.db.query(TenantGLMapping.platform_category)
            .filter(
                TenantGLMapping.tenant_id == self.tenant_id,
                TenantGLMapping.is_active == True,
            )
            .distinct()
            .all()
        )
        return {r[0] for r in rows if r[0]}

    # ------------------------------------------------------------------
    # STEP 1 — find_uncategorized_expenses
    # ------------------------------------------------------------------

    def _step_find_uncategorized_expenses(self) -> StepResult:
        ps, pe = self._period_start(), self._period_end()
        anomalies: list[AnomalyItem] = []

        # All bill lines in period via VendorBill.bill_date
        bill_lines = (
            self.db.query(VendorBillLine, VendorBill, Vendor)
            .join(VendorBill, VendorBillLine.bill_id == VendorBill.id)
            .join(Vendor, VendorBill.vendor_id == Vendor.id)
            .filter(
                VendorBill.company_id == self.tenant_id,
                func.date(VendorBill.bill_date) >= ps,
                func.date(VendorBill.bill_date) <= pe,
                VendorBill.deleted_at.is_(None),
                VendorBillLine.deleted_at.is_(None),
            )
            .all()
        )

        total_bill_lines = len(bill_lines)
        valid_categories = self._get_tenant_platform_categories()

        uncategorized_lines = []
        for line, bill, vendor in bill_lines:
            cat = line.expense_category
            issue = None

            if not cat or cat.strip() == "":
                issue = "uncategorized"
            elif cat not in valid_categories:
                issue = "orphaned_category"

            if issue:
                uncategorized_lines.append({
                    "line_id": line.id,
                    "bill_id": bill.id,
                    "vendor_name": vendor.name,
                    "description": line.description,
                    "amount": float(line.amount),
                    "current_category": cat if issue == "orphaned_category" else None,
                    "issue": issue,
                })

        uncategorized_count = sum(1 for l in uncategorized_lines if l["issue"] == "uncategorized")
        orphaned_count = sum(1 for l in uncategorized_lines if l["issue"] == "orphaned_category")
        uncategorized_total = Decimal(str(sum(l["amount"] for l in uncategorized_lines)))

        data = {
            "total_bill_lines_in_period": total_bill_lines,
            "uncategorized_count": uncategorized_count,
            "orphaned_category_count": orphaned_count,
            "uncategorized_total": float(uncategorized_total),
            "lines": uncategorized_lines,
        }

        msg = (
            f"{uncategorized_count} uncategorized and "
            f"{orphaned_count} orphaned-category "
            f"expense lines found totaling "
            f"${uncategorized_total:,.2f}."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 2 — classify_expenses
    # ------------------------------------------------------------------

    def _step_classify_expenses(self) -> StepResult:
        anomalies: list[AnomalyItem] = []
        lines = self.step_results.get("find_uncategorized_expenses", {}).get("lines", [])

        classifications = []
        high_confidence_count = 0
        high_confidence_total = Decimal(0)
        needs_review_count = 0
        needs_review_total = Decimal(0)
        failed_count = 0

        for line_info in lines:
            try:
                result = self._classify_single_line(line_info)
                confidence = Decimal(str(result.get("confidence", 0)))
                proposed_category = result.get("category", "other_expense")
                reasoning = result.get("reasoning", "")

                classification = {
                    "line_id": line_info["line_id"],
                    "vendor_name": line_info["vendor_name"],
                    "description": line_info["description"],
                    "amount": line_info["amount"],
                    "proposed_category": proposed_category,
                    "confidence": float(confidence),
                    "reasoning": reasoning,
                    "needs_review": confidence < self.CONFIDENCE_THRESHOLD,
                }
                classifications.append(classification)

                amt = Decimal(str(line_info["amount"]))

                if confidence >= self.CONFIDENCE_THRESHOLD:
                    high_confidence_count += 1
                    high_confidence_total += amt
                else:
                    needs_review_count += 1
                    needs_review_total += amt
                    anomalies.append(self._make_anomaly(
                        severity=AnomalySeverity.WARNING,
                        anomaly_type="expense_low_confidence",
                        entity_type="vendor_bill_line",
                        entity_id=line_info["line_id"],
                        description=(
                            f"Expense line '{line_info['description']}' "
                            f"from {line_info['vendor_name']} "
                            f"(${line_info['amount']:,.2f}): "
                            f"best guess '{proposed_category}' "
                            f"at {float(confidence):.0%} confidence. "
                            f"Manual review required."
                        ),
                        amount=amt,
                    ))

            except Exception as e:
                failed_count += 1
                logger.warning(
                    "Classification failed for line %s: %s",
                    line_info["line_id"], e,
                )
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.WARNING,
                    anomaly_type="expense_classification_failed",
                    entity_type="vendor_bill_line",
                    entity_id=line_info["line_id"],
                    description=(
                        f"Classification failed for '{line_info['description']}' "
                        f"from {line_info['vendor_name']}: {e}"
                    ),
                    amount=Decimal(str(line_info["amount"])),
                ))

        classified_count = high_confidence_count + needs_review_count

        data = {
            "classified_count": classified_count,
            "high_confidence_count": high_confidence_count,
            "high_confidence_total": float(high_confidence_total),
            "needs_review_count": needs_review_count,
            "needs_review_total": float(needs_review_total),
            "failed_count": failed_count,
            "classifications": classifications,
        }

        msg = (
            f"{classified_count} lines classified. "
            f"{high_confidence_count} auto-apply ready, "
            f"{needs_review_count} need manual review, "
            f"{failed_count} failed."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    def _classify_single_line(self, line_info: dict) -> dict:
        """Classify a single expense line using Claude Haiku."""
        import anthropic

        client = anthropic.Anthropic()
        user_message = (
            f"Vendor: {line_info['vendor_name']}\n"
            f"Description: {line_info['description']}\n"
            f"Amount: ${line_info['amount']:,.2f}"
        )

        response = client.messages.create(
            model=CLASSIFICATION_MODEL,
            max_tokens=CLASSIFICATION_MAX_TOKENS,
            system=CLASSIFICATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        result_text = response.content[0].text
        return json.loads(result_text)

    # ------------------------------------------------------------------
    # STEP 3 — map_to_gl_accounts
    # ------------------------------------------------------------------

    def _step_map_to_gl_accounts(self) -> StepResult:
        anomalies: list[AnomalyItem] = []
        classify_data = self.step_results.get("classify_expenses", {})
        classifications = classify_data.get("classifications", [])

        mappings = []
        mapped_count = 0
        unmapped_count = 0
        ready_to_post_count = 0

        for clf in classifications:
            if clf.get("needs_review"):
                # Skip GL mapping for needs_review lines
                continue

            proposed_category = clf["proposed_category"]

            gl_mapping = (
                self.db.query(TenantGLMapping)
                .filter(
                    TenantGLMapping.tenant_id == self.tenant_id,
                    TenantGLMapping.platform_category == proposed_category,
                    TenantGLMapping.is_active == True,
                )
                .first()
            )

            if gl_mapping:
                mapped_count += 1
                ready_to_post_count += 1
                mappings.append({
                    "line_id": clf["line_id"],
                    "description": clf["description"],
                    "vendor_name": clf["vendor_name"],
                    "amount": clf["amount"],
                    "proposed_category": proposed_category,
                    "confidence": clf["confidence"],
                    "gl_account_number": gl_mapping.account_number,
                    "gl_account_name": gl_mapping.account_name,
                    "mapping_status": "mapped",
                })
            else:
                unmapped_count += 1
                mappings.append({
                    "line_id": clf["line_id"],
                    "description": clf["description"],
                    "vendor_name": clf["vendor_name"],
                    "amount": clf["amount"],
                    "proposed_category": proposed_category,
                    "confidence": clf["confidence"],
                    "gl_account_number": None,
                    "gl_account_name": None,
                    "mapping_status": "no_gl_mapping",
                })
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.INFO,
                    anomaly_type="expense_no_gl_mapping",
                    description=(
                        f"Category '{proposed_category}' has no GL account mapping "
                        f"for this tenant. Add a mapping in Settings → GL Accounts "
                        f"before this can post."
                    ),
                ))

        data = {
            "mapped_count": mapped_count,
            "unmapped_count": unmapped_count,
            "ready_to_post_count": ready_to_post_count,
            "mappings": mappings,
        }

        msg = (
            f"{mapped_count} lines mapped to GL accounts. "
            f"{ready_to_post_count} ready to post on approval. "
            f"{unmapped_count} need GL mapping configured."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 4 — generate_report
    # ------------------------------------------------------------------

    def _step_generate_report(self) -> StepResult:
        find_data = self.step_results.get("find_uncategorized_expenses", {})
        classify_data = self.step_results.get("classify_expenses", {})
        gl_data = self.step_results.get("map_to_gl_accounts", {})

        critical = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.CRITICAL)
        warning = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.WARNING)
        info = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.INFO)

        executive_summary = {
            "period": f"{self._period_start()} to {self._period_end()}",
            "total_uncategorized": find_data.get("uncategorized_count", 0) + find_data.get("orphaned_category_count", 0),
            "total_classified": classify_data.get("classified_count", 0),
            "auto_apply_ready": gl_data.get("ready_to_post_count", 0),
            "auto_apply_total": classify_data.get("high_confidence_total", 0),
            "needs_review": classify_data.get("needs_review_count", 0),
            "needs_review_total": classify_data.get("needs_review_total", 0),
            "no_gl_mapping": gl_data.get("unmapped_count", 0),
            "anomaly_count": self.job.anomaly_count,
            "dry_run": self.dry_run,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Build HTML report
        report_html = self._build_report_html(executive_summary, classify_data, gl_data)

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
            f"Ready for review."
        )

        return StepResult(message=msg, data={"report_generated": True}, anomalies=[])

    def _build_report_html(self, summary: dict, classify_data: dict, gl_data: dict) -> str:
        """Build the HTML review report."""
        ps = self._period_start()
        pe = self._period_end()
        dry_run_badge = (
            '<span style="background:#f59e0b;color:#fff;padding:2px 8px;border-radius:4px;'
            'font-size:12px;margin-left:8px;">DRY RUN</span>'
            if self.dry_run else ""
        )

        # Metric cards
        cards_html = f"""
        <div class="cards">
            <div class="card">
                <div class="card-value">{summary['total_uncategorized']}</div>
                <div class="card-label">Uncategorized Found</div>
            </div>
            <div class="card" style="background:#dcfce7;">
                <div class="card-value">{summary['auto_apply_ready']}</div>
                <div class="card-label">Auto-Apply Ready</div>
            </div>
            <div class="card" style="background:#fef3c7;">
                <div class="card-value">{summary['needs_review']}</div>
                <div class="card-label">Needs Review</div>
            </div>
            <div class="card">
                <div class="card-value">{summary['no_gl_mapping']}</div>
                <div class="card-label">No GL Mapping</div>
            </div>
        </div>
        """

        # Auto-apply section
        auto_rows = ""
        for m in gl_data.get("mappings", []):
            if m["mapping_status"] == "mapped":
                auto_rows += f"""
                <tr>
                    <td>{m['vendor_name']}</td>
                    <td>{m['description']}</td>
                    <td style="text-align:right;">${m['amount']:,.2f}</td>
                    <td>{m['proposed_category']}</td>
                    <td>{m['gl_account_number'] or ''} — {m['gl_account_name'] or ''}</td>
                    <td>{m['confidence']:.0%}</td>
                </tr>"""

        auto_section = ""
        if auto_rows:
            auto_section = f"""
            <h2 style="color:#16a34a;">Auto-Apply on Approval</h2>
            <p style="font-size:13px;color:#71717a;">These will be applied on approval.</p>
            <table>
                <thead><tr><th>Vendor</th><th>Description</th><th style="text-align:right;">Amount</th>
                <th>Category</th><th>GL Account</th><th>Confidence</th></tr></thead>
                <tbody>{auto_rows}</tbody>
            </table>
            """

        # Needs review section
        review_rows = ""
        classifications = classify_data.get("classifications", [])
        all_categories = ", ".join(EXPENSE_CATEGORIES)
        for clf in classifications:
            if clf.get("needs_review"):
                review_rows += f"""
                <tr>
                    <td>{clf['vendor_name']}</td>
                    <td>{clf['description']}</td>
                    <td style="text-align:right;">${clf['amount']:,.2f}</td>
                    <td><strong>{clf['proposed_category']}</strong> ({clf['confidence']:.0%})</td>
                    <td style="font-size:12px;color:#71717a;">{clf.get('reasoning', '')}</td>
                </tr>"""

        review_section = ""
        if review_rows:
            review_section = f"""
            <h2 style="color:#d97706;">Needs Manual Review</h2>
            <p style="font-size:13px;color:#71717a;">
                Select correct category before approving. Available categories: {all_categories}
            </p>
            <table>
                <thead><tr><th>Vendor</th><th>Description</th><th style="text-align:right;">Amount</th>
                <th>Best Guess</th><th>Reasoning</th></tr></thead>
                <tbody>{review_rows}</tbody>
            </table>
            """

        # No GL mapping section
        unmapped_categories = set()
        for m in gl_data.get("mappings", []):
            if m["mapping_status"] == "no_gl_mapping":
                unmapped_categories.add(m["proposed_category"])
        unmapped_section = ""
        if unmapped_categories:
            cat_list = "".join(f"<li>{c}</li>" for c in sorted(unmapped_categories))
            unmapped_section = f"""
            <h2 style="color:#71717a;">Categories Missing GL Mapping</h2>
            <p style="font-size:13px;color:#71717a;">Configure these in Settings → GL Accounts.</p>
            <ul>{cat_list}</ul>
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
            <h1>Expense Categorization{dry_run_badge}</h1>
            <div class="meta">{ps} to {pe} &middot; Generated {summary['generated_at']}</div>
            {cards_html}
            {auto_section}
            {review_section}
            {unmapped_section}
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
