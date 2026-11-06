"""
API v1 router — aggregates all route modules under /api/v1/.

All new routes should be registered here. The bare /api/ prefix is
kept as a deprecated alias that adds a Deprecation header.
"""

from fastapi import APIRouter, Depends

from app.api.area_guard import enforce_area_limit

from app.api.routes import (
    accounting,
    invites,
    accounting_connection,
    ai,
    ai_command,
    command_bar,
    edge_panel,
    saved_views,
    spaces,
    themes_tenant,
    nl_creation,
    workflow_authoring,
    coordination_focus,
    peek,
    portal,
    portal_admin,
    email_accounts,
    email_actions,
    email_inbox,
    email_webhooks,
    calendar_accounts,
    calendar_actions,
    calendar_consent,
    calendar_events,
    calendar_freebusy,
    personalization_studio,
    personalization_studio_family_portal,
    workshop,
    tasks,
    triage,
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
from app.api.routes import (
    admin_email_classification as email_classification_routes,
)
from app.api.routes import vault_documents as vault_documents_routes
from app.api.routes import saved_orders as saved_orders_routes
from app.api.routes import external_accounts as external_accounts_routes
from app.api.routes import intelligence as intelligence_routes
from app.api.routes import (   # noqa: E402 — continuation of main import
    call_intelligence,
    ringcentral,
    note,
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
    focus as focus_routes,
    onboarding_touches,
    operator_profile as operator_profile_routes,
    company_entities,
    carrier_portal,
    cases,
    cemeteries,
    disinterments,
    disinterment_charge_types,
    docusign_webhook,
    intake,
    intake_adapters,
    union_rotations,
    charge_library,
    charge_terms,
    companies,
    behavioral_analytics,
    customers,
    deliveries,
    discount,
    dispatch,
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
    completeness,
    two_step,
    payroll_reports,
    vault_accounting,
    vault_molds,
    vault_supplier,
    widget_definitions,
    widgets,
    widget_data,
    work_orders,
)

# ⚠️ ONE CENTRAL AREA CHECK, ATTACHED HERE AND NOWHERE ELSE.
#
# `enforce_area_limit` refuses a user on an area-limited role any tenant
# endpoint that is not tagged `area:<key>` for one of their areas, plus the
# common set in `app/core/areas.py`. Default deny: an UNTAGGED endpoint is
# refused.
#
# It is on the router constructor rather than on each `include_router` call
# below so a new router cannot be added without it — which is the whole reason
# it exists. Measured 2026-11-03: 1063 of 1920 tenant endpoints had no per-user
# gate, and 886 had no handler-level check either; gating them one at a time was
# 886 chances to miss one, plus every future endpoint.
#
# For a role with `limited_to_areas IS NULL` — which is every existing role, by
# construction, because r221 did not backfill — this is a single indexed role
# lookup and a return. Behaviour for those users is unchanged.
#
# ⚠️ IT MUST STAY ON `v1_router` ITSELF, NOT ON THE TWO MOUNTS IN main.py. The
# router is mounted twice (at `/api/v1` and at the deprecated `/api` alias); a
# dependency on one mount would leave the other as a way around the guard.
v1_router = APIRouter(dependencies=[Depends(enforce_area_limit)])

# --- Route registration (alphabetical) ---
v1_router.include_router(
    accounting.router, prefix="/accounting", tags=["Accounting Integration", "area:accounting"]
)
v1_router.include_router(
    accounting_connection.router,
    prefix="/accounting-connection",
    tags=["Accounting Connection", "area:accounting"],
)
v1_router.include_router(ai.router, prefix="/ai", tags=["AI"])
v1_router.include_router(ai_command.router, prefix="/ai", tags=["AI Command"])
# Command Bar Platform Layer (Phase 1). New contract at
# /api/v1/command-bar/query. See CLAUDE.md §4 "Command Bar Migration
# Tracking" for the deprecation plan on the legacy /ai-command/*
# routes above.
v1_router.include_router(
    command_bar.router, prefix="/command-bar", tags=["Command Bar"]
)
# Saved Views Platform Layer — Phase 2.
v1_router.include_router(
    saved_views.router, prefix="/saved-views", tags=["Saved Views"]
)
# Spaces — Phase 3 of UI/UX Arc. Per-user workspace contexts.
v1_router.include_router(spaces.router, prefix="/spaces", tags=["Spaces"])
# R-2.5 — tenant-realm theme resolve. Tenant operators read the active
# theme inheritance walk for their own (vertical, tenant_id) context
# on production routes (PresetThemeProvider mount). Distinct from the
# admin-realm endpoint at /api/platform/admin/visual-editor/themes/
# resolve which permits arbitrary scope arguments; this tenant
# endpoint infers vertical + tenant_id from `current_user.company`.
v1_router.include_router(
    themes_tenant.router, prefix="/themes", tags=["Themes (tenant)"]
)
# R-5.0 — edge panel tenant-realm endpoints (resolve/preferences/tenant-config).
# Authoring lives in the admin-realm visual editor at
# /api/platform/admin/visual-editor/compositions/ (kind=edge_panel rows).
v1_router.include_router(
    edge_panel.router, prefix="/edge-panel", tags=["Edge Panel"]
)
# Phase 8e.2.1 — tenant-admin portal user + branding management.
# TENANT realm (require_admin), mounted at /api/v1/portal/admin/*.
# Registered BEFORE the public /portal router so the /{tenant_slug}/…
# parameterized routes don't swallow `/admin/*` by matching
# `tenant_slug="admin"` (FastAPI uses first-match routing).
v1_router.include_router(
    portal_admin.router, prefix="/portal/admin", tags=["Portal Admin", "area:settings"]
)
# Phase 8e.2 — portal endpoints (both public + portal-authed).
# Path segment carries the tenant slug so portal URLs are identity-
# tight (no X-Company-Slug header dependency). See
# SPACES_ARCHITECTURE.md §10.
v1_router.include_router(portal.router, prefix="/portal", tags=["Portal", "area:settings"])
# NOTE: Admin Visual Editor routes (themes, component configurations,
# workflow templates — Phase 2/3/4) relocated to platform_router under
# /api/platform/admin/visual-editor/* in the corrective relocation
# phase (May 2026). They live in app/api/routes/admin/visual_editor_*.py
# and are gated by Depends(get_current_platform_user). See platform.py.
# Email Primitive — Phase W-4b Layer 1 Step 1 (BRIDGEABLE_MASTER §3.26.15).
# Tenant-admin endpoints for managing EmailAccount + EmailAccountAccess.
# Coexists with existing transactional email infrastructure (D-7 DeliveryService
# + email_sends model) — different architectural concern (conversation/inbox
# vs fire-and-forget transactional send). See app.services.email package.
v1_router.include_router(
    email_accounts.router, prefix="/email-accounts", tags=["Email Accounts", "area:documents"]
)
# Email Primitive — Phase W-4b Layer 1 Step 2 webhook endpoints.
# PUBLIC routes (no Bearer auth) authenticated via per-provider
# signature verification (Gmail Pub/Sub JWT + MS Graph clientState).
v1_router.include_router(
    email_webhooks.router,
    prefix="/email/webhooks",
    tags=["Email Webhooks", "area:documents"],
)
# Email Primitive — Phase W-4b Layer 1 Step 4a inbox surface.
# Read path (GET /threads + GET /threads/{id}) + status mutations
# (POST /messages/{id}/read|unread + POST /threads/{id}/archive|flag).
# Per-tenant isolation via current_user; per-account access via
# EmailAccountAccess junction; cross-tenant masking inheritance hooks
# present (passthrough in Step 4a; full masking lands alongside
# operator-action affordances in Step 4b+).
v1_router.include_router(
    email_inbox.router, prefix="/email", tags=["Email Inbox", "area:documents"]
)
# Email Primitive — Phase W-4b Layer 1 Step 4c operational-action affordance API.
# Two surfaces sharing one commit logic: inline action for Bridgeable users
# (POST /email/messages/{id}/actions/{idx}/commit) + magic-link surface
# for non-Bridgeable recipients (GET/POST /email/actions/{token}). Public
# magic-link routes auth via token; inline routes auth via session.
# kill-the-portal canonical case (quote_approval) per §3.26.15.17.
v1_router.include_router(
    email_actions.router, prefix="/email", tags=["Email Actions", "area:documents"]
)
# Calendar Primitive — Phase W-4b Layer 1 Calendar Step 1 (BRIDGEABLE_MASTER
# §3.26.16). Tenant-admin endpoints for managing CalendarAccount +
# CalendarAccountAccess + tenant CRUD for CalendarEvent. Coexists with
# existing Vault iCal feed at /api/v1/vault/calendar.ics — different
# architectural concern (one-way iCal export vs threaded calendar primitive
# with provider abstraction). See app.services.calendar package.
v1_router.include_router(
    calendar_accounts.router,
    prefix="/calendar-accounts",
    tags=["Calendar Accounts", "area:scheduling"],
)
v1_router.include_router(
    calendar_events.router,
    prefix="/calendar-events",
    tags=["Calendar Events", "area:scheduling"],
)
# Calendar Step 3 — Free/busy substrate (per-account + cross-tenant)
# per §3.26.16.14 endpoint shape. Mounted at /calendar (NOT
# /calendar-accounts) to match canonical endpoint paths
# /api/v1/calendar/free-busy + /api/v1/calendar/free-busy/cross-tenant.
v1_router.include_router(
    calendar_freebusy.router,
    prefix="/calendar",
    tags=["Calendar Free/Busy", "area:scheduling"],
)
# Calendar Step 4 — operational-action affordance routes per §3.26.16.17.
# Two surfaces:
#   inline_router → mounted at /calendar-events (authenticated inline
#     action commit at /{event_id}/actions/{action_idx}/commit)
#   public_router → mounted at /calendar (public magic-link surface at
#     /actions/{token} + /actions/{token}/commit)
# Pattern parallels Email Step 4c email_actions.py post-Path-B
# substrate consolidation (calendar tokens use platform_action_tokens
# substrate via linked_entity_type='calendar_event').
v1_router.include_router(
    calendar_actions.inline_router,
    prefix="/calendar-events",
    tags=["Calendar Actions", "area:scheduling"],
)
v1_router.include_router(
    calendar_actions.public_router,
    prefix="/calendar",
    tags=["Calendar Actions", "area:scheduling"],
)
# Calendar Step 4.1 — PTR consent upgrade UI write-side per §3.26.16.6
# + §3.26.16.14 + §3.26.11.10 cross-tenant Focus consent precedent.
# Mounted at /calendar to match canonical endpoint paths
# /api/v1/calendar/consent + /api/v1/calendar/consent/{relationship_id}/...
v1_router.include_router(
    calendar_consent.router,
    prefix="/calendar",
    tags=["Calendar Consent", "area:scheduling"],
)
# Personalization Studio — Phase 1B canvas implementation.
# Canonical Generation Focus instance lifecycle + canvas commit endpoints
# per Phase 1A canonical-pattern-establisher service substrate +
# Phase 1B canvas commit boundary at canonical edit-finish per Phase A
# Session 3.8.3 canonical compositor pattern.
v1_router.include_router(
    personalization_studio.router,
    prefix="/personalization-studio",
    tags=["Personalization Studio", "area:personalization"],
)
# Personalization Studio family portal — Phase 1E.
# Magic-link contextual surface per §3.26.11.9 + Path B substrate +
# §2.5 Portal Extension Pattern. Public token-authenticated endpoints
# at /portal/{tenant_slug}/personalization-studio/family-approval/{token}.
# JWT realm "portal" guard at substrate (Anti-pattern 16): no JWT
# accepted; magic-link is sole authentication factor.
v1_router.include_router(
    personalization_studio_family_portal.router,
    prefix="/portal",
    tags=["Personalization Studio Family Portal", "area:settings"],
)
# Workshop primitive — Phase 1D template-type registration + per-tenant
# Tune mode customization. Per BRIDGEABLE_MASTER §3.26.14 Workshop
# primitive canon. Phase 1D registers burial_vault_personalization_studio;
# Step 2 + future Generation Focus templates extend the registry.
v1_router.include_router(
    workshop.router,
    prefix="/workshop",
    tags=["Workshop", "area:personalization"],
)
# NL Creation — Phase 4 of UI/UX Arc. Natural language creation w/ live overlay.
v1_router.include_router(
    nl_creation.router, prefix="/nl-creation", tags=["NL Creation"]
)
# Builder AI Assistant Phase 1a — backend workflow-authoring generation path
# (NL → validated canvas_state). UI review loop = Phase 1b.
v1_router.include_router(
    workflow_authoring.router,
    prefix="/workflow-authoring",
    tags=["Workflow Authoring"],
)

# JCF-1 — Job Coordination Focus (the assembly substrate; tenant realm).
v1_router.include_router(
    coordination_focus.router,
    prefix="/coordination-focus",
    tags=["Coordination Focus", "area:scheduling"],
)
# Tasks — Phase 5 (deferred from Phase 4). Generic task entity.
v1_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
# Triage — Phase 5 of UI/UX Arc. Platform layer for queue-based decision work.
v1_router.include_router(triage.router, prefix="/triage", tags=["Triage"])
# Peek — Follow-up 4 of UI/UX Arc (arc finale). Slim per-entity
# summaries for hover + click peek panels across 4 surfaces.
v1_router.include_router(peek.router, prefix="/peek", tags=["Peek"])
v1_router.include_router(ai_settings.router, prefix="/settings/ai", tags=["AI Settings", "area:settings"])
v1_router.include_router(
    ancillary_orders.router, prefix="/extensions/funeral-kanban", tags=["Ancillary Orders", "area:settings"]
)
v1_router.include_router(
    announcements.router, prefix="/announcements", tags=["Announcements"]
)
v1_router.include_router(
    driver_announcements.router, prefix="", tags=["Driver Announcements"]
)
v1_router.include_router(api_keys.router, prefix="/api-keys", tags=["API Keys", "area:settings"])
v1_router.include_router(ap.router, prefix="/ap", tags=["Accounts Payable", "area:accounting"])
v1_router.include_router(audit.router, prefix="/audit-logs", tags=["Audit Logs", "area:settings"])
v1_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
v1_router.include_router(
    billing.router, prefix="/billing", tags=["Billing", "area:accounting"]
)
v1_router.include_router(
    billing_groups.router, prefix="/billing-groups", tags=["Billing Groups", "area:accounting"]
)
v1_router.include_router(
    call_intelligence.router,
    prefix="/integrations/ringcentral",
    tags=["Call Intelligence", "area:settings"],
)
v1_router.include_router(note.router, prefix="/note", tags=["Note"])
v1_router.include_router(
    ringcentral.router,
    prefix="/integrations/ringcentral",
    tags=["Call Intelligence", "area:settings"],
)
v1_router.include_router(
    bom.router, prefix="/bom", tags=["Bill of Materials", "area:catalog"]
)
v1_router.include_router(
    briefings.router, prefix="/briefings", tags=["Morning Briefings"]
)
v1_router.include_router(
    focus_routes.router, prefix="/focus", tags=["Focus Primitive"]
)
v1_router.include_router(
    onboarding_touches.router,
    prefix="/onboarding-touches",
    tags=["Phase 7 Onboarding Touches", "area:settings"],
)
v1_router.include_router(
    operator_profile_routes.router,
    prefix="/operator-profile",
    tags=["Phase W-4a Operator Profile"],
)
# ⚠️ **THE `/pulse` PREFIX AND ITS TWO ROUTES WERE DELETED ON 2026-11-06.**
# Pulse itself was retired in bf2412df; these two endpoints kept answering
# under its dead prefix and the mount comment here already said "the prefix is
# now a misnomer and a rename is owed".
#
# They were NOT pulse: they lived in `customer_composition_sources.py` and
# returned a CUSTOMER's email threads and calendar events. Nothing called them
# — no frontend, no scheduled job — so James ruled deletion over re-homing.
#
# ⚠️ Unlike the SSRF diagnostic deleted the same day, this was authenticated,
# tested and working machinery; its only fault was having no consumer. The
# SERVICES survive (`customer_email_threads_service`,
# `customer_calendar_events_service` use each other), so if a composition
# surface ever wants this data, a route under `/customers` tagged
# `area:customers` is a small addition rather than a rebuild.
v1_router.include_router(
    bundles.router, prefix="/products", tags=["Product Bundles", "area:catalog"]
)
v1_router.include_router(
    carrier_portal.router, prefix="/carrier", tags=["Carrier Portal", "area:scheduling"]
)
v1_router.include_router(
    cases.router, prefix="/cases", tags=["Funeral Home Cases", "area:cases"]
)
v1_router.include_router(
    cemeteries.router, prefix="/cemeteries", tags=["Cemeteries", "area:customers"]
)
v1_router.include_router(
    disinterments.router, prefix="/disinterments", tags=["Disinterments", "area:cases"]
)
v1_router.include_router(
    disinterment_charge_types.router,
    prefix="/disinterment-charge-types",
    tags=["Disinterment Charge Types", "area:pricing"],
)
v1_router.include_router(
    docusign_webhook.router, prefix="/docusign", tags=["DocuSign", "area:documents"]
)
v1_router.include_router(
    intake.router, prefix="/intake", tags=["Public Intake", "area:documents"]
)
v1_router.include_router(
    intake_adapters.router,
    prefix="/intake-adapters",
    tags=["Intake Adapters", "area:documents"],
)
v1_router.include_router(
    union_rotations.router, prefix="/union-rotations", tags=["Union Rotations", "area:scheduling"]
)
v1_router.include_router(
    charge_library.router, prefix="/charge-library", tags=["Charge Library", "area:pricing"]
)
v1_router.include_router(
    charge_terms.router, prefix="/onboarding/charge-terms", tags=["Charge Terms", "area:settings"]
)
# companies.router MUST come before company_entities.router — both share
# the /companies prefix and company_entities has /{entity_id} catch-all
# that would swallow /settings, /tenant-settings, etc.
v1_router.include_router(
    companies.router, prefix="/companies", tags=["Company Management", "area:settings"]
)
v1_router.include_router(
    company_entities.router, prefix="/companies", tags=["Company Entities", "area:settings"]
)
v1_router.include_router(
    configurable_items.router, prefix="/configurable", tags=["Configurable Items", "area:catalog"]
)
v1_router.include_router(
    product_lines.router, prefix="/product-lines", tags=["Product Lines", "area:catalog"]
)
v1_router.include_router(
    core.router, prefix="/core", tags=["Core UI"]
)
v1_router.include_router(
    customers.router, prefix="/customers", tags=["Customers", "area:customers"]
)
v1_router.include_router(
    deliveries.router, prefix="/delivery", tags=["Delivery & Dispatch", "area:scheduling"]
)
# Phase B Session 1 — dispatch schedule state machine + hole-dug.
v1_router.include_router(
    dispatch.router, prefix="/dispatch", tags=["Dispatch", "area:scheduling"]
)
v1_router.include_router(
    discount.router, prefix="/discount", tags=["Early Payment Discount", "area:pricing"]
)
v1_router.include_router(
    finance_charges.router, prefix="/finance-charges", tags=["Finance Charges", "area:accounting"]
)
v1_router.include_router(
    behavioral_analytics.router, prefix="/behavioral", tags=["Behavioral Analytics"]
)
v1_router.include_router(
    data_import.router, prefix="/data-import", tags=["Data Import", "area:settings"]
)
v1_router.include_router(
    delivery_portal.router, prefix="/portal", tags=["Delivery Portal", "area:settings"]
)
v1_router.include_router(
    direct_ship.router, prefix="/extensions/funeral-kanban", tags=["Direct Ship", "area:settings"]
)
v1_router.include_router(
    delivery_settings.router, prefix="/settings", tags=["Delivery Settings", "area:settings"]
)
v1_router.include_router(
    delivery_types.router, prefix="/delivery-types", tags=["Delivery Types", "area:scheduling"]
)
v1_router.include_router(
    departments.router, prefix="/departments", tags=["Departments", "area:settings"]
)
v1_router.include_router(
    documents.router, prefix="/documents", tags=["Documents", "area:documents"]
)
# Phase D-1 — canonical Documents layer (admin-gated, tenant-scoped).
# Legacy /documents/* remains above for the old Document model callers.
v1_router.include_router(
    documents_v2.router, prefix="/documents-v2", tags=["Documents (canonical)", "area:documents"]
)
# Phase D-4 native signing
v1_router.include_router(
    signing_public.router, prefix="/sign", tags=["Signing (public)", "area:documents"]
)
v1_router.include_router(
    signing_admin.router, prefix="/admin/signing", tags=["Signing (admin)", "area:settings"]
)
v1_router.include_router(
    driver_mobile.router, prefix="/driver", tags=["Driver Mobile", "area:scheduling"]
)
v1_router.include_router(
    employee_profiles.router,
    prefix="/employee-profiles",
    tags=["Employee Profiles", "area:people"],
)
v1_router.include_router(
    equipment.router, prefix="/equipment", tags=["Equipment", "area:production"]
)
v1_router.include_router(
    extensions.router, prefix="/extensions", tags=["Extension Catalog", "area:settings"]
)
v1_router.include_router(
    feature_flags.router, prefix="/feature-flags", tags=["Feature Flags", "area:settings"]
)
v1_router.include_router(
    functional_areas.router, prefix="/team", tags=["Functional Areas", "area:settings"]
)
v1_router.include_router(
    fh_portal.router, prefix="/portal/family", tags=["Family Portal", "area:settings"]
)
v1_router.include_router(
    fh_price_list.router, prefix="/price-list", tags=["Funeral Home Price List", "area:pricing"]
)
v1_router.include_router(
    ftc_compliance.router, prefix="/ftc", tags=["FTC Compliance", "area:accounting"]
)
v1_router.include_router(
    cemetery_directory.router,
    prefix="/onboarding/cemeteries",
    tags=["Cemetery Directory", "area:settings"],
)
v1_router.include_router(
    funeral_home_directory.router,
    prefix="/onboarding/customers",
    tags=["Funeral Home Directory", "area:settings"],
)
v1_router.include_router(
    funeral_kanban.router, prefix="/extensions/funeral-kanban", tags=["Funeral Kanban", "area:settings"]
)
v1_router.include_router(
    hierarchy.router, prefix="/hierarchy", tags=["Org Hierarchy", "area:customers"]
)
v1_router.include_router(
    historical_order_import.router,
    prefix="/historical-orders",
    tags=["Historical Order Import", "area:orders"],
)
v1_router.include_router(
    internal.router, prefix="/internal", tags=["Internal", "area:settings"]
)
v1_router.include_router(
    inventory.router, prefix="/inventory", tags=["Inventory", "area:inventory"]
)
v1_router.include_router(
    job_queue.router, prefix="/jobs", tags=["Job Queue", "area:production"]
)
v1_router.include_router(modules.router, prefix="/modules", tags=["Modules", "area:settings"])
v1_router.include_router(
    migration.router, prefix="/migration", tags=["Data Migration", "area:settings"]
)
v1_router.include_router(
    network.router, prefix="/network", tags=["Network", "area:settings"]
)
v1_router.include_router(
    notifications.router, prefix="/notifications", tags=["Notifications"]
)
v1_router.include_router(
    onboarding.router, prefix="/onboarding", tags=["Onboarding", "area:settings"]
)
v1_router.include_router(
    onboarding_flow.router, prefix="/onboarding-flow", tags=["Onboarding Flow", "area:settings"]
)
v1_router.include_router(
    agents.router,
    prefix="/agents",
    tags=["Agents", "area:accounting"],
)
v1_router.include_router(
    proactive_agents.router,
    prefix="/proactive-agents",
    tags=["Proactive Agents", "area:accounting"],
)
v1_router.include_router(
    report_intelligence.router,
    prefix="/report-intelligence",
    tags=["Report Intelligence"],
)
v1_router.include_router(
    network_intelligence.router,
    prefix="/network",
    tags=["Network Intelligence", "area:settings"],
)
v1_router.include_router(
    delivery_intelligence.router,
    prefix="/delivery",
    tags=["Delivery Intelligence", "area:scheduling"],
)
v1_router.include_router(
    training_routes.router,
    prefix="/training",
    tags=["Employee Training", "area:safety"],
)
v1_router.include_router(
    financial_health.router,
    prefix="/health",
    tags=["Financial Health"],
)
v1_router.include_router(
    financials_board.router,
    prefix="/financials",
    tags=["Financials Board", "area:accounting"],
)
v1_router.include_router(
    journal_entries.router,
    prefix="/journal-entries",
    tags=["Journal Entries", "area:accounting"],
)
v1_router.include_router(
    knowledge_base.router,
    prefix="/knowledge-base",
    tags=["Knowledge Base"],
)
v1_router.include_router(
    locations.router,
    prefix="/locations",
    tags=["Locations", "area:settings"],
)
v1_router.include_router(
    price_management.router,
    prefix="/price-management",
    tags=["Price Management", "area:pricing"],
)
v1_router.include_router(
    operations_board.router,
    prefix="/operations-board",
    tags=["Operations Board"],
)
v1_router.include_router(
    programs.router, prefix="/programs", tags=["Programs", "area:personalization"]
)
v1_router.include_router(
    purchasing.router,
    prefix="/purchasing",
    tags=["Purchasing", "area:accounting"],
)
v1_router.include_router(
    reconciliation.router,
    prefix="/reconciliation",
    tags=["Reconciliation", "area:accounting"],
)
v1_router.include_router(
    tax.router,
    prefix="/tax",
    tags=["Tax", "area:accounting"],
)
v1_router.include_router(
    inter_licensee_pricing.router,
    prefix="/inter-licensee-pricing",
    tags=["Inter-Licensee Pricing", "area:pricing"],
)
v1_router.include_router(
    transfers.router,
    prefix="/transfers",
    tags=["Licensee Transfers", "area:inventory"],
)
v1_router.include_router(
    reports.router,
    prefix="/reports",
    tags=["Reports"],
)
v1_router.include_router(
    order_station.router,
    prefix="/order-station",
    tags=["Order Entry Station", "area:orders"],
)
v1_router.include_router(
    template_seasons.router,
    prefix="/template-seasons",
    tags=["Template Seasons", "area:catalog"],
)
v1_router.include_router(
    performance_notes.router,
    prefix="/performance-notes",
    tags=["Performance Notes", "area:people"],
)
v1_router.include_router(
    platform_fees.router, prefix="/platform-fees", tags=["Platform Fees", "area:accounting"]
)
v1_router.include_router(
    price_list_import.router, prefix="/catalog", tags=["Price List Import", "area:catalog"]
)
v1_router.include_router(
    production_log.router, prefix="/production", tags=["Production Log", "area:production"]
)
v1_router.include_router(
    spring_burials.router, tags=["Spring Burials", "area:orders"]
)
v1_router.include_router(
    catalog_builder.router, tags=["Catalog Builder", "area:catalog"]
)
v1_router.include_router(
    products.router, prefix="/products", tags=["Products", "area:catalog"]
)
v1_router.include_router(
    urn_catalog.router, prefix="/products", tags=["Urn Catalog", "area:catalog"]
)
v1_router.include_router(
    urn_sales.router, prefix="/urns", tags=["Urn Sales", "area:resale"]
)
v1_router.include_router(
    projects.router, prefix="/projects", tags=["Project Management", "area:orders"]
)
v1_router.include_router(
    purchase_orders.router, prefix="/purchase-orders", tags=["Purchase Orders", "area:accounting"]
)
v1_router.include_router(
    qc.router, prefix="/qc", tags=["Quality Control", "area:production"]
)
v1_router.include_router(
    safety_program_generation.router,
    prefix="/safety/programs",
    tags=["Safety Program Generation", "area:safety"],
)
v1_router.include_router(
    safety.router, prefix="/safety", tags=["Safety Management", "area:safety"]
)
v1_router.include_router(
    safety_training_system.router,
    prefix="/safety",
    tags=["Safety Training System", "area:safety"],
)
v1_router.include_router(
    statements.router, prefix="/statements", tags=["Statements", "area:accounting"]
)
v1_router.include_router(roles.router, prefix="/roles", tags=["Role Management", "area:settings"])
v1_router.include_router(
    permissions.router, prefix="/permissions", tags=["Permission Management", "area:settings"]
)
v1_router.include_router(
    sage_exports.router, prefix="/sage-exports", tags=["Sage Exports", "area:accounting"]
)
v1_router.include_router(
    service_territory.router, prefix="/settings", tags=["Service Territory", "area:settings"]
)
v1_router.include_router(
    sales.router, prefix="/sales", tags=["Sales & AR", "area:orders"]
)
v1_router.include_router(
    social_service_certificates.router,
    prefix="/social-service-certificates",
    tags=["Social Service Certificates", "area:cases"],
)
v1_router.include_router(
    super_admin.router, prefix="/super-admin", tags=["Super Admin", "area:settings"]
)
v1_router.include_router(
    sync_logs.router, prefix="/sync-logs", tags=["Sync Logs", "area:settings"]
)
v1_router.include_router(
    tenant_onboarding.router,
    prefix="/tenant-onboarding",
    tags=["Tenant Onboarding", "area:settings"],
)
v1_router.include_router(
    tenant_onboarding_admin.router,
    prefix="/admin/tenant-onboarding",
    tags=["Tenant Onboarding Admin", "area:settings"],
)
v1_router.include_router(
    unified_import.router,
    prefix="/onboarding/import",
    tags=["Unified Import", "area:settings"],
)
v1_router.include_router(users.router, prefix="/users", tags=["User Management", "area:settings"])
# ⚠️ PUBLIC BY DESIGN — she has no credential yet. Not area-tagged, because
# `enforce_area_limit` returns early for an unauthenticated caller and these two
# routes are reached by exactly that caller. What gates them is the 256-bit
# single-use token, not a permission. See app/api/routes/invites.py.
v1_router.include_router(invites.router, prefix="/invites", tags=["Invites", "area:settings"])
v1_router.include_router(
    vendor_bills.router, prefix="/vendor-bills", tags=["Vendor Bills", "area:accounting"]
)
v1_router.include_router(
    vendor_payments.router, prefix="/vendor-payments", tags=["Vendor Payments", "area:accounting"]
)
v1_router.include_router(vendors.router, prefix="/vendors", tags=["Vendors", "area:accounting"])
v1_router.include_router(
    website_intelligence.router, tags=["Website Intelligence", "area:settings"]
)
v1_router.include_router(
    legacy.router, prefix="/legacy", tags=["Legacy", "area:personalization"]
)
v1_router.include_router(
    legacy_delivery.router, prefix="/legacy", tags=["Legacy Delivery", "area:settings"]
)
v1_router.include_router(
    legacy_email.router, prefix="/legacy", tags=["Legacy Email", "area:settings"]
)
v1_router.include_router(
    legacy_studio.router, prefix="/legacy-studio", tags=["Legacy Studio", "area:personalization"]
)
v1_router.include_router(
    personalization.router, prefix="/personalization", tags=["Personalization", "area:personalization"]
)
v1_router.include_router(
    training_lifecycle.router, prefix="/training", tags=["Training", "area:safety"]
)
v1_router.include_router(
    webhooks.router, prefix="/webhooks", tags=["Webhooks", "area:settings"]
)
v1_router.include_router(
    vault.router, prefix="/vault", tags=["Vault"]
)
# CR-2 A-3: the completeness review + the nil-claim pattern.
v1_router.include_router(
    completeness.router,
    prefix="/completeness",
    tags=["Completeness"],
)

# Two-step sign-in. Tagged `area:mfa_enroll` so a user who owes a second step
# can reach exactly these endpoints and nothing else — the confinement is the
# area guard's, not a second mechanism. See app/api/routes/two_step.py.
v1_router.include_router(
    two_step.router,
    prefix="/two-step",
    tags=["Two-Step Sign-In", "area:mfa_enroll"],
)

# Weekly payroll dues reports (accountant/admin). Reporting only — does not run
# payroll and does not touch the planned Check integration.
v1_router.include_router(
    payroll_reports.router,
    prefix="/payroll-reports",
    # `area:payroll` is what an area-limited payroll role is allowed to reach.
    # Declared here, at the router registration layer, so it cannot drift from
    # the routes it describes. See app/core/areas.py.
    tags=["Payroll Reports", "area:payroll"],
)

# V-1e: Accounting admin sub-tree under /vault/accounting/*
v1_router.include_router(
    vault_accounting.router,
    prefix="/vault/accounting",
    tags=["Vault / Accounting Admin"],
)
v1_router.include_router(
    vault_molds.router, prefix="/vault-molds", tags=["Vault Molds", "area:production"]
)
v1_router.include_router(
    vault_supplier.router, prefix="/vault-supplier", tags=["Vault Supplier", "area:customers"]
)
v1_router.include_router(
    widget_definitions.router,
    prefix="/widget-definitions",
    tags=["Widget Builder"],
)
v1_router.include_router(
    widgets.router, prefix="/widgets", tags=["Widget Framework"]
)
v1_router.include_router(
    widget_data.router, prefix="/widget-data", tags=["Widget Data"]
)
v1_router.include_router(
    work_orders.router, prefix="/work-orders", tags=["Work Orders", "area:orders"]
)

# Funeral Home vertical (FH-1a + FH-1b)
v1_router.include_router(
    fh_cases.router, prefix="/fh/cases", tags=["FH Cases", "area:customers"]
)
v1_router.include_router(
    fh_cemetery.router, prefix="/fh/cemetery", tags=["FH Cemetery", "area:customers"]
)
v1_router.include_router(
    fh_network.router, prefix="/fh/network", tags=["FH Network", "area:customers"]
)
v1_router.include_router(
    fh_monument.router, prefix="/fh/monument", tags=["FH Monument", "area:customers"]
)

# Workflow Engine (Phase W-1)
v1_router.include_router(
    workflow_routes.router, prefix="/workflows", tags=["Workflows"]
)

# Email Classification cascade (Phase R-6.1a)
v1_router.include_router(
    email_classification_routes.router,
    prefix="/email-classification",
    tags=["Email Classification", "area:documents"],
)

# Saved Orders (Compose Templates)
v1_router.include_router(
    saved_orders_routes.router, prefix="/saved-orders", tags=["Saved Orders", "area:orders"]
)

# External Accounts (Playwright workflow credentials)
v1_router.include_router(
    external_accounts_routes.router, prefix="/external-accounts", tags=["External Accounts", "area:accounting"]
)

# Vault Documents (Phase W-2 — native document layer on R2)
v1_router.include_router(
    vault_documents_routes.router, prefix="/vault-documents", tags=["Vault Documents", "area:documents"]
)

# Bridgeable Intelligence — unified AI layer (Phase 1 backbone)
v1_router.include_router(
    intelligence_routes.router, prefix="/intelligence", tags=["Intelligence"]
)

# The Bridgeable Map — tenant MoC surface (Tenant Ponder-Editor P2)
from app.api.routes import moc_tenant as moc_tenant_routes  # noqa: E402

v1_router.include_router(
    moc_tenant_routes.router, prefix="/moc", tags=["Bridgeable Map", "area:cases"]
)

from app.api.routes import plaid as plaid_routes  # noqa: E402

v1_router.include_router(
    plaid_routes.router, prefix="/plaid", tags=["Plaid", "area:accounting"]
)

# Opas Product List + Product panes — platform-catalog reads (2026-10-06)
from app.api.routes import catalog_pane as catalog_pane_routes  # noqa: E402

v1_router.include_router(
    catalog_pane_routes.router, prefix="/catalog-pane", tags=["Opas Catalog Pane", "area:personalization"]
)

# ⚠️ THE FIRST ENDPOINTS THAT RETURN `CaptureState`. Registered the same way the catalog
# pane is — at the bottom, with its own prefix — so the typed pane and the catalog panes
# sit side by side rather than one being folded into an unrelated router.
from app.api.routes import capture as capture_routes  # noqa: E402

v1_router.include_router(
    capture_routes.router, prefix="/capture", tags=["Opas Typed Capture", "area:documents"]
)

# Opas Order List + shortened sales order. Same mount style as the catalog pane:
# its own prefix, read off the caller's company, no shared router edited above.
from app.api.routes import order_list_pane as order_list_pane_routes  # noqa: E402

v1_router.include_router(
    order_list_pane_routes.router, prefix="/order-list", tags=["Opas Order List", "area:orders"]
)
