# CLAUDE.md — Bridgeable Platform

## 1. Project Overview

**Bridgeable** (getbridgeable.com) is a multi-tenant SaaS business management platform for the death care industry, specifically Wilbert burial vault licensees and their connected funeral homes. The platform manages the full operational lifecycle: funeral order processing, delivery scheduling, inventory, AR/AP, monthly billing, cross-licensee transfers, safety compliance, and financial reporting.

**Company context:**
- **Sunnycrest Precast** — first customer and development partner (vault manufacturer in Auburn, NY); live at `sunnycrest.getbridgeable.com`
- **Able Holdings** — holding company that owns the Bridgeable platform
- **Wilbert** — national franchise network of ~200 burial vault licensees. Bridgeable targets this network as its primary market.
- **Strategic goal:** Demo at the September 2026 Wilbert licensee meeting. Multi-vertical SaaS expansion planned beyond death care.

**4 tenant presets:** `manufacturing` (primary, most features), `funeral_home`, `cemetery`, `crematory`

## 1a. Core UX Philosophy — "Monitor through hubs. Act through the command bar."

**This is the foundational design principle of Bridgeable. Every feature decision must be evaluated against it.**

### The Two Modes

**MODE 1 — MONITORING (Hub Dashboards)**

Monitoring is passive awareness. The platform surfaces what matters without being asked.

- Information comes to the user — they do not hunt for it
- Hub dashboards are role-aware: admins see team metrics, directors see their cases, drivers see their deliveries
- Morning briefing, operations board, compliance hub, case dashboard — all monitoring surfaces
- Widgets are the unit of monitoring
- A user scanning their hub should know everything they need to know for their day without clicking anything

**MODE 2 — ACTING (Command Bar)**

Acting is intent-driven execution. The user states what they want in natural language. The platform executes or guides — never requires navigation.

- The command bar (Cmd+K) is the PRIMARY way to do anything
- Natural language input replaces forms wherever possible
- Workflows execute inline — the user never leaves their context
- The platform detects intent, extracts structured data, and populates records automatically
- The UI (pages, forms, nav) exists as a BACKUP, not the default
- A user should be able to complete 90% of their work without navigating to any page

### The Decision Framework for Every New Feature

When designing any new feature, ask these two questions:

**Question 1: Does the user need to NOTICE this without asking?**
- If yes → it belongs in a hub dashboard widget
- It should surface automatically based on role
- The user should see it when they open their hub
- Example: "3 compliance items due this week" → Widget on the manufacturing hub dashboard

**Question 2: Does the user DO this when they have an intent?**
- If yes → it belongs in the command bar as a workflow
- A UI page for it may exist but is not the primary path
- The command bar entry point is designed first
- The page is the fallback for complex cases
- Example: "Create a vault order for Hopkins" → Command bar workflow with natural language overlay → UI order form exists but is the backup

**If a feature is both (needs monitoring AND action):**
- Put a summary widget on the hub
- The widget has a quick-action button
- The button triggers the command bar workflow or navigates to the relevant page
- Example: "3 overdue compliance items [Review →]" → Widget surfaces the problem (monitoring) → [Review →] takes action (acting)

### What This Means in Practice

**A feature is INCOMPLETE if:**
- It can only be accessed by navigating to a page
- It has no command bar workflow or hub widget entry point
- A user needs to know WHERE to go to do it
- It requires filling out a traditional form when natural language could collect the same data

**A feature is COMPLETE if:**
- Monitoring aspects surface in the appropriate hub
- Action aspects are accessible from the command bar
- Natural language handles multi-field data entry
- The UI page exists for deep editing / complex cases but is not required for the primary use case

**The Scribe is the model:**
- Director has a conversation (natural input)
- Platform extracts structured data (intelligent processing)
- Director reviews and confirms (not re-enters)
- The form exists for corrections, not primary entry

**The command bar is the model:**
- User states intent in natural language
- Platform identifies workflow, extracts fields in real time
- Fields populate below as user types
- User confirms, not re-enters
- Slide-over opens for any remaining detail

### Specific Rules for Claude When Planning or Building

1. **Never design a feature as form-only.** Every feature that collects user input must have a command bar workflow with natural language extraction as the primary entry point. The form is secondary.

2. **Never design a monitoring feature as page-only.** Every metric, status, or alert that users need to notice must have a hub widget representation. A page for detail is fine. A page as the only surface is not.

3. **When recommending a new feature, always specify:**
   - Which hub(s) get a widget for this feature
   - What the command bar workflow looks like
   - What natural language inputs it accepts
   - What the UI backup page looks like
   If you cannot specify all four, the feature is not fully designed.

4. **When writing a build prompt, always include:**
   - The hub widget if the feature has a monitoring aspect
   - The command bar workflow registration if it has an action aspect
   - The overlay config (natural language vs. form)
   - The UI page as the backup path

5. **Result suppression in the command bar:**
   - Question queries → answers and records only, no nav
   - Action queries → workflows only, no duplicate actions
   - If a workflow covers an intent, suppress the action
   - Nav results only when no better result exists

6. **Workflow philosophy:**
   - One workflow per intent, not one per record type
   - Universal workflows that adapt via natural language are better than multiple specialized workflows
   - "Create Order" handles all order types through product type detection — not separate vault/disinterment/Redi-Rock workflows
   - When a new product line is added, it extends existing workflows, not creates new ones

### Why This Matters for September

The Wilbert demo works because of this philosophy:
- A manufacturer opens the command bar and creates a vault order by typing one sentence
- A funeral director types a sentence and a case populates
- A director types "what is our price for a monticello" and gets the answer immediately
- Nobody navigates to a form

That is the demo. That is the product. Navigation-first software cannot do this. Form-first software cannot do this. This philosophy is what makes Bridgeable different.

## 2. Technical Stack

### Backend
| Component | Version |
|-----------|---------|
| Python | 3.13+ |
| FastAPI | 0.115.6 |
| SQLAlchemy | 2.0.36 (sync, not async) |
| Alembic | 1.14.1 |
| Pydantic | 2.10.4 |
| APScheduler | >=3.10.0 |
| Anthropic SDK | >=0.42.0 |
| PostgreSQL | 16 |
| PyMuPDF (fitz) | >=1.24 |
| httpx | >=0.27 |
| BeautifulSoup4 | >=4.12 |
| Uvicorn | 0.34.0 |

### Frontend
| Component | Version |
|-----------|---------|
| React | 19.2 |
| Vite | 7.3 |
| TypeScript | 5.9 |
| Tailwind CSS | 4.2 (v4 — uses `@base-ui/react`, no `asChild`) |
| shadcn/ui | 4.0 |
| React Router | 7.13 |
| Axios | 1.13 |
| Lucide React | 0.577 |

### Infrastructure
- **Hosting:** Railway (backend + frontend as separate services)
- **DNS/SSL:** Cloudflare
- **Database:** PostgreSQL on Railway (production), local PostgreSQL 16 (`bridgeable_dev`)
- **File storage:** Railway persistent volume
- **No query library** — data fetching is plain Axios via `frontend/src/lib/api-client.ts`

### Third-Party Integrations
- **Claude API** (Anthropic) — AI briefings, content generation, collections drafts, product extraction, COA analysis
- **Google Places API** — funeral home discovery, cemetery geocoding
- **QuickBooks Online** — OAuth accounting sync (`backend/app/services/accounting/`)
- **Sage 100** — CSV export accounting sync
- **Twilio** — SMS delivery confirmations
- **Stripe** — payment processing (configured, not fully wired)

## 3. Design Philosophy

All new features and flows should adhere to these guiding principles:

### Hub-Based Organization
The platform is organized around **hubs** — central data repositories (CRM, Orders, Inventory, AR/AP, Knowledge Base, etc.) that serve as the single source of truth. Every feature should read from and write to these hubs rather than maintaining isolated data stores. Cross-feature visibility comes naturally when data lives in the right hub.

### Widget-Based Dashboards
Dashboards (Operations Board, Financials Board, Morning Briefing) are composed of **widgets** that pull data from hubs. Features contribute to dashboards via the registry pattern (`BoardContributor`), not by embedding dashboard logic in feature code. This keeps dashboards composable and extensible.

### Agent Actions with Human Review
The primary workflow pattern is: **agent performs analysis/action → human reviews and approves**. This applies to:
- Accounting agents (month-end close, collections, categorization) — agent runs, human approves via token-based email
- Call Intelligence — AI extracts order data from calls, human confirms before saving
- Catalog ingestion — parser extracts products, human reviews pricing before publishing
- Certificate generation — system auto-generates on delivery, human approves before sending

Whenever possible, build the automated path first, then add the human review gate. The goal is to minimize manual data entry while maintaining human oversight for consequential actions.

### Playwright + Claude API Testing Framework
All features should be built with the existing **Playwright E2E + Claude API** testing framework in mind. Every new endpoint and UI flow should be testable against the staging environment (`sunnycresterp-staging.up.railway.app`). Tests authenticate via the staging API, exercise real backend logic, and verify end-to-end behavior.

## 4. Architecture

### Multi-Tenant SaaS
- Tenants are `companies` records. All tenant-scoped tables have a `company_id` or `tenant_id` FK.
- Subdomain routing: `{slug}.getbridgeable.com` → tenant app, `admin.getbridgeable.com` → platform admin
- `isPlatformAdmin()` in `frontend/src/lib/platform.ts` detects `admin.*` subdomain
- Tenant isolation is enforced at the service layer — all queries filter by `company_id`

### OperationsBoardRegistry Pattern
Singleton registry (`frontend/src/services/operations-board-registry.ts`) where features register as `BoardContributor` objects. Core features register as permanent contributors (`requires_extension: null`). Extensions register with their extension key and only render when active. Same pattern used for `FinancialsBoardRegistry`.

### AI Patterns
- **AIService** (`backend/app/services/ai_service.py`): Single `call_anthropic()` function, uses `claude-sonnet-4-20250514` by default. Forces JSON-only responses.
- **AICommandBar**: Frontend component for natural language input on various pages
- **ConfirmationCard**: Shows AI-extracted data for human review before saving
- **Briefing Service**: Uses `claude-haiku-4-5-20250514` for cost-effective daily briefings
- **Accounting Analysis**: Uses `claude-haiku-4-5-20250514` for COA classification (confidence threshold 0.85 for auto-approve)

### Extension System
Extensions (Wastewater, Redi-Rock, Rosetta, NPCA Audit Prep, Urn Sales) are tracked in `tenant_extensions`. When enabled, they register contributors to the Operations Board registry, add navigation items, and unlock features. Core modules are always available; extensions are per-tenant opt-in.

