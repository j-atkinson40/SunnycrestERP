"""Month-End Close Agent — Phase 2, first real agent implementation.

Pre-flight financial verification layer that runs before statement generation.
Surfaces anomalies for accountant review, then triggers generate_statement_run()
on approval with auto-approval of unflagged statement items.

Steps:
  1. verify_invoice_coverage — match delivered orders to invoices
  2. reconcile_payments — find unmatched / duplicate payments
  3. ar_aging_snapshot — bucket open invoices by age
  4. revenue_summary — period revenue with outlier detection
  5. customer_statements — reuse statement service flag detection
  6. anomaly_detection — cross-step checks
  7. prior_period_comparison — compare to prior agent runs
  8. generate_report — assemble executive summary
"""

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import ClassVar

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.agent import AgentJob
from app.models.customer import Customer
from app.models.customer_payment import CustomerPayment, CustomerPaymentApplication
from app.models.invoice import Invoice
from app.models.sales_order import SalesOrder
from app.models.statement import CustomerStatement, StatementRun
from app.schemas.agent import (
    AgentJobType,
    AnomalyItem,
    AnomalySeverity,
    StepResult,
)
from app.services.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


# Flag code → anomaly severity mapping for statement flags
FLAG_SEVERITY = {
    "open_dispute": AnomalySeverity.CRITICAL,
    "high_balance_variance": AnomalySeverity.WARNING,
    "payment_after_cutoff": AnomalySeverity.WARNING,
    "large_balance": AnomalySeverity.WARNING,
    "credit_balance": AnomalySeverity.INFO,
    "first_statement": AnomalySeverity.INFO,
}


