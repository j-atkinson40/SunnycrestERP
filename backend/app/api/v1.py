"""
API v1 router — aggregates all route modules under /api/v1/.

All new routes should be registered here. The bare /api/ prefix is
kept as a deprecated alias that adds a Deprecation header.
"""

from fastapi import APIRouter

from app.api.routes import (
    accounting,
    accounting_connection,
    ai,
    ai_command,
    ai_settings,
    core,
    configurable_items,
    product_lines,
    ancillary_orders,
    announcements,
)
from app.api.routes.fh import cases as fh_cases
from app.api.routes.fh import cemetery as fh_cemetery
from app.api.routes.fh import network as fh_network
from app.api.routes.fh import monument as fh_monument
from app.api.routes import workflows as workflow_routes
from app.api.routes import vault_documents as vault_documents_routes
from app.api.routes import saved_orders as saved_orders_routes
from app.api.routes import external_accounts as external_accounts_routes
from app.api.routes import intelligence as intelligence_routes
from app.api.routes import (   # noqa: E402 — continuation of main import
    call_intelligence,
    ringcentral,
    data_import,
    driver_announcements,
    internal,
    knowledge_base,
    locations,
    price_management,
    ap,
    api_keys,
    audit,
    auth,
    billing,
    billing_groups,
    bom,
    briefings,
    bundles,
    company_entities,
    carrier_portal,
    cases,
    cemeteries,
    disinterments,
    disinterment_charge_types,
    docusign_webhook,
    intake,
    union_rotations,
    charge_library,
    charge_terms,
    companies,
    behavioral_analytics,
    customers,
    deliveries,
    discount,
    finance_charges,
    delivery_portal,
    direct_ship,
    delivery_settings,
    delivery_types,
    delivery_intelligence,
    departments,
    training as training_routes,
    documents,
    documents_v2,
    signing_admin,
    signing_public,
    driver_mobile,
    employee_profiles,
    equipment,
    extensions,
    feature_flags,
    financial_health,
    functional_areas,
    fh_portal,
    fh_price_list,
    ftc_compliance,
    cemetery_directory,
    funeral_home_directory,
    funeral_kanban,
    hierarchy,
    historical_order_import,
    inventory,
    job_queue,
    migration,
    modules,
    network,
    agents,
    proactive_agents,
    report_intelligence,
    network_intelligence,
    financials_board,
    journal_entries,
    notifications,
    onboarding,
    onboarding_flow,
    operations_board,
    permissions,
    programs,
    purchasing,
    reconciliation,
    reports,
    tax,
    inter_licensee_pricing,
    transfers,
    order_station,
    template_seasons,
    performance_notes,
    platform_fees,
    price_list_import,
    production_log,
    catalog_builder,
    spring_burials,
    urn_catalog,
    urn_sales,
    products,
    projects,
    purchase_orders,
    qc,
    safety,
    safety_program_generation,
    safety_training_system,
    statements,
    roles,
    sage_exports,
    service_territory,
    sales,
    social_service_certificates,
    super_admin,
    sync_logs,
    tenant_onboarding,
    tenant_onboarding_admin,
    unified_import,
    users,
    vendor_bills,
    vendor_payments,
    vendors,
    legacy,
    legacy_delivery,
    legacy_email,
    legacy_studio,
    personalization,
    training_lifecycle,
    webhooks,
    website_intelligence,
    vault,
    vault_accounting,
    vault_molds,
    vault_supplier,
    widgets,
    widget_data,
    work_orders,
)

v1_router = APIRouter()