**Urn Sales:** `urn_sales` extension — full urn product catalog, order lifecycle (stocked + drop-ship), two-gate engraving proof approval, Wilbert catalog ingestion pipeline (PDF auto-fetch + web enrichment), pricing tools. All routes gated by `require_extension("urn_sales")`. 6 tables, 42+ API endpoints, 39 E2E tests.

**NPCA:** `npca_audit_prep` is a proper extension. All dashboard elements and nav items are gated by `hasModule("npca_audit_prep")`. Auto-enables when `npca_certification_status = "certified"` is set during platform admin tenant setup.

### Settings Pattern
Tenant settings are stored as a JSONB field on the `companies` table (`settings_json` column), accessed via `company.settings` property and `company.set_setting(key, value)` method. A `tenant_settings` database table also exists (migrations create it) but is orphaned — application code uses `Company.settings_json` exclusively.

## 5. Database

- **~235 tables** (ORM models for all but the orphaned `tenant_settings` table)
- **Current migration head:** `r14_urn_catalog_pdf_fetch`
- **116 migration files** in `backend/alembic/versions/`
- **Single root:** `e1e2120b6b65` (create_users_table)

### Running Migrations Locally
```bash
cd backend && source .venv/bin/activate
DATABASE_URL=postgresql://localhost:5432/bridgeable_dev alembic upgrade head
```

### Idempotent Migrations
`backend/alembic/env.py` monkey-patches `op.add_column`, `op.create_table`, and `op.create_index` to be idempotent. This allows the same migration chain to run on both fresh databases and databases where tables were created outside migrations.

### Table Name Conventions
These are the **correct** table names (corrected from old incorrect names):
- Customer payments: `customer_payments` (not `payments`)
- Sales orders: `sales_orders` (not `orders`)
- Vendor bills: `vendor_bills` (not `bills`)
- Customer payment applications: `customer_payment_applications`

### Key Schema Patterns
- All IDs are `String(36)` UUIDs generated with `uuid.uuid4()`
- Timestamps use `DateTime(timezone=True)` with `default=lambda: datetime.now(timezone.utc)`
- Soft deletes via `is_active` boolean (not physical deletion)
- JSONB used extensively for flexible fields (settings, config, metadata)
- `company_id` or `tenant_id` FK on all tenant-scoped tables

## 6. Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app, middleware, startup/shutdown
│   ├── config.py            # pydantic-settings, reads .env
│   ├── database.py          # SQLAlchemy engine + SessionLocal
│   ├── scheduler.py         # APScheduler — 13 registered jobs + JOB_REGISTRY
│   ├── worker.py            # Background job queue worker (polls DB/Redis)
│   ├── models/              # 157 model files, 170 exports in __init__.py
│   ├── services/            # 109 service files (business logic)
│   │   ├── ai_service.py            # Claude API wrapper
│   │   ├── agent_service.py         # AR/AP/Collections agents
│   │   ├── proactive_agents.py      # 6 proactive agent functions
│   │   ├── briefing_service.py
│   │   ├── onboarding_service.py    # MANUFACTURING_CHECKLIST_ITEMS
│   │   ├── accounting_analysis_service.py  # COA AI analysis (Haiku)
│   │   ├── accounting/              # QBO + Sage providers
│   │   ├── urn_product_service.py   # Urn CRUD + AI search
│   │   ├── urn_order_service.py     # Urn order lifecycle + scheduling feeds
│   │   ├── urn_engraving_service.py # Two-gate proof approval, Wilbert form PDF
│   │   ├── wilbert_pdf_parser.py    # PyMuPDF catalog parser (259 SKUs)
│   │   ├── wilbert_ingestion_service.py  # PDF→upsert→web enrich orchestrator
│   │   ├── urn_catalog_scraper.py   # Wilbert.com web scraper
│   │   ├── wilbert_scraper_config.py # CSS selectors + category URLs
│   │   └── ...
│   ├── api/
│   │   ├── v1.py            # Route aggregator (94+ modules registered)
│   │   ├── deps.py          # Auth dependencies (get_current_user, require_admin)
│   │   ├── routes/          # 104 route files, 945+ total endpoints
│   │   └── platform.py      # Platform admin routes
│   ├── core/
│   │   └── security.py      # JWT + bcrypt utilities
│   └── jobs/
│       └── __init__.py      # Job handler registry
├── alembic/
│   ├── env.py               # Idempotent op wrappers
│   └── versions/            # 114 migration files
├── data/
│   ├── us-county-tax-rates.json
│   └── us-zip-county-mapping.json
├── static/safety-templates/ # Generated safety training PDFs
├── .env                     # LOCAL only — points to bridgeable_dev
└── .env.example             # All env vars documented

frontend/
├── src/
│   ├── App.tsx              # 150+ route definitions, platform admin detection
│   ├── contexts/
│   │   └── auth-context.tsx # JWT auth state, token refresh
│   ├── lib/
│   │   ├── api-client.ts    # Axios with token refresh interceptor
│   │   ├── platform.ts      # isPlatformAdmin(), platform mode
│   │   ├── tenant.ts        # getCompanySlug(), subdomain routing
│   │   └── utils.ts         # cn() for tailwind class merging
│   ├── components/
│   │   ├── ui/              # shadcn/ui v4 components
│   │   ├── dashboard/       # ManufacturingDashboard, SpringBurialWidget, etc.
│   │   ├── morning-briefing-card.tsx
│   │   ├── contextual-explanation.tsx
│   │   ├── confirmation-card.tsx
│   │   └── protected-route.tsx
│   ├── pages/               # Page components organized by feature
│   │   ├── urns/
│   │   │   ├── urn-catalog.tsx      # Product catalog + pricing + sync
│   │   │   ├── urn-orders.tsx       # Order dashboard + status filters
│   │   │   ├── urn-order-form.tsx   # Create/edit order
│   │   │   └── proof-approval.tsx   # Public FH proof approval (token)
│   │   └── compliance/
│   │       └── npca-audit-prep.tsx  # Placeholder — feature not yet built
│   ├── services/
│   │   ├── navigation-service.ts        # Preset-driven nav
│   │   ├── operations-board-registry.ts # Board contributor registry
│   │   └── board-contributors/index.ts  # Core contributor registrations
│   └── types/
│       └── operations-board.ts
├── Dockerfile               # Node build → nginx, port 8080
│                            # Accepts VITE_APP_DOMAIN build arg (default: getbridgeable.com)
├── nginx.conf
└── package.json
```

## 7. Environment Setup

### Local Development
```bash
# Prerequisites: PostgreSQL 16, Python 3.13+, Node 22+
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"

# Database
createdb bridgeable_dev

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DATABASE_URL=postgresql://localhost:5432/bridgeable_dev alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

### Backend Environment Variables
All defined in `backend/app/config.py` via pydantic-settings. Copy `backend/.env.example` to `backend/.env`.

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `DATABASE_URL` | ✅ | — | PostgreSQL connection string |
| `SECRET_KEY` | ✅ | — | JWT signing key |
| `ALGORITHM` | — | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | — | `30` | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | — | `7` | Refresh token TTL |
| `CONSOLE_TOKEN_EXPIRE_MINUTES` | — | `480` | Production/delivery terminal TTL |
| `CORS_ORIGINS` | — | `["http://localhost:5173"]` | Allowed CORS origins (JSON array) |
| `CORS_ORIGIN_REGEX` | — | `""` | Regex for wildcard CORS (`.*getbridgeable\\.com` in prod) |
| `ENVIRONMENT` | — | `dev` | `dev`, `staging`, or `production` |
| `FRONTEND_URL` | — | `http://localhost:5173` | Used in email links |
| `PLATFORM_DOMAIN` | — | `getbridgeable.com` | Domain for tenant URLs |
| `APP_NAME` | — | `Bridgeable` | OpenAPI title, notification sender name |
| `SUPPORT_EMAIL` | — | `support@getbridgeable.com` | Support email in notifications |
| `ANTHROPIC_API_KEY` | — | `""` | Claude API (AI features degrade gracefully without it) |
| `GOOGLE_PLACES_API_KEY` | — | `""` | Funeral home directory discovery |
| `REDIS_URL` | — | `""` | Job queue (falls back to DB polling without it) |
| `STRIPE_SECRET_KEY` | — | `""` | Payment processing |
| `STRIPE_WEBHOOK_SECRET` | — | `""` | Stripe webhook validation |
| `QBO_CLIENT_ID` | — | `""` | QuickBooks Online OAuth |
| `QBO_CLIENT_SECRET` | — | `""` | QuickBooks Online OAuth |
| `QBO_REDIRECT_URI` | — | `""` | QuickBooks Online OAuth callback |
| `TWILIO_ACCOUNT_SID` | — | `""` | SMS delivery confirmations |
| `TWILIO_AUTH_TOKEN` | — | `""` | SMS delivery confirmations |
| `TWILIO_FROM_NUMBER` | — | `""` | SMS sender number |
| `PLATFORM_ADMIN_EMAIL` | — | `""` | Seeds platform super admin on first startup |
| `PLATFORM_ADMIN_PASSWORD` | — | `""` | Seeds platform super admin on first startup |

### Frontend Environment Variables
Copy `frontend/.env.example` to `frontend/.env`.

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `VITE_API_URL` | ✅ | `http://localhost:8000` | Backend API base URL |
| `VITE_APP_NAME` | — | `Bridgeable` | Brand name used in UI |
| `VITE_APP_DOMAIN` | — | `getbridgeable.com` | Base domain for subdomain routing; injected at Docker build time |
| `VITE_ENVIRONMENT` | — | `dev` | Environment identifier |

### CRITICAL RULE
**Never point local `DATABASE_URL` at Railway production.** Production credentials live exclusively in the Railway dashboard.

## 8. URLs and Domains

| Environment | Frontend | Backend | Platform Admin |
|-------------|----------|---------|----------------|
| **Production** | `app.getbridgeable.com` | `api.getbridgeable.com` | `admin.getbridgeable.com` |
| **Local** | `localhost:5173` | `localhost:8000` | `admin.localhost:5173` |

Tenant pattern: `{slug}.getbridgeable.com`
First live tenant: `sunnycrest.getbridgeable.com`

## 9. Key Features and Modules

