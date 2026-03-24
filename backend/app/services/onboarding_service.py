"""Onboarding service — legacy employee onboarding + tenant onboarding."""

import json
import logging
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session, joinedload

from app.models.onboarding import OnboardingChecklist as LegacyOnboardingChecklist
from app.models.onboarding import OnboardingTemplate
from app.models.onboarding_checklist import TenantOnboardingChecklist as OnboardingChecklist
from app.models.onboarding_checklist_item import OnboardingChecklistItem
from app.models.onboarding_data_import import OnboardingDataImport
from app.models.onboarding_help_dismissal import OnboardingHelpDismissal
from app.models.onboarding_integration_setup import OnboardingIntegrationSetup
from app.models.onboarding_scenario import OnboardingScenario
from app.models.onboarding_scenario_step import OnboardingScenarioStep
from app.models.product import Product
from app.models.product_catalog_template import ProductCatalogTemplate
from app.schemas.onboarding import (
    OnboardingTemplateCreate,
    OnboardingTemplateUpdate,
)

logger = logging.getLogger(__name__)


# ===================================================================
# Legacy employee-onboarding (unchanged)
# ===================================================================


def get_templates(
    db: Session, company_id: str, include_inactive: bool = False
) -> list[OnboardingTemplate]:
    query = db.query(OnboardingTemplate).filter(
        OnboardingTemplate.company_id == company_id
    )
    if not include_inactive:
        query = query.filter(OnboardingTemplate.is_active == True)  # noqa: E712
    return query.order_by(OnboardingTemplate.created_at.desc()).all()


def get_template(
    db: Session, template_id: str, company_id: str
) -> OnboardingTemplate:
    tmpl = (
        db.query(OnboardingTemplate)
        .filter(
            OnboardingTemplate.id == template_id,
            OnboardingTemplate.company_id == company_id,
        )
        .first()
    )
    if not tmpl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding template not found",
        )
    return tmpl


def create_template(
    db: Session, data: OnboardingTemplateCreate, company_id: str
) -> OnboardingTemplate:
    tmpl = OnboardingTemplate(
        company_id=company_id,
        name=data.name,
        items=json.dumps(data.items),
    )
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return tmpl


def update_template(
    db: Session,
    template_id: str,
    data: OnboardingTemplateUpdate,
    company_id: str,
) -> OnboardingTemplate:
    tmpl = get_template(db, template_id, company_id)
    if data.name is not None:
        tmpl.name = data.name
    if data.items is not None:
        tmpl.items = json.dumps(data.items)
    if data.is_active is not None:
        tmpl.is_active = data.is_active
    db.commit()
    db.refresh(tmpl)
    return tmpl


def get_checklists_for_user(
    db: Session, user_id: str, company_id: str
) -> list[LegacyOnboardingChecklist]:
    return (
        db.query(LegacyOnboardingChecklist)
        .filter(
            LegacyOnboardingChecklist.user_id == user_id,
            LegacyOnboardingChecklist.company_id == company_id,
        )
        .order_by(LegacyOnboardingChecklist.created_at.desc())
        .all()
    )


def assign_checklist(
    db: Session, user_id: str, template_id: str, company_id: str
) -> LegacyOnboardingChecklist:
    tmpl = get_template(db, template_id, company_id)
    template_items = json.loads(tmpl.items)
    checklist_items = [
        {"label": item, "completed": False} for item in template_items
    ]
    checklist = LegacyOnboardingChecklist(
        company_id=company_id,
        user_id=user_id,
        template_id=template_id,
        items=json.dumps(checklist_items),
    )
    db.add(checklist)
    db.commit()
    db.refresh(checklist)
    return checklist


def update_checklist_item(
    db: Session,
    checklist_id: str,
    item_index: int,
    completed: bool,
    company_id: str,
) -> LegacyOnboardingChecklist:
    cl = (
        db.query(LegacyOnboardingChecklist)
        .filter(
            LegacyOnboardingChecklist.id == checklist_id,
            LegacyOnboardingChecklist.company_id == company_id,
        )
        .first()
    )
    if not cl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding checklist not found",
        )
    items = json.loads(cl.items)
    if item_index < 0 or item_index >= len(items):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid item index",
        )
    items[item_index]["completed"] = completed
    cl.items = json.dumps(items)
    db.commit()
    db.refresh(cl)
    return cl


# ===================================================================
# Tenant Onboarding — Checklist item & scenario definitions
# ===================================================================