class MonthEndCloseAgent(BaseAgent):
    """Pre-flight financial verification for monthly close."""

    JOB_TYPE = AgentJobType.MONTH_END_CLOSE

    STEPS: ClassVar[list[str]] = [
        "verify_invoice_coverage",
        "reconcile_payments",
        "ar_aging_snapshot",
        "revenue_summary",
        "customer_statements",
        "anomaly_detection",
        "prior_period_comparison",
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
        """Build an AnomalyItem for inclusion in StepResult.anomalies."""
        return AnomalyItem(
            severity=severity,
            anomaly_type=anomaly_type,
            description=description,
            entity_type=entity_type,
            entity_id=entity_id,
            amount=amount,
        )

    # ------------------------------------------------------------------
    # STEP 1 — verify_invoice_coverage
    # ------------------------------------------------------------------

    def _step_verify_invoice_coverage(self) -> StepResult:
        ps, pe = self._period_start(), self._period_end()
        anomalies: list[AnomalyItem] = []

        # Orders delivered in the period
        delivered_orders = (
            self.db.query(SalesOrder)
            .filter(
                SalesOrder.company_id == self.tenant_id,
                SalesOrder.status.in_(["delivered", "completed"]),
                SalesOrder.delivered_at.isnot(None),
                func.date(SalesOrder.delivered_at) >= ps,
                func.date(SalesOrder.delivered_at) <= pe,
            )
            .all()
        )

        # All orders in period (any status)
        all_orders = (
            self.db.query(SalesOrder)
            .filter(
                SalesOrder.company_id == self.tenant_id,
                func.date(SalesOrder.order_date) >= ps,
                func.date(SalesOrder.order_date) <= pe,
            )
            .count()
        )

        uninvoiced = []
        mismatched = []
        invoiced_count = 0

        for order in delivered_orders:
            # Check for linked invoices
            invoices = (
                self.db.query(Invoice)
                .filter(
                    Invoice.company_id == self.tenant_id,
                    Invoice.sales_order_id == order.id,
                )
                .all()
            )

            customer = (
                self.db.query(Customer)
                .filter(Customer.id == order.customer_id)
                .first()
            )
            customer_name = customer.name if customer else "Unknown"
            delivered_date = order.delivered_at.strftime("%Y-%m-%d") if order.delivered_at else "N/A"

            if not invoices:
                order_total = Decimal(str(order.total or 0))
                uninvoiced.append({
                    "order_id": order.id,
                    "order_number": order.number,
                    "customer_name": customer_name,
                    "amount": float(order_total),
                    "delivered_date": delivered_date,
                })
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.CRITICAL,
                    anomaly_type="uninvoiced_delivery",
                    entity_type="order",
                    entity_id=order.id,
                    description=(
                        f"Order #{order.number} for {customer_name} "
                        f"delivered {delivered_date} has no invoice."
                    ),
                    amount=order_total,
                ))
            else:
                invoiced_count += 1
                # Check amount match
                inv_total = sum(Decimal(str(i.total or 0)) for i in invoices)
                order_total = Decimal(str(order.total or 0))
                variance = abs(inv_total - order_total)
                if variance > Decimal("0.01"):
                    mismatched.append({
                        "order_id": order.id,
                        "order_number": order.number,
                        "customer_name": customer_name,
                        "order_total": float(order_total),
                        "invoice_total": float(inv_total),
                        "variance": float(variance),
                    })
                    anomalies.append(self._make_anomaly(
                        severity=AnomalySeverity.WARNING,
                        anomaly_type="invoice_amount_mismatch",
                        entity_type="order",
                        entity_id=order.id,
                        description=(
                            f"Order #{order.number} total ${order_total:,.2f} "
                            f"does not match invoice total ${inv_total:,.2f} "
                            f"(variance: ${variance:,.2f})."
                        ),
                        amount=variance,
                    ))

        delivered_count = len(delivered_orders)
        coverage_pct = round(invoiced_count / delivered_count * 100, 1) if delivered_count > 0 else 100.0

        data = {
            "orders_in_period": all_orders,
            "delivered_count": delivered_count,
            "invoiced_count": invoiced_count,
            "uninvoiced_orders": uninvoiced,
            "mismatched_orders": mismatched,
            "coverage_pct": coverage_pct,
        }

        n_uninvoiced = len(uninvoiced)
        msg = (
            f"{invoiced_count} of {delivered_count} delivered orders invoiced "
            f"({coverage_pct:.1f}% coverage). {n_uninvoiced} uninvoiced "
            f"deliver{'y' if n_uninvoiced == 1 else 'ies'} flagged."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 2 — reconcile_payments
    # ------------------------------------------------------------------

    def _step_reconcile_payments(self) -> StepResult:
        ps, pe = self._period_start(), self._period_end()
        anomalies: list[AnomalyItem] = []

        payments = (
            self.db.query(CustomerPayment)
            .filter(
                CustomerPayment.company_id == self.tenant_id,
                func.date(CustomerPayment.payment_date) >= ps,
                func.date(CustomerPayment.payment_date) <= pe,
                CustomerPayment.deleted_at.is_(None),
            )
            .all()
        )

        payments_total = Decimal(0)
        matched_count = 0
        unmatched_payments = []
        duplicate_suspects = []

        # Group by (customer_id, amount) for duplicate detection
        payment_groups: dict[tuple[str, str], list] = defaultdict(list)

        for p in payments:
            amt = Decimal(str(p.total_amount or 0))
            payments_total += amt

            # Check if matched to any invoice
            apps = (
                self.db.query(CustomerPaymentApplication)
                .filter(CustomerPaymentApplication.payment_id == p.id)
                .all()
            )

            customer = (
                self.db.query(Customer)
                .filter(Customer.id == p.customer_id)
                .first()
            )
            customer_name = customer.name if customer else "Unknown"
            pay_date = p.payment_date.strftime("%Y-%m-%d") if p.payment_date else "N/A"

            if not apps:
                unmatched_payments.append({
                    "payment_id": p.id,
                    "customer_name": customer_name,
                    "amount": float(amt),
                    "payment_date": pay_date,
                    "reference": p.reference_number,
                })
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.WARNING,
                    anomaly_type="unmatched_payment",
                    entity_type="payment",
                    entity_id=p.id,
                    description=(
                        f"Payment of ${amt:,.2f} received {pay_date} "
                        f"from {customer_name} is not matched to any invoice."
                    ),
                    amount=amt,
                ))
            else:
                matched_count += 1

            # Duplicate detection grouping
            amount_key = str(amt.quantize(Decimal("0.01")))
            payment_groups[(p.customer_id, amount_key)].append(p)

        # Detect duplicates: same customer+amount within 3 days
        for (cust_id, _), group in payment_groups.items():
            if len(group) < 2:
                continue
            group.sort(key=lambda x: x.payment_date)
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    delta = abs((group[j].payment_date - group[i].payment_date).days)
                    if delta <= 3:
                        customer = (
                            self.db.query(Customer)
                            .filter(Customer.id == cust_id)
                            .first()
                        )
                        cname = customer.name if customer else "Unknown"
                        amt = Decimal(str(group[i].total_amount or 0))
                        d1 = group[i].payment_date.strftime("%Y-%m-%d")
                        d2 = group[j].payment_date.strftime("%Y-%m-%d")
                        dup_entry = {
                            "customer_name": cname,
                            "amount": float(amt),
                            "payment_ids": [group[i].id, group[j].id],
                            "dates": [d1, d2],
                        }
                        if dup_entry not in duplicate_suspects:
                            duplicate_suspects.append(dup_entry)
                            anomalies.append(self._make_anomaly(
                                severity=AnomalySeverity.CRITICAL,
                                anomaly_type="duplicate_payment",
                                entity_type="payment",
                                entity_id=group[j].id,
                                description=(
                                    f"Possible duplicate: two payments of ${amt:,.2f} "
                                    f"from {cname} on {d1} and {d2} ({delta} days apart)."
                                ),
                                amount=amt,
                            ))

        data = {
            "payments_count": len(payments),
            "payments_total": float(payments_total),
            "matched_count": matched_count,
            "unmatched_count": len(unmatched_payments),
            "unmatched_payments": unmatched_payments,
            "duplicate_suspects": duplicate_suspects,
        }

        msg = (
            f"{len(payments)} payments totalling ${payments_total:,.2f}. "
            f"{matched_count} matched, {len(unmatched_payments)} unmatched. "
            f"{len(duplicate_suspects)} duplicate suspect(s)."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 3 — ar_aging_snapshot
    # ------------------------------------------------------------------

    def _step_ar_aging_snapshot(self) -> StepResult:
        pe = self._period_end()
        anomalies: list[AnomalyItem] = []

        open_invoices = (
            self.db.query(Invoice)
            .filter(
                Invoice.company_id == self.tenant_id,
                Invoice.status.notin_(["paid", "void", "write_off", "draft"]),
            )
            .all()
        )

        buckets = {"current": [], "bucket_30": [], "bucket_60": [], "bucket_90": []}
        by_customer: dict[str, dict] = {}

        for inv in open_invoices:
            balance = Decimal(str(inv.total or 0)) - Decimal(str(inv.amount_paid or 0))
            if balance <= 0:
                continue

            # Age from due_date, fall back to invoice_date
            age_from = inv.due_date or inv.invoice_date
            if age_from:
                if hasattr(age_from, "date"):
                    age_from = age_from.date()
                days = (pe - age_from).days
            else:
                days = 0

            if days > 90:
                bucket_key = "bucket_90"
            elif days > 60:
                bucket_key = "bucket_60"
            elif days > 30:
                bucket_key = "bucket_30"
            else:
                bucket_key = "current"

            buckets[bucket_key].append({"invoice_id": inv.id, "balance": balance, "days": days})

            # Per-customer accumulation
            cid = inv.customer_id
            if cid not in by_customer:
                customer = self.db.query(Customer).filter(Customer.id == cid).first()
                by_customer[cid] = {
                    "customer_id": cid,
                    "customer_name": customer.name if customer else "Unknown",
                    "current": Decimal(0),
                    "bucket_30": Decimal(0),
                    "bucket_60": Decimal(0),
                    "bucket_90": Decimal(0),
                    "total": Decimal(0),
                }
            by_customer[cid][bucket_key] += balance
            by_customer[cid]["total"] += balance

            # Flag 90+ day invoices
            if days > 90:
                customer = self.db.query(Customer).filter(Customer.id == cid).first()
                cname = customer.name if customer else "Unknown"
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.WARNING,
                    anomaly_type="overdue_ar_90plus",
                    entity_type="invoice",
                    entity_id=inv.id,
                    description=(
                        f"Invoice #{inv.number} for {cname} is {days} days "
                        f"past due. Balance: ${balance:,.2f}."
                    ),
                    amount=balance,
                ))

        # Compute totals
        def _bucket_summary(items):
            return {
                "count": len(items),
                "total": float(sum(i["balance"] for i in items)),
            }

        total_ar = sum(
            sum(i["balance"] for i in items) for items in buckets.values()
        )

        # Serialize by_customer for JSON
        customer_aging = []
        for c in sorted(by_customer.values(), key=lambda x: x["total"], reverse=True):
            customer_aging.append({
                "customer_id": c["customer_id"],
                "customer_name": c["customer_name"],
                "current": float(c["current"]),
                "bucket_30": float(c["bucket_30"]),
                "bucket_60": float(c["bucket_60"]),
                "bucket_90": float(c["bucket_90"]),
                "total": float(c["total"]),
            })

        data = {
            "snapshot_date": pe.isoformat(),
            "total_ar": float(total_ar),
            "current": _bucket_summary(buckets["current"]),
            "bucket_30": _bucket_summary(buckets["bucket_30"]),
            "bucket_60": _bucket_summary(buckets["bucket_60"]),
            "bucket_90": _bucket_summary(buckets["bucket_90"]),
            "by_customer": customer_aging,
        }

        msg = (
            f"Total AR: ${total_ar:,.2f}. "
            f"Current: {len(buckets['current'])}, "
            f"30+: {len(buckets['bucket_30'])}, "
            f"60+: {len(buckets['bucket_60'])}, "
            f"90+: {len(buckets['bucket_90'])}."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 4 — revenue_summary
    # ------------------------------------------------------------------

    def _step_revenue_summary(self) -> StepResult:
        ps, pe = self._period_start(), self._period_end()
        anomalies: list[AnomalyItem] = []

        invoices = (
            self.db.query(Invoice)
            .filter(
                Invoice.company_id == self.tenant_id,
                func.date(Invoice.invoice_date) >= ps,
                func.date(Invoice.invoice_date) <= pe,
            )
            .all()
        )

        total_revenue = Decimal(0)
        by_customer: dict[str, dict] = {}

        for inv in invoices:
            amt = Decimal(str(inv.total or 0))
            total_revenue += amt
            cid = inv.customer_id
            if cid not in by_customer:
                customer = self.db.query(Customer).filter(Customer.id == cid).first()
                by_customer[cid] = {
                    "customer_name": customer.name if customer else "Unknown",
                    "total": Decimal(0),
                    "count": 0,
                }
            by_customer[cid]["total"] += amt
            by_customer[cid]["count"] += 1

        invoice_count = len(invoices)
        avg_order_value = (
            (total_revenue / invoice_count).quantize(Decimal("0.01"), ROUND_HALF_UP)
            if invoice_count > 0
            else Decimal(0)
        )

        # Adaptive outlier detection — query prior completed month-end close jobs
        prior_jobs = (
            self.db.query(AgentJob)
            .filter(
                AgentJob.tenant_id == self.tenant_id,
                AgentJob.job_type == "month_end_close",
                AgentJob.status == "complete",
                AgentJob.period_end < ps,
            )
            .order_by(AgentJob.period_end.desc())
            .limit(6)
            .all()
        )

        history_months = len(prior_jobs)
        outlier_detection = "deferred"

        if history_months >= 3:
            prior_revenues = []
            for pj in prior_jobs:
                rp = pj.report_payload or {}
                es = rp.get("executive_summary", {})
                pr = es.get("total_revenue")
                if pr is not None:
                    prior_revenues.append(Decimal(str(pr)))
            if len(prior_revenues) >= 3:
                mean = sum(prior_revenues) / len(prior_revenues)
                variance = sum((r - mean) ** 2 for r in prior_revenues) / len(prior_revenues)
                stddev = variance ** Decimal("0.5")
                threshold = mean + (Decimal("2.5") * stddev)
                if total_revenue > threshold and stddev > 0:
                    outlier_detection = "active"
                    anomalies.append(self._make_anomaly(
                        severity=AnomalySeverity.WARNING,
                        anomaly_type="revenue_outlier",
                        description=(
                            f"Total revenue ${total_revenue:,.2f} exceeds "
                            f"historical threshold of ${threshold:,.2f} "
                            f"(mean + 2.5 stddev)."
                        ),
                        amount=total_revenue,
                    ))
                else:
                    outlier_detection = "active"

        customer_summary = sorted(
            [{"customer_name": v["customer_name"], "total": float(v["total"]), "count": v["count"]}
             for v in by_customer.values()],
            key=lambda x: x["total"],
            reverse=True,
        )

        data = {
            "total_revenue": float(total_revenue),
            "invoice_count": invoice_count,
            "average_order_value": float(avg_order_value),
            "by_customer": customer_summary,
            "outlier_detection": outlier_detection,
            "history_months_available": history_months,
        }

        msg = (
            f"${total_revenue:,.2f} total revenue from {invoice_count} invoices. "
            f"Avg order value: ${avg_order_value:,.2f}. "
            f"Outlier detection: {outlier_detection} "
            f"({history_months} prior months available)."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 5 — customer_statements
    # ------------------------------------------------------------------

    def _step_customer_statements(self) -> StepResult:
        from app.services.statement_generation_service import (
            calculate_statement_data,
            detect_flags,
            get_eligible_customers,
        )

        ps, pe = self._period_start(), self._period_end()
        anomalies: list[AnomalyItem] = []

        # Part A — eligible customers
        eligible = get_eligible_customers(
            db=self.db,
            tenant_id=str(self.tenant_id),
            period_end=pe,
        )

        customers_data = []
        total_opening = Decimal(0)
        total_closing = Decimal(0)
        flag_count = 0

        # Part B — per-customer statement data + flags
        for customer in eligible:
            data = calculate_statement_data(
                db=self.db,
                tenant_id=str(self.tenant_id),
                customer_id=str(customer.id),
                period_start=ps,
                period_end=pe,
            )

            flags = detect_flags(
                db=self.db,
                tenant_id=str(self.tenant_id),
                customer=customer,
                statement_data=data,
                period_end=pe,
            )

            opening = Decimal(str(data["opening_balance"]))
            closing = Decimal(str(data["closing_balance"]))
            total_opening += opening
            total_closing += closing

            # Part C — map flags to anomalies
            for flag in flags:
                flag_code = flag.get("code", "unknown")
                severity = FLAG_SEVERITY.get(flag_code, AnomalySeverity.INFO)
                anomalies.append(self._make_anomaly(
                    severity=severity,
                    anomaly_type=f"statement_{flag_code}",
                    entity_type="customer",
                    entity_id=customer.id,
                    description=flag.get("message", ""),
                    amount=Decimal(str(closing)) if closing != 0 else None,
                ))
                flag_count += 1

            net_change = Decimal(str(data["invoices_total"])) - Decimal(str(data["payments_total"]))
            customers_data.append({
                "customer_id": customer.id,
                "customer_name": customer.name,
                "opening_balance": float(opening),
                "closing_balance": float(closing),
                "invoices_in_period": data["invoice_count"],
                "payments_in_period": float(data["payments_total"]),
                "flags": flags,
                "net_change": float(net_change),
            })

        # Part D — check for StatementRun conflict
        statement_run_conflict = False
        existing_run_id = None
        existing_run = (
            self.db.query(StatementRun)
            .filter(
                StatementRun.tenant_id == self.tenant_id,
                StatementRun.statement_period_month == ps.month,
                StatementRun.statement_period_year == ps.year,
            )
            .first()
        )
        if existing_run and existing_run.status != "draft":
            statement_run_conflict = True
            existing_run_id = existing_run.id
            anomalies.append(self._make_anomaly(
                severity=AnomalySeverity.CRITICAL,
                anomaly_type="statement_run_conflict",
                description=(
                    f"A statement run for this period already exists "
                    f"with status '{existing_run.status}'. "
                    f"Review before proceeding."
                ),
            ))

        conflict_msg = (
            f"Statement run conflict detected (status: {existing_run.status})."
            if statement_run_conflict
            else "No statement run conflict."
        )

        data = {
            "eligible_customer_count": len(eligible),
            "statement_run_conflict": statement_run_conflict,
            "existing_statement_run_id": existing_run_id,
            "customers": customers_data,
            "total_opening_balance": float(total_opening),
            "total_closing_balance": float(total_closing),
        }

        msg = (
            f"{len(eligible)} customers eligible for statements. "
            f"{flag_count} statement flags detected. "
            f"{conflict_msg}"
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 6 — anomaly_detection (cross-step)
    # ------------------------------------------------------------------

    def _step_anomaly_detection(self) -> StepResult:
        anomalies: list[AnomalyItem] = []
        ps, pe = self._period_start(), self._period_end()

        payments_data = self.step_results.get("reconcile_payments", {})
        revenue_data = self.step_results.get("revenue_summary", {})
        statements_data = self.step_results.get("customer_statements", {})

        # CHECK A — Collection rate
        total_collected = Decimal(str(payments_data.get("payments_total", 0)))
        total_invoiced = Decimal(str(revenue_data.get("total_revenue", 0)))
        history_months = revenue_data.get("history_months_available", 0)

        collection_rate_pct = 0.0
        if total_invoiced > 0:
            collection_rate_pct = float(total_collected / total_invoiced * 100)
            if collection_rate_pct < 50 and history_months > 0:
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.WARNING,
                    anomaly_type="low_collection_rate",
                    description=(
                        f"Collection rate is {collection_rate_pct:.1f}% "
                        f"(${total_collected:,.2f} collected vs "
                        f"${total_invoiced:,.2f} invoiced). "
                        f"Consider reviewing AR follow-up."
                    ),
                ))

        # CHECK B — Zero-activity customers
        eligible_customers = statements_data.get("customers", [])
        inactive_customers = []

        for cust in eligible_customers:
            if cust["invoices_in_period"] == 0 and float(cust.get("payments_in_period", 0)) == 0:
                # Check if they had activity in prior period
                prev_start = (ps.replace(day=1) - timedelta(days=1)).replace(day=1)
                prev_end = ps - timedelta(days=1)
                prior_inv = (
                    self.db.query(Invoice)
                    .filter(
                        Invoice.company_id == self.tenant_id,
                        Invoice.customer_id == cust["customer_id"],
                        func.date(Invoice.invoice_date) >= prev_start,
                        func.date(Invoice.invoice_date) <= prev_end,
                    )
                    .count()
                )
                if prior_inv > 0:
                    inactive_customers.append(cust["customer_name"])
                    anomalies.append(self._make_anomaly(
                        severity=AnomalySeverity.INFO,
                        anomaly_type="inactive_customer",
                        entity_type="customer",
                        entity_id=cust["customer_id"],
                        description=(
                            f"{cust['customer_name']} had activity last period "
                            f"but none this period."
                        ),
                    ))

        # CHECK C — Invoice volume vs prior
        current_count = revenue_data.get("invoice_count", 0)
        if history_months > 0:
            prior_jobs = (
                self.db.query(AgentJob)
                .filter(
                    AgentJob.tenant_id == self.tenant_id,
                    AgentJob.job_type == "month_end_close",
                    AgentJob.status == "complete",
                    AgentJob.period_end < ps,
                )
                .order_by(AgentJob.period_end.desc())
                .limit(3)
                .all()
            )
            prior_counts = []
            for pj in prior_jobs:
                rp = pj.report_payload or {}
                es = rp.get("executive_summary", {})
                pc = es.get("invoice_count")
                if pc is not None:
                    prior_counts.append(pc)
            if prior_counts:
                prior_avg = sum(prior_counts) / len(prior_counts)
                if prior_avg > 0 and current_count < prior_avg * 0.5:
                    anomalies.append(self._make_anomaly(
                        severity=AnomalySeverity.INFO,
                        anomaly_type="low_invoice_volume",
                        description=(
                            f"Invoice count ({current_count}) is less than half "
                            f"the prior average ({prior_avg:.0f}). "
                            f"Verify all orders are invoiced."
                        ),
                    ))

        data = {
            "cross_step_anomalies_added": len(anomalies),
            "collection_rate_pct": round(collection_rate_pct, 1),
            "inactive_customers": inactive_customers,
        }

        msg = (
            f"{len(anomalies)} cross-step anomalies. "
            f"Collection rate: {collection_rate_pct:.1f}%. "
            f"{len(inactive_customers)} inactive customer(s) with prior activity."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 7 — prior_period_comparison
    # ------------------------------------------------------------------

    def _step_prior_period_comparison(self) -> StepResult:
        ps = self._period_start()

        prior_jobs = (
            self.db.query(AgentJob)
            .filter(
                AgentJob.tenant_id == self.tenant_id,
                AgentJob.job_type == "month_end_close",
                AgentJob.status == "complete",
                AgentJob.period_end < ps,
            )
            .order_by(AgentJob.period_end.desc())
            .limit(13)
            .all()
        )

        # Current period data from prior steps
        revenue_data = self.step_results.get("revenue_summary", {})
        aging_data = self.step_results.get("ar_aging_snapshot", {})

        current_revenue = Decimal(str(revenue_data.get("total_revenue", 0)))
        current_count = revenue_data.get("invoice_count", 0)
        current_ar = Decimal(str(aging_data.get("total_ar", 0)))

        def _extract_comparison(job):
            rp = job.report_payload or {}
            es = rp.get("executive_summary", {})
            rev = es.get("total_revenue")
            cnt = es.get("invoice_count")
            ar = es.get("total_ar")
            if rev is None:
                return None

            rev = Decimal(str(rev))
            ar = Decimal(str(ar)) if ar is not None else Decimal(0)
            cnt = cnt or 0

            period_label = f"{job.period_start} to {job.period_end}" if job.period_start else "Unknown"

            def _var(cur, prev):
                if prev and prev != 0:
                    return round(float((cur - prev) / prev * 100), 1)
                return None

            return {
                "period_label": period_label,
                "revenue": float(rev),
                "revenue_variance_pct": _var(current_revenue, rev),
                "invoice_count": cnt,
                "invoice_count_variance_pct": _var(Decimal(current_count), Decimal(cnt)) if cnt else None,
                "total_ar": float(ar),
                "ar_variance_pct": _var(current_ar, ar),
            }

        vs_prior = None
        vs_same_month_ly = None

        if prior_jobs:
            vs_prior = _extract_comparison(prior_jobs[0])

        # Same month last year
        target_month = ps.month
        target_year = ps.year - 1
        for pj in prior_jobs:
            if pj.period_start and pj.period_start.month == target_month and pj.period_start.year == target_year:
                vs_same_month_ly = _extract_comparison(pj)
                break

        comparison_available = vs_prior is not None

        data = {
            "comparison_available": comparison_available,
            "vs_prior_month": vs_prior,
            "vs_same_month_last_year": vs_same_month_ly,
        }

        if comparison_available:
            rev_var = vs_prior.get("revenue_variance_pct")
            msg = (
                f"Prior month comparison available. "
                f"Revenue variance: {rev_var:+.1f}%."
                if rev_var is not None
                else "Prior month comparison available (no revenue data)."
            )
        else:
            msg = "No prior completed month-end close runs found for comparison."

        return StepResult(message=msg, data=data, anomalies=[])

    # ------------------------------------------------------------------
    # STEP 8 — generate_report
    # ------------------------------------------------------------------

    def _step_generate_report(self) -> StepResult:
        revenue_data = self.step_results.get("revenue_summary", {})
        payments_data = self.step_results.get("reconcile_payments", {})
        aging_data = self.step_results.get("ar_aging_snapshot", {})
        statements_data = self.step_results.get("customer_statements", {})
        anomaly_data = self.step_results.get("anomaly_detection", {})
        comparison_data = self.step_results.get("prior_period_comparison", {})

        # Count anomalies by severity
        critical = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.CRITICAL)
        warning = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.WARNING)
        info = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.INFO)

        rev_var = None
        vs_prior = comparison_data.get("vs_prior_month")
        if vs_prior:
            rev_var = vs_prior.get("revenue_variance_pct")

        executive_summary = {
            "period": f"{self._period_start()} to {self._period_end()}",
            "total_revenue": revenue_data.get("total_revenue", 0),
            "invoice_count": revenue_data.get("invoice_count", 0),
            "payments_received_total": payments_data.get("payments_total", 0),
            "total_ar": aging_data.get("total_ar", 0),
            "eligible_customers": statements_data.get("eligible_customer_count", 0),
            "anomaly_count": self.job.anomaly_count,
            "critical_anomaly_count": critical,
            "warning_anomaly_count": warning,
            "info_anomaly_count": info,
            "collection_rate_pct": anomaly_data.get("collection_rate_pct", 0),
            "prior_period_revenue_variance_pct": rev_var,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": self.dry_run,
        }

        # Store executive_summary in step_results so _assemble_report() includes it
        self.step_results["generate_report"] = {"report_generated": True}

        # Override report_payload to include executive_summary at top level
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

        # Generate HTML report
        from app.services.agents.approval_gate import ApprovalGateService
        self.job.report_payload["report_html"] = ApprovalGateService.generate_review_html(self.job)

        self.db.commit()

        msg = (
            f"Report ready. {self.job.anomaly_count} anomalies "
            f"({critical} critical, {warning} warning, {info} info). "
            f"Ready for accountant review."
        )

        return StepResult(message=msg, data={"report_generated": True}, anomalies=[])

    # ------------------------------------------------------------------
    # Override _assemble_report to skip — generate_report step handles it
    # ------------------------------------------------------------------

    def _assemble_report(self) -> None:
        """Skip default assembly — generate_report step already built report_payload."""
        # report_payload is already set by _step_generate_report
        pass