### Accounting & Finance
| Feature | Status | Key Files |
|---------|--------|-----------|
| AR (invoices, payments, aging) | Built | `invoice.py`, `customer_payment.py`, `sales_service.py` |
| AP (vendor bills, payments) | Built | `vendor_bill.py`, `vendor_bill_service.py` |
| Purchase Orders (3-way match) | Built | `purchase_order.py`, `purchase_order_service.py` |
| Journal Entries (recurring, reversals) | Built | `journal_entry.py`, `journal_entry_service.py` |
| Bank Reconciliation | Built | `reconciliation.py`, `reconciliation_service.py` |
| Monthly Statements | Built | `statement.py`, `statement_generation_service.py` |
| Finance Charges | Built | `finance_charge.py`, `finance_charge_service.py` |
| Early Payment Discounts | Built | `early_payment_discount_service.py` |
| Tax System (jurisdictions, exemptions) | Built | `tax.py`, `county_geographic_service.py` |
| Cross-Tenant Billing | Built | `cross_tenant_statement_service.py` |
| Financial Reports (13 types) | Built | `financial_report_service.py` |
| Audit Packages | Built (stub) | `report_intelligence_service.py` |
| COA Analysis (AI) | Built | `accounting_analysis_service.py`, `accounting_connection.py` |

### Operations
| Feature | Status | Key Files |
|---------|--------|-----------|
| Operations Board (registry-driven) | Built | `operations-board.tsx`, `operations-board-registry.ts` |
| Financials Board (5 zones) | Built | `financials-board.tsx` |
| Order Management | Built | `sales_order.py`, `sales_service.py` |
| Delivery Scheduling | Built | `delivery.py`, `delivery_service.py` |
| Cross-Licensee Transfers | Built | `licensee_transfer.py`, `licensee_transfer_service.py` |
| Inter-Licensee Pricing | Built | `inter_licensee_pricing.py` |
| Social Service Certificates | Built | `social_service_certificate.py`, `social_service_certificate_service.py` |

### Urn Sales Extension
| Feature | Status | Key Files |
|---------|--------|-----------|
| Urn Product Catalog | Built | `urn_product.py`, `urn_product_service.py`, `urn-catalog.tsx` |
| Wilbert PDF Ingestion + Image Extraction | Built | `wilbert_pdf_parser.py`, `wilbert_ingestion_service.py` |
| Website Enrichment | Built | `urn_catalog_scraper.py`, `wilbert_scraper_config.py` |
| Catalog PDF Auto-Fetch | Built | `urn_catalog_scraper.py`, `wilbert_scraper_config.py` |
| Pricing Tools (inline, bulk, CSV) | Built | `wilbert_ingestion_service.py`, `urn-catalog.tsx` |
| Stocked + Drop Ship Orders | Built | `urn_order.py`, `urn_order_service.py` |
| Engraving Workflow (two-gate) | Built | `urn_engraving_job.py`, `urn_engraving_service.py` |
| FH Proof Approval (token-based) | Built | `urn_engraving_service.py`, `proof-approval.tsx` |
| Scheduling Board Integration | Built | `urn_order_service.py` (ancillary + drop-ship feeds) |
| Urn Inventory Tracking | Built | `urn_inventory.py` |
| Tenant Settings | Built | `urn_tenant_settings.py` |

### Safety & Compliance
| Feature | Status | Key Files |
|---------|--------|-----------|
| Safety Training (12 OSHA topics) | Built | `safety_training_system_service.py` |
| Equipment Inspections | Built | `safety_service.py` |
| Toolbox Talks + Suggestions | Built | `toolbox_suggestion_service.py` |
| OSHA 300 Log | Built | `osha_300_entry.py` |
| Monthly Safety Program Generation | Built | `safety_program_generation_service.py`, `osha_scraper_service.py` |
| NPCA Audit Prep | Extension — placeholder UI | `pages/compliance/npca-audit-prep.tsx` |

### Intelligence Layer
| Feature | Status | Key Files |
|---------|--------|-----------|
| Financial Health Scores | Built | `financial_health_service.py` |
| Cross-System Insights | Built | `cross_system_insight_service.py` |
| Behavioral Analytics | Built | `behavioral_analytics_service.py` |
| Network Intelligence | Built | `network_intelligence_service.py` |
| Report Commentary (AI) | Stub | `report_intelligence_service.py` |

### Onboarding — Manufacturing Preset (25 items)

| Sort | Key | Tier |
|------|-----|------|
| 2 | `connect_accounting` | must_complete |
| 3 | `accounting_import_review` | must_complete |
| 4 | `setup_tax_rates` | must_complete |
| 5 | `setup_tax_jurisdictions` | must_complete |
| 6 | `add_products` | must_complete |
| 7 | `setup_price_list` | should_complete |
| 8 | `setup_financial_accounts` | should_complete |
| 9 | `add_employees` | must_complete |
| 10 | `setup_safety_training` | must_complete |
| 11 | `setup_scheduling_board` | must_complete |
| 12 | `setup_purchasing_settings` | optional |
| 13 | `configure_cross_tenant` | must_complete |
| 75 | `setup_inter_licensee_pricing` | optional |
| 99 | `setup_team_intelligence` | must_complete |

## 10. Agent Jobs

### Scheduled (13 total) — `backend/app/scheduler.py`

| Job | Schedule | Source File |
|-----|----------|-------------|
| `ar_aging_monitor` | Daily 11:00pm ET | `agent_service.py` |
| `collections_sequence` | Daily 11:05pm ET | `agent_service.py` |
| `ap_upcoming_payments` | Daily 11:10pm ET | `agent_service.py` |
| `receiving_discrepancy_monitor` | Daily 11:15pm ET | `proactive_agents.py` |
| `balance_reduction_advisor` | Daily 11:20pm ET | `proactive_agents.py` |
| `missing_entry_detector` | Daily 11:25pm ET | `proactive_agents.py` |
| `tax_filing_prep` | Daily 11:30pm ET | `proactive_agents.py` |
| `uncleared_check_monitor` | Daily 11:35pm ET | `proactive_agents.py` |
| `financial_health_score` | Daily 5:03am ET | `financial_health_service.py` |
| `cross_system_synthesis` | Daily 6:07am ET | `cross_system_insight_service.py` |
| `reorder_suggestion` | Monday 6:12am ET | `proactive_agents.py` |
| `network_snapshot` | 1st of month 2:17am ET | `network_intelligence_service.py` |
| `onboarding_pattern` | 1st of month 4:13am ET | `network_intelligence_service.py` |
| `safety_program_generation` | 1st of month 6:00am ET | `safety_program_generation_service.py` |

All jobs use `_run_per_tenant()` or `_run_global()` wrappers with per-session DB isolation and error logging. All are manually triggerable via `JOB_REGISTRY` dict and the agent trigger API endpoint.

### Not Yet Implemented (~30 jobs)
`CREDIT_MONITOR`, `PAYMENT_MATCHER`, `1099_MONITOR`, `VENDOR_STATEMENT_RECONCILIATION`, `STATEMENT_RUN_MONITOR`, `RECONCILIATION_MONITOR`, `ABANDONED_RECONCILIATION_MONITOR`, `PO_DELIVERY_MONITOR`, `THREE_WAY_MATCH_MONITOR`, `RECURRING_ENTRY_RUNNER`, `REVERSAL_RUNNER`, `STALE_DRAFT_MONITOR`, `FINANCE_CHARGE_CALCULATOR`, `FINANCE_CHARGE_REMINDER`, `EXEMPTION_EXPIRY_MONITOR`, `DELIVERY_INTELLIGENCE_JOB`, `DELIVERY_WEEKLY_REVIEW`, `SEASONAL_PREP_JOB`, `NETWORK_ANALYSIS_JOB`, `NETWORK_READINESS_JOB`, `EMPLOYEE_COACHING_MONITOR`, `COLLECTIONS_INSIGHT_JOB`, `PAYMENT_PREDICTION_JOB`, `VENDOR_RELIABILITY_JOB`, `VENDOR_PRICING_DRIFT_JOB`, `FINANCE_CHARGE_INSIGHT_JOB`, `DISCOUNT_UPTAKE_JOB`, `RELATIONSHIP_HEALTH_JOB`, `PROFILE_UPDATE_JOB`, `OUTCOME_CLOSURE_JOB`

## 11. Current Build Status

| Metric | Count |
|--------|-------|
| Database tables | ~258 |
| ORM model files | 165+ |
| ORM model exports (`__init__.py`) | 178+ |
| API route files | 105+ |
| API endpoints | 955+ |
| Route modules registered in v1.py | 95+ |
| Frontend routes | 150+ |
| Backend service files | 117+ |
| Migration files | 119 |
| Migration head | `vault_04_multi_location` |
| Agent jobs (scheduled) | 14 |
| Accounting agents (registered) | 12/12 (complete) |
| Accounting agent tests | 105 passing |
| Urn Sales E2E tests | 39/39 passing |
| Safety Program Generation E2E tests | 12/12 passing |
| Agent jobs (not yet built) | ~30 |
| TypeScript errors | 0 |
| Backend import errors | 0 |
| Migration chain | Single head, no broken links |

## 12. Coding Conventions

### API Routes
```python
# backend/app/api/routes/{module}.py
router = APIRouter()

@router.get("/endpoint")
def get_something(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Docstring."""
    return db.query(Model).filter(Model.company_id == current_user.company_id).all()
```
Register in `backend/app/api/v1.py`:
```python
v1_router.include_router(module.router, prefix="/module", tags=["Module"])
```

### SQLAlchemy Models
```python
class Entity(Base):
    __tablename__ = "entities"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```
Import in `backend/app/models/__init__.py` and add to `__all__`.

### Frontend Pages
```tsx
export default function FeaturePage() {
  const [data, setData] = useState(null)
  useEffect(() => { apiClient.get("/endpoint").then(r => setData(r.data)) }, [])
  return <div className="space-y-6 p-6">...</div>
}
```
Register route in `frontend/src/App.tsx`. Add nav item in `frontend/src/services/navigation-service.ts`.

### Nightly Agent Jobs
Add function in the appropriate service file. Add wrapper in `backend/app/scheduler.py`. Add to `JOB_REGISTRY`. Per-tenant jobs use `_run_per_tenant()`.

### Accounting Agents (Phase 1 Infrastructure)

**Architecture:** Shared infrastructure for 13 accounting agents (month-end close, AR collections, unbilled orders, etc.). Agents run as background jobs with a human-in-the-loop approval gate before committing changes.