# --- Route registration (alphabetical) ---
v1_router.include_router(
    accounting.router, prefix="/accounting", tags=["Accounting Integration"]
)
v1_router.include_router(
    accounting_connection.router,
    prefix="/accounting-connection",
    tags=["Accounting Connection"],
)
v1_router.include_router(ai.router, prefix="/ai", tags=["AI"])
v1_router.include_router(ai_command.router, prefix="/ai", tags=["AI Command"])
v1_router.include_router(ai_settings.router, prefix="/settings/ai", tags=["AI Settings"])
v1_router.include_router(
    ancillary_orders.router, prefix="/extensions/funeral-kanban", tags=["Ancillary Orders"]
)
v1_router.include_router(
    announcements.router, prefix="/announcements", tags=["Announcements"]
)
v1_router.include_router(
    driver_announcements.router, prefix="", tags=["Driver Announcements"]
)
v1_router.include_router(api_keys.router, prefix="/api-keys", tags=["API Keys"])
v1_router.include_router(ap.router, prefix="/ap", tags=["Accounts Payable"])
v1_router.include_router(audit.router, prefix="/audit-logs", tags=["Audit Logs"])
v1_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
v1_router.include_router(
    billing.router, prefix="/billing", tags=["Billing"]
)
v1_router.include_router(
    billing_groups.router, prefix="/billing-groups", tags=["Billing Groups"]
)
v1_router.include_router(
    call_intelligence.router,
    prefix="/integrations/ringcentral",
    tags=["Call Intelligence"],
)
v1_router.include_router(
    ringcentral.router,
    prefix="/integrations/ringcentral",
    tags=["Call Intelligence"],
)
v1_router.include_router(
    bom.router, prefix="/bom", tags=["Bill of Materials"]
)
v1_router.include_router(
    briefings.router, prefix="/briefings", tags=["Morning Briefings"]
)
v1_router.include_router(
    bundles.router, prefix="/products", tags=["Product Bundles"]
)
v1_router.include_router(
    carrier_portal.router, prefix="/carrier", tags=["Carrier Portal"]
)
v1_router.include_router(
    cases.router, prefix="/cases", tags=["Funeral Home Cases"]
)
v1_router.include_router(
    cemeteries.router, prefix="/cemeteries", tags=["Cemeteries"]
)
v1_router.include_router(
    disinterments.router, prefix="/disinterments", tags=["Disinterments"]
)
v1_router.include_router(
    disinterment_charge_types.router,
    prefix="/disinterment-charge-types",
    tags=["Disinterment Charge Types"],
)
v1_router.include_router(
    docusign_webhook.router, prefix="/docusign", tags=["DocuSign"]
)
v1_router.include_router(
    intake.router, prefix="/intake", tags=["Public Intake"]
)
v1_router.include_router(
    union_rotations.router, prefix="/union-rotations", tags=["Union Rotations"]
)
v1_router.include_router(
    charge_library.router, prefix="/charge-library", tags=["Charge Library"]
)
v1_router.include_router(
    charge_terms.router, prefix="/onboarding/charge-terms", tags=["Charge Terms"]
)
# companies.router MUST come before company_entities.router — both share
# the /companies prefix and company_entities has /{entity_id} catch-all
# that would swallow /settings, /tenant-settings, etc.
v1_router.include_router(
    companies.router, prefix="/companies", tags=["Company Management"]
)
v1_router.include_router(
    company_entities.router, prefix="/companies", tags=["Company Entities"]
)
v1_router.include_router(
    configurable_items.router, prefix="/configurable", tags=["Configurable Items"]
)
v1_router.include_router(
    product_lines.router, prefix="/product-lines", tags=["Product Lines"]
)
v1_router.include_router(
    core.router, prefix="/core", tags=["Core UI"]
)
v1_router.include_router(
    customers.router, prefix="/customers", tags=["Customers"]
)
v1_router.include_router(
    deliveries.router, prefix="/delivery", tags=["Delivery & Dispatch"]
)
v1_router.include_router(
    discount.router, prefix="/discount", tags=["Early Payment Discount"]
)
v1_router.include_router(
    finance_charges.router, prefix="/finance-charges", tags=["Finance Charges"]
)
v1_router.include_router(
    behavioral_analytics.router, prefix="/behavioral", tags=["Behavioral Analytics"]
)
v1_router.include_router(
    data_import.router, prefix="/data-import", tags=["Data Import"]
)
v1_router.include_router(
    delivery_portal.router, prefix="/portal", tags=["Delivery Portal"]
)
v1_router.include_router(
    direct_ship.router, prefix="/extensions/funeral-kanban", tags=["Direct Ship"]
)
v1_router.include_router(
    delivery_settings.router, prefix="/settings", tags=["Delivery Settings"]
)
v1_router.include_router(
    delivery_types.router, prefix="/delivery-types", tags=["Delivery Types"]
)
v1_router.include_router(
    departments.router, prefix="/departments", tags=["Departments"]
)
v1_router.include_router(
    documents.router, prefix="/documents", tags=["Documents"]
)
# Phase D-1 — canonical Documents layer (admin-gated, tenant-scoped).
# Legacy /documents/* remains above for the old Document model callers.
v1_router.include_router(
    documents_v2.router, prefix="/documents-v2", tags=["Documents (canonical)"]
)
# Phase D-4 native signing
v1_router.include_router(
    signing_public.router, prefix="/sign", tags=["Signing (public)"]
)
v1_router.include_router(
    signing_admin.router, prefix="/admin/signing", tags=["Signing (admin)"]
)
v1_router.include_router(
    driver_mobile.router, prefix="/driver", tags=["Driver Mobile"]
)
v1_router.include_router(
    employee_profiles.router,
    prefix="/employee-profiles",
    tags=["Employee Profiles"],
)
v1_router.include_router(
    equipment.router, prefix="/equipment", tags=["Equipment"]
)
v1_router.include_router(
    extensions.router, prefix="/extensions", tags=["Extension Catalog"]
)
v1_router.include_router(
    feature_flags.router, prefix="/feature-flags", tags=["Feature Flags"]
)
v1_router.include_router(
    functional_areas.router, prefix="/team", tags=["Functional Areas"]
)
v1_router.include_router(
    fh_portal.router, prefix="/portal/family", tags=["Family Portal"]
)
v1_router.include_router(
    fh_price_list.router, prefix="/price-list", tags=["Funeral Home Price List"]
)
v1_router.include_router(
    ftc_compliance.router, prefix="/ftc", tags=["FTC Compliance"]
)
v1_router.include_router(
    cemetery_directory.router,
    prefix="/onboarding/cemeteries",
    tags=["Cemetery Directory"],
)
v1_router.include_router(
    funeral_home_directory.router,
    prefix="/onboarding/customers",
    tags=["Funeral Home Directory"],
)
v1_router.include_router(
    funeral_kanban.router, prefix="/extensions/funeral-kanban", tags=["Funeral Kanban"]
)
v1_router.include_router(
    hierarchy.router, prefix="/hierarchy", tags=["Org Hierarchy"]
)
v1_router.include_router(
    historical_order_import.router,
    prefix="/historical-orders",
    tags=["Historical Order Import"],
)
v1_router.include_router(
    internal.router, prefix="/internal", tags=["Internal"]
)
v1_router.include_router(
    inventory.router, prefix="/inventory", tags=["Inventory"]
)
v1_router.include_router(
    job_queue.router, prefix="/jobs", tags=["Job Queue"]
)
v1_router.include_router(modules.router, prefix="/modules", tags=["Modules"])
v1_router.include_router(
    migration.router, prefix="/migration", tags=["Data Migration"]
)
v1_router.include_router(
    network.router, prefix="/network", tags=["Network"]
)
v1_router.include_router(
    notifications.router, prefix="/notifications", tags=["Notifications"]
)
v1_router.include_router(
    onboarding.router, prefix="/onboarding", tags=["Onboarding"]
)
v1_router.include_router(
    onboarding_flow.router, prefix="/onboarding-flow", tags=["Onboarding Flow"]
)
v1_router.include_router(
    agents.router,
    prefix="/agents",
    tags=["Agents"],
)
v1_router.include_router(
    proactive_agents.router,
    prefix="/proactive-agents",
    tags=["Proactive Agents"],
)
v1_router.include_router(
    report_intelligence.router,
    prefix="/report-intelligence",
    tags=["Report Intelligence"],
)
v1_router.include_router(
    network_intelligence.router,
    prefix="/network",
    tags=["Network Intelligence"],
)
v1_router.include_router(
    delivery_intelligence.router,
    prefix="/delivery",
    tags=["Delivery Intelligence"],
)
v1_router.include_router(
    training_routes.router,
    prefix="/training",
    tags=["Employee Training"],
)
v1_router.include_router(
    financial_health.router,
    prefix="/health",
    tags=["Financial Health"],
)
v1_router.include_router(
    financials_board.router,
    prefix="/financials",
    tags=["Financials Board"],
)
v1_router.include_router(
    journal_entries.router,
    prefix="/journal-entries",
    tags=["Journal Entries"],
)
v1_router.include_router(
    knowledge_base.router,
    prefix="/knowledge-base",
    tags=["Knowledge Base"],
)
v1_router.include_router(
    locations.router,
    prefix="/locations",
    tags=["Locations"],
)
v1_router.include_router(
    price_management.router,
    prefix="/price-management",
    tags=["Price Management"],
)
v1_router.include_router(
    operations_board.router,
    prefix="/operations-board",
    tags=["Operations Board"],
)
v1_router.include_router(
    programs.router, prefix="/programs", tags=["Programs"]
)
v1_router.include_router(
    purchasing.router,
    prefix="/purchasing",
    tags=["Purchasing"],
)
v1_router.include_router(
    reconciliation.router,
    prefix="/reconciliation",
    tags=["Reconciliation"],
)
v1_router.include_router(
    tax.router,
    prefix="/tax",
    tags=["Tax"],
)
v1_router.include_router(
    inter_licensee_pricing.router,
    prefix="/inter-licensee-pricing",
    tags=["Inter-Licensee Pricing"],
)
v1_router.include_router(
    transfers.router,
    prefix="/transfers",
    tags=["Licensee Transfers"],
)
v1_router.include_router(
    reports.router,
    prefix="/reports",
    tags=["Reports"],
)
v1_router.include_router(
    order_station.router,
    prefix="/order-station",
    tags=["Order Entry Station"],
)
v1_router.include_router(
    template_seasons.router,
    prefix="/template-seasons",
    tags=["Template Seasons"],
)
v1_router.include_router(
    performance_notes.router,
    prefix="/performance-notes",
    tags=["Performance Notes"],
)
v1_router.include_router(
    platform_fees.router, prefix="/platform-fees", tags=["Platform Fees"]
)
v1_router.include_router(
    price_list_import.router, prefix="/catalog", tags=["Price List Import"]
)
v1_router.include_router(
    production_log.router, prefix="/production", tags=["Production Log"]
)
v1_router.include_router(
    spring_burials.router, tags=["Spring Burials"]
)
v1_router.include_router(
    catalog_builder.router, tags=["Catalog Builder"]
)
v1_router.include_router(
    products.router, prefix="/products", tags=["Products"]
)
v1_router.include_router(
    urn_catalog.router, prefix="/products", tags=["Urn Catalog"]
)
v1_router.include_router(
    urn_sales.router, prefix="/urns", tags=["Urn Sales"]
)
v1_router.include_router(
    projects.router, prefix="/projects", tags=["Project Management"]
)
v1_router.include_router(
    purchase_orders.router, prefix="/purchase-orders", tags=["Purchase Orders"]
)
v1_router.include_router(
    qc.router, prefix="/qc", tags=["Quality Control"]
)
v1_router.include_router(
    safety_program_generation.router,
    prefix="/safety/programs",
    tags=["Safety Program Generation"],
)
v1_router.include_router(
    safety.router, prefix="/safety", tags=["Safety Management"]
)
v1_router.include_router(
    safety_training_system.router,
    prefix="/safety",
    tags=["Safety Training System"],
)
v1_router.include_router(
    statements.router, prefix="/statements", tags=["Statements"]
)
v1_router.include_router(roles.router, prefix="/roles", tags=["Role Management"])
v1_router.include_router(
    permissions.router, prefix="/permissions", tags=["Permission Management"]
)
v1_router.include_router(
    sage_exports.router, prefix="/sage-exports", tags=["Sage Exports"]
)
v1_router.include_router(
    service_territory.router, prefix="/settings", tags=["Service Territory"]
)
v1_router.include_router(
    sales.router, prefix="/sales", tags=["Sales & AR"]
)
v1_router.include_router(
    social_service_certificates.router,
    prefix="/social-service-certificates",
    tags=["Social Service Certificates"],
)
v1_router.include_router(
    super_admin.router, prefix="/super-admin", tags=["Super Admin"]
)
v1_router.include_router(
    sync_logs.router, prefix="/sync-logs", tags=["Sync Logs"]
)
v1_router.include_router(
    tenant_onboarding.router,
    prefix="/tenant-onboarding",
    tags=["Tenant Onboarding"],
)
v1_router.include_router(
    tenant_onboarding_admin.router,
    prefix="/admin/tenant-onboarding",
    tags=["Tenant Onboarding Admin"],
)
v1_router.include_router(
    unified_import.router,
    prefix="/onboarding/import",
    tags=["Unified Import"],
)
v1_router.include_router(users.router, prefix="/users", tags=["User Management"])
v1_router.include_router(
    vendor_bills.router, prefix="/vendor-bills", tags=["Vendor Bills"]
)
v1_router.include_router(
    vendor_payments.router, prefix="/vendor-payments", tags=["Vendor Payments"]
)
v1_router.include_router(vendors.router, prefix="/vendors", tags=["Vendors"])
v1_router.include_router(
    website_intelligence.router, tags=["Website Intelligence"]
)
v1_router.include_router(
    legacy.router, prefix="/legacy", tags=["Legacy"]
)
v1_router.include_router(
    legacy_delivery.router, prefix="/legacy", tags=["Legacy Delivery"]
)
v1_router.include_router(
    legacy_email.router, prefix="/legacy", tags=["Legacy Email"]
)
v1_router.include_router(
    legacy_studio.router, prefix="/legacy-studio", tags=["Legacy Studio"]
)
v1_router.include_router(
    personalization.router, prefix="/personalization", tags=["Personalization"]
)
v1_router.include_router(
    training_lifecycle.router, prefix="/training", tags=["Training"]
)
v1_router.include_router(
    webhooks.router, prefix="/webhooks", tags=["Webhooks"]
)
v1_router.include_router(
    vault.router, prefix="/vault", tags=["Vault"]
)
# V-1e: Accounting admin sub-tree under /vault/accounting/*
v1_router.include_router(
    vault_accounting.router,
    prefix="/vault/accounting",
    tags=["Vault / Accounting Admin"],
)
v1_router.include_router(
    vault_molds.router, prefix="/vault-molds", tags=["Vault Molds"]
)
v1_router.include_router(
    vault_supplier.router, prefix="/vault-supplier", tags=["Vault Supplier"]
)
v1_router.include_router(
    widgets.router, prefix="/widgets", tags=["Widget Framework"]
)
v1_router.include_router(
    widget_data.router, prefix="/widget-data", tags=["Widget Data"]
)
v1_router.include_router(
    work_orders.router, prefix="/work-orders", tags=["Work Orders"]
)