MANUFACTURING_CHECKLIST_ITEMS = [
    # MUST COMPLETE — strict sequence
    # 1. Company info (implicit — handled by company setup)
    # 2. Connect accounting — position 2, immediately after company
    {
        "item_key": "connect_accounting",
        "tier": "must_complete",
        "category": "integration",
        "title": "Connect your accounting software",
        "description": (
            "Connect QuickBooks or upload your Sage chart of accounts. "
            "We'll use it to pre-configure your GL mappings, import your "
            "customers and vendors, and keep your financials in sync."
        ),
        "estimated_minutes": 10,
        "action_type": "navigate",
        "action_target": "/onboarding/accounting",
        "sort_order": 2,
    },
    # 3. Review imported data — hidden until accounting connected
    {
        "item_key": "accounting_import_review",
        "tier": "must_complete",
        "category": "integration",
        "title": "Review your imported data",
        "description": (
            "Confirm the GL account mappings, customers, and vendors we "
            "found in your accounting system. High-confidence items are "
            "pre-approved — you only review exceptions."
        ),
        "estimated_minutes": 5,
        "action_type": "navigate",
        "action_target": "/onboarding/accounting/review",
        "depends_on": '["connect_accounting"]',
        "sort_order": 3,
    },
    # 4. Product catalog
    {
        "item_key": "add_products",
        "tier": "must_complete",
        "category": "data_setup",
        "title": "Set up your product catalog",
        "description": (
            "Tell us which vault lines and equipment you carry — "
            "we'll build your catalog automatically."
        ),
        "estimated_minutes": 15,
        "action_type": "navigate",
        "action_target": "/onboarding/catalog-builder",
        "sort_order": 4,
    },
    # 5. Price list — hidden until products set up
    {
        "item_key": "setup_price_list",
        "tier": "should_complete",
        "category": "data_setup",
        "title": "Upload your price list",
        "description": (
            "Upload your current price list. Products on your price list "
            "will be automatically approved from your imported catalog. "
            "Items not on your price list will be flagged for review."
        ),
        "estimated_minutes": 5,
        "action_type": "navigate",
        "action_target": "/onboarding/price-list",
        "depends_on": '["add_products"]',
        "sort_order": 5,
    },
    # 6. Add team
    {
        "item_key": "add_employees",
        "tier": "must_complete",
        "category": "team",
        "title": "Add your team",
        "description": (
            "Add the people who work here so you can assign deliveries, "
            "track QC inspections, and manage access."
        ),
        "estimated_minutes": 15,
        "action_type": "navigate",
        "action_target": "/onboarding/team",
        "sort_order": 6,
    },
    # 7. Safety training
    {
        "item_key": "setup_safety_training",
        "tier": "must_complete",
        "category": "team",
        "title": "Set up your safety training program",
        "description": (
            "Choose your training documents and personalize them "
            "with your facility details."
        ),
        "estimated_minutes": 10,
        "action_type": "navigate",
        "action_target": "/onboarding/safety-training",
        "sort_order": 7,
    },
    # 8. Scheduling board
    {
        "item_key": "setup_scheduling_board",
        "tier": "must_complete",
        "category": "workflow",
        "title": "Set up your scheduling board",
        "description": (
            "Configure your delivery scheduling board — drivers, Saturday "
            "handling, and capacity settings."
        ),
        "estimated_minutes": 5,
        "action_type": "navigate",
        "action_target": "/onboarding/scheduling",
        "sort_order": 8,
    },
    # 9. Network preferences
    {
        "item_key": "configure_cross_tenant",
        "tier": "must_complete",
        "category": "workflow",
        "title": "Configure network preferences",
        "description": (
            "Set your delivery area, choose how you work with connected "
            "funeral homes, and configure driver status milestones."
        ),
        "estimated_minutes": 5,
        "action_type": "navigate",
        "action_target": "/onboarding/network-preferences",
        "sort_order": 9,
    },
    # 10. Team intelligence — last must_complete
    {
        "item_key": "setup_team_intelligence",
        "tier": "must_complete",
        "category": "team",
        "title": "Set up morning briefings and announcements",
        "description": (
            "Configure morning briefings and announcements for your team. "
            "Complete your other setup steps first — briefings are most useful "
            "once your products, customers, team, and safety programs are in place."
        ),
        "estimated_minutes": 10,
        "action_type": "navigate",
        "action_target": "/onboarding/team-intelligence",
        "depends_on": '["add_employees"]',
        "sort_order": 99,
    },
    # SHOULD COMPLETE
    {
        "item_key": "run_vault_scenario",
        "tier": "should_complete",
        "category": "workflow",
        "title": "Walk through a vault order (5 min)",
        "description": (
            "See exactly what happens when a funeral home calls to order a "
            "vault — from order to delivery."
        ),
        "estimated_minutes": 5,
        "action_type": "navigate",
        "action_target": "/onboarding/scenarios/vault_order_walkthrough",
        "sort_order": 101,
    },
    {
        "item_key": "setup_charges",
        "tier": "should_complete",
        "category": "data_setup",
        "title": "Configure your fees and surcharges",
        "description": (
            "Tell the system which fees you charge and at what rates. "
            "These appear automatically on orders and invoices."
        ),
        "estimated_minutes": 10,
        "action_type": "navigate",
        "action_target": "/onboarding/charges",
        "sort_order": 102,
    },
    {
        "item_key": "setup_sms_confirmation",
        "tier": "should_complete",
        "category": "integration",
        "title": "Set up driver SMS confirmation",
        "description": (
            "Your drivers confirm pickups and deliveries by texting a keyword "
            "— no app required."
        ),
        "estimated_minutes": 10,
        "action_type": "navigate",
        "action_target": "/delivery/settings",
        "sort_order": 103,
    },
    {
        "item_key": "run_production_log_scenario",
        "tier": "should_complete",
        "category": "workflow",
        "title": "Log your first day of production (2 min)",
        "description": (
            "See how to record what you made today and watch inventory "
            "update automatically."
        ),
        "estimated_minutes": 2,
        "action_type": "navigate",
        "action_target": "/onboarding/scenarios/production_log_walkthrough",
        "sort_order": 104,
    },
    {
        "item_key": "set_inventory_minimums",
        "tier": "should_complete",
        "category": "data_setup",
        "title": "Set stock minimums",
        "description": (
            "Tell the system how much of each product you want to keep on "
            "hand — it'll alert you when you're running low."
        ),
        "estimated_minutes": 10,
        "action_type": "navigate",
        "action_target": "/inventory",
        "sort_order": 105,
    },
    {
        "item_key": "invite_team",
        "tier": "should_complete",
        "category": "team",
        "title": "Invite your team to log in",
        "description": (
            "Send login invitations to your dispatcher, foreman, and office staff."
        ),
        "estimated_minutes": 5,
        "action_type": "navigate",
        "action_target": "/admin/users",
        "sort_order": 106,
    },
    # OPTIONAL
    {
        "item_key": "setup_safety",
        "tier": "optional",
        "category": "explore",
        "title": "Set up safety management",
        "description": (
            "Get your OSHA records, inspection checklists, and safety programs "
            "into the system."
        ),
        "estimated_minutes": 30,
        "action_type": "navigate",
        "action_target": "/safety",
        "sort_order": 201,
    },
    {
        "item_key": "explore_extensions",
        "tier": "optional",
        "category": "explore",
        "title": "Browse the extension catalog",
        "description": "See additional capabilities you can add to your workspace.",
        "estimated_minutes": 5,
        "action_type": "navigate",
        "action_target": "/extensions",
        "sort_order": 202,
    },
    {
        "item_key": "run_month_end_scenario",
        "tier": "optional",
        "category": "workflow",
        "title": "Walk through month-end reporting (5 min)",
        "description": (
            "See how to close out a month — sync review, outstanding invoices, "
            "and production summary."
        ),
        "estimated_minutes": 5,
        "action_type": "navigate",
        "action_target": "/onboarding/scenarios/month_end_walkthrough",
        "sort_order": 203,
    },
    {
        "item_key": "customize_invoice_template",
        "tier": "optional",
        "category": "data_setup",
        "title": "Customize your invoice",
        "description": (
            "Add your logo and adjust the layout of invoices sent to customers."
        ),
        "estimated_minutes": 10,
        "action_type": "navigate",
        "action_target": "/admin/settings",
        "sort_order": 204,
    },
    {
        "item_key": "complete_urn_catalog",
        "tier": "optional",
        "category": "data_setup",
        "title": "Import your full Wilbert urn catalog",
        "description": (
            "Upload your Wilbert price list to add your complete urn "
            "selection beyond the starter set."
        ),
        "estimated_minutes": 10,
        "action_type": "navigate",
        "action_target": "/products/urns",
        "sort_order": 205,
    },
]