**Key files:**
- `backend/app/services/agents/base_agent.py` — Abstract base class all agents extend
- `backend/app/services/agents/agent_runner.py` — Job creation, validation, execution orchestrator
- `backend/app/services/agents/approval_gate.py` — Token-based email approval workflow (simple path for weekly agents, full path with period lock for month-end)
- `backend/app/services/agents/period_lock.py` — Financial period locking service
- `backend/app/services/agents/ar_collections_agent.py` — AR Collections Agent (Phase 3)
- `backend/app/services/agents/unbilled_orders_agent.py` — Unbilled Orders Agent (Phase 4)
- `backend/app/services/agents/cash_receipts_agent.py` — Cash Receipts Matching Agent (Phase 5)
- `backend/app/services/agents/expense_categorization_agent.py` — Expense Categorization Agent (Phase 6)
- `backend/app/services/agents/estimated_tax_prep_agent.py` — Estimated Tax Prep Agent (Phase 7)
- `backend/app/services/agents/inventory_reconciliation_agent.py` — Inventory Reconciliation Agent (Phase 8)
- `backend/app/services/agents/budget_vs_actual_agent.py` — Budget vs. Actual Agent (Phase 9)
- `backend/app/services/agents/prep_1099_agent.py` — 1099 Prep Agent (Phase 10)
- `backend/app/services/agents/year_end_close_agent.py` — Year-End Close Agent (Phase 11)
- `backend/app/services/agents/tax_package_agent.py` — Tax Package Compilation Agent (Phase 12)
- `backend/app/services/agents/annual_budget_agent.py` — Annual Budget Agent (Phase 13)
- `backend/app/schemas/agent.py` — All Pydantic schemas (enums, request/response models)
- `backend/app/api/routes/agents.py` — API endpoints (under `/api/v1/agents/accounting`)
- `frontend/src/pages/agents/AgentDashboard.tsx` — Run agents, view history, manage period locks
- `frontend/src/pages/agents/ApprovalReview.tsx` — Review anomalies, approve/reject with period lock

**Database tables:** `agent_jobs` (extended), `agent_run_steps`, `agent_anomalies`, `agent_schedules`, `period_locks`

**Job lifecycle:** `pending` → `running` → `awaiting_approval` → `approved` → `complete` (or `rejected`/`failed`)

**Creating a new agent (Phase 2+):**
```python
from app.services.agents.base_agent import BaseAgent
from app.schemas.agent import StepResult, AnomalySeverity

class MonthEndCloseAgent(BaseAgent):
    STEPS = ["validate_balances", "post_accruals", "reconcile"]

    def run_step(self, step_name: str) -> StepResult:
        if step_name == "validate_balances":
            # Read-only analysis — always safe
            issues = self._check_balances()
            for issue in issues:
                self.add_anomaly(
                    severity=AnomalySeverity.WARNING,
                    anomaly_type="balance_mismatch",
                    description=issue["desc"],
                    amount=issue["amount"],
                )
            return StepResult(message=f"Found {len(issues)} issues", data={"issues": issues})
        elif step_name == "post_accruals":
            self.guard_write()  # Raises DryRunGuardError if dry_run=True
            # ... commit financial writes ...
            return StepResult(message="Posted accruals", data={})
```
Register in `AgentRunner.AGENT_REGISTRY`:
```python
from app.schemas.agent import AgentJobType
AgentRunner.AGENT_REGISTRY[AgentJobType.MONTH_END_CLOSE] = MonthEndCloseAgent
```

**Period lock integration:** `PeriodLockService.check_date_in_locked_period()` is called in `sales_service.py` before creating invoices or recording payments. Returns `PeriodLockedError` (HTTP 409) if the date falls in a locked period.

**Dry-run mode:** Default for all agent runs. `guard_write()` prevents any database mutations. Produces the same report/anomalies as a live run without committing changes.

**Approval gate:** After agent completes, generates a `secrets.token_urlsafe(48)` token, sends HTML email with approve/reject buttons. Token expires after 72 hours. No auth required — the token IS the auth. Approval locks the period; rejection does not.

### shadcn/ui v4
Uses `@base-ui/react` — **no `asChild` prop**. Use `render={<Component />}` instead. Use `buttonVariants()` for styling Links as buttons.

## 13. Business Context

### Tenant Types
- **Manufacturer** (Wilbert licensee) — produces burial vaults, manages deliveries, bills funeral homes monthly
- **Funeral Home** — orders vaults, pays on charge account, receives monthly statements
- **Cemetery** — orders cemetery products, interacts with manufacturers
- **Crematory** — specialized funeral service operations

### Product Lines
- **Funeral Service** (core) — burial vaults, urn vaults, cemetery equipment
- **Urn Sales** (extension) — cremation urns (stocked + Wilbert drop-ship), engraving workflow, Wilbert catalog ingestion
- **Wastewater** (extension) — septic tanks, precast wastewater products
- **Redi-Rock** (extension) — retaining wall blocks for contractors
- **Rosetta Hardscapes** (extension) — hardscape products
- **NPCA Audit Prep** (extension) — compliance and audit readiness; auto-enabled when `npca_certification_status = "certified"`

### Key Business Workflows
1. **Monthly Statement Billing** — funeral homes get consolidated statements, not individual invoices
2. **Finance Charges** — calculated on overdue balances, reviewed before posting
3. **Early Payment Discounts** — 2% if paid by 15th of month
4. **Cross-Licensee Transfers** — NY licensee transfers burial to NJ licensee; billing chains automatically
5. **Spring Burial Season** — March–May peak, requires delivery capacity management

## 14. Recent Changes

