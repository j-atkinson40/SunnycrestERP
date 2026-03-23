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
    ancillary_orders,
    ap,
    api_keys,
    audit,
    auth,
    billing,
    bom,
    briefings,
    bundles,
    carrier_portal,
    cases,
    charge_library,
    companies,
    customers,
    deliveries,
    delivery_portal,
    direct_ship,
    delivery_settings,
    delivery_types,
    departments,
    documents,
    driver_mobile,
    employee_profiles,
    equipment,
    extensions,
    feature_flags,
    functional_areas,
    fh_portal,
    fh_price_list,
    ftc_compliance,
    funeral_home_directory,
    funeral_kanban,
    hierarchy,
    inventory,
    job_queue,
    modules,
    network,
    notifications,
    onboarding,
    order_station,
    performance_notes,
    platform_fees,
    price_list_import,
    production_log,
    catalog_builder,
    spring_burials,
    urn_catalog,
    products,
    projects,
    purchase_orders,
    qc,
    safety,
    roles,
    sage_exports,
    service_territory,
    sales,
    super_admin,
    sync_logs,
    tenant_onboarding,
    tenant_onboarding_admin,
    users,
    vendor_bills,
    vendor_payments,
    vendors,
    webhooks,
    website_intelligence,
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
v1_router.include_router(
    ancillary_orders.router, prefix="/extensions/funeral-kanban", tags=["Ancillary Orders"]
)
v1_router.include_router(api_keys.router, prefix="/api-keys", tags=["API Keys"])
v1_router.include_router(ap.router, prefix="/ap", tags=["Accounts Payable"])
v1_router.include_router(audit.router, prefix="/audit-logs", tags=["Audit Logs"])
v1_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
v1_router.include_router(
    billing.router, prefix="/billing", tags=["Billing"]
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
    charge_library.router, prefix="/charge-library", tags=["Charge Library"]
)
v1_router.include_router(
    companies.router, prefix="/companies", tags=["Company Management"]
)
v1_router.include_router(
    customers.router, prefix="/customers", tags=["Customers"]
)
v1_router.include_router(
    deliveries.router, prefix="/delivery", tags=["Delivery & Dispatch"]
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
    inventory.router, prefix="/inventory", tags=["Inventory"]
)
v1_router.include_router(
    job_queue.router, prefix="/jobs", tags=["Job Queue"]
)
v1_router.include_router(modules.router, prefix="/modules", tags=["Modules"])
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
    order_station.router,
    prefix="/order-station",
    tags=["Order Entry Station"],
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
    projects.router, prefix="/projects", tags=["Project Management"]
)
v1_router.include_router(
    purchase_orders.router, prefix="/purchase-orders", tags=["Purchase Orders"]
)
v1_router.include_router(
    qc.router, prefix="/qc", tags=["Quality Control"]
)
v1_router.include_router(
    safety.router, prefix="/safety", tags=["Safety Management"]
)
v1_router.include_router(roles.router, prefix="/roles", tags=["Role Management"])
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
    webhooks.router, prefix="/webhooks", tags=["Webhooks"]
)
v1_router.include_router(
    work_orders.router, prefix="/work-orders", tags=["Work Orders"]
)