FUNERAL_HOME_CHECKLIST_ITEMS = [
    # ── MUST COMPLETE (5 items) ──
    {
        "item_key": "setup_price_list",
        "tier": "must_complete",
        "category": "data_setup",
        "title": "Set your service prices",
        "description": (
            "Your price list is the foundation of FTC-compliant invoicing — "
            "every service and merchandise item needs a price."
        ),
        "estimated_minutes": 20,
        "action_type": "navigate",
        "action_target": "/funeral-home/price-list",
        "sort_order": 1,
    },
    {
        "item_key": "review_ftc_compliance",
        "tier": "must_complete",
        "category": "workflow",
        "title": "Review FTC compliance requirements",
        "description": (
            "Review your General Price List for FTC Funeral Rule compliance "
            "and generate your GPL document."
        ),
        "estimated_minutes": 15,
        "action_type": "navigate",
        "action_target": "/funeral-home/compliance",
        "sort_order": 2,
    },
    {
        "item_key": "link_vault_supplier",
        "tier": "must_complete",
        "category": "integration",
        "title": "Connect your vault supplier",
        "description": (
            "Link to your vault manufacturer so you can order directly "
            "through the platform."
        ),
        "estimated_minutes": 10,
        "action_type": "navigate",
        "action_target": "/admin/settings",
        "sort_order": 3,
    },
    {
        "item_key": "add_directors",
        "tier": "must_complete",
        "category": "team",
        "title": "Add your funeral directors",
        "description": (
            "Add your directors so they can be assigned to cases and manage "
            "arrangements."
        ),
        "estimated_minutes": 10,
        "action_type": "navigate",
        "action_target": "/admin/users",
        "sort_order": 4,
    },
    {
        "item_key": "connect_accounting",
        "tier": "must_complete",
        "category": "integration",
        "title": "Connect your accounting software",
        "description": (
            "Connect QuickBooks or set up Sage export so invoices flow to "
            "your books automatically."
        ),
        "estimated_minutes": 30,
        "action_type": "modal",
        "action_target": "integration_setup_modal",
        "sort_order": 5,
    },
    # ── SHOULD COMPLETE (4 items) ──
    {
        "item_key": "run_first_call_scenario",
        "tier": "should_complete",
        "category": "workflow",
        "title": "Walk through a first call",
        "description": (
            "See the full workflow from first call through opening a case."
        ),
        "estimated_minutes": 5,
        "action_type": "navigate",
        "action_target": "/onboarding/scenarios/first_call_walkthrough",
        "sort_order": 6,
    },
    {
        "item_key": "run_vault_order_scenario",
        "tier": "should_complete",
        "category": "workflow",
        "title": "Walk through ordering a vault",
        "description": (
            "See how to place a vault order with your manufacturer through "
            "the platform."
        ),
        "estimated_minutes": 5,
        "action_type": "navigate",
        "action_target": "/onboarding/scenarios/fh_vault_order_walkthrough",
        "sort_order": 7,
    },
    {
        "item_key": "send_test_portal",
        "tier": "should_complete",
        "category": "workflow",
        "title": "Send a test family portal invite",
        "description": (
            "See what the family portal looks like by sending yourself a test invite."
        ),
        "estimated_minutes": 5,
        "action_type": "navigate",
        "action_target": "/funeral-home/cases",
        "sort_order": 8,
    },
    {
        "item_key": "invite_staff",
        "tier": "should_complete",
        "category": "team",
        "title": "Invite your team to log in",
        "description": (
            "Send login invitations to your directors and office staff."
        ),
        "estimated_minutes": 5,
        "action_type": "navigate",
        "action_target": "/admin/users",
        "sort_order": 9,
    },
    # ── OPTIONAL (3 items) ──
    {
        "item_key": "explore_extensions",
        "tier": "optional",
        "category": "explore",
        "title": "Browse the extension catalog",
        "description": (
            "See additional capabilities you can add to your funeral home."
        ),
        "estimated_minutes": 5,
        "action_type": "navigate",
        "action_target": "/extensions",
        "sort_order": 10,
    },
    {
        "item_key": "customize_invoice_template",
        "tier": "optional",
        "category": "data_setup",
        "title": "Customize your invoice",
        "description": (
            "Add your logo and adjust the layout of statement of goods and services."
        ),
        "estimated_minutes": 10,
        "action_type": "navigate",
        "action_target": "/admin/settings",
        "sort_order": 11,
    },
    {
        "item_key": "setup_cremation_preferences",
        "tier": "optional",
        "category": "data_setup",
        "title": "Set up cremation preferences",
        "description": (
            "Configure default cremation providers, authorization templates, "
            "and remains disposition options."
        ),
        "estimated_minutes": 10,
        "action_type": "navigate",
        "action_target": "/admin/settings",
        "sort_order": 12,
    },
]

# Map preset names to their item lists
_PRESET_ITEMS: dict[str, list[dict]] = {
    "manufacturing": MANUFACTURING_CHECKLIST_ITEMS,
    "funeral_home": FUNERAL_HOME_CHECKLIST_ITEMS,
}


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