- **Multi-Location Support (Model A — Single Tenant, Multiple Locations):** Location-aware architecture enabling multi-plant licensees (WMA president demo target: 11 locations). **Architectural principle:** one company = one tenant = one vault = one login domain. Locations are a filter/dimension, not separate tenants. **Single-location companies see zero UI change** — one implicit primary location created silently, no selector visible. **Database:** 2 new tables (`locations`, `user_location_access`), `location_id` FK added to 7 existing tables (`sales_orders`, `deliveries`, `vault_items`, `work_orders`, `equipment`, `employee_profiles`, `production_log_entries`). Data migration creates primary location per company and assigns all existing records. All existing users get all-location access (null location_id = admin). Migration `vault_04_multi_location`. **Backend:** `location_service.py` with 13 methods — `get_location_filter()` is the core query-filtering method used by all services. `get_locations_overview()` returns per-location stats with attention/on_track/no_activity status. 10 API endpoints under `/api/v1/locations/`. Vault service updated: `query_vault_items`, `get_vault_summary`, `get_upcoming_events`, `create_vault_item` all accept `location_id`. **Frontend:** `LocationProvider` context (fetches locations, persists selection to localStorage, exposes `isMultiLocation` flag). `LocationSelector` — compact popover in sidebar, renders null for single-location. `LocationsOverview` page (`/locations`) — grid of location cards with stats (the jaw-drop screen for the WMA demo). `LocationSettings` page (`/settings/locations`) — full CRUD + per-location user access management. `TransferRequest` component for cross-location inventory transfers via vault items. Navigation service updated with `requiresMultiLocation` filter. **Key design decisions:** location_id nullable everywhere (backward compatible), user_location_access.location_id=NULL means all-access, overview endpoint returns aggregated cross-location stats.
- **Bridgeable Core UI — Universal Command Bar, Entity Timeline, Notifications:** Three-surface interaction layer built on top of every vertical. **Universal Command Bar** (`Cmd+K`/`Ctrl+K`): Alfred-style search + action + navigation + NLP. Claude API intent classification with 800ms timeout, falls back to local fuzzy search. Numbered shortcuts `Cmd+1`–`Cmd+5` for keyboard-first execution. Voice input via Web Speech API with real audio waveform visualization (Web Audio API AnalyserNode). Action registry pattern (`actionRegistry.ts`) with 13 manufacturing actions, extensible per vertical. `CommandBarProvider` wraps the entire app. **Entity Timeline** (`EntityTimeline.tsx`): right-side slide-over panel (420px) showing vault history for any record, grouped by date. Filter tabs (All/Events/Documents/Communications). `HistoryButton` component added to CRM company detail and sales order detail pages. **Smart Plant Voice Mode** (`SmartPlantCommandBar.tsx`): touch-first variant for plant floor terminals — auto-execute on high confidence (>0.92), large touch buttons for medium confidence. **Backend:** 3 new endpoints under `/api/v1/core/` (`POST /command`, `GET /recent-actions`, `POST /log-action`). `core_command_service.py` with entity pre-resolution (companies, orders, products), Claude API classification, and local search fallback. **Database:** `user_actions` table for command bar action history. Migration `vault_03_core_ui`. **Sidebar:** old AI command bar replaced with `⌘K` trigger button that opens the universal command bar. Migration head: `vault_03_core_ui`.
- **Bridgeable Core Vault Migration (Foundation + Steps 1-4):** Unified data layer via `Vault` and `VaultItem` models. Two new tables: `vaults` (company-level containers) and `vault_items` (30+ column flexible items supporting documents, events, communications, reminders, assets, compliance items, and production records). `VaultItem` uses `item_type` discriminator with `event_type`/`event_type_sub` for domain specificity, `metadata_json` JSONB for domain-specific fields, `shared_with_company_ids` JSONB for cross-tenant visibility, and `source_entity_id` for back-reference to legacy records. **Dual-write pattern** added to 5 services: `delivery_service.py` (deliveries, routes, media → vault events/documents), `work_order_service.py` (pour events → vault), `operations_board_service.py` (production log → vault), `safety_service.py` (training events, attendee records → vault events/documents). **Vault compliance sync** (`vault_compliance_sync.py`): scans overdue inspections, expiring training certs, and regulatory deadlines (OSHA 300A), creates/updates VaultItems with deduplication via `source_entity_id` keys. **Calendar sync**: iCal feed endpoint (`GET /vault/calendar.ics`) with token-based auth, role-filtered events. `calendar_token` column added to users. **10 API endpoints** under `/api/v1/vault/`: items CRUD, summary, upcoming-events, cross-tenant, calendar.ics, compliance sync, calendar token generation. **Data migration** (`vault_02_data_migration`): idempotent SQL migration of existing deliveries, routes, pour events, production logs, training events, and training records into vault_items (source="migrated"). Migration `vault_01_core_tables` creates tables + indexes (composite on company_id/item_type/event_start, GIN on metadata_json). Migration head: `vault_02_data_migration`.
- **PDF-Native Image Extraction for Urn Catalog:** The Wilbert PDF catalog is now the sole reliable source of truth for product images. `extract_product_images()` in `wilbert_pdf_parser.py` extracts embedded JPEG images from each catalog page via PyMuPDF's `page.get_images()` and `doc.extract_image()`, filters by size (min 80x80px) and aspect ratio (max 4:1), converts to JPEG at 85% quality, and associates with SKUs via catalog page mapping. `_extract_and_upload_images()` in `wilbert_ingestion_service.py` uploads extracted images to R2 at `tenants/{company_id}/urn_catalog/images/{sku}.jpg` and sets `r2_image_key` on the product. Images are resolved to public URLs server-side in the product list/detail endpoints via `_resolve_product_image_url()`. Web enrichment (`enrich_products_from_web`) now skips image fetch for products with existing `r2_image_key` (PDF images take precedence), and wraps individual product enrichment in try/except for resilience. SECTION_MAP updated from Volume 11 (88 pages) to Volume 8 (78 pages). New `GET /urns/catalog/sync-status` endpoint returns product completeness metrics (images, descriptions, prices, dimensions). Frontend `urn-catalog.tsx` updated: data completeness bar with green/amber indicators, larger product image in expanded detail row, `r2_image_key` indicator, sync status after each operation. `CatalogIngestionResponse` and `CatalogPdfFetchResponse` schemas now include `images_uploaded` count.
- **Monthly Safety Program Generation:** AI-powered monthly safety program creation with OSHA regulatory scraping. Full pipeline: `osha_scraper_service.py` scrapes OSHA standard pages (httpx + BeautifulSoup, 14 standard URL mappings), `safety_program_generation_service.py` generates 7-section programs via Claude Sonnet (Purpose/Scope, Responsibilities, Definitions, Procedures, Training, Recordkeeping, Review), WeasyPrint renders professional PDF with cover page. Table: `safety_program_generations` with full lifecycle tracking (OSHA scrape → generation → PDF → approval). Approval workflow: draft → pending_review → approved/rejected. On approve: creates/updates `SafetyProgram` record. Scheduler job: 1st of month at 6am ET via `job_safety_program_generation`. Morning briefing integration: shows pending reviews count, missing monthly generations, failed generations. Permission: `safety.trainer` (view, generate, approve). 7 API endpoints under `/safety/programs/` (list, detail, generate, ad-hoc topic, approve, reject, regenerate-pdf). Frontend: `safety-programs.tsx` rewritten with AI Generated + Manual tabs. Migration `r15_safety_program_generation`. 12 E2E tests (all passing). Route ordering fix: generation router registered before safety router to prevent `{program_id}` catch-all conflict.
- **Urn Catalog PDF Auto-Fetch:** One-click "Fetch & Sync Catalog" replaces manual PDF upload. `UrnCatalogScraper.fetch_catalog_pdf()` downloads the Wilbert catalog PDF from a direct URL (`https://www.wilbert.com/assets/1/7/CCV8-Cremation_Choices_Catalog.pdf`), computes MD5 hash for change detection, archives to R2, and triggers `ingest_from_pdf()` if changed. Fallback URL resolver (`_resolve_pdf_url()`) scrapes the catalog landing page if the direct URL changes. Web enrichment runs automatically in background via FastAPI `BackgroundTasks` (creates its own DB session to avoid lifecycle issues). UI button always uses `force=true`; hash-based skip is for automated/scheduled runs. 3 new columns on `urn_tenant_settings` (catalog_pdf_hash, catalog_pdf_last_fetched, catalog_pdf_r2_key). Migration `r14_urn_catalog_pdf_fetch`. Frontend simplified: single "Fetch & Sync Catalog" button with collapsed manual upload fallback. 2 new E2E tests in standalone `urn-catalog-pdf-fetch.spec.ts`. PyMuPDF (`fitz`) dependency added to `requirements.txt` (was documented but missing, causing silent 0-product returns on staging).
- **Social Service Certificates:** Government benefit program delivery confirmations auto-generated when Social Service Graveliner orders are delivered. Table: `social_service_certificates` with status lifecycle (pending_approval → approved → sent, or voided). `social_service_certificate_service.py`: `generate_pending()` auto-creates on delivery completion (identifies SS products by pattern matching), `approve()` triggers PDF email to funeral home, `void()` with reason. WeasyPrint PDF generator (`pdf_generators/social_service_certificate_pdf.py`) produces professional letter-size document with company letterhead, deceased info, product details, and delivery timestamp. 6 API endpoints under `/api/v1/social-service-certificates/` (requires `invoice.approve` permission): pending list, all with status filter, detail, approve, void, PDF download (presigned R2 URL). Frontend page with status filter, approve/void/view-pdf actions, color-coded status badges. Migration `r13_social_service_certificates`.
- **Wilbert Urn Catalog Ingestion Pipeline:** Full ingestion system for Wilbert's 88-page PDF catalog. `wilbert_pdf_parser.py`: PyMuPDF-based line-by-line state machine parser extracts 259 products with SKUs (P-prefix urns, D-prefix jewelry), dimensions (height, width/diameter, depth, cubic inches), engravability flags, material categories (Metal/Wood/Stone/Glass/Ceramic/etc.), companion/memento linkage, and catalog page numbers. `wilbert_ingestion_service.py`: orchestrator with `ingest_from_pdf()` (PDF→upsert by SKU), `apply_bulk_markup()` (cost→retail with rounding), `import_prices_from_csv()`. `urn_catalog_scraper.py`: rewritten with real CSS selectors from wilbert.com research crawl (`.product-list`, `h1.item-name`, `div.item-desc p`, `#productImage img.main-image`), 9 category URLs, SKU inference from image filenames, `enrich_products_from_web()` for descriptions/images. `wilbert_scraper_config.py`: all real selectors, category URLs, site origin. Migration `r12_urn_catalog_ingestion`: 11 new columns on `urn_products` (height, width_or_diameter, depth, cubic_inches, product_type, companion_of_sku, wilbert_description, wilbert_long_description, color_name, catalog_page, r2_image_key), 3 new columns on `urn_catalog_sync_logs` (sync_type, pdf_filename, products_skipped), 2 new indexes. 6 new API endpoints: `POST /urns/catalog/ingest-pdf` (file upload), `POST /urns/catalog/enrich-from-web`, `PATCH /urns/products/{id}/pricing`, `POST /urns/pricing/bulk-markup`, `POST /urns/pricing/import-csv`, `POST /urns/pricing/import-json`. Frontend `urn-catalog.tsx` rewritten: pricing columns (Cost, Retail, Margin%) with inline click-to-edit, "Sync from Wilbert" dialog (PDF upload + optional web enrichment), Bulk Markup tool (filter by material/type, % + rounding), CSV Price Import, material/type filter dropdowns, expandable detail rows (dimensions, descriptions, companion links), unpriced product amber warnings. Design decisions: prices uploaded/entered in-platform (no WilbertDirect scraping), Wilbert marketing materials/images OK (licensee rights), font options deferred to tenant settings.
- **Urn Sales Extension (Complete):** Full urn sales lifecycle as a tenant extension (`urn_sales`). 6 tables: `urn_products` (product catalog with stocked/drop-ship source), `urn_inventory` (stocked product tracking), `urn_orders` (order management with fulfillment_type), `urn_engraving_jobs` (two-gate proof approval), `urn_tenant_settings` (configurable lead times, approval windows), `urn_catalog_sync_logs` (sync audit trail). `urn_product_service.py`: CRUD + AI-powered search (Claude extracts search terms, ILIKE query with relevance scoring). `urn_order_service.py`: create/confirm/cancel/deliver lifecycle, stocked inventory reservation on confirm, auto-release on cancel, ancillary items for scheduling board (configurable window, default 3 days), drop-ship visibility feed, search by FH/decedent. `urn_engraving_service.py`: two-gate proof approval — Gate 1: FH approval via token-based email (72hr expiry, no auth required), Gate 2: staff approve/reject. Wilbert form generation (PDF via weasyprint). Auto-send FH email when `fh_contact_email` exists on proof upload. Keepsake set support: scaffolds N engraving jobs from companion_skus, propagate specs to companions, all-jobs approval gate. Verbal approval flagging (stores transcript excerpt, does NOT auto-approve). Correction summary for resubmissions. `urn_intake_agent.py`: email intake + proof matching. 41 API endpoints under `/api/v1/urns/`. Frontend: `urn-catalog.tsx` (product management), `urn-orders.tsx` (order dashboard with status filters), `urn-order-form.tsx` (create order), `proof-approval.tsx` (public FH approval page). Migration `r11_urn_sales`. Extension gated via `require_extension("urn_sales")`. 37 E2E Playwright tests (all passing).
- **Year-End Close + Tax Package Agents (Phases 11 & 12) — ACCOUNTING AGENT SUITE COMPLETE:** YearEndCloseAgent (Phase 11): Extends MonthEndCloseAgent (not BaseAgent) — inherits all 8 month-end steps + 5 new year-end steps (13 total). execute() validates Dec 1–Dec 31 period, fails immediately if invalid. New steps: full_year_summary (full year + 4 quarters income statement, vs approved AnnualBudgetAgent with 15% variance threshold, vs prior year), depreciation_review (JournalEntryLine pattern matching for depreciation/amortization, 20% monthly variance threshold excluding December), accruals_review (December accrual keyword matching with January reversal check), inventory_valuation (InventoryItem × Product.cost_price, flags no-cost products), retained_earnings_summary (net income from step 9, distribution keyword matching, beginning RE from equity accounts). Uses FULL approval path (statement run + period lock, same as MonthEndCloseAgent). TaxPackageAgent (Phase 12): READ-ONLY capstone agent, extends BaseAgent. 5 steps: collect_agent_outputs (queries completed agent_jobs for tax year, groups by job_type, tracks month_end_closes 0-12), assess_completeness (CRITICAL gaps: missing year_end_close/1099_prep, WARNING: months not closed/missing tax estimates, INFO: optional agents; readiness_score = required_score × 0.6 + recommended_score × 0.4), compile_financial_statements (extracts from year_end_close report_payload), compile_supporting_schedules (6 schedules: A=1099 vendors, B=tax estimates, C=inventory, D=AR aging, E=budget vs actual, F=anomaly summary), generate_report (professional HTML with cover page, TOC, financial statements, supporting schedules, CPA disclaimer). Uses SIMPLE approval (no period lock). All 12 AgentJobType enum values now registered in AgentRunner. 19 tests in `test_phase_11_12_agents.py`. Total agent tests: 105 passing.
- **1099 Prep + Annual Budget Agents (Phases 10 & 13):** Prep1099Agent: 4 steps (compute vendor payment totals via VendorPaymentApplication.amount_applied, classify 1099 eligibility — INCLUDE/NEEDS_REVIEW/BELOW_THRESHOLD based on is_1099_vendor flag and $600 IRS threshold, flag data gaps — missing tax IDs CRITICAL, unreviewed vendors WARNING, w9_tracking_not_implemented INFO always, orphaned payments WARNING, generate HTML report with filing deadline banner and CPA disclaimer). `mask_tax_id()` helper — never stores or displays full tax IDs. AnnualBudgetAgent: 5 steps (pull prior year actuals via get_income_statement for full year + 4 quarters, compute quarterly seasonal shares, apply growth assumptions — defaults 5% rev / 3% COGS / 3% expense overridable via report_payload.assumptions, generate budget lines with quarterly_breakdown matching Phase 9 _extract_budget_for_period contract Q1-Q4 keys, generate HTML report with assumptions banner and scenario re-run guidance). Flags budget_projects_loss WARNING if net income < 0. Budget stored at report_payload.budget for Phase 9 consumption. Both added to SIMPLE_APPROVAL_TYPES — no financial writes, no period lock. 10 agents now registered in AgentRunner. 17 tests in `test_phase_10_13_agents.py`. Total agent tests: 86 passing.
- **Inventory Reconciliation + Budget vs. Actual Agents (Phases 8–9):** InventoryReconciliationAgent: 6 steps (snapshot current inventory with last transaction lookup, verify transaction integrity — InventoryItem.quantity_on_hand vs InventoryTransaction.quantity_after, compute reserved quantity from confirmed/processing SalesOrderLines, reconcile production vs deliveries — two-method comparison of transaction ledger vs ProductionLogEntry-minus-delivered, check physical count freshness with 90/180 day thresholds, generate HTML report). Anomaly types: `inventory_balance_mismatch` (CRITICAL), `inventory_no_transaction_history`, `inventory_oversold` (CRITICAL), `inventory_at_risk`, `inventory_reconciliation_variance` (WARNING ≤2 units, CRITICAL >2), `inventory_unplanned_production`, `inventory_count_overdue`, `inventory_large_count_adjustment`. BudgetVsActualAgent: 4 steps (get income statement for period + YTD via get_income_statement(), get comparison basis with priority: formal_budget > prior_year_same_period > prior_quarter > none, compute variances at summary + GL line level with 15% threshold, generate HTML report with comparison basis banner). Favorable direction: revenue/gross_profit/net_income ABOVE = favorable; COGS/expenses BELOW = favorable. Both added to SIMPLE_APPROVAL_TYPES — no financial writes, no period lock on approval. 8 agents now registered in AgentRunner. 16 tests in `test_phase_8_9_agents.py`. Total agent tests: 69 passing.
- **Expense Categorization + Estimated Tax Prep Agents (Phases 6–7):** ExpenseCategorizationAgent: 4 steps (find uncategorized/orphaned VendorBillLines, classify via Claude Haiku with 0.85 confidence threshold, map to GL accounts via TenantGLMapping, generate HTML report). On approval: writes high-confidence categories to VendorBillLine.expense_category; low-confidence lines require manual review (Phase 6b). EstimatedTaxPrepAgent: 5 steps (income statement via get_income_statement(), YTD annualization, quarterly tax liability with federal 20–25% range + state TaxRate lookup, prior payment detection via JournalEntry/VendorBill, HTML report with mandatory CPA disclaimer). Purely informational — no financial writes on approval. Both added to SIMPLE_APPROVAL_TYPES. Fixed naive datetime comparison bug in approval_gate.py token expiry check. 16 tests in `test_phase_6_7_agents.py`. Total agent tests: 53 passing.
- **Three Weekly Agents (Phases 3–5):** ARCollectionsAgent, UnbilledOrdersAgent, CashReceiptsAgent. All registered in `AgentRunner.AGENT_REGISTRY`. Approval gate updated with `SIMPLE_APPROVAL_TYPES` set for weekly agents — no period lock, no statement run on approval. ARCollectionsAgent: 4 steps (AR snapshot, tier classification, Claude-drafted collection emails with fallback templates, report). UnbilledOrdersAgent: 3 steps (find unbilled delivered orders, pattern analysis — repeat customers/backlog growth/high value, report). CashReceiptsAgent: 4 steps (collect unmatched payments, auto-match via 4 rules — exact+customer/exact+any/subset-sum/unresolvable, flag stale payments, report). Auto-match writes only in non-dry-run mode via `guard_write()`. 15 tests in `test_phase_3_4_5_agents.py`. Total agent tests: 49 passing.
- **MonthEndCloseAgent (Phase 2):** First real agent implementation. 8-step pre-flight verification: invoice coverage, payment reconciliation, AR aging snapshot, revenue summary with adaptive outlier detection, customer statement flag detection (reuses `statement_generation_service`), cross-step anomaly checks, prior period comparison, executive report generation. On approval: triggers `generate_statement_run()`, auto-approves unflagged statement items, locks period. Agent registered in `AgentRunner.AGENT_REGISTRY`. Anomaly types: `uninvoiced_delivery`, `invoice_amount_mismatch`, `unmatched_payment`, `duplicate_payment`, `overdue_ar_90plus`, `revenue_outlier`, `low_collection_rate`, `inactive_customer`, `low_invoice_volume`, `statement_run_conflict`, and 6 statement flags (`statement_open_dispute`, `statement_high_balance_variance`, etc.). Seed script: `scripts/seed_agent_test.py`. 11 tests.
- **Accounting Agent Infrastructure (Phase 1):** Built shared foundation for 13 accounting agents. 5 tables (`agent_run_steps`, `agent_anomalies`, `agent_schedules`, `period_locks` + extended `agent_jobs`), base agent class, approval gate with token-based email workflow, period lock service with financial write guards on invoices/payments, agent runner with validation, full API endpoints, frontend dashboard + approval review page. Migration `r10_agent_infra`. 22 tests passing.
- **Document Service R2 Migration:** `document_service.py` rewritten for Cloudflare R2 storage. Download route returns 307 redirect to signed URLs. Lazy migration for existing local files. Admin bulk migration endpoint.
- **Platform rename:** "ERP Platform" → "Bridgeable" throughout frontend. `VITE_APP_NAME=Bridgeable` in `.env`. `APP_NAME` default in `config.py` changed to `"Bridgeable"`. `SUPPORT_EMAIL` changed to `"support@getbridgeable.com"`.
- **Domain migration:** All `yourerp.com` references replaced with `VITE_APP_DOMAIN`. `platform.app` fallbacks replaced with `getbridgeable.com`. `tenant.ts` comments updated. `company-register.tsx` fallback fixed.
- **`backend/.env.example`:** Updated header, corrected `DATABASE_URL` to `bridgeable_dev`, documented all vars (Twilio, Google Places, `PLATFORM_ADMIN_*`).
- **APScheduler:** Installed (`>=3.10.0`). `start_scheduler()` / `shutdown_scheduler()` called from FastAPI lifespan. 13 jobs registered.
- **Proactive agents:** 6 new agent functions in `proactive_agents.py` — wired into scheduler nightly/weekly runs.
- **NPCA moved to extension-only:** Dashboard `isNpcaEnabled` now uses `hasModule("npca_audit_prep")`. `/npca` placeholder page created at `frontend/src/pages/compliance/npca-audit-prep.tsx`.
- **`npca_certification_status`:** Added to `CompanyResponse` Pydantic schema and frontend `Company` type so `/auth/me` returns it.
- **Migration chain fixes:** 4 duplicate revision IDs renamed. Merge migrations created. Table names corrected (`payments→customer_payments`, `orders→sales_orders`, `bills→vendor_bills`).
- **Idempotent migrations:** `alembic/env.py` monkey-patches `add_column`, `create_table`, `create_index`.
- **Environment separation:** Local `.env` → `bridgeable_dev`. Railway credentials in Railway dashboard only.
- **CORS:** `.*getbridgeable\.com` regex in production.
- **`StatementRunItem` ORM model:** Added retroactively.