# Funeral Home vertical (FH-1a + FH-1b)
v1_router.include_router(
    fh_cases.router, prefix="/fh/cases", tags=["FH Cases"]
)
v1_router.include_router(
    fh_cemetery.router, prefix="/fh/cemetery", tags=["FH Cemetery"]
)
v1_router.include_router(
    fh_network.router, prefix="/fh/network", tags=["FH Network"]
)
v1_router.include_router(
    fh_monument.router, prefix="/fh/monument", tags=["FH Monument"]
)

# Workflow Engine (Phase W-1)
v1_router.include_router(
    workflow_routes.router, prefix="/workflows", tags=["Workflows"]
)

# Saved Orders (Compose Templates)
v1_router.include_router(
    saved_orders_routes.router, prefix="/saved-orders", tags=["Saved Orders"]
)

# External Accounts (Playwright workflow credentials)
v1_router.include_router(
    external_accounts_routes.router, prefix="/external-accounts", tags=["External Accounts"]
)

# Vault Documents (Phase W-2 — native document layer on R2)
v1_router.include_router(
    vault_documents_routes.router, prefix="/vault-documents", tags=["Vault Documents"]
)

# Bridgeable Intelligence — unified AI layer (Phase 1 backbone)
v1_router.include_router(
    intelligence_routes.router, prefix="/intelligence", tags=["Intelligence"]
)