MANUFACTURING_SCENARIOS = [
    {
        "scenario_key": "vault_order_walkthrough",
        "title": "Vault Order Walkthrough",
        "description": (
            "Walk through the full lifecycle of a vault order — from the "
            "funeral home's call to delivery confirmation."
        ),
        "estimated_minutes": 5,
        "steps": [
            {
                "step_number": 1,
                "title": "Receive the order call",
                "instruction": (
                    "A funeral home calls to order a vault. Click 'New Order' "
                    "to start entering the details."
                ),
                "target_route": "/orders/new",
                "target_element": "button[data-id='new-order']",
                "completion_trigger": "navigate",
                "hint_text": "Look for the 'New Order' button in the top right.",
            },
            {
                "step_number": 2,
                "title": "Select the customer",
                "instruction": (
                    "Search for the funeral home by name and select them as "
                    "the customer for this order."
                ),
                "target_route": "/orders/new",
                "target_element": "input[data-id='customer-search']",
                "completion_trigger": "field_filled",
                "hint_text": "Start typing the funeral home name to see suggestions.",
            },
            {
                "step_number": 3,
                "title": "Add products to the order",
                "instruction": (
                    "Add a vault (and any accessories like liners) to the order."
                ),
                "target_route": "/orders/new",
                "target_element": "button[data-id='add-line-item']",
                "completion_trigger": "field_filled",
                "hint_text": "Click 'Add Item' and search for the vault model.",
            },
            {
                "step_number": 4,
                "title": "Set the delivery details",
                "instruction": (
                    "Enter the cemetery name, delivery date, and any special "
                    "instructions (e.g., graveside setup time)."
                ),
                "target_route": "/orders/new",
                "target_element": "input[data-id='delivery-address']",
                "completion_trigger": "field_filled",
                "hint_text": "The delivery section is below the order items.",
            },
            {
                "step_number": 5,
                "title": "Submit the order",
                "instruction": (
                    "Review the order total and click 'Place Order' to confirm."
                ),
                "target_route": "/orders/new",
                "target_element": "button[data-id='submit-order']",
                "completion_trigger": "click",
                "hint_text": "Check the total before submitting.",
            },
            {
                "step_number": 6,
                "title": "See the delivery created",
                "instruction": (
                    "The system automatically creates a delivery. Click to "
                    "view it on the dispatch board."
                ),
                "target_route": "/delivery",
                "target_element": None,
                "completion_trigger": "navigate",
                "hint_text": "The delivery appears on the dispatch board for the requested date.",
            },
            {
                "step_number": 7,
                "title": "Confirm delivery completion",
                "instruction": (
                    "After the driver delivers, they confirm via SMS or the "
                    "app. See the proof-of-delivery photos here."
                ),
                "target_route": "/delivery",
                "target_element": None,
                "completion_trigger": "navigate",
                "hint_text": "Completed deliveries show photos and a signature.",
            },
        ],
    },
    {
        "scenario_key": "production_log_walkthrough",
        "title": "Daily Production Log Walkthrough",
        "description": (
            "See how to record what you produced today and watch "
            "inventory update automatically."
        ),
        "estimated_minutes": 2,
        "steps": [
            {
                "step_number": 1,
                "title": "Open the production log",
                "instruction": (
                    "This is where you record what you produced today. "
                    "It's simple — just pick a product and enter the quantity."
                ),
                "target_route": "/production-log",
                "target_element": None,
                "completion_trigger": "navigate",
                "hint_text": "The production log is your daily record of what was made.",
            },
            {
                "step_number": 2,
                "title": "Log a product",
                "instruction": (
                    "Select a product from the dropdown, enter how many you "
                    "produced, and click 'Log Production'. Watch the inventory "
                    "count update automatically."
                ),
                "target_route": "/production-log",
                "target_element": None,
                "completion_trigger": "field_filled",
                "hint_text": "Pick any product and enter a quantity to see it in action.",
            },
            {
                "step_number": 3,
                "title": "That's it — production logged",
                "instruction": (
                    "Every entry updates your inventory automatically. At month "
                    "end, the production summary feeds your NPCA audit records. "
                    "No work orders needed."
                ),
                "target_route": "/production-log",
                "target_element": None,
                "completion_trigger": "navigate",
                "hint_text": "You can always come back and edit or add more entries.",
            },
        ],
    },
    {
        "scenario_key": "month_end_walkthrough",
        "title": "Month-End Reporting Walkthrough",
        "description": (
            "See how to close out a month — sync review, outstanding invoices, "
            "and production summary."
        ),
        "estimated_minutes": 5,
        "steps": [
            {
                "step_number": 1,
                "title": "Review sync status",
                "instruction": (
                    "Check the sync dashboard to make sure all transactions "
                    "exported to your accounting software."
                ),
                "target_route": "/admin/sync",
                "target_element": None,
                "completion_trigger": "navigate",
                "hint_text": "Red items need attention before closing the month.",
            },
            {
                "step_number": 2,
                "title": "Review outstanding invoices",
                "instruction": (
                    "Open the AR aging report to see who still owes you money."
                ),
                "target_route": "/reports/ar-aging",
                "target_element": None,
                "completion_trigger": "navigate",
                "hint_text": "Filter by 30/60/90 days to prioritize follow-ups.",
            },
            {
                "step_number": 3,
                "title": "Review production summary",
                "instruction": (
                    "Check the production report for the month — units poured, "
                    "QC pass rate, and inventory levels."
                ),
                "target_route": "/reports/production",
                "target_element": None,
                "completion_trigger": "navigate",
                "hint_text": "Compare this month to last month to spot trends.",
            },
            {
                "step_number": 4,
                "title": "Export month-end package",
                "instruction": (
                    "Generate the month-end export package for your accountant."
                ),
                "target_route": "/reports/export",
                "target_element": "button[data-id='export-month-end']",
                "completion_trigger": "click",
                "hint_text": "The package includes all transactions, adjustments, and summaries.",
            },
        ],
    },
]

FUNERAL_HOME_SCENARIOS = [
    {
        "scenario_key": "first_call_walkthrough",
        "title": "First Call Walkthrough",
        "description": (
            "See how to take a first call and open a new case in the system."
        ),
        "estimated_minutes": 3,
        "steps": [
            {
                "step_number": 1,
                "title": "Type the first call details",
                "instruction": (
                    "A family calls to report a death. Type the deceased's "
                    "name, date of death, and the caller's contact information."
                ),
                "target_route": "/funeral-home/cases/new",
                "target_element": "input[data-id='deceased-first-name']",
                "completion_trigger": "field_filled",
                "hint_text": "Fill in the basic information from the first call.",
            },
            {
                "step_number": 2,
                "title": "Review the case card",
                "instruction": (
                    "Review the case summary card with the information you "
                    "entered. Confirm the details are correct."
                ),
                "target_route": "/funeral-home/cases/new",
                "target_element": None,
                "completion_trigger": "navigate",
                "hint_text": "The case card shows a summary before you save.",
            },
            {
                "step_number": 3,
                "title": "Open the case",
                "instruction": (
                    "Click 'Create Case' to open the case. You'll land on "
                    "the full case record where you can add services, contacts, "
                    "and more."
                ),
                "target_route": "/funeral-home/cases/new",
                "target_element": "button[data-id='create-case']",
                "completion_trigger": "click",
                "hint_text": "The case is now open and ready for arrangements.",
            },
        ],
    },
    {
        "scenario_key": "fh_vault_order_walkthrough",
        "title": "Ordering a Vault Walkthrough",
        "description": (
            "See how to place a vault order with your manufacturer through "
            "the platform."
        ),
        "estimated_minutes": 3,
        "steps": [
            {
                "step_number": 1,
                "title": "Browse the vault catalog",
                "instruction": (
                    "Open the vault ordering page and browse your manufacturer's "
                    "catalog. Filter by size, material, and price range."
                ),
                "target_route": "/funeral-home/vault-orders/new",
                "target_element": None,
                "completion_trigger": "navigate",
                "hint_text": "Your manufacturer was linked during setup.",
            },
            {
                "step_number": 2,
                "title": "Select a vault and set delivery details",
                "instruction": (
                    "Choose the vault model, enter the delivery date, cemetery, "
                    "and any special instructions."
                ),
                "target_route": "/funeral-home/vault-orders/new",
                "target_element": None,
                "completion_trigger": "field_filled",
                "hint_text": "Delivery details are sent directly to the manufacturer.",
            },
            {
                "step_number": 3,
                "title": "Submit the order",
                "instruction": (
                    "Review and submit the vault order. The manufacturer receives "
                    "it instantly and you can track delivery status in real time."
                ),
                "target_route": "/funeral-home/vault-orders/new",
                "target_element": "button[data-id='submit-vault-order']",
                "completion_trigger": "click",
                "hint_text": "The order goes directly to the manufacturer's dispatch system.",
            },
        ],
    },
]