## 15. Known Issues and Tech Debt

### Active Issues
- **Orphaned `tenant_settings` table** — migrations create it, but app code uses `Company.settings_json` exclusively.
- **COA extraction not implemented** — `tenant_accounting_import_staging` exists but no QBO/Sage API extraction. Only Sage CSV upload works.
- **Sage API version detection** — always returns "could not reach server"; CSV is the only real Sage path.
- **`/npca` is a placeholder** — nav item links to it; only shows "coming soon". No actual NPCA audit features built.
- **Audit package generation is a stub** — `report_intelligence_service.py:195` has a TODO for async Claude call.
- **Accountant invitation email** — `accounting_connection.py:304` has a TODO; email is not sent.
- **~30 unimplemented agent jobs** — schemas and services exist, job runners not built.

### Tech Debt
- `@app.on_event("startup/shutdown")` — deprecated FastAPI pattern; should migrate to lifespan context manager
- No query caching — all reads hit PostgreSQL directly
- AIService creates new Anthropic client per call — should use connection pooling
- `StatementRunItem` model added retroactively — verify all service code references it correctly
- `APP_NAME` used as Redis key prefix in `job_queue_service.py` — key shifts if `APP_NAME` env changes

## 16. Next Priorities

### Top Priority — Data Migration Tool
**Waiting on:** Sage CSV export files from Sunnycrest accountant (invoice history, customer list, cash receipts).

Once received:
1. Complete COA AI analysis flow end-to-end with real Sage data
2. Build customer import (Sage customer list → Bridgeable customers)
3. Build AR import (invoice history → open invoices + aging balances)
4. Build payment history import
5. Validate imported balances against Sunnycrest's current Sage totals

### Short Term (13 simpler agent jobs)
`STALE_DRAFT_MONITOR`, `REVERSAL_RUNNER`, `PO_DELIVERY_MONITOR`, `RECONCILIATION_MONITOR`, `ABANDONED_RECONCILIATION_MONITOR`, `STATEMENT_RUN_MONITOR`, `FINANCE_CHARGE_REMINDER`, `EXEMPTION_EXPIRY_MONITOR`, `1099_MONITOR`, `DELIVERY_WEEKLY_REVIEW`, `FINANCE_CHARGE_INSIGHT_JOB`, `DISCOUNT_UPTAKE_JOB`, `OUTCOME_CLOSURE_JOB`

### Medium Term
- Build actual NPCA Audit Prep feature (compliance score engine, gap analysis, audit package ZIP)
- ~~Staging environment on Railway~~ ✅ Done (April 2026)
- ~~End-to-end testing with real Sunnycrest data~~ ✅ Done (April 2026)
- Performance optimization for report generation
- Migrate FastAPI `@app.on_event` to lifespan context manager

## 17. Recent Build Sessions

### Session: April 16, 2026 — Bridgeable Core Vault Migration

Unified data layer — every feature reads from and writes to vault_items.

**New models:** `Vault` (container per company), `VaultItem` (30+ columns, JSONB metadata)

**Dual-write integration (5 services):**
- `delivery_service.py` — deliveries → delivery events, routes → route events, media → delivery_confirmation docs
- `work_order_service.py` — pour events → production_pour events
- `operations_board_service.py` — production log → production_record items
- `safety_service.py` — training events → safety_training events, attendees → training_completion docs

