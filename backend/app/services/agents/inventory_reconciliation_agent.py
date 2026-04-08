"""Inventory Reconciliation Agent — Phase 8.

Quarterly agent that reconciles physical inventory records against what
the system expects based on production and deliveries.  Surfaces
discrepancies, computes reserved vs available, and flags products whose
on-hand balance cannot be explained by the transaction history.

Steps:
  1. snapshot_current_inventory
  2. verify_transaction_integrity
  3. compute_reserved_quantity
  4. reconcile_production_vs_deliveries
  5. check_physical_count_freshness
  6. generate_report
"""

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import ClassVar

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.inventory_item import InventoryItem
from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product
from app.models.production_log_entry import ProductionLogEntry
from app.models.sales_order import SalesOrder, SalesOrderLine
from app.models.work_order import WorkOrder
from app.schemas.agent import (
    AgentJobType,
    AnomalyItem,
    AnomalySeverity,
    StepResult,
)
from app.services.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# Physical count freshness thresholds (days)
FRESH_THRESHOLD = 90
STALE_THRESHOLD = 180
LARGE_COUNT_ADJUSTMENT_THRESHOLD = 5


class InventoryReconciliationAgent(BaseAgent):
    """Quarterly agent that reconciles inventory records."""

    JOB_TYPE = AgentJobType.INVENTORY_RECONCILIATION

    STEPS: ClassVar[list[str]] = [
        "snapshot_current_inventory",
        "verify_transaction_integrity",
        "compute_reserved_quantity",
        "reconcile_production_vs_deliveries",
        "check_physical_count_freshness",
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
    # STEP 1 — snapshot_current_inventory
    # ------------------------------------------------------------------

    def _step_snapshot_current_inventory(self) -> StepResult:
        # All tracked inventory items for this tenant
        items = (
            self.db.query(InventoryItem, Product)
            .join(Product, InventoryItem.product_id == Product.id)
            .filter(
                InventoryItem.company_id == self.tenant_id,
                Product.is_inventory_tracked == True,
                InventoryItem.is_active == True,
            )
            .all()
        )

        # Most recent transaction per product (for step 2)
        from sqlalchemy import desc

        products_data = []
        total_units = 0
        zero_stock = 0
        below_reorder = 0

        for inv_item, product in items:
            last_txn = (
                self.db.query(InventoryTransaction)
                .filter(
                    InventoryTransaction.company_id == self.tenant_id,
                    InventoryTransaction.product_id == product.id,
                )
                .order_by(desc(InventoryTransaction.created_at))
                .first()
            )

            qty = inv_item.quantity_on_hand or 0
            total_units += qty

            if qty == 0:
                zero_stock += 1

            if inv_item.reorder_point is not None and qty < inv_item.reorder_point:
                below_reorder += 1

            products_data.append({
                "inventory_item_id": inv_item.id,
                "product_id": product.id,
                "product_name": product.name,
                "sku": product.sku,
                "quantity_on_hand": qty,
                "last_counted_at": inv_item.last_counted_at.isoformat() if inv_item.last_counted_at else None,
                "spare_covers": inv_item.spare_covers if hasattr(inv_item, "spare_covers") else 0,
                "spare_bases": inv_item.spare_bases if hasattr(inv_item, "spare_bases") else 0,
                "reorder_point": inv_item.reorder_point,
                "location": inv_item.location,
                "last_txn_quantity_after": last_txn.quantity_after if last_txn else None,
                "last_txn_date": last_txn.created_at.isoformat() if last_txn and last_txn.created_at else None,
                "has_transactions": last_txn is not None,
            })

        data = {
            "snapshot_date": date.today().isoformat(),
            "product_count": len(products_data),
            "total_units_on_hand": total_units,
            "products": products_data,
            "zero_stock_count": zero_stock,
            "below_reorder_count": below_reorder,
        }

        msg = (
            f"{len(products_data)} tracked products. "
            f"{total_units} total units on hand. "
            f"{below_reorder} products below reorder point."
        )

        return StepResult(message=msg, data=data, anomalies=[])

    # ------------------------------------------------------------------
    # STEP 2 — verify_transaction_integrity
    # ------------------------------------------------------------------

    def _step_verify_transaction_integrity(self) -> StepResult:
        snapshot = self.step_results.get("snapshot_current_inventory", {})
        products = snapshot.get("products", [])
        anomalies: list[AnomalyItem] = []

        integrity_ok = 0
        mismatch_count = 0
        no_history_count = 0
        mismatches = []

        for p in products:
            on_hand = p["quantity_on_hand"]
            has_txns = p["has_transactions"]
            last_txn_qty = p["last_txn_quantity_after"]

            if not has_txns:
                if on_hand > 0:
                    no_history_count += 1
                    anomalies.append(self._make_anomaly(
                        severity=AnomalySeverity.WARNING,
                        anomaly_type="inventory_no_transaction_history",
                        entity_type="inventory_item",
                        entity_id=p["inventory_item_id"],
                        description=(
                            f"{p['product_name']}: shows {on_hand} units on hand "
                            f"but has no transaction history. Opening balance "
                            f"may not have been recorded."
                        ),
                    ))
                else:
                    integrity_ok += 1
                continue

            if on_hand == last_txn_qty:
                integrity_ok += 1
            else:
                mismatch_count += 1
                variance = on_hand - last_txn_qty
                mismatches.append({
                    "product_name": p["product_name"],
                    "sku": p["sku"],
                    "quantity_on_hand": on_hand,
                    "last_transaction_quantity_after": last_txn_qty,
                    "variance": variance,
                    "last_transaction_date": p["last_txn_date"],
                })
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.CRITICAL,
                    anomaly_type="inventory_balance_mismatch",
                    entity_type="inventory_item",
                    entity_id=p["inventory_item_id"],
                    description=(
                        f"{p['product_name']}: quantity_on_hand is {on_hand} "
                        f"but last transaction shows {last_txn_qty}. "
                        f"Data integrity issue — a write occurred outside "
                        f"the transaction system."
                    ),
                ))

        data = {
            "products_checked": len(products),
            "integrity_ok_count": integrity_ok,
            "mismatch_count": mismatch_count,
            "no_history_count": no_history_count,
            "mismatches": mismatches,
        }

        msg = (
            f"{integrity_ok} of {len(products)} products have clean "
            f"transaction history. {mismatch_count} balance mismatches detected."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 3 — compute_reserved_quantity
    # ------------------------------------------------------------------

    def _step_compute_reserved_quantity(self) -> StepResult:
        snapshot = self.step_results.get("snapshot_current_inventory", {})
        products = snapshot.get("products", [])
        anomalies: list[AnomalyItem] = []

        total_reserved = 0
        products_with_reservations = 0
        oversold_count = 0
        at_risk_count = 0
        inventory_list = []

        for p in products:
            product_id = p["product_id"]
            on_hand = p["quantity_on_hand"]

            # Compute reserved from confirmed/processing orders
            reserved_result = (
                self.db.query(
                    func.coalesce(
                        func.sum(SalesOrderLine.quantity - SalesOrderLine.quantity_shipped),
                        0,
                    )
                )
                .join(SalesOrder, SalesOrderLine.sales_order_id == SalesOrder.id)
                .filter(
                    SalesOrder.company_id == self.tenant_id,
                    SalesOrder.status.in_(["confirmed", "processing"]),
                    SalesOrderLine.product_id == product_id,
                    (SalesOrderLine.quantity - SalesOrderLine.quantity_shipped) > 0,
                )
                .scalar()
            )
            reserved = int(float(reserved_result or 0))

            # Count confirmed orders for this product
            confirmed_orders = (
                self.db.query(func.count(SalesOrder.id.distinct()))
                .join(SalesOrderLine, SalesOrderLine.sales_order_id == SalesOrder.id)
                .filter(
                    SalesOrder.company_id == self.tenant_id,
                    SalesOrder.status.in_(["confirmed", "processing"]),
                    SalesOrderLine.product_id == product_id,
                    (SalesOrderLine.quantity - SalesOrderLine.quantity_shipped) > 0,
                )
                .scalar()
            ) or 0

            available = on_hand - reserved

            if reserved > 0:
                products_with_reservations += 1
                total_reserved += reserved

            if available < 0:
                oversold_count += 1
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.CRITICAL,
                    anomaly_type="inventory_oversold",
                    entity_type="inventory_item",
                    entity_id=p["inventory_item_id"],
                    description=(
                        f"{p['product_name']}: {on_hand} units on hand but "
                        f"{reserved} reserved for confirmed orders. "
                        f"Oversold by {abs(available)} units."
                    ),
                ))
            elif available == 0 and reserved > 0:
                at_risk_count += 1
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.WARNING,
                    anomaly_type="inventory_at_risk",
                    entity_type="inventory_item",
                    entity_id=p["inventory_item_id"],
                    description=(
                        f"{p['product_name']}: fully committed with "
                        f"{reserved} reserved and 0 available. "
                        f"Any new orders cannot be filled from stock."
                    ),
                ))

            inventory_list.append({
                "product_name": p["product_name"],
                "sku": p["sku"],
                "quantity_on_hand": on_hand,
                "reserved_quantity": reserved,
                "available_quantity": available,
                "confirmed_order_count": confirmed_orders,
            })

        data = {
            "products_with_reservations": products_with_reservations,
            "total_reserved_units": total_reserved,
            "oversold_count": oversold_count,
            "at_risk_count": at_risk_count,
            "inventory": inventory_list,
        }

        msg = (
            f"{total_reserved} units reserved across "
            f"{products_with_reservations} products. "
            f"{oversold_count} products oversold. "
            f"{at_risk_count} at zero available."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 4 — reconcile_production_vs_deliveries
    # ------------------------------------------------------------------

    def _step_reconcile_production_vs_deliveries(self) -> StepResult:
        snapshot = self.step_results.get("snapshot_current_inventory", {})
        products = snapshot.get("products", [])
        anomalies: list[AnomalyItem] = []

        period_start = self._period_start()
        period_end = self._period_end()
        # Convert dates to datetimes for comparison with DateTime fields
        period_start_dt = datetime(period_start.year, period_start.month, period_start.day, tzinfo=timezone.utc)
        period_end_dt = datetime(period_end.year, period_end.month, period_end.day, 23, 59, 59, tzinfo=timezone.utc)

        total_produced = 0
        total_delivered = 0
        clean_count = 0
        variance_count = 0
        unplanned_count = 0
        reconciliation = []

        for p in products:
            product_id = p["product_id"]

            # METHOD A — Transaction ledger net change
            net_txn_result = (
                self.db.query(func.coalesce(func.sum(InventoryTransaction.quantity_change), 0))
                .filter(
                    InventoryTransaction.company_id == self.tenant_id,
                    InventoryTransaction.product_id == product_id,
                    InventoryTransaction.created_at >= period_start_dt,
                    InventoryTransaction.created_at <= period_end_dt,
                )
                .scalar()
            )
            net_from_transactions = int(float(net_txn_result or 0))

            # METHOD B — Production minus deliveries
            produced_result = (
                self.db.query(func.coalesce(func.sum(ProductionLogEntry.quantity_produced), 0))
                .filter(
                    ProductionLogEntry.tenant_id == self.tenant_id,
                    ProductionLogEntry.product_id == product_id,
                    ProductionLogEntry.log_date >= period_start,
                    ProductionLogEntry.log_date <= period_end,
                )
                .scalar()
            )
            produced = int(float(produced_result or 0))

            # Delivered = quantity_shipped on lines for delivered/completed orders
            delivered_result = (
                self.db.query(
                    func.coalesce(func.sum(SalesOrderLine.quantity_shipped), 0)
                )
                .join(SalesOrder, SalesOrderLine.sales_order_id == SalesOrder.id)
                .filter(
                    SalesOrder.company_id == self.tenant_id,
                    SalesOrder.status.in_(["delivered", "completed"]),
                    SalesOrder.delivered_at >= period_start_dt,
                    SalesOrder.delivered_at <= period_end_dt,
                    SalesOrderLine.product_id == product_id,
                )
                .scalar()
            )
            delivered = int(float(delivered_result or 0))

            net_from_ops = produced - delivered
            variance = net_from_transactions - net_from_ops

            total_produced += produced
            total_delivered += delivered

            # Determine status
            if produced == 0 and delivered == 0 and net_from_transactions == 0:
                status = "no_activity"
                clean_count += 1
            elif variance == 0:
                status = "clean"
                clean_count += 1
            else:
                status = "variance"
                variance_count += 1
                severity = (
                    AnomalySeverity.WARNING if abs(variance) <= 2
                    else AnomalySeverity.CRITICAL
                )
                anomalies.append(self._make_anomaly(
                    severity=severity,
                    anomaly_type="inventory_reconciliation_variance",
                    entity_type="inventory_item",
                    entity_id=p["inventory_item_id"],
                    description=(
                        f"{p['product_name']}: transaction ledger shows net change "
                        f"of {net_from_transactions} units but production-minus-deliveries "
                        f"shows {net_from_ops}. Unexplained variance: {variance:+d} units."
                    ),
                ))

            # Check for unplanned production (production with no work order)
            if produced > 0:
                wo_count = (
                    self.db.query(func.count(WorkOrder.id))
                    .filter(
                        WorkOrder.company_id == self.tenant_id,
                        WorkOrder.product_id == product_id,
                        WorkOrder.status != "cancelled",
                    )
                    .scalar()
                ) or 0

                if wo_count == 0:
                    unplanned_count += 1
                    anomalies.append(self._make_anomaly(
                        severity=AnomalySeverity.INFO,
                        anomaly_type="inventory_unplanned_production",
                        description=(
                            f"{p['product_name']}: {produced} units produced in period "
                            f"with no linked work order. Speculative stock build."
                        ),
                    ))

            reconciliation.append({
                "product_name": p["product_name"],
                "sku": p["sku"],
                "produced": produced,
                "delivered": delivered,
                "net_from_transactions": net_from_transactions,
                "net_from_ops": net_from_ops,
                "variance": variance,
                "status": status,
            })

        products_reconciled = len(reconciliation)
        data = {
            "period_start": str(period_start),
            "period_end": str(period_end),
            "products_reconciled": products_reconciled,
            "clean_count": clean_count,
            "variance_count": variance_count,
            "total_produced": total_produced,
            "total_delivered": total_delivered,
            "unplanned_production_count": unplanned_count,
            "reconciliation": reconciliation,
        }

        msg = (
            f"{clean_count} of {products_reconciled} products reconcile cleanly. "
            f"{variance_count} variances. "
            f"Period: {total_produced} produced, {total_delivered} delivered."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 5 — check_physical_count_freshness
    # ------------------------------------------------------------------

    def _step_check_physical_count_freshness(self) -> StepResult:
        snapshot = self.step_results.get("snapshot_current_inventory", {})
        products = snapshot.get("products", [])
        anomalies: list[AnomalyItem] = []

        period_start = self._period_start()
        period_end = self._period_end()
        period_start_dt = datetime(period_start.year, period_start.month, period_start.day, tzinfo=timezone.utc)
        period_end_dt = datetime(period_end.year, period_end.month, period_end.day, 23, 59, 59, tzinfo=timezone.utc)
        today = date.today()

        fresh_count = 0
        stale_count = 0
        overdue_count = 0
        never_counted = 0
        large_adjustments = 0
        by_product = []

        # Count transactions in period
        count_txns_in_period = (
            self.db.query(InventoryTransaction)
            .filter(
                InventoryTransaction.company_id == self.tenant_id,
                InventoryTransaction.transaction_type == "count",
                InventoryTransaction.created_at >= period_start_dt,
                InventoryTransaction.created_at <= period_end_dt,
            )
            .all()
        )

        # Check for large count adjustments
        for txn in count_txns_in_period:
            adjustment = txn.quantity_change
            if abs(adjustment) > LARGE_COUNT_ADJUSTMENT_THRESHOLD:
                large_adjustments += 1
                product = self.db.query(Product).filter(Product.id == txn.product_id).first()
                pname = product.name if product else "Unknown"
                txn_date = txn.created_at.date() if hasattr(txn.created_at, "date") else txn.created_at
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.INFO,
                    anomaly_type="inventory_large_count_adjustment",
                    description=(
                        f"{pname}: physical count on {txn_date} required "
                        f"adjustment of {adjustment:+d} units."
                    ),
                ))

        for p in products:
            last_counted_str = p["last_counted_at"]
            product_name = p["product_name"]

            if last_counted_str is None:
                never_counted += 1
                overdue_count += 1
                freshness = "overdue"
                days_since = None
                anomalies.append(self._make_anomaly(
                    severity=AnomalySeverity.WARNING,
                    anomaly_type="inventory_count_overdue",
                    entity_type="inventory_item",
                    entity_id=p["inventory_item_id"],
                    description=(
                        f"{product_name}: never physically counted. "
                        f"Recommend counting before period close."
                    ),
                ))
            else:
                last_counted = datetime.fromisoformat(last_counted_str)
                if last_counted.tzinfo is None:
                    last_counted = last_counted.replace(tzinfo=timezone.utc)
                days_since = (datetime.now(timezone.utc) - last_counted).days

                if days_since <= FRESH_THRESHOLD:
                    freshness = "fresh"
                    fresh_count += 1
                elif days_since <= STALE_THRESHOLD:
                    freshness = "stale"
                    stale_count += 1
                else:
                    freshness = "overdue"
                    overdue_count += 1
                    anomalies.append(self._make_anomaly(
                        severity=AnomalySeverity.WARNING,
                        anomaly_type="inventory_count_overdue",
                        entity_type="inventory_item",
                        entity_id=p["inventory_item_id"],
                        description=(
                            f"{product_name}: last physical count was "
                            f"{days_since} days ago. Recommend counting "
                            f"before period close."
                        ),
                    ))

            by_product.append({
                "product_name": product_name,
                "last_counted_at": last_counted_str,
                "days_since_count": days_since,
                "freshness_status": freshness,
            })

        data = {
            "fresh_count": fresh_count,
            "stale_count": stale_count,
            "overdue_count": overdue_count,
            "never_counted_count": never_counted,
            "count_transactions_in_period": len(count_txns_in_period),
            "large_adjustments": large_adjustments,
            "by_product": by_product,
        }

        msg = (
            f"{fresh_count} products fresh, {stale_count} stale, "
            f"{overdue_count} overdue for physical count."
        )

        return StepResult(message=msg, data=data, anomalies=anomalies)

    # ------------------------------------------------------------------
    # STEP 6 — generate_report
    # ------------------------------------------------------------------

    def _step_generate_report(self) -> StepResult:
        snapshot = self.step_results.get("snapshot_current_inventory", {})
        integrity = self.step_results.get("verify_transaction_integrity", {})
        reserved = self.step_results.get("compute_reserved_quantity", {})
        recon = self.step_results.get("reconcile_production_vs_deliveries", {})
        freshness = self.step_results.get("check_physical_count_freshness", {})

        total_on_hand = snapshot.get("total_units_on_hand", 0)
        total_reserved_units = reserved.get("total_reserved_units", 0)
        total_available = total_on_hand - total_reserved_units

        critical = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.CRITICAL)
        warning = sum(1 for a in self.anomalies if a.severity == AnomalySeverity.WARNING)

        executive_summary = {
            "period": f"{self._period_start()} to {self._period_end()}",
            "snapshot_date": date.today().isoformat(),
            "total_products": snapshot.get("product_count", 0),
            "total_units_on_hand": total_on_hand,
            "total_reserved": total_reserved_units,
            "total_available": total_available,
            "oversold_count": reserved.get("oversold_count", 0),
            "transaction_integrity_issues": integrity.get("mismatch_count", 0),
            "reconciliation_variances": recon.get("variance_count", 0),
            "count_overdue": freshness.get("overdue_count", 0),
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
            executive_summary, snapshot, integrity, reserved, recon, freshness,
        )
        self.db.commit()

        msg = (
            f"Inventory reconciliation report ready. "
            f"{snapshot.get('product_count', 0)} products, "
            f"{total_on_hand} on hand, {total_reserved_units} reserved, "
            f"{total_available} available."
        )

        return StepResult(message=msg, data={"report_generated": True}, anomalies=[])

    def _build_report_html(
        self,
        summary: dict,
        snapshot: dict,
        integrity: dict,
        reserved: dict,
        recon: dict,
        freshness: dict,
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

        # Critical issues section
        critical_html = ""
        critical_anomalies = [a for a in self.anomalies if a.severity == AnomalySeverity.CRITICAL]
        if critical_anomalies:
            rows = ""
            for a in critical_anomalies:
                rows += (
                    f'<tr><td><span style="background:#dc2626;color:#fff;padding:2px 8px;'
                    f'border-radius:4px;font-size:12px;">CRITICAL</span></td>'
                    f'<td>{a.anomaly_type}</td>'
                    f'<td>{a.description}</td></tr>'
                )
            critical_html = f"""
            <h2 style="color:#dc2626;">Critical Issues</h2>
            <table><thead><tr><th>Severity</th><th>Type</th><th>Description</th></tr></thead>
            <tbody>{rows}</tbody></table>"""

        # Inventory status table
        inv_rows = ""
        for item in reserved.get("inventory", []):
            avail = item["available_quantity"]
            if avail < 0:
                row_style = "background:#fef2f2;"
            elif avail == 0 and item["reserved_quantity"] > 0:
                row_style = "background:#fffbeb;"
            else:
                row_style = ""

            # Find freshness for this product
            freshness_status = "—"
            for fp in freshness.get("by_product", []):
                if fp["product_name"] == item["product_name"]:
                    freshness_status = fp["freshness_status"]
                    break

            inv_rows += (
                f'<tr style="{row_style}">'
                f'<td>{item["product_name"]}</td>'
                f'<td>{item["sku"] or "—"}</td>'
                f'<td style="text-align:right;">{item["quantity_on_hand"]}</td>'
                f'<td style="text-align:right;">{item["reserved_quantity"]}</td>'
                f'<td style="text-align:right;">{item["available_quantity"]}</td>'
                f'<td>{freshness_status}</td></tr>'
            )

        # Reconciliation table
        recon_rows = ""
        for r in recon.get("reconciliation", []):
            status_color = {
                "clean": "#16a34a", "variance": "#dc2626", "no_activity": "#71717a"
            }.get(r["status"], "#71717a")
            recon_rows += (
                f'<tr><td>{r["product_name"]}</td>'
                f'<td style="text-align:right;">{r["produced"]}</td>'
                f'<td style="text-align:right;">{r["delivered"]}</td>'
                f'<td style="text-align:right;">{r["net_from_transactions"]}</td>'
                f'<td style="text-align:right;">{r["net_from_ops"]}</td>'
                f'<td style="text-align:right;">{r["variance"]:+d}</td>'
                f'<td style="color:{status_color};">{r["status"]}</td></tr>'
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
            <h1>Inventory Reconciliation{dry_run_badge}</h1>
            <div class="meta">{period_label} &middot; Generated {summary.get('generated_at', '')}</div>

            <div class="cards">
                <div class="card">
                    <div class="card-value">{summary.get('total_units_on_hand', 0)}</div>
                    <div class="card-label">Total On Hand</div>
                </div>
                <div class="card">
                    <div class="card-value">{summary.get('total_reserved', 0)}</div>
                    <div class="card-label">Reserved</div>
                </div>
                <div class="card">
                    <div class="card-value">{summary.get('total_available', 0)}</div>
                    <div class="card-label">Available</div>
                </div>
                <div class="card">
                    <div class="card-value">{summary.get('anomaly_count', 0)}</div>
                    <div class="card-label">Anomalies</div>
                </div>
            </div>

            {critical_html}

            <h2>Inventory Status</h2>
            <table>
                <thead><tr><th>Product</th><th>SKU</th><th style="text-align:right;">On Hand</th><th style="text-align:right;">Reserved</th><th style="text-align:right;">Available</th><th>Count Status</th></tr></thead>
                <tbody>{inv_rows or '<tr><td colspan="6" style="text-align:center;">No tracked products</td></tr>'}</tbody>
            </table>

            <h2>Production vs. Delivery Reconciliation</h2>
            <table>
                <thead><tr><th>Product</th><th style="text-align:right;">Produced</th><th style="text-align:right;">Delivered</th><th style="text-align:right;">Txn Net</th><th style="text-align:right;">Ops Net</th><th style="text-align:right;">Variance</th><th>Status</th></tr></thead>
                <tbody>{recon_rows or '<tr><td colspan="7" style="text-align:center;">No reconciliation data</td></tr>'}</tbody>
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