_PRESET_SCENARIOS: dict[str, list[dict]] = {
    "manufacturing": MANUFACTURING_SCENARIOS,
    "funeral_home": FUNERAL_HOME_SCENARIOS,
}


# ===================================================================
# Tenant Onboarding — Core service functions
# ===================================================================


def fix_checklist_targets(db: Session) -> None:
    """Patch stale action_target / tier values on existing checklist items
    and backfill any missing items from the current seed definitions.

    Called on startup so that code-level changes to the seed definitions
    propagate to tenants that were already initialised.
    """
    _TARGET_FIXES = {
        "add_employees": "/onboarding/team",
        "connect_accounting": "/onboarding/accounting",
        "setup_team_intelligence": "/onboarding/team-intelligence",
        "setup_safety_training": "/onboarding/safety-training",
    }
    for item_key, correct_target in _TARGET_FIXES.items():
        db.query(OnboardingChecklistItem).filter(
            OnboardingChecklistItem.item_key == item_key,
            OnboardingChecklistItem.action_target != correct_target,
        ).update({"action_target": correct_target})

    # Fix setup_safety_training — remove all dependencies, should be available immediately
    db.query(OnboardingChecklistItem).filter(
        OnboardingChecklistItem.item_key == "setup_safety_training",
        OnboardingChecklistItem.depends_on.isnot(None),
    ).update({"depends_on": None})

    # Move setup_team_intelligence to last among must_complete (sort_order 99)
    db.query(OnboardingChecklistItem).filter(
        OnboardingChecklistItem.item_key == "setup_team_intelligence",
        OnboardingChecklistItem.sort_order != 99,
    ).update({
        "sort_order": 99,
        "description": (
            "Configure morning briefings and announcements for your team. "
            "Complete your other setup steps first \u2014 briefings are most useful "
            "once your products, customers, team, and safety programs are in place."
        ),
    })

    # Fix action_type for items that were incorrectly set to "modal"
    db.query(OnboardingChecklistItem).filter(
        OnboardingChecklistItem.item_key == "connect_accounting",
        OnboardingChecklistItem.action_type != "navigate",
    ).update({"action_type": "navigate"})

    # Promote configure_cross_tenant to must_complete (was should_complete)
    db.query(OnboardingChecklistItem).filter(
        OnboardingChecklistItem.item_key == "configure_cross_tenant",
        OnboardingChecklistItem.tier != "must_complete",
    ).update({"tier": "must_complete"})

    # Remove deprecated checklist items that were folded into other items
    _DEPRECATED_ITEMS = ["configure_delivery_zones"]
    db.query(OnboardingChecklistItem).filter(
        OnboardingChecklistItem.item_key.in_(_DEPRECATED_ITEMS),
    ).delete(synchronize_session=False)

    # Remove setup_funeral_home_customers from active checklists (moved to standing feature)
    # Only remove if not already completed — keep completed records for history
    db.query(OnboardingChecklistItem).filter(
        OnboardingChecklistItem.item_key == "setup_funeral_home_customers",
        OnboardingChecklistItem.status.in_(["not_started", "in_progress"]),
    ).delete(synchronize_session=False)

    # Fix configure_cross_tenant — remove dependency on setup_funeral_home_customers
    db.query(OnboardingChecklistItem).filter(
        OnboardingChecklistItem.item_key == "configure_cross_tenant",
    ).update({"depends_on": None})

    # Fix connect_accounting — must be position 2, updated description
    db.query(OnboardingChecklistItem).filter(
        OnboardingChecklistItem.item_key == "connect_accounting",
    ).update({
        "sort_order": 2,
        "description": (
            "Connect QuickBooks or upload your Sage chart of accounts. "
            "We'll use it to pre-configure your GL mappings, import your "
            "customers and vendors, and keep your financials in sync."
        ),
        "estimated_minutes": 10,
    })

    # Fix add_products — position 4
    db.query(OnboardingChecklistItem).filter(
        OnboardingChecklistItem.item_key == "add_products",
    ).update({"sort_order": 4})

    # Fix add_employees — position 6
    db.query(OnboardingChecklistItem).filter(
        OnboardingChecklistItem.item_key == "add_employees",
    ).update({"sort_order": 6})

    # Fix setup_safety_training — position 7
    db.query(OnboardingChecklistItem).filter(
        OnboardingChecklistItem.item_key == "setup_safety_training",
    ).update({"sort_order": 7})

    # Fix setup_scheduling_board — position 8
    db.query(OnboardingChecklistItem).filter(
        OnboardingChecklistItem.item_key == "setup_scheduling_board",
    ).update({"sort_order": 8})

    # Fix configure_cross_tenant — position 9
    db.query(OnboardingChecklistItem).filter(
        OnboardingChecklistItem.item_key == "configure_cross_tenant",
    ).update({"sort_order": 9})

    # --- Backfill missing checklist items for existing tenants ---
    # Get all existing checklists grouped by preset
    checklists = db.query(OnboardingChecklist).all()
    for checklist in checklists:
        preset = checklist.preset or "manufacturing"
        items_def = _PRESET_ITEMS.get(preset, MANUFACTURING_CHECKLIST_ITEMS)

        # Get existing item keys for this tenant
        existing_keys = {
            row.item_key
            for row in db.query(OnboardingChecklistItem.item_key).filter(
                OnboardingChecklistItem.tenant_id == checklist.tenant_id,
            ).all()
        }

        # Insert any missing items
        for item_def in items_def:
            if item_def["item_key"] not in existing_keys:
                item = OnboardingChecklistItem(
                    tenant_id=checklist.tenant_id,
                    checklist_id=checklist.id,
                    item_key=item_def["item_key"],
                    tier=item_def["tier"],
                    category=item_def["category"],
                    title=item_def["title"],
                    description=item_def.get("description"),
                    estimated_minutes=item_def.get("estimated_minutes", 0),
                    action_type=item_def["action_type"],
                    action_target=item_def.get("action_target"),
                    sort_order=item_def.get("sort_order", 0),
                    depends_on=item_def.get("depends_on"),
                )
                db.add(item)
                logger.info(
                    "Backfilled checklist item %s for tenant %s",
                    item_def["item_key"],
                    checklist.tenant_id,
                )

    db.commit()