**Vault compliance sync:** `vault_compliance_sync.py` — periodic scan creates/updates VaultItems for overdue inspections, expiring training certs, regulatory deadlines (OSHA 300A)

**Calendar sync:** iCal feed at `GET /vault/calendar.ics` with token-based auth, role-filtered events

**10 API endpoints:** items CRUD, summary, upcoming-events, cross-tenant, calendar.ics, compliance sync, calendar token gen

**Cross-tenant foundation:** `shared_with_company_ids` JSONB enables delivery confirmations visible to funeral homes

**Migrations:** `vault_01_core_tables` (DDL), `vault_02_data_migration` (idempotent data migration of legacy records)

**Migration head:** `vault_02_data_migration`

---

### Session: April 9, 2026 — Nav Reorganization + Resale Hub Shell

- Created Resale hub (`/resale`) gated by `urn_sales` extension
- `/resale/catalog` and `/resale/orders` alias existing urn pages
- `/resale/inventory` stub page added
- Removed standalone Urn Catalog, Urn Orders, Disinterments top-level nav items
- Disinterments added as sub-item under Order Station
- SS Certificates added as sub-item under Compliance (alongside NPCA)
- Added missing icons: Agents → Bot, Compliance → ShieldCheck, Disinterments → Shovel, Resale → Store
- Compliance and Order Station use same expand/collapse sub-nav pattern as Legacy Studio
- Added Store, Shovel, FileCheck, Bot, Shield, ShoppingBag, Boxes, Skull to sidebar ICON_MAP

---

### Session: April 9, 2026 — Social Service Certificates + Urn Catalog PDF Auto-Fetch

---

#### Social Service Certificates (Complete)

Auto-generated delivery confirmations for government Social Service Graveliner benefit program.

**Table:** `social_service_certificates` — status lifecycle: `pending_approval` → `approved` → `sent` (or `voided` at any point)

**Auto-generation trigger:** When a sales order containing a Social Service Graveliner product is delivered, `generate_pending()` creates a pending certificate. SS products identified by pattern matching ("social service", "ss graveliner", etc.).

**Approval workflow:**
- Admin reviews pending certificates in `/social-service-certificates`
- Approve → generates PDF via WeasyPrint, emails to funeral home's billing email with PDF attachment
- Void → records reason, marks certificate permanently voided

**PDF Generator (`pdf_generators/social_service_certificate_pdf.py`):**
- Professional letter-size government-facing document
- Company letterhead, deceased name, funeral home, cemetery, product details, delivery date/time
- Stored in R2 with presigned download URLs

**API:** 6 endpoints under `/api/v1/social-service-certificates/` (requires `invoice.approve` permission)

**Frontend:** `/social-service-certificates` — status filter dropdown, certificate table with approve/void/view-pdf actions, color-coded status badges

**Migration:** `r13_social_service_certificates` (revises `r12_urn_catalog_ingestion`)

---

#### Urn Catalog PDF Auto-Fetch (Complete)

One-click catalog sync replaces manual PDF upload. Downloads, parses, and enriches the Wilbert catalog automatically.

**How it works:**
1. `fetch_catalog_pdf()` downloads PDF from direct URL via httpx (no Playwright needed)
2. MD5 hash compared against stored hash — skips parse if unchanged (unless `force=true`)
3. PDF archived to R2 with hash-based key for versioning
4. `ingest_from_pdf()` parses 259 products via PyMuPDF state machine (~5s)
5. Web enrichment runs in background via FastAPI `BackgroundTasks` (~3 min, 100+ pages with 1.5s polite delay)
6. Background task creates its own `SessionLocal()` to avoid DB session lifecycle issues

**Fallback URL resolver:** `_resolve_pdf_url()` tries direct URL first (`HEAD` request), falls back to scraping the catalog landing page for `.pdf` links if Wilbert moves the file.

**Config (`wilbert_scraper_config.py`):**
- `CATALOG_PDF_URL` — direct PDF URL
- `CATALOG_PDF_PAGE_URL` — landing page for fallback resolution

**New tenant settings fields:** `catalog_pdf_hash`, `catalog_pdf_last_fetched`, `catalog_pdf_r2_key`

**Frontend:** Single "Fetch & Sync Catalog" button (always `force=true`), collapsed manual upload fallback. Removed standalone enrich button — web enrichment is automatic.

**Migration:** `r14_urn_catalog_pdf_fetch` (revises `r13_social_service_certificates`)

**E2E Tests:** 2 tests in `urn-catalog-pdf-fetch.spec.ts` (both passing)

---

### Session: April 9, 2026 — Urn Sales Extension + Wilbert Catalog Ingestion Pipeline

---

#### Urn Sales Extension (Complete)

Full urn sales lifecycle as a tenant extension (`urn_sales`), gated by `require_extension("urn_sales")`.

**Tables (6):** `urn_products`, `urn_inventory`, `urn_orders`, `urn_engraving_jobs`, `urn_tenant_settings`, `urn_catalog_sync_logs`

**Two fulfillment paths:**
- **Stocked**: Inventory reserved on confirm, released on cancel, decremented on deliver
- **Drop Ship**: Ordered from Wilbert, tracked via `wilbert_order_ref` + `tracking_number`

**Engraving workflow — two-gate proof approval:**
- Gate 1: FH approval via token-based email (`secrets.token_urlsafe(48)`, 72hr expiry, no auth)
- Gate 2: Staff approve/reject with notes
- Auto-sends FH email when `fh_contact_email` exists on proof upload
- Keepsake sets: scaffold N engraving jobs from `companion_skus`, propagate specs, all-jobs approval gate
- Verbal approval: stores transcript excerpt, flags but does NOT auto-approve
- Correction summary tracks resubmission history

**Scheduling board integration:**
- Ancillary items feed: stocked orders with `need_by_date` within configurable window (default 3 days)
- Drop-ship visibility feed: all pending drop-ship orders with tracking

**Key services:**
- `urn_product_service.py` — CRUD + Claude-powered natural language search
- `urn_order_service.py` — full lifecycle + scheduling feeds
- `urn_engraving_service.py` — two-gate proofs, Wilbert form PDF, keepsake propagation
- `urn_intake_agent.py` — email intake + proof matching

**Frontend pages:** `/urns/catalog`, `/urns/orders`, `/urns/orders/new`, `/proof-approval/{token}` (public)

**API:** 41 endpoints under `/api/v1/urns/`

**Migration:** `r11_urn_sales` (revises `r10_agent_infra`)

---

#### Wilbert Catalog Ingestion Pipeline (Complete)

Ingests Wilbert's 88-page PDF catalog (Volume 11) into `urn_products`, with optional website enrichment.

**PDF Parser (`wilbert_pdf_parser.py`):**
- PyMuPDF (`fitz`) text extraction → line-by-line state machine
- Handles Wilbert's two-line dimension format (label on one line, value on next)
- Extracts 259 products: SKU (P-prefix urns, D-prefix jewelry), product type (Urn/Memento/Heart/Pendant), dimensions, cubic inches, engravability flag, material category, companion linkage, catalog page
- Section-aware: maps page ranges to material categories (Metal 4-17, Wood 18-31, Stone 32-36, etc.)
- Deduplicates by SKU (keeps latest occurrence)

**Website Scraper (`urn_catalog_scraper.py`):**
- Real CSS selectors from research crawl: `.product-list`, `h1.item-name`, `div.item-desc p`, `#productImage img.main-image`
- 9 category URLs under `/store/cremation/urns/{material}/`
- SKU inference from image filenames (e.g., `P2013-CloisonneOpal-750.jpg`)
- Enriches with short/long descriptions and hi-res product images
- Polite crawl: 1.5s delay, custom User-Agent

**Ingestion Orchestrator (`wilbert_ingestion_service.py`):**
- `ingest_from_pdf()` — full pipeline: parse PDF → upsert by SKU → optional web enrichment
- `apply_bulk_markup()` — cost → retail with configurable % and rounding ($0.01/$0.50/$1/$5)
- `import_prices_from_csv()` — match by SKU, update cost/retail

**Migration:** `r12_urn_catalog_ingestion` (revises `r11_urn_sales`) — 11 new columns on `urn_products`, 3 on `urn_catalog_sync_logs`, 2 indexes

**6 new API endpoints:**
- `POST /urns/catalog/ingest-pdf` — file upload + parse
- `POST /urns/catalog/enrich-from-web` — website enrichment pass
- `PATCH /urns/products/{id}/pricing` — inline single-product price edit
- `POST /urns/pricing/bulk-markup` — bulk markup by material/type
- `POST /urns/pricing/import-csv` — CSV price import
- `POST /urns/pricing/import-json` — JSON price import

**Frontend (`urn-catalog.tsx` rewrite):**
- Pricing columns: Cost, Retail, Margin% with inline click-to-edit
- "Sync from Wilbert" dialog: PDF upload + optional web enrichment toggle
- Bulk Markup tool: filter by material/type, set %, choose rounding, only-unpriced option
- CSV Price Import dialog
- Material and Type filter dropdowns (populated from data)
- Expandable detail rows: dimensions, descriptions, companion links, catalog page
- Unpriced product warnings (count in header, amber row highlight)

