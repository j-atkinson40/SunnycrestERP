"""Unbilled Orders Agent — Phase 4.

Weekly agent that finds delivered orders with no invoice.
Revenue protection — catches billable work before it slips through.

Steps:
  1. find_unbilled_orders — delivered orders with no linked invoice
  2. analyze_patterns — repeat customers, aging acceleration, high value
  3. generate_report — executive summary + HTML report
"""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import ClassVar

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.sales_order import SalesOrder
from app.schemas.agent import (
    AgentJobType,
    AnomalyItem,
    AnomalySeverity,
    StepResult,
)
from app.services.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# Urgency thresholds (days unbilled)
URGENCY_LOW_MAX = 7
URGENCY_MEDIUM_MAX = 21


class UnbilledOrdersAgent(BaseAgent):
    """Weekly agent that identifies delivered orders with no invoice."""

    JOB_TYPE = AgentJobType.UNBILLED_ORDERS

    STEPS: ClassVar[list[str]] = [
        "find_unbilled_orders",
        "analyze_patterns",
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
    # STEP 1 — find_unbilled_orders
    # ------------------------------------------------------------------

    def _step_find_unbilled_orders(self) -> StepResult:
        today = date.today()
        anomalies: list[AnomalyItem] = []

        # All delivered orders for this tenant with delivered_at set
        delivered_orders = (
            self.db.query(SalesOrder)
            .filter(
                SalesOrder.company_id == self.tenant_id,
                SalesOrder.status.in_(["delivered", "completed"]),
                SalesOrder.delivered_at.isnot(None),
            )
            .all()
        )

        unbilled = []

        for order in delivered_orders:
            # Check if any invoice links to this order
            invoice_count = (
                self.db.query(Invoice)
                .filter(
                    Invoice.company_id == self.tenant_id,
                    Invoice.sales_order_id == order.id,
                )
                .count()
            )
            if invoice_count > 0:
                continue

            customer = (
                self.db.query(Customer)
                .filter(Customer.id == order.customer_id)
                .first()
            )
            customer_name = customer.name if customer else "Unknown"

            delivered_date = order.delivered_at.date() if hasattr(order.delivered_at, "date") else order.delivered_at
            days_unbilled = (today - delivered_date).days if delivered_date else 0

            # Estimated value from order total (may be null)
            estimated_value = Decimal(str(order.total or 0))

            # Classify urgency
            if days_unbilled <= URGENCY_LOW_MAX:
                urgency = "LOW"
            elif days_unbilled <= URGENCY_MEDIUM_MAX:
                urgency = "MEDIUM"
            else:
                urgency = "HIGH"

            # Cemetery name if available
            cemetery_name = None
            if order.cemetery_id:
                from app.models.cemetery import Cemetery
                cemetery = self.db.query(Cemetery).filter(Cemetery.id == order.cemetery_id).first()
                cemetery_name = cemetery.name if cemetery else None

            unbilled.append({
                "order_id": order.id,
                "order_number": order.number,
                "customer_id": order.customer_id,
                "customer_name": customer_name,
                "delivered_date": str(delivered_date) if delivered_date else None,
                "days_unbilled": max(days_unbilled, 0),
                "estimated_value": float(estimated_value),
                "urgency": urgency,
                "vault_type": order.order_type,
                "cemetery_name": cemetery_name,
            })

            # Add anomalies for HIGH and MEDIUM
            if urgency == "HIGH":
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.CRITICAL,
                    anomaly_type="unbilled_high",
                    entity_type="order",
                    entity_id=order.id,
                    description=(
                        f"Order #{order.number} for {customer_name} "
                        f"delivered {days_unbilled} days ago, still not invoiced. "
                        f"Est. value: ${float(estimated_value):,.2f}."
                    ),
                    amount=estimated_value,
                ))
            elif urgency == "MEDIUM":
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.WARNING,
                    anomaly_type="unbilled_medium",
                    entity_type="order",
                    entity_id=order.id,
                    description=(
                        f"Order #{order.number} for {customer_name} "
                        f"delivered {days_unbilled} days ago, still not invoiced. "
                        f"Est. value: ${float(estimated_value):,.2f}."
                    ),
                    amount=estimated_value,
                ))

        # Compute totals
        total_value = Decimal(0)
        low_count = low_value = 0
        medium_count = medium_value = 0
        high_count = high_value = 0

        for o in unbilled:
            val = Decimal(str(o["estimated_value"]))
            total_value += val
            if o["urgency"] == "LOW":
                low_count += 1
                low_value += float(val)
            elif o["urgency"] == "MEDIUM":
                medium_count += 1
                medium_value += float(val)
            else:
                high_count += 1
                high_value += float(val)

        data = {
            "total_unbilled_count": len(unbilled),
            "total_estimated_value": float(total_value),
            "low_count": low_count,
            "low_value": low_value,
            "medium_count": medium_count,
            "medium_value": medium_value,
            "high_count": high_count,
            "high_value": high_value,
            "orders": unbilled,
        }

        msg = (
            f"{len(unbilled)} unbilled delivered orders, "
            f"estimated ${float(total_value):,.2f} in uninvoiced revenue. "
            f"{high_count} high urgency."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 2 — analyze_patterns
    # ------------------------------------------------------------------

    def _step_analyze_patterns(self) -> StepResult:
        unbilled_data = self.step_results.get("find_unbilled_orders", {})
        orders = unbilled_data.get("orders", [])
        anomalies: list[AnomalyItem] = []
        patterns_found = 0

        # PATTERN A — Repeat customers
        customer_groups: dict[str, list[dict]] = {}
        for o in orders:
            cid = o["customer_id"]
            if cid not in customer_groups:
                customer_groups[cid] = []
            customer_groups[cid].append(o)

        repeat_customers = []
        for cid, group in customer_groups.items():
            if len(group) >= 2:
                total = sum(Decimal(str(o["estimated_value"])) for o in group)
                cname = group[0]["customer_name"]
                repeat_customers.append({
                    "customer_name": cname,
                    "count": len(group),
                    "total": float(total),
                })
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.WARNING,
                    anomaly_type="unbilled_repeat_customer",
                    entity_type="customer",
                    entity_id=cid,
                    description=(
                        f"{cname} has {len(group)} unbilled delivered orders "
                        f"totaling ${float(total):,.2f}. "
                        f"Possible billing workflow issue for this customer."
                    ),
                    amount=total,
                ))
                patterns_found += 1

        # PATTERN B — Aging acceleration
        low_count = unbilled_data.get("low_count", 0)
        medium_count = unbilled_data.get("medium_count", 0)
        high_count = unbilled_data.get("high_count", 0)
        backlog_growing = (
            high_count > medium_count > low_count
            and high_count > 0
        )

        if backlog_growing:
            anomalies.append(self._make_anomaly(
                severity=AnomalySeverity.WARNING,
                anomaly_type="unbilled_backlog_growing",
                description=(
                    f"Unbilled order backlog appears to be growing: "
                    f"{low_count} recent, {medium_count} medium, {high_count} old. "
                    f"Billing workflow may need attention."
                ),
            ))
            patterns_found += 1

        # PATTERN C — High value single order
        # Average order value from all invoiced orders
        avg_query = (
            self.db.query(func.avg(Invoice.total))
            .filter(
                Invoice.company_id == self.tenant_id,
                Invoice.status.notin_(["void", "write_off"]),
            )
            .scalar()
        )
        avg_order_value = Decimal(str(avg_query or 0))

        high_value_orders = []
        if avg_order_value > 0:
            threshold = avg_order_value * 3
            for o in orders:
                val = Decimal(str(o["estimated_value"]))
                if val > threshold:
                    high_value_orders.append({
                        "order_number": o["order_number"],
                        "value": float(val),
                    })
                    anomalies.append(self._make_anomaly(
                        severity=AnomalySeverity.WARNING,
                        anomaly_type="unbilled_high_value",
                        entity_type="order",
                        entity_id=o["order_id"],
                        description=(
                            f"Order #{o['order_number']} for "
                            f"${float(val):,.2f} is significantly above "
                            f"average order value and remains unbilled."
                        ),
                        amount=val,
                    ))
                    patterns_found += 1

        data = {
            "patterns_found": patterns_found,
            "repeat_customers": repeat_customers,
            "backlog_growing": backlog_growing,
            "high_value_orders": high_value_orders,
        }

        msg = (
            f"{patterns_found} billing patterns flagged. "
            f"{len(repeat_customers)} customers with multiple unbilled orders."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 3 — generate_report
    # ------------------------------------------------------------------

    def _step_generate_report(self) -> StepResult:
        unbilled_data = self.step_results.get("find_unbilled_orders", {})
        pattern_data = self.step_results.get("analyze_patterns", {})

        total_count = unbilled_data.get("total_unbilled_count", 0)
        total_value = unbilled_data.get("total_estimated_value", 0)
        high_count = unbilled_data.get("high_count", 0)
        high_value = unbilled_data.get("high_value", 0)

        critical = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.CRITICAL)
        warning = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.WARNING)
        info = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.INFO)

        executive_summary = {
            "report_date": date.today().isoformat(),
            "total_unbilled_count": total_count,
            "total_estimated_value": total_value,
            "high_urgency_count": high_count,
            "high_urgency_value": high_value,
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
            executive_summary, unbilled_data, pattern_data,
        )
        self.db.commit()

        msg = (
            f"Unbilled orders report ready. "
            f"${total_value:,.2f} in uninvoiced revenue identified."
        )

        return StepResult(message=msg, data={"report_generated": True}, anomalies=[])

    def _build_report_html(
        self,
        summary: dict,
        unbilled_data: dict,
        pattern_data: dict,
    ) -> str:
        total_count = summary.get("total_unbilled_count", 0)
        total_value = summary.get("total_estimated_value", 0)
        high_count = summary.get("high_urgency_count", 0)
        high_value = summary.get("high_urgency_value", 0)

        dry_run_badge = (
            '<span style="background:#f59e0b;color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:12px;margin-left:8px;">DRY RUN</span>'
            if self.dry_run else ""
        )

        # Urgency breakdown table
        urgency_data = [
            ("HIGH", unbilled_data.get("high_count", 0), unbilled_data.get("high_value", 0), "Immediate billing"),
            ("MEDIUM", unbilled_data.get("medium_count", 0), unbilled_data.get("medium_value", 0), "Bill this week"),
            ("LOW", unbilled_data.get("low_count", 0), unbilled_data.get("low_value", 0), "Monitor"),
        ]
        urgency_colors = {"HIGH": "#dc2626", "MEDIUM": "#d97706", "LOW": "#16a34a"}

        urgency_rows = ""
        for urg, count, value, action in urgency_data:
            color = urgency_colors[urg]
            urgency_rows += (
                f'<tr><td><span style="background:{color};color:#fff;padding:2px 8px;'
                f'border-radius:4px;font-size:12px;">{urg}</span></td>'
                f'<td>{count}</td>'
                f'<td style="text-align:right;">${value:,.2f}</td>'
                f'<td>{action}</td></tr>'
            )

        # Order list
        orders = unbilled_data.get("orders", [])
        # Sort: HIGH first, then MEDIUM, then LOW
        urgency_sort = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        orders_sorted = sorted(orders, key=lambda o: urgency_sort.get(o.get("urgency", "LOW"), 3))

        order_rows = ""
        for o in orders_sorted:
            urg = o.get("urgency", "LOW")
            color = urgency_colors.get(urg, "#6b7280")
            order_rows += (
                f'<tr><td>{o.get("order_number", "")}</td>'
                f'<td>{o.get("customer_name", "")}</td>'
                f'<td>{o.get("cemetery_name", "") or "—"}</td>'
                f'<td>{o.get("vault_type", "") or "—"}</td>'
                f'<td>{o.get("delivered_date", "")}</td>'
                f'<td>{o.get("days_unbilled", 0)}</td>'
                f'<td style="text-align:right;">${o.get("estimated_value", 0):,.2f}</td>'
                f'<td><span style="background:{color};color:#fff;padding:2px 8px;'
                f'border-radius:4px;font-size:12px;">{urg}</span></td></tr>'
            )

        # Patterns section
        patterns_html = ""
        if pattern_data.get("patterns_found", 0) > 0:
            patterns_html = "<h2>Billing Patterns</h2><ul>"
            for rc in pattern_data.get("repeat_customers", []):
                patterns_html += (
                    f'<li><strong>{rc["customer_name"]}</strong>: '
                    f'{rc["count"]} unbilled orders totaling ${rc["total"]:,.2f}</li>'
                )
            if pattern_data.get("backlog_growing"):
                patterns_html += "<li><strong>Warning:</strong> Unbilled backlog is growing over time.</li>"
            for hv in pattern_data.get("high_value_orders", []):
                patterns_html += (
                    f'<li>High value: Order #{hv["order_number"]} '
                    f'(${hv["value"]:,.2f}) above average</li>'
                )
            patterns_html += "</ul>"

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
            <h1>Unbilled Orders Audit{dry_run_badge}</h1>
            <div class="meta">{period_label} &middot; Generated {summary.get('generated_at', '')}</div>

            <div class="cards">
                <div class="card">
                    <div class="card-value">{total_count}</div>
                    <div class="card-label">Unbilled Orders</div>
                </div>
                <div class="card">
                    <div class="card-value">${total_value:,.0f}</div>
                    <div class="card-label">Est. Value</div>
                </div>
                <div class="card">
                    <div class="card-value">{high_count}</div>
                    <div class="card-label">High Urgency</div>
                </div>
                <div class="card">
                    <div class="card-value">${high_value:,.0f}</div>
                    <div class="card-label">High Urgency Value</div>
                </div>
            </div>

            <h2>Urgency Breakdown</h2>
            <table>
                <thead><tr><th>Urgency</th><th>Orders</th><th style="text-align:right;">Est. Value</th><th>Action</th></tr></thead>
                <tbody>{urgency_rows}</tbody>
            </table>

            <h2>Order Detail</h2>
            <table>
                <thead><tr><th>Order #</th><th>Customer</th><th>Cemetery</th><th>Type</th><th>Delivered</th><th>Days</th><th style="text-align:right;">Value</th><th>Urgency</th></tr></thead>
                <tbody>{order_rows or '<tr><td colspan="8" style="text-align:center;color:#16a34a;">No unbilled orders found</td></tr>'}</tbody>
            </table>

            {patterns_html}
        </div>
        </body>
        </html>
        """

    # ------------------------------------------------------------------
    # Override _assemble_report — generate_report step handles it
    # ------------------------------------------------------------------

    def _assemble_report(self) -> None:
        pass