def initialize_checklist(
    db: Session, tenant_id: str, preset: str
) -> OnboardingChecklist:
    """Called when a tenant is created. Generates checklist items + scenarios.

    Idempotent — if a checklist already exists for the tenant it is returned
    without modification.
    """
    existing = (
        db.query(OnboardingChecklist)
        .filter(OnboardingChecklist.tenant_id == tenant_id)
        .first()
    )
    if existing:
        return existing

    # --- Create checklist record ---
    checklist = OnboardingChecklist(
        tenant_id=tenant_id,
        preset=preset,
        status="not_started",
        must_complete_percent=0,
        overall_percent=0,
    )
    db.add(checklist)
    db.flush()  # get checklist.id

    # --- Create checklist items ---
    items_def = _PRESET_ITEMS.get(preset, MANUFACTURING_CHECKLIST_ITEMS)
    for item_def in items_def:
        item = OnboardingChecklistItem(
            tenant_id=tenant_id,
            checklist_id=checklist.id,
            item_key=item_def["item_key"],
            tier=item_def["tier"],
            category=item_def["category"],
            title=item_def["title"],
            description=item_def.get("description"),
            estimated_minutes=item_def.get("estimated_minutes", 0),
            action_type=item_def["action_type"],
            action_target=item_def.get("action_target"),
            sort_order=item_def.get("sort_order", 0),
            depends_on=item_def.get("depends_on"),
        )
        db.add(item)

    # NOTE: charge library seeding moved to tenant creation endpoint
    # to avoid transaction issues if the table doesn't exist yet.

    # --- Create scenarios + steps ---
    scenarios_def = _PRESET_SCENARIOS.get(preset, MANUFACTURING_SCENARIOS)
    for scenario_def in scenarios_def:
        steps_def = scenario_def.get("steps", [])
        scenario = OnboardingScenario(
            tenant_id=tenant_id,
            scenario_key=scenario_def["scenario_key"],
            preset=preset,
            title=scenario_def["title"],
            description=scenario_def.get("description"),
            estimated_minutes=scenario_def.get("estimated_minutes", 0),
            step_count=len(steps_def),
            status="not_started",
            current_step=0,
        )
        db.add(scenario)
        db.flush()  # get scenario.id

        for step_def in steps_def:
            step = OnboardingScenarioStep(
                scenario_id=scenario.id,
                tenant_id=tenant_id,
                step_number=step_def["step_number"],
                title=step_def["title"],
                instruction=step_def["instruction"],
                target_route=step_def.get("target_route"),
                target_element=step_def.get("target_element"),
                completion_trigger=step_def.get("completion_trigger"),
                hint_text=step_def.get("hint_text"),
            )
            db.add(step)

    db.commit()
    db.refresh(checklist)
    return checklist


def check_completion(
    db: Session, tenant_id: str, item_key: str
) -> bool:
    """Check if a checklist item's completion trigger is met.

    Idempotent — if already complete, returns False (not newly completed).
    MUST NOT raise exceptions; logs and returns False on error.
    """
    try:
        item = (
            db.query(OnboardingChecklistItem)
            .filter(
                OnboardingChecklistItem.tenant_id == tenant_id,
                OnboardingChecklistItem.item_key == item_key,
            )
            .first()
        )
        if not item:
            return False
        if item.status == "completed":
            return False

        item.status = "completed"
        item.completed_at = datetime.now(UTC)
        db.flush()

        recalculate_progress(db, tenant_id)

        # If must_complete just hit 100%, offer check-in call
        checklist = (
            db.query(OnboardingChecklist)
            .filter(OnboardingChecklist.tenant_id == tenant_id)
            .first()
        )
        if (
            checklist
            and checklist.must_complete_percent == 100
            and checklist.check_in_call_offered_at is None
        ):
            checklist.check_in_call_offered_at = datetime.now(UTC)

        db.commit()
        return True
    except Exception:
        logger.exception(
            "check_completion failed for tenant=%s item_key=%s",
            tenant_id,
            item_key,
        )
        try:
            db.rollback()
        except Exception:
            pass
        return False


def recalculate_progress(db: Session, tenant_id: str) -> None:
    """Recalculate must_complete_percent, overall_percent, and checklist status."""
    checklist = (
        db.query(OnboardingChecklist)
        .filter(OnboardingChecklist.tenant_id == tenant_id)
        .first()
    )
    if not checklist:
        return

    items = (
        db.query(OnboardingChecklistItem)
        .filter(OnboardingChecklistItem.checklist_id == checklist.id)
        .all()
    )

    # Must-complete progress
    must_items = [i for i in items if i.tier == "must_complete"]
    must_done = [i for i in must_items if i.status == "completed"]
    if must_items:
        checklist.must_complete_percent = int(
            len(must_done) / len(must_items) * 100
        )
    else:
        checklist.must_complete_percent = 100

    # Overall progress (skip "skipped" items from denominator)
    active_items = [i for i in items if i.status != "skipped"]
    completed_items = [i for i in active_items if i.status == "completed"]
    if active_items:
        checklist.overall_percent = int(
            len(completed_items) / len(active_items) * 100
        )
    else:
        checklist.overall_percent = 100

    # Status
    any_started = any(
        i.status in ("completed", "in_progress") for i in items
    )
    all_must_done = checklist.must_complete_percent == 100
    all_done = checklist.overall_percent == 100

    if all_done:
        checklist.status = "fully_complete"
    elif all_must_done:
        checklist.status = "must_complete_done"
    elif any_started:
        checklist.status = "in_progress"
    else:
        checklist.status = "not_started"

    db.flush()


def get_checklist(db: Session, tenant_id: str) -> OnboardingChecklist | None:
    """Return the full checklist with items, sorted by tier then sort_order."""
    checklist = (
        db.query(OnboardingChecklist)
        .options(joinedload(OnboardingChecklist.items))
        .filter(OnboardingChecklist.tenant_id == tenant_id)
        .first()
    )
    if checklist and checklist.items:
        tier_order = {"must_complete": 0, "should_complete": 1, "optional": 2}
        checklist.items.sort(
            key=lambda i: (tier_order.get(i.tier, 99), i.sort_order)
        )
    return checklist


