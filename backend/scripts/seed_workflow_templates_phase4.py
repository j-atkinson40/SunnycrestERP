"""Phase 4 backfill seed — funeral_cascade + quote_to_pour.

Authors two canonical vertical_default workflow templates with
canvas_state shapes that match exactly what the admin canvas
editor produces. Idempotent — running twice is a no-op (uses the
service's create_template path which versions on existing tuple
match, but we short-circuit when the active row's canvas_state
already matches the seeded payload).

Run via:

    cd backend
    DATABASE_URL=postgresql://localhost:5432/bridgeable_dev \\
        python scripts/seed_workflow_templates_phase4.py

Without DATABASE_URL the script will use the env-configured
default. Safe to re-run.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from app.database import SessionLocal
from app.services.workflow_templates import (
    create_template,
    list_templates,
    update_template,
)


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")


# ─── Canvas builders ─────────────────────────────────────────────


def _node(
    nid: str,
    ntype: str,
    *,
    label: str = "",
    config: dict[str, Any] | None = None,
    x: int = 0,
    y: int = 0,
) -> dict[str, Any]:
    return {
        "id": nid,
        "type": ntype,
        "label": label,
        "position": {"x": x, "y": y},
        "config": config or {},
    }


def _edge(
    eid: str,
    source: str,
    target: str,
    *,
    label: str = "",
    condition: str = "",
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": eid,
        "source": source,
        "target": target,
        "label": label,
    }
    if condition:
        out["condition"] = condition
    return out


# ─── Funeral cascade canvas (funeral_home vertical) ──────────────


def funeral_cascade_canvas() -> dict[str, Any]:
    """The September Wilbert demo's centerpiece. When a funeral
    home director commits an Arrangement Generation Focus, this
    cascade fires across funeral home + cemetery + vault
    manufacturer + crematory tenants.

    Sequential + parallel paths represented as:
      start → trigger_arrangement_commit → generate_case_file →
      branch_disposition (decision) →
        burial_path: cross_tenant_order_vault → cross_tenant_plot_reservation →
                     generate_burial_documents
        cremation_path: cross_tenant_cremation_request →
                        generate_cremation_authorization
      → parallel_join (both paths converge) →
      generate_obituary_draft → schedule_service_date →
      generate_service_program → send_family_notification →
      file_death_certificate → schedule_grief_check_in → end
    """
    nodes: list[dict[str, Any]] = [
        _node("n_start", "start", label="Cascade triggered", x=0, y=0),
        _node(
            "n_trigger_arrangement_commit",
            "input",
            label="Arrangement commit event",
            config={
                "input_type": "event",
                "event": "generation_focus.commit",
                "event_filter": {
                    "focus_template": "arrangement-scribe",
                },
            },
            x=0,
            y=120,
        ),
        _node(
            "n_generate_case_file",
            "generate_document",
            label="Generate case file VaultItem",
            config={
                "template_key": "fh_case.case_file",
                "entity_type": "fh_case",
                "context": {
                    "case_id": "{trigger.entity_id}",
                },
            },
            x=0,
            y=240,
        ),
        _node(
            "n_branch_disposition",
            "decision",
            label="Disposition: burial or cremation?",
            config={
                "expression": "trigger.disposition",
                "branches": ["burial", "cremation", "both"],
            },
            x=0,
            y=360,
        ),
        # ── Burial path ────────────────────────────────────────
        _node(
            "n_cross_tenant_order_vault",
            "cross_tenant_order",
            label="Vault order → manufacturer",
            config={
                "target_tenant_resolver": "selected_vault_manufacturer",
                "order_type": "vault",
                "fields": {
                    "vault_sku": "{trigger.vault_selection}",
                    "service_date": "{trigger.service_date}",
                },
            },
            x=-300,
            y=520,
        ),
        _node(
            "n_cross_tenant_plot_reservation",
            "cross_tenant_request",
            label="Plot reservation → cemetery",
            config={
                "target_tenant_resolver": "selected_cemetery",
                "request_type": "plot_reservation",
                "fields": {
                    "plot_id": "{trigger.plot_selection}",
                    "deceased_name": "{trigger.deceased_name}",
                    "service_date": "{trigger.service_date}",
                },
            },
            x=-300,
            y=640,
        ),
        _node(
            "n_generate_burial_documents",
            "generate_document",
            label="Generate burial documents (cemetery permit + vault delivery scheduling)",
            config={
                "template_keys": [
                    "cemetery.burial_permit",
                    "vault.delivery_scheduling_request",
                ],
            },
            x=-300,
            y=760,
        ),
        # ── Cremation path ─────────────────────────────────────
        _node(
            "n_cross_tenant_cremation_request",
            "cross_tenant_request",
            label="Cremation request → crematory",
            config={
                "target_tenant_resolver": "selected_crematory",
                "request_type": "cremation_authorization",
                "fields": {
                    "deceased_name": "{trigger.deceased_name}",
                    "next_of_kin_authorization_id": "{trigger.noc_id}",
                },
            },
            x=300,
            y=520,
        ),
        _node(
            "n_generate_cremation_authorization",
            "generate_document",
            label="Generate cremation authorization documents",
            config={
                "template_keys": [
                    "cremation.authorization",
                    "cremation.next_of_kin_consent",
                ],
            },
            x=300,
            y=640,
        ),
        # ── Common path post-disposition ───────────────────────
        _node("n_join", "parallel_join", label="Paths converge", x=0, y=900),
        _node(
            "n_generate_obituary_draft",
            "generation-focus-invocation",
            label="Generate obituary draft",
            config={
                "focusTemplateName": "arrangement-scribe",
                "extraction_template": "obituary",
                "reviewMode": "review-by-default",
            },
            x=0,
            y=1020,
        ),
        _node(
            "n_schedule_service_date",
            "schedule",
            label="Schedule service in calendar",
            config={
                "calendar_target": "fh_internal",
                "event_type": "funeral_service",
                "scheduled_for": "{trigger.service_date}",
            },
            x=0,
            y=1140,
        ),
        _node(
            "n_generate_service_program",
            "generate_document",
            label="Generate service program PDF",
            config={
                "template_key": "fh.service_program",
            },
            x=0,
            y=1260,
        ),
        _node(
            "n_send_family_notification",
            "send-communication",
            label="Family notification (email)",
            config={
                "channel": "email",
                "templateKey": "fh.family_arrangement_summary",
                "recipientBinding": "{trigger.informant_email}",
                "maxRetries": 3,
            },
            x=0,
            y=1380,
        ),
        _node(
            "n_file_death_certificate",
            "playwright_action",
            label="File death certificate (state portal)",
            config={
                "playwright_step_id": "state_dc_filing",
                "fields": {
                    "deceased_name": "{trigger.deceased_name}",
                    "date_of_death": "{trigger.date_of_death}",
                    "filing_jurisdiction": "{trigger.filing_state}",
                },
                "deferred_until_reach_layer_ships": True,
            },
            x=0,
            y=1500,
        ),
        _node(
            "n_schedule_grief_check_in",
            "schedule",
            label="Grief check-in (3 days post-service)",
            config={
                "calendar_target": "fh_internal",
                "event_type": "grief_followup",
                "scheduled_for": "{trigger.service_date} + 3 days",
            },
            x=0,
            y=1620,
        ),
        _node("n_end", "end", label="Cascade complete", x=0, y=1740),
    ]

    edges: list[dict[str, Any]] = [
        _edge("e_start", "n_start", "n_trigger_arrangement_commit"),
        _edge("e_trigger_to_case", "n_trigger_arrangement_commit", "n_generate_case_file"),
        _edge("e_case_to_branch", "n_generate_case_file", "n_branch_disposition"),
        # Branch outgoing edges — both burial-path nodes and
        # cremation-path nodes are reachable from the decision.
        # The "both" disposition reaches both paths via separate
        # outgoing edges.
        _edge(
            "e_branch_burial",
            "n_branch_disposition",
            "n_cross_tenant_order_vault",
            condition="disposition == 'burial' or disposition == 'both'",
            label="burial",
        ),
        _edge(
            "e_branch_cremation",
            "n_branch_disposition",
            "n_cross_tenant_cremation_request",
            condition="disposition == 'cremation' or disposition == 'both'",
            label="cremation",
        ),
        # Burial path internal edges
        _edge(
            "e_vault_to_plot",
            "n_cross_tenant_order_vault",
            "n_cross_tenant_plot_reservation",
        ),
        _edge(
            "e_plot_to_burial_docs",
            "n_cross_tenant_plot_reservation",
            "n_generate_burial_documents",
        ),
        # Cremation path internal edges
        _edge(
            "e_cremation_to_authorization",
            "n_cross_tenant_cremation_request",
            "n_generate_cremation_authorization",
        ),
        # Both paths converge at parallel_join
        _edge("e_burial_to_join", "n_generate_burial_documents", "n_join"),
        _edge(
            "e_cremation_to_join",
            "n_generate_cremation_authorization",
            "n_join",
        ),
        # Common path post-join
        _edge("e_join_to_obituary", "n_join", "n_generate_obituary_draft"),
        _edge(
            "e_obituary_to_service",
            "n_generate_obituary_draft",
            "n_schedule_service_date",
        ),
        _edge(
            "e_service_to_program",
            "n_schedule_service_date",
            "n_generate_service_program",
        ),
        _edge(
            "e_program_to_family",
            "n_generate_service_program",
            "n_send_family_notification",
        ),
        _edge(
            "e_family_to_dc",
            "n_send_family_notification",
            "n_file_death_certificate",
        ),
        _edge(
            "e_dc_to_grief",
            "n_file_death_certificate",
            "n_schedule_grief_check_in",
        ),
        _edge("e_grief_to_end", "n_schedule_grief_check_in", "n_end"),
    ]

    return {
        "version": 1,
        "trigger": {
            "trigger_type": "event",
            "trigger_config": {
                "event": "generation_focus.commit",
                "event_filter": {"focus_template": "arrangement-scribe"},
            },
        },
        "nodes": nodes,
        "edges": edges,
    }


# ─── Manufacturing quote-to-pour canvas (manufacturing vertical) ─


def quote_to_pour_canvas() -> dict[str, Any]:
    """Sunnycrest's bid-intake → production-pour → delivery flow.

    Sequential + branching:
      start → trigger_quote_or_order_received →
      generate_sales_order_vault_item → check_inventory (decision) →
        in_stock_path: schedule_pickup_or_delivery →
                      generate_bol
        production_path: schedule_pour → allocate_molds →
                         generate_production_schedule
      → parallel_join → qc_check (decision) →
        qc_pass: generate_delivery_documents →
                  schedule_delivery → generate_invoice →
                  trigger_payment_collection_workflow
        qc_fail: log_qc_anomaly → schedule_pour (loop back, marked iteration)
      → end
    """
    nodes: list[dict[str, Any]] = [
        _node("n_start", "start", label="Trigger received", x=0, y=0),
        _node(
            "n_trigger_quote_or_order",
            "input",
            label="Quote or cross-tenant order received",
            config={
                "input_type": "event",
                "event_filter": {
                    "or": [
                        {"event": "generation_focus.commit", "focus_template": "quote-builder"},
                        {"event": "cross_tenant_order.received"},
                    ],
                },
            },
            x=0,
            y=120,
        ),
        _node(
            "n_generate_sales_order_vault_item",
            "generate_document",
            label="Generate SalesOrder VaultItem",
            config={
                "template_key": "mfg.sales_order",
                "entity_type": "sales_order",
            },
            x=0,
            y=240,
        ),
        _node(
            "n_check_inventory",
            "decision",
            label="In stock vs. needs production?",
            config={
                "expression": "inventory_check.quantity_on_hand >= order.quantity",
                "branches": ["in_stock", "production_required"],
            },
            x=0,
            y=360,
        ),
        # ── In-stock path ──────────────────────────────────────
        _node(
            "n_schedule_pickup_or_delivery",
            "schedule",
            label="Schedule pickup or delivery",
            config={
                "calendar_target": "delivery_calendar",
                "event_type": "pickup_or_delivery",
                "scheduled_for": "{order.required_date}",
            },
            x=-300,
            y=520,
        ),
        _node(
            "n_generate_bol_in_stock",
            "generate_document",
            label="Generate Bill of Lading",
            config={"template_key": "mfg.bill_of_lading"},
            x=-300,
            y=640,
        ),
        # ── Production-required path ───────────────────────────
        _node(
            "n_schedule_pour",
            "schedule",
            label="Schedule pour",
            config={
                "calendar_target": "production_calendar",
                "event_type": "pour",
                "scheduled_for": "next_available_pour_slot",
            },
            x=300,
            y=520,
        ),
        _node(
            "n_allocate_molds",
            "action",
            label="Allocate molds for pour",
            config={
                "action_type": "create_record",
                "record_type": "mold_allocation",
                "fields": {
                    "vault_sku": "{order.vault_sku}",
                    "pour_date": "{schedule_pour.scheduled_for}",
                },
            },
            x=300,
            y=640,
        ),
        _node(
            "n_generate_production_schedule",
            "generate_document",
            label="Generate production schedule",
            config={"template_key": "mfg.production_schedule"},
            x=300,
            y=760,
        ),
        # ── Common path post-stock-or-production ───────────────
        _node("n_join", "parallel_join", label="Paths converge", x=0, y=900),
        _node(
            "n_qc_check",
            "decision",
            label="QC check",
            config={
                "expression": "qc.passes_inspection",
                "branches": ["qc_pass", "qc_fail"],
            },
            x=0,
            y=1020,
        ),
        # QC pass path
        _node(
            "n_generate_delivery_documents",
            "generate_document",
            label="Generate delivery documents (BOL + COC + NPCA cert)",
            config={
                "template_keys": [
                    "mfg.bill_of_lading_final",
                    "mfg.certificate_of_compliance",
                    "mfg.npca_cert",
                ],
            },
            x=0,
            y=1180,
        ),
        _node(
            "n_schedule_delivery",
            "schedule",
            label="Schedule delivery",
            config={
                "calendar_target": "delivery_calendar",
                "event_type": "delivery",
                "scheduled_for": "{order.required_date}",
            },
            x=0,
            y=1300,
        ),
        _node(
            "n_generate_invoice",
            "generate_document",
            label="Generate invoice",
            config={
                "template_key": "ar.invoice",
                "entity_type": "invoice",
            },
            x=0,
            y=1420,
        ),
        _node(
            "n_trigger_payment_collection",
            "action",
            label="Trigger payment collection workflow",
            config={
                "action_type": "call_service_method",
                "method_name": "ar_collections.run_collections_pipeline",
                "kwargs": {
                    "invoice_id": "{output.n_generate_invoice.id}",
                },
            },
            x=0,
            y=1540,
        ),
        # QC fail path
        _node(
            "n_log_qc_anomaly",
            "log_vault_item",
            label="Log QC anomaly",
            config={
                "item_type": "qc_anomaly",
                "metadata": {
                    "order_id": "{order.id}",
                    "anomaly_severity": "{qc.severity}",
                },
            },
            x=0,
            y=1180,
        ),
        _node("n_end", "end", label="Workflow complete", x=0, y=1660),
    ]

    edges: list[dict[str, Any]] = [
        _edge("e_start", "n_start", "n_trigger_quote_or_order"),
        _edge(
            "e_trigger_to_so",
            "n_trigger_quote_or_order",
            "n_generate_sales_order_vault_item",
        ),
        _edge(
            "e_so_to_inventory",
            "n_generate_sales_order_vault_item",
            "n_check_inventory",
        ),
        # Inventory branch
        _edge(
            "e_inventory_in_stock",
            "n_check_inventory",
            "n_schedule_pickup_or_delivery",
            condition="branch == 'in_stock'",
            label="in stock",
        ),
        _edge(
            "e_inventory_production",
            "n_check_inventory",
            "n_schedule_pour",
            condition="branch == 'production_required'",
            label="needs production",
        ),
        # In-stock path internal
        _edge(
            "e_stock_to_bol",
            "n_schedule_pickup_or_delivery",
            "n_generate_bol_in_stock",
        ),
        # Production path internal
        _edge("e_pour_to_molds", "n_schedule_pour", "n_allocate_molds"),
        _edge(
            "e_molds_to_schedule",
            "n_allocate_molds",
            "n_generate_production_schedule",
        ),
        # Both paths converge
        _edge("e_stock_to_join", "n_generate_bol_in_stock", "n_join"),
        _edge(
            "e_production_to_join",
            "n_generate_production_schedule",
            "n_join",
        ),
        # Post-join QC check
        _edge("e_join_to_qc", "n_join", "n_qc_check"),
        _edge(
            "e_qc_pass",
            "n_qc_check",
            "n_generate_delivery_documents",
            condition="branch == 'qc_pass'",
            label="pass",
        ),
        _edge(
            "e_qc_fail",
            "n_qc_check",
            "n_log_qc_anomaly",
            condition="branch == 'qc_fail'",
            label="fail",
        ),
        # QC pass path
        _edge(
            "e_delivery_docs_to_schedule",
            "n_generate_delivery_documents",
            "n_schedule_delivery",
        ),
        _edge(
            "e_delivery_to_invoice",
            "n_schedule_delivery",
            "n_generate_invoice",
        ),
        _edge(
            "e_invoice_to_collections",
            "n_generate_invoice",
            "n_trigger_payment_collection",
        ),
        _edge(
            "e_collections_to_end",
            "n_trigger_payment_collection",
            "n_end",
        ),
        # QC fail terminates (no auto-loop to pour — admin
        # intervention required); deliberate to keep the seeded
        # workflow acyclic.
        _edge("e_qc_fail_to_end", "n_log_qc_anomaly", "n_end"),
    ]

    return {
        "version": 1,
        "trigger": {
            "trigger_type": "event",
            "trigger_config": {
                "events": [
                    {"event": "generation_focus.commit", "focus_template": "quote-builder"},
                    {"event": "cross_tenant_order.received"},
                ],
            },
        },
        "nodes": nodes,
        "edges": edges,
    }


# ─── Idempotent seed ─────────────────────────────────────────────


def _maybe_seed(
    db,
    *,
    scope: str,
    vertical: str,
    workflow_type: str,
    display_name: str,
    description: str,
    canvas_state: dict[str, Any],
) -> str:
    """Returns 'created' / 'updated' / 'noop' per outcome."""
    existing = list_templates(
        db,
        scope=scope,
        vertical=vertical,
        workflow_type=workflow_type,
    )
    active = next((t for t in existing if t.is_active), None)
    if active is None:
        create_template(
            db,
            scope=scope,
            vertical=vertical,
            workflow_type=workflow_type,
            display_name=display_name,
            description=description,
            canvas_state=canvas_state,
            notify_forks=False,
        )
        return "created"

    # Compare canonicalized JSON to detect drift
    cur = json.dumps(active.canvas_state, sort_keys=True)
    new = json.dumps(canvas_state, sort_keys=True)
    if cur == new and active.display_name == display_name and active.description == description:
        return "noop"

    update_template(
        db,
        active.id,
        display_name=display_name,
        description=description,
        canvas_state=canvas_state,
        notify_forks=False,  # backfill should not flag forks
    )
    return "updated"


def main() -> int:
    db = SessionLocal()
    try:
        results: dict[str, str] = {}

        results["funeral_cascade"] = _maybe_seed(
            db,
            scope="vertical_default",
            vertical="funeral_home",
            workflow_type="funeral_cascade",
            display_name="Funeral Cascade",
            description=(
                "Triggered when an Arrangement Generation Focus commits. "
                "Coordinates work across funeral home, cemetery, vault "
                "manufacturer, and crematory tenants based on disposition. "
                "Canonical September Wilbert demo workflow."
            ),
            canvas_state=funeral_cascade_canvas(),
        )

        results["quote_to_pour"] = _maybe_seed(
            db,
            scope="vertical_default",
            vertical="manufacturing",
            workflow_type="quote_to_pour",
            display_name="Quote to Pour",
            description=(
                "Manufacturer's bid intake → production pour → delivery "
                "flow. Triggered by quote-builder commit OR cross-tenant "
                "order received. Branches on inventory availability + QC "
                "outcome."
            ),
            canvas_state=quote_to_pour_canvas(),
        )

        for workflow_type, outcome in results.items():
            logger.info("seed_workflow_templates: %s → %s", workflow_type, outcome)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