**Design decisions:**
- Prices uploaded or manually entered in-platform (no WilbertDirect scraping — avoid stepping on Wilbert's toes)
- Wilbert marketing materials/images are OK (licensee rights)
- Font options deferred to tenant settings (future)

**E2E Tests:** 37/37 passing (Playwright, staging)

---

### Session: April 7, 2026 — Call Intelligence, Knowledge Base, Price Management, Platform Email, Staging Environment

---

#### Call Intelligence (Complete)

Feature formerly called "RingCentral Integration" — rebranded to "Call Intelligence" throughout UI. RingCentral is a provider underneath, not the feature name. No user-visible text says "RingCentral" except the Connect button and provider dropdown in settings.

**Three prompts fully built and deployed:**

**PROMPT 1 — OAuth + Webhook Infrastructure**
- Tables: `ringcentral_connections`, `ringcentral_extension_mappings`, `ringcentral_call_log`
- OAuth flow: `/settings/call-intelligence`
- Webhook: `POST /api/v1/integrations/ringcentral/webhook`
- SSE endpoint for real-time call events
- Extension → Bridgeable user mapping UI
- Token refresh background task
- Webhook renewal task

**PROMPT 2 — Transcription + Extraction Pipeline**
- Tables: `ringcentral_call_extractions`
- Services:
  - `transcription_service.py` — Deepgram Nova-2, speaker diarization
  - `call_extraction_service.py` — Claude extraction, fuzzy company match, draft order creation
  - `after_call_service.py` — orchestrator: transcribe → extract → draft order, 10s delay after call ends
- Voicemail handling (RC transcription + Deepgram fallback)
- Morning briefing integration
- Reprocess endpoint for re-running extraction

**PROMPT 3 — CallOverlay UI (Complete)**
- `contexts/call-context.tsx` — SSE connection, call state, preferences
- `components/call/CallOverlay.tsx` — 3 states: ringing / active / review
  - KB panel slides in at top when knowledge query detected
  - Pushes order sections down
  - Dismisses after configurable timer or when price is detected spoken (Phase 2 — timer is Phase 1 fallback)
- `components/call/MinimizedCallPill.tsx`
- `pages/calls/call-log.tsx`
- `App.tsx`: `CallContextProvider` + `CallOverlay` mounted globally

**Key design decisions:**
- Answer via physical RC phone (not WebRTC)
- Deepgram post-call transcription (Phase 1)
- Live streaming transcription = Phase 2
- After-call fires ONLY if no order created during call (prevents duplicates)
- "Still Needed" panel is primary feature — catches what FD forgot to mention
- Missing fields are tappable → shows callback number

**ENV VARS REQUIRED:**
- `RINGCENTRAL_CLIENT_ID`, `RINGCENTRAL_CLIENT_SECRET`, `DEEPGRAM_API_KEY`
- RC App: production, private, server-side web app
- Redirect URI: `https://api.getbridgeable.com/api/v1/integrations/ringcentral/oauth/callback`
- Scopes: Call Control, Read Accounts, Read Call Recording, Read Presence, Webhook Subscriptions, Read Call Log

---

#### Call Intelligence Knowledge Base (Complete)

Platform-wide feature powering live call assistance, mid-call price lookup, and future AI answering service.

**Tables:**
- `kb_categories` — per tenant, system + custom
- `kb_documents` — uploaded or manual text
- `kb_chunks` — parsed content for retrieval
- `kb_pricing_entries` — structured price data
- `kb_extension_notifications` — briefing hooks

**Services:**
- `kb_parsing_service.py` — Claude parses uploaded documents; extracts structured pricing into `kb_pricing_entries` automatically; supports PDF, DOCX, TXT, CSV, manual
- `kb_retrieval_service.py` — `retrieve_for_call()` called mid-call; pricing tier logic: matched CRM company → contractor tier, unmatched caller → show both tiers; returns brief answer for overlay display
- `kb_setup_service.py` — `seed_categories_for_tenant()` called on tenant create + extension enable

**Pages:**
- `/knowledge-base` — main KB page
- `/knowledge-base/{slug}` — category detail with document list + upload

**KB Coaching Banner:**
- `KBCoachingBanner.tsx` — adapts copy based on vertical + enabled extensions; dismissible per user (localStorage); re-shows when new extension enabled

**System categories by vertical:**
- ALL: Company Policies
- Manufacturing: Pricing, Product Specs, Personalization Options
- Manufacturing + Cemetery ext: Cemetery Policies
- Funeral Home: GPL, Service Packages, Grief Resources
- Cemetery: Equipment Policies, Section Policies

**Extension install notifications:**
- When extension activated → inserts into `kb_extension_notifications` with `briefing_date = tomorrow`
- Admin morning briefing shows recommendation to add related KB content

---

#### Price Management + PDF Generation (Complete)

**Tables:**
- `price_list_versions` — version history
- `price_list_items` — items per version (includes previous prices for comparison)
- `price_list_templates` — PDF layout settings
- `price_update_settings` — rounding prefs per tenant

**Pages:**
- `/pricing` — 3 tabs: Current Price List, Price Increase Tool (4-step wizard), Version History
- `/pricing/templates` — template builder with live HTML preview
- `/pricing/{version_id}/send` — bulk email UI

**Price Increase Tool flow:**
1. Select scope (entire list / category / individual items)
2. Set percentage + tiers (standard / contractor / homeowner); multiple rules allowed (different % per category)
3. Rounding from settings (none / nearest $1 / nearest $5 / nearest $10 / manual)
4. Schedule with effective date

**Effective date logic:**
- Orders created ON OR AFTER effective date get new pricing
- Orders created BEFORE effective date keep original pricing regardless of status
- Draft orders keep old pricing
- Activates automatically at midnight
- Day-before reminder to admins at 8am
- Midnight notification to all office staff

**PDF Generation:**
- weasyprint (HTML → PDF)
- Layouts: grouped (by category) or flat; 1 or 2 column
- Branding: logo, primary color, header/footer text
- Layout replication: upload existing PDF → Claude analyzes structure → applies detected settings
- Sunnycrest layout reference: 2 pages, 2-column, navy category headers, medium blue sub-category headers, logo top-left in circle, serif headers, bullet point items, right-aligned prices

**Cross-tenant pricing (foundation only):**
- Architecture placeholder in `activate_price_version()`
- Full implementation deferred until funeral home vertical is built
- Will use `platform_tenant_relationships`

**Services:**
- `price_increase_service.py` — `calculate_price_increase()`, `apply_price_increase()`, `activate_price_version()`
- `price_list_pdf_service.py` — `generate_price_list_pdf()`
- `price_activation_task.py` — midnight activation scheduler, 8am day-before reminder

---

#### Platform Email Infrastructure (Complete)

**Tables:**
- `platform_email_settings` — per tenant
- `email_sends` — audit log of all emails

**Sending modes:**
- **Platform mode (default):** Resend API (`RESEND_API_KEY` in Railway); from: `noreply@mail.getbridgeable.com`; reply-to: tenant's real email
- **SMTP mode (optional):** Tenant provides own SMTP credentials; encrypted at rest; test send verification before saving

**Service:** `email_service.py`
- `send_email()` — single email
- `send_price_list_email()` — bulk to FH list; generates PDF once, sends to all; individual or all funeral home customers

**Page:** `/settings/email`
- Sending mode toggle, from name + reply-to config, SMTP credentials (optional), test send button, BCC preferences, email history table

**Used by:** invoices, statements, legacy proofs, price lists (all email goes through this service)

**ENV VARS:** `RESEND_API_KEY` (already in Railway); domain verified: `getbridgeable.com` — SPF/DKIM records in Cloudflare

---

#### Staging Environment (Complete)

**Railway staging environment** — created by duplicating production, separate PostgreSQL instance.

| Service | URL |
|---------|-----|
| Backend | `sunnycresterp-staging.up.railway.app` |
| Frontend | `determined-renewal-staging.up.railway.app` |
| Postgres | Separate staging DB |

**Migration status:** `z9g4h5i6j7k8` (head)

**Seed data** (`backend/scripts/seed_staging.py`):
- Tenant: `staging-test-001` / Test Vault Co
- Users: admin, office, driver, production (passwords: `TestAdmin123!` etc.)
- 8 company entities (5 FH + 3 cemeteries)
- 10 contacts, 25 products across 6 categories
- 10 orders in various states, 3 invoices (paid/outstanding/overdue)
- 1 active price list version, 5 KB categories + 1 manual doc

**Test Suite Results (Final):**

| Suite | File | Results |
|-------|------|---------|
| API | `backend/tests/test_comprehensive.py` | 43/44 passed, 1 skipped (contacts route path, non-blocking) |
| Business flows | `frontend/tests/e2e/business-flows.spec.ts` | 44/44 passed |
| Automated flows | `frontend/tests/e2e/automated-flows.spec.ts` | 34/34 passed |
| **Total** | | **121/122 passing** |

```bash
# Run API tests
cd backend && source .venv/bin/activate
python3 -m pytest tests/test_comprehensive.py -v --tb=short

# Run E2E tests
cd frontend && npx playwright test --project=chromium
```

**Critical fixes deployed to staging:**
- Driver permissions + console page at `/driver`
- Auto-delivery eligibility fix (`scheduled_date <= today`, `required_date` fallback)
- Statement run page at `/ar/statements`
- Internal trigger endpoints at `/api/v1/internal/` (preview + execute auto-delivery)
- Job audit logging (`job_runs` table)
- `shipped` → `delivered` status rename throughout (migration + backward compat)

**Known staging quirk:** Tenant slug not auto-detected from Railway URL — use `?slug=testco` query parameter on first visit (persists to localStorage automatically). Fixed in codebase: `frontend/src/lib/tenant.ts` bootstraps slug from `?slug=` param.

---

#### CRM Visibility Bug Fix (April 7, 2026)

**Bug:** `crm_visibility_service.py` `never_visible` filter hid records where `customer_type IS NULL` — even when `is_funeral_home=True` or `is_cemetery=True`. This caused all company entities without an explicit `customer_type` to be invisible in the CRM.

**Fix:** Added role flag guards (`is_funeral_home`, `is_cemetery`, `is_licensee`, `is_crematory`, `is_vendor`) to the unclassified exclusion in all 3 functions: `get_crm_visible_filter()`, `get_hidden_count()`, `get_hidden_companies()`. Records with role flags are no longer treated as "unclassified."

**Impact:** Affected any tenant where company_entities were created with role flags but without `customer_type` set. Staging data patched (28 FH + 255 cemetery entities).

---

#### Production Status

**Sunnycrest is live at:** `sunnycrest.getbridgeable.com`

- Go-live date: April 7, 2026
- First tenant: Sunnycrest Vault (James Atkinson)
- Migration head: `r15_safety_program_generation`

**All core features production-ready:**
- ✅ Order management
- ✅ Invoice + AR system
- ✅ CRM (`company_entities`)
- ✅ Cemetery system
- ✅ Call Intelligence (RC connected)
- ✅ Knowledge Base
- ✅ Price Management
- ✅ Platform Email (Resend)
- ✅ Morning Briefing
- ✅ Onboarding checklist
- ✅ Staging environment + test suites (121/122 passing)
- ✅ Driver console (`/driver`)
- ✅ Monthly statements (`/ar/statements`)
- ✅ Auto-delivery with eligibility preview (`/api/v1/internal/trigger-auto-delivery`)
- ✅ Job audit logging (`job_runs` table)
- ✅ Urn Sales extension (37/37 E2E passing)
- ✅ Wilbert catalog ingestion pipeline (PDF + web + pricing)
- ✅ Catalog PDF auto-fetch with hash-based change detection
- ✅ Social Service Certificates (auto-generate + approve + email)
- ✅ Monthly Safety Program Generation (OSHA scrape + Claude AI + PDF + approval workflow, 12/12 E2E passing)

**Next build focus:** Funeral Home vertical — Phase FH-1 prompts ready. Key dependency: 70-field case file data model (design with AI Arrangement Scribe in mind from day one).