def skip_item(db: Session, tenant_id: str, item_key: str) -> None:
    """Mark a checklist item as skipped."""
    item = (
        db.query(OnboardingChecklistItem)
        .filter(
            OnboardingChecklistItem.tenant_id == tenant_id,
            OnboardingChecklistItem.item_key == item_key,
        )
        .first()
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Checklist item '{item_key}' not found",
        )
    item.status = "skipped"
    recalculate_progress(db, tenant_id)
    db.commit()


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


def get_scenarios(
    db: Session, tenant_id: str
) -> list[OnboardingScenario]:
    """Return all scenarios for tenant with steps."""
    return (
        db.query(OnboardingScenario)
        .options(joinedload(OnboardingScenario.steps))
        .filter(OnboardingScenario.tenant_id == tenant_id)
        .order_by(OnboardingScenario.scenario_key)
        .all()
    )


def start_scenario(
    db: Session, tenant_id: str, scenario_key: str
) -> OnboardingScenario:
    """Mark scenario as in_progress, set started_at and current_step=1."""
    scenario = (
        db.query(OnboardingScenario)
        .options(joinedload(OnboardingScenario.steps))
        .filter(
            OnboardingScenario.tenant_id == tenant_id,
            OnboardingScenario.scenario_key == scenario_key,
        )
        .first()
    )
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_key}' not found",
        )
    if scenario.status == "not_started":
        scenario.status = "in_progress"
        scenario.started_at = datetime.now(UTC)
        scenario.current_step = 1
        db.commit()
        db.refresh(scenario)
    return scenario


def advance_scenario(
    db: Session, tenant_id: str, scenario_key: str, step_number: int
) -> OnboardingScenario:
    """Advance scenario to next step. If last step, mark completed."""
    scenario = (
        db.query(OnboardingScenario)
        .options(joinedload(OnboardingScenario.steps))
        .filter(
            OnboardingScenario.tenant_id == tenant_id,
            OnboardingScenario.scenario_key == scenario_key,
        )
        .first()
    )
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_key}' not found",
        )

    if step_number >= scenario.step_count:
        # Last step — mark completed
        scenario.status = "completed"
        scenario.completed_at = datetime.now(UTC)
        scenario.current_step = scenario.step_count
    else:
        scenario.current_step = step_number + 1

    db.commit()
    db.refresh(scenario)
    return scenario


# ---------------------------------------------------------------------------
# Product Catalog Templates
# ---------------------------------------------------------------------------


def get_product_templates(
    db: Session,
    preset: str | None = None,
    category: str | None = None,
) -> list[ProductCatalogTemplate]:
    """Get product catalog templates, optionally filtered."""
    query = db.query(ProductCatalogTemplate)
    if preset:
        query = query.filter(ProductCatalogTemplate.preset == preset)
    if category:
        query = query.filter(ProductCatalogTemplate.category == category)
    return query.order_by(ProductCatalogTemplate.sort_order).all()


def import_product_templates(
    db: Session, tenant_id: str, items: list
) -> int:
    """Import selected product templates as real products for the tenant.

    Each item should have: template_id, optional price, optional sku.
    Returns the count of products created.
    """
    count = 0
    for item in items:
        template_id = item.template_id if hasattr(item, "template_id") else item.get("template_id")
        price = item.price if hasattr(item, "price") else item.get("price")
        sku = item.sku if hasattr(item, "sku") else item.get("sku")

        template = db.query(ProductCatalogTemplate).get(template_id)
        if not template:
            continue

        product = Product(
            company_id=tenant_id,
            name=template.product_name,
            description=template.product_description,
            sku=sku or (template.sku_prefix if template.sku_prefix else None),
            price=price,
            unit_of_measure=template.default_unit,
            is_active=True,
        )
        db.add(product)
        count += 1

    if count:
        db.commit()
    return count


# ---------------------------------------------------------------------------
# Data Imports
# ---------------------------------------------------------------------------


def create_data_import(
    db: Session, tenant_id: str, import_type: str, source_format: str
) -> OnboardingDataImport:
    """Create a new data import session."""
    di = OnboardingDataImport(
        tenant_id=tenant_id,
        import_type=import_type,
        source_format=source_format,
        status="not_started",
    )
    db.add(di)
    db.commit()
    db.refresh(di)
    return di


def update_data_import(
    db: Session, import_id: str, **kwargs
) -> OnboardingDataImport:
    """Update import session with field mapping, status, etc."""
    di = db.query(OnboardingDataImport).get(import_id)
    if not di:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data import not found",
        )
    for key, value in kwargs.items():
        if key == "field_mapping" and isinstance(value, dict):
            setattr(di, key, json.dumps(value))
        elif hasattr(di, key):
            setattr(di, key, value)
    db.commit()
    db.refresh(di)
    return di


# ---------------------------------------------------------------------------
# Help Dismissals
# ---------------------------------------------------------------------------


def dismiss_help(
    db: Session, tenant_id: str, employee_id: str, help_key: str
) -> None:
    """Record that a user dismissed a help tooltip/panel."""
    existing = (
        db.query(OnboardingHelpDismissal)
        .filter(
            OnboardingHelpDismissal.tenant_id == tenant_id,
            OnboardingHelpDismissal.employee_id == employee_id,
            OnboardingHelpDismissal.help_key == help_key,
        )
        .first()
    )
    if existing:
        return
    dismissal = OnboardingHelpDismissal(
        tenant_id=tenant_id,
        employee_id=employee_id,
        help_key=help_key,
    )
    db.add(dismissal)
    db.commit()


def get_dismissed_help(
    db: Session, tenant_id: str, employee_id: str
) -> list[str]:
    """Get list of dismissed help keys for a user."""
    rows = (
        db.query(OnboardingHelpDismissal.help_key)
        .filter(
            OnboardingHelpDismissal.tenant_id == tenant_id,
            OnboardingHelpDismissal.employee_id == employee_id,
        )
        .all()
    )
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Check-in Call
# ---------------------------------------------------------------------------


def schedule_check_in_call(
    db: Session, tenant_id: str, scheduled: bool
) -> None:
    """Record check-in call scheduling decision."""
    checklist = (
        db.query(OnboardingChecklist)
        .filter(OnboardingChecklist.tenant_id == tenant_id)
        .first()
    )
    if not checklist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding checklist not found for tenant",
        )
    checklist.check_in_call_scheduled = scheduled
    db.commit()


# ---------------------------------------------------------------------------
# White Glove Import
# ---------------------------------------------------------------------------


def request_white_glove_import(
    db: Session,
    tenant_id: str,
    import_type: str,
    description: str,
    contact_email: str,
    file_url: str | None = None,
) -> OnboardingDataImport:
    """Create a white-glove import request."""
    di = OnboardingDataImport(
        tenant_id=tenant_id,
        import_type=import_type,
        source_format="white_glove",
        status="pending_review",
        file_url=file_url,
    )
    db.add(di)
    db.flush()

    # Mark checklist as having a white-glove request
    checklist = (
        db.query(OnboardingChecklist)
        .filter(OnboardingChecklist.tenant_id == tenant_id)
        .first()
    )
    if checklist:
        checklist.white_glove_import_requested = True

    db.commit()
    db.refresh(di)
    return di


# ---------------------------------------------------------------------------
# Onboarding Analytics (platform admin)
# ---------------------------------------------------------------------------


def get_onboarding_analytics(db: Session) -> dict:
    """Platform-wide onboarding analytics for admin dashboard."""
    now = datetime.now(UTC)
    seven_days_ago = now - timedelta(days=7)

    # Total checklists
    total_checklists = (
        db.query(sa_func.count(OnboardingChecklist.id)).scalar() or 0
    )

    # Average time from checklist creation to first completed item (proxy for "first order")
    avg_hours = None
    if total_checklists > 0:
        first_completions = (
            db.query(
                OnboardingChecklistItem.tenant_id,
                sa_func.min(OnboardingChecklistItem.completed_at).label("first_done"),
            )
            .filter(OnboardingChecklistItem.status == "completed")
            .group_by(OnboardingChecklistItem.tenant_id)
            .subquery()
        )
        avg_result = (
            db.query(
                sa_func.avg(
                    sa_func.extract(
                        "epoch",
                        first_completions.c.first_done
                        - OnboardingChecklist.created_at,
                    )
                )
            )
            .join(
                first_completions,
                OnboardingChecklist.tenant_id == first_completions.c.tenant_id,
            )
            .scalar()
        )
        if avg_result is not None:
            avg_hours = round(float(avg_result) / 3600, 1)

    # % of tenants with must_complete 100% within 7 days
    recent_total = (
        db.query(sa_func.count(OnboardingChecklist.id))
        .filter(OnboardingChecklist.created_at >= seven_days_ago)
        .scalar()
        or 0
    )
    recent_complete = (
        db.query(sa_func.count(OnboardingChecklist.id))
        .filter(
            OnboardingChecklist.created_at >= seven_days_ago,
            OnboardingChecklist.must_complete_percent == 100,
        )
        .scalar()
        or 0
    )
    must_complete_rate_7d = (
        round(recent_complete / recent_total * 100, 1)
        if recent_total > 0
        else 0.0
    )

    # Most-skipped / stuck checklist items (drop-off)
    drop_off_query = (
        db.query(
            OnboardingChecklistItem.item_key,
            OnboardingChecklistItem.title,
            sa_func.count(OnboardingChecklistItem.id).label("total"),
        )
        .group_by(
            OnboardingChecklistItem.item_key,
            OnboardingChecklistItem.title,
        )
        .all()
    )
    completed_counts = dict(
        db.query(
            OnboardingChecklistItem.item_key,
            sa_func.count(OnboardingChecklistItem.id),
        )
        .filter(OnboardingChecklistItem.status == "completed")
        .group_by(OnboardingChecklistItem.item_key)
        .all()
    )
    checklist_drop_off = [
        {
            "item_key": row.item_key,
            "title": row.title,
            "total": row.total,
            "completed": completed_counts.get(row.item_key, 0),
            "completion_rate": round(
                completed_counts.get(row.item_key, 0) / row.total * 100, 1
            )
            if row.total > 0
            else 0.0,
        }
        for row in drop_off_query
    ]
    checklist_drop_off.sort(key=lambda x: x["completion_rate"])

    # Integration adoption
    integration_rows = (
        db.query(
            OnboardingIntegrationSetup.integration_type,
            sa_func.count(OnboardingIntegrationSetup.id),
        )
        .group_by(OnboardingIntegrationSetup.integration_type)
        .all()
    )
    integration_adoption = {row[0]: row[1] for row in integration_rows}

    # Scenario completion rates
    scenario_total = (
        db.query(
            OnboardingScenario.scenario_key,
            sa_func.count(OnboardingScenario.id).label("total"),
        )
        .group_by(OnboardingScenario.scenario_key)
        .all()
    )
    scenario_completed = dict(
        db.query(
            OnboardingScenario.scenario_key,
            sa_func.count(OnboardingScenario.id),
        )
        .filter(OnboardingScenario.status == "completed")
        .group_by(OnboardingScenario.scenario_key)
        .all()
    )
    scenario_completion = {
        row.scenario_key: {
            "total": row.total,
            "completed": scenario_completed.get(row.scenario_key, 0),
        }
        for row in scenario_total
    }

    # White glove request stats
    wg_total = (
        db.query(sa_func.count(OnboardingDataImport.id))
        .filter(OnboardingDataImport.source_format == "white_glove")
        .scalar()
        or 0
    )
    wg_completed = (
        db.query(sa_func.count(OnboardingDataImport.id))
        .filter(
            OnboardingDataImport.source_format == "white_glove",
            OnboardingDataImport.status == "completed",
        )
        .scalar()
        or 0
    )
    white_glove_requests = {
        "total": wg_total,
        "completed": wg_completed,
    }

    # Check-in call acceptance rate
    offered = (
        db.query(sa_func.count(OnboardingChecklist.id))
        .filter(OnboardingChecklist.check_in_call_offered_at.isnot(None))
        .scalar()
        or 0
    )
    accepted = (
        db.query(sa_func.count(OnboardingChecklist.id))
        .filter(
            OnboardingChecklist.check_in_call_offered_at.isnot(None),
            OnboardingChecklist.check_in_call_scheduled == True,  # noqa: E712
        )
        .scalar()
        or 0
    )
    check_in_call_rate = (
        round(accepted / offered * 100, 1) if offered > 0 else 0.0
    )

    return {
        "avg_time_to_first_order_hours": avg_hours,
        "must_complete_rate_7d": must_complete_rate_7d,
        "checklist_drop_off": checklist_drop_off,
        "integration_adoption": integration_adoption,
        "scenario_completion": scenario_completion,
        "white_glove_requests": white_glove_requests,
        "check_in_call_rate": check_in_call_rate,
    }
