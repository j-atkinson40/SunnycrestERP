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

- **Bridgeable Documents — Phase D-7 Delivery Abstraction (complete):** Channel-agnostic send interface — every email / SMS / future-channel send in the platform flows through one service with full audit trail. "Integrate now, make native later" made concrete: when Bridgeable's native email ships, it plugs in as a new channel implementation without any caller changes. **Migration `r26_delivery_abstraction`**: creates `document_deliveries` table (company_id + document_id + channel + recipient_type/value/name + subject + body_preview + template_key + status + provider + provider_message_id + provider_response JSONB + error_message/code + retry_count/max_retries + scheduled_for + sent_at/delivered_at/failed_at + caller_module + 4 caller_* linkage FKs + metadata_json), adds 6 targeted indexes (partial indexes on active states and non-null FKs for efficient queries), and extends `intelligence_executions.caller_delivery_id` closing the symmetric-linkage loop with D-6 (AI executions traceable to the delivery they triggered, deliveries traceable to the execution that drafted them). **`app.services.delivery` package** — protocol-based channel interface + orchestrator: `channels/base.py` defines the `DeliveryChannel` Protocol + `Recipient`, `Attachment`, `ChannelSendRequest`, `ChannelSendResult` dataclasses (duck-typed — any class with `channel_type` + `provider` class attrs + `send` method qualifies). `channels/email_channel.py` wraps Resend — the **ONLY module in the codebase allowed to import `resend`** (lint-enforced via `test_documents_d7_lint.py`), error classification maps connection/timeout errors to retryable and auth/validation to non-retryable. `channels/sms_channel.py` stubs with `success=False, error_code="NOT_IMPLEMENTED", retryable=False` so SMS callers get clean `status=rejected` rather than crashes. **`delivery_service.py` orchestrator**: resolves content (calls `document_renderer.render_html()` when `template_key` set, else uses caller-supplied body), fetches + attaches document PDF when `document_id` set and channel supports attachments (best-effort — R2 miss logs but doesn't block send), creates `DocumentDelivery` row with `status=pending` before dispatch, dispatches via `get_channel(channel).send()`, inline-retries retryable errors bounded by `max_retries` (default 3), updates row with provider response + status (`sent` on success, `failed` after exhaustion, `rejected` for non-retryable like SMS stub). Convenience builders: `send_email_with_template`, `send_email_raw`. **`send_document` workflow step type** — promoted to top-level like `ai_prompt` in Phase 3d. `_execute_send_document` reads config (`channel`, `recipient`, `template_key`/`template_context` OR `body`, `subject`, `reply_to`, optional `document_id`), auto-populates `caller_workflow_run_id` + `caller_workflow_step_id`, returns `{delivery_id, status, provider_message_id, error_message, channel, recipient}` referenceable by downstream steps. **7 email caller categories migrated** through DeliveryService while keeping public signatures intact: signing invite/completed/declined/voided (`signing/notification_service.py` — signature envelope linkage auto-populated), statement (`email_service.send_statement_email`), collections, user invitation, accountant invitation, alert digest, invoice, legacy proof (`legacy_email_service.send_email`). Test-mode behavior preserved (no API key = logs + no-op). **Admin UI** — new `/admin/documents/deliveries` DeliveryLog page (channel + status + recipient-search + template-key filters, 7 columns, status color coding with 7 states), `/admin/documents/deliveries/{id}` DeliveryDetail (metadata + template + error details + 6 linkage rows with clickable links to Document / Workflow Run / Intelligence Execution / Signature Envelope + body preview + provider response JSONB + Resend button). Nav entry "Delivery Log" under Platform admin. **4 new API endpoints** on `/documents-v2/*`: `GET /deliveries` (list with filters, defaults last 7 days), `GET /deliveries/{id}` (detail, tenant-scoped 404 otherwise), `POST /deliveries/{id}/resend` (reuses preserved inputs — templates re-render with current content so resend-after-edit uses the newer version), `POST /deliveries` (ad-hoc admin send). **Tests:** 31 new D-7 tests in `test_documents_d7_delivery.py` covering channel registry (6 — email/sms providers, unknown channel, attachment+html support flags, register_channel for provider swap), SMS stub behavior (1), DeliveryService core (8 — row creation, body/template rendering, failure handling, SMS rejection, signature envelope linkage, missing content rejection, unknown channel rejection), retry logic (3 — retryable increments then fails, non-retryable fails immediately, retry-then-success), workflow integration (4 — step creates delivery + populates linkage + rejects missing channel/recipient), migrated callers (5 — statement/collections/invitation/alert-digest/signing-invite create delivery rows with template_key + caller_module populated), empty-alert short-circuit (1), admin API (3 — list tenant-scoped, get detail, cross-tenant 404). Plus 2 lint tests enforcing `resend` imports outside EmailChannel. Test fixture updates on D-2/D-4/D-5/D-6 suites for the new `document_deliveries` table. Total: 661 passed, 2 skipped (was 628 D-6, +31 delivery + 2 lint) — no regressions. Migration head: `r26_delivery_abstraction`. New architecture doc: `backend/docs/delivery_architecture.md` (full protocol walkthrough, channel registry, content resolution, retry semantics, how to add a new channel, migrated caller table). DEBT.md: 4 new entries (inline retry vs background queue, Resend webhook callbacks not wired, bulk send not implemented, scheduled_send column exists but unused). **Deferred per spec:** native email/SMS implementations (separate workstreams), bulk send, scheduled send, Resend webhook handling for `delivered` status, SendDocumentConfig frontend designer component (D-8 polish alongside the workflow builder pass).
- **Bridgeable Documents — Phase D-6 Cross-Tenant Document Fabric (complete):** Unified cross-tenant document sharing that replaces 4 ad-hoc mechanisms (statements-as-email-attachments, VaultItem.shared_with_company_ids for delivery media, raw cross-tenant statement rows, implicit legacy-vault-print sharing) with one `document_shares` table + service + lint-enforced query abstraction. **Migration `r25_document_sharing`**: creates `document_shares` (document_id + owner/target + permission/reason + granted/revoked timestamps + source_module, partial unique index on `(document_id, target) WHERE revoked_at IS NULL`), `document_share_events` (append-only audit of granted/revoked/accessed events, sequence by created_at DESC), and adds `intelligence_executions.caller_document_share_id` FK completing the symmetric Intelligence-linkage pattern. **Owner-tenant model:** Option A chosen over copy-on-share — one source of truth owned by the creating tenant, target tenants see the same storage_key via active share rows, revocation is a timestamp flag on the share row not a data delete. **`Document.visible_to(company_id)` class method** — returns `or_(Document.company_id == X, EXISTS(active share to X))` — the single SQL expression that unifies owned + shared visibility. Every cross-tenant-relevant query in `documents_v2.py` (`_get_visible_document`, `list_documents`, `list_document_log`) rewrote to use it. Owner-only operations (grant, revoke) use separate `_get_owned_document_or_404` helper that rejects even valid shared-read visibility because *writing* requires ownership. **`document_sharing_service`** with `grant_share` (requires active `PlatformTenantRelationship` either direction — structural boundary against ad-hoc proliferation), `revoke_share` (timestamp-only, future-access cutoff, explicit UI copy about already-downloaded copies being outside platform control), `ensure_share` (idempotent variant for auto-generated shares from migrated generators — bypasses relationship check because the generator's existence evidences the business relationship), `list_outgoing_shares`, `list_incoming_shares`, `record_access`, `list_events_for_share`. Re-granting after revocation creates a new row — audit trail stays linear, revoked rows preserved forever. **5 new API endpoints** on `/documents-v2/*`: `POST /{id}/shares` (grant — owner-only, 201), `GET /{id}/shares` (list outgoing — owner-only), `POST /shares/{id}/revoke`, `GET /shares/{id}/events` (visible to owner OR target), `GET /inbox` (documents shared TO this tenant, combines share + Document metadata + owner company name). **Generator migrations (3 of 6 document types from audit):** `cross_tenant_statement_service.deliver_statement_cross_tenant` registers a share alongside the existing ReceivedStatement row; `delivery_service._sync_media_to_vault` creates a per-delivery canonical `delivery_confirmation` Document + share (VaultItem writes keep running for backward compat); `legacy_vault_print_service.generate` auto-shares with `vault_manufacturer_company_id`. The other 3 (training certs, COIs, licensee transfer notifications) were identified in audit as conceptual cross-tenant flows without backing platform generators — D-6 infrastructure is ready for them; when their generators ship they call `ensure_share()` following the same pattern. **Admin UI:** new `/admin/documents/inbox` page (tenant's incoming shares with filters for document_type + include_revoked, clickable to DocumentDetail, status badges), new `DocumentSharesPanel` component on DocumentDetail (outbox table with grant/revoke actions, owner-only — target tenants see a read-only acknowledgment), fork dialog with typed target UUID + reason, explicit revoke confirmation warning about already-downloaded copies. Nav entry "Inbox" added under Platform admin. **Lint gate** (`test_documents_d6_lint.py`) enforces `Document.visible_to()` usage — direct `Document.company_id == X` filters are forbidden outside a permanent allowlist of owner-only paths (renderer, sharing service, legacy document service, signing services, generator paths, etc). 19 files on the allowlist with per-file justification comments. **Tests:** 29 new D-6 tests in `test_documents_d6_sharing.py` covering grant (7 — with/without relationship, self-target rejection, duplicate active rejection, event write, relationship both-directions, ensure_share idempotency, ensure_share bypass), revoke + re-grant (4), `visible_to()` (5 — owner sees, non-owner without share doesn't, share target sees, revoked hides, is_visible_to instance method), listing (3 — outgoing/incoming/exclude-revoked), audit append-only (2 — service has no update/delete, record_access doesn't mutate share), generator migrations (3 — statement creates share, legacy vault print helper, same-tenant noop), API permission gates (3 — cannot grant non-owned, owner can fetch owned, visible_document resolves shared), Intelligence linkage (1 — column exists). Plus 2 lint tests. Fixtures updated on D-1 + D-3 suites for new `document_shares` / `document_share_events` tables. Total: 628 passed, 2 skipped (was 597 D-5, +29 sharing + 2 lint) — no regressions once fixtures updated. Migration head: `r25_document_sharing`. Architecture doc `documents_architecture.md` extended with "Cross-tenant document sharing (D-6)" section covering model, grant/revoke semantics, `visible_to()` contract, migrated types, and inbox design. DEBT.md: pre-D-6 data backfill script flagged as needing future work (admin inbox shows post-D-6 shares only until backfill runs); 3 deferred document types flagged as "infra-ready, awaiting generators."
- **Bridgeable Documents — Phase D-5 Disinterment Migration + Anchor-Based Signature Overlay (complete):** Disinterment release form signing fully migrated from DocuSign to native signing. Cover-page signature approach replaced with PyMuPDF-based anchor overlay — signatures now render directly on the signature lines of the source document, matching the visual quality DocuSign provides. **Migration `r24_disinterment_native_signing`**: adds `disinterment_cases.signature_envelope_id` FK (nullable, partial index `WHERE NOT NULL`), keeps `docusign_envelope_id` + `sig_*` columns for backward compat. Adds `signature_fields.anchor_x_offset`, `anchor_y_offset`, `anchor_units` for fine-tuning placement without re-rendering the source template. **Anchor overlay engine** — two new internal modules in `app/services/signing/`: `_overlay_engine.py` (PyMuPDF-based single-pass overlay — opens source PDF once, calls `page.search_for(anchor)` to resolve positions, places every signature via `page.insert_image()`, returns modified bytes; missed anchors collected for audit events), `_signature_image.py` (PIL-based signature image generation — drawn signatures decode base64 PNG and resize preserving aspect ratio; typed signatures render via Caveat-Regular.ttf if bundled, PIL default otherwise, with auto-shrink to fit target bounds; 3× PPI for print-quality crispness). `signature_renderer.py` rewritten to use the new engine with a cover-page fallback if overlay fails (missing R2, PDF corruption, all anchors unresolvable). **Disinterment flow rewiring:** `disinterment_service.send_for_signatures` replaced the DocuSign-specific implementation with a native-signing call — creates envelope with 4 parties (`funeral_home_director`, `cemetery_rep`, `next_of_kin`, `manufacturer`) in sequential routing, each with an anchor-mapped signature field (`/sig_funeral_home/`, etc). Stricter validation: missing name/email for any party raises `ValueError` (DocuSign path silently skipped missing parties). **sig_* column sync:** `signature_service.sync_disinterment_case_status` called on every state transition (view, consent, sign, decline, void, complete) to mirror envelope party state into the legacy `sig_*` columns — existing code reading those fields continues to see coherent state. Case transitions to `signatures_complete` when envelope completes. **`FieldInput` enhancement:** now accepts `party_role` (decouples field definition from party ordering) OR `signing_order`. Also accepts `anchor_x_offset`, `anchor_y_offset`, `anchor_units`. **DocuSign deprecation (soft):** `docusign_service.py` and `docusign_webhook.py` stay alive for any in-flight DocuSign envelopes created pre-cutover. `create_envelope` emits `DeprecationWarning`; module docstrings flag deprecation with SQL query for tracking remaining legacy envelopes. No new DocuSign envelopes originate from the codebase. **Template already compatible:** the disinterment release-form template has styled `.sig-anchor` as `color: white; font-size: 1px` since D-1 — anchors are already invisible in rendered PDFs while remaining extractable by text search. No template update needed. **Frontend updates:** `disinterment-detail.tsx` reads `signature_envelope_id` in addition to `docusign_envelope_id`, shows "View signature envelope" link when native envelope exists (routes to `/admin/documents/signing/envelopes/{id}`), falls back to "Legacy DocuSign envelope: {id}" readout for pre-cutover cases. "Sent for signatures via DocuSign" toast → "Sent for signatures". **Visual verification:** end-to-end test renders a 4-party disinterment form and applies typed signatures; all 4 anchors resolve (x0=200, y spaced 60pt), all 4 overlays apply cleanly (`applied=4, missed=[]`), signed PDF grows from 3KB to 1.14MB (PNG signatures embedded). **Tests:** 22 new D-5 tests in `test_documents_d5_signing.py` covering anchor overlay primitives (5 — placement, multi-signature single pass, missing-anchor fallback, skip-without-position, offset respect), signature image generation (6 — drawn PNG, data-URI strip, typed PNG, party-resolver drawn/typed/empty paths), field party-role resolution (3), disinterment case sync (5 — consent/sign/complete/decline/null-docusign_envelope_id), DocuSign deprecation (3 — importable, warning emitted, webhook module still importable). Total: 597 passed, 2 skipped (was 575 D-4, +22 D-5) — no regressions. Migration head: `r24_disinterment_native_signing`. Architecture doc `signing_architecture.md` extended with "Anchor-based overlay" and "Disinterment migration (D-5)" sections. DEBT.md: marked cover-page-vs-overlay resolved, DocuSign-active reframed as "pending deletion after legacy envelopes resolve" with SQL tracking query, added cremation-authorization deferred entry. Cremation authorization migration remains deferred to a separate focused build as spec'd.
- **Bridgeable Documents — Phase D-4 Native Signing Infrastructure (complete):** Full e-signature infrastructure replacing DocuSign — US ESIGN Act compliant, runs in parallel with existing DocuSign integration. D-4 does NOT migrate any existing flows; D-5 will swap disinterment. **Migration `r23_native_signing`**: creates 4 tables (`signature_envelopes`, `signature_parties`, `signature_fields`, `signature_events` — the last is append-only by service-layer contract) and seeds 5 new platform templates (`pdf.signature_certificate` for the ESIGN-compliant Certificate of Completion, plus `email.signing_invite` / `signing_completed` / `signing_declined` / `signing_voided`). **Envelope state machine:** `draft → sent → in_progress → completed/declined/voided/expired`. **Party state machine:** `pending → sent → viewed → consented → signed/declined/expired`. Every state transition writes a `SignatureEvent` with monotonically-increasing `sequence_number` per envelope + `meta_json` for event-specific data (previous_active_version_id, rolled_back_to_version_id, etc). **`app.services.signing` package** — 5 modules: `token_service` (256-bit cryptographic tokens via `secrets.token_urlsafe(32)`), `signature_service` (envelope CRUD + lifecycle — `create_envelope`, `send_envelope`, `record_party_view`, `record_party_consent`, `record_party_signature`, `record_party_decline`, `void_envelope`, `resend_notification`, `complete_envelope`, `check_expiration`), `signature_renderer` (applies signatures to a new DocumentVersion via a signatures cover page — anchor-based inline overlay is D-5), `certificate_service` (renders Certificate of Completion via managed template with parties, signatures, IPs, hashes, event timeline), `notification_service` (5 email types via existing EmailService + managed templates). **Document hashing:** SHA-256 of the PDF captured at envelope creation + at completion for tamper detection. **Public signer routes** `/api/v1/sign/*` (no auth — `signer_token` is sole auth mechanism, in-process token-bucket rate limit of 10 req/min per token): `GET /{token}/status` (returns envelope + party status + is_my_turn + signed-by-previous-parties for sequential routing), `GET /{token}/document` (307 redirect to presigned R2 URL, records `link_viewed` event), `POST /{token}/consent` (records ESIGN consent text), `POST /{token}/sign` (captures signature + field values, advances routing, completes envelope if last party), `POST /{token}/decline` (cancels envelope). **Admin routes** `/api/v1/admin/signing/*` (admin-gated, tenant-scoped): `POST /envelopes` (create in draft), `POST /envelopes/{id}/send` (transition draft → sent, notify), `GET /envelopes` (list with status/document filters), `GET /envelopes/{id}` (detail with parties+fields), `POST /envelopes/{id}/void` (with reason, cancels pending parties), `POST /parties/{id}/resend` (resend invite email, increments counter), `GET /envelopes/{id}/events` (paginated audit timeline). **Frontend signer experience** `/sign/{token}` — 4-step public page: Welcome → Review (embedded iframe PDF) → Consent (ESIGN checkbox) → Sign (Draw canvas with mouse/touch support OR Type in Caveat-style script font). Terminal screens for expired/voided/declined/completed/not-my-turn. Decline modal with 10-500 char reason. **Frontend admin UI** under `/admin/documents/signing/`: `SigningEnvelopeLibrary` (table with status filter, "New envelope" button), `SigningEnvelopeDetail` (parties table with resend-notification, fields table, events timeline, void/send actions, download signed PDF + certificate when completed), `CreateEnvelopeWizard` (4-step: select document → add signers → add signature fields → review & create). Nav entry "Signing" under Platform admin. **Tests:** 31 new backend tests in `test_documents_d4_signing.py` covering envelope creation (5), send lifecycle (3), signer flow (6 — view/consent/sign/decline/completion/sequential-advance), field handling (2 — persistence, required-field enforcement), void + resend + expiration (3), tamper detection hash (2), audit integrity (3), public route token validation + rate limiting (2), permission gates (2), token uniqueness (2). Public routes tested end-to-end via FastAPI TestClient. Total: 575 passed, 2 skipped (was 544 in D-3) — no regressions. **Deferred per spec:** disinterment migration (D-5), workflow engine `request_signature` step type (D-5+), SMS verification (awaits native SMS), notarization (indefinite), bulk signing (indefinite), anchor-based inline signature overlay (D-5+), DocuSign deprecation (after D-5 migrations complete). Migration head: `r23_native_signing`. New architecture doc: `backend/docs/signing_architecture.md` (full state-machine + ESIGN compliance walkthrough + developer usage).
- **Bridgeable Documents — Phase D-3 Template Editing + Versioning (complete):** D-3 adds the editing surface on top of D-2's read-only template registry. Tenant admins can create draft versions, preview them (client-side Jinja substitution), test-render them (backend-backed, flagged test documents), and activate them with diff + changelog safety gates. Platform templates can only be edited by super_admins with typed-confirmation-text; tenant admins can **fork** a platform template to their tenant (creates a tenant-scoped copy with independent v1 starting history that auto-overrides the platform via D-2's hybrid lookup). **Migration `r22_document_template_editing`**: adds `documents.is_test_render` (Boolean, default False) with partial index `WHERE is_test_render = TRUE`, creates `document_template_audit_log` table (template_id + nullable version_id + action + actor + changelog + jsonb meta + created_at). **New model:** `DocumentTemplateAuditLog` mirrors `IntelligencePromptAuditLog`. **New service:** `template_validator.py` uses `jinja2.meta.find_undeclared_variables` (real AST parsing, auto-excludes loop locals) to detect `undeclared_variable` (error — blocks activation), `unused_variable` (warning — unless marked `{"optional": true}`), and `invalid_jinja_syntax` (error). **Extended `template_service.py`** with `create_draft`, `update_draft`, `delete_draft`, `activate_version`, `rollback_to_version`, `fork_platform_to_tenant`, `write_audit`, `list_audit`. Rollback creates a monotonically-numbered new active version cloning the retired target's content (target stays retired — no row is ever reactivated, keeping the audit trail linear). **`document_renderer.render()` accepts `is_test_render`** kwarg; production code path unchanged. **Document Log endpoint** excludes test renders by default — `include_test_renders=true` opts in. **8 new API endpoints** under `/api/v1/documents-v2/admin/templates/{template_id}/`: `GET /edit-permission` (preflight for UI — returns `can_edit`, `requires_super_admin`, `requires_confirmation_text`, `can_fork`); `POST /versions/draft` (409 if draft exists); `PATCH /versions/{id}` (drafts only); `DELETE /versions/{id}` (drafts only); `POST /versions/{id}/activate` (validates variable schema — 400 with issue list on errors; 409 on non-draft; writes audit row); `POST /versions/{id}/rollback`; `POST /fork-to-tenant`; `POST /versions/{id}/test-render` (any version status — draft/active/retired; PDF path creates flagged Document, HTML/text returns string); `GET /audit` (paginated timeline). Platform-global activations + rollbacks require `confirmation_text == template_key`. **Frontend — template editor** on `DocumentTemplateDetail.tsx`: mode toggle (view / edit), body + subject (email only) + variable_schema + css_variables + changelog fields, save draft / preview / test-render / activate / discard / cancel toolbar, draft indicator banner. **Five new modal components** in `components/documents/`: `TemplatePreviewModal` (client-side substitution, iframe HTML preview, disclaimer about control-flow limitations), `TemplateTestRenderModal` (JSON context editor, cost hint, iframe/PDF result), `TemplateActivationDialog` (side-by-side field diff, changelog editor, platform-template confirmation field, inline validation issues), `TemplateRollbackDialog` (target version content + changelog + confirmation), `TemplateForkDialog` (fork explanation with bullets). `DocumentTemplateLibrary` shows "draft" badge when a template has a draft in progress (backend preloads `has_draft` in one query, no N+1). **Tests:** 36 new D-3 tests in `test_documents_d3.py` covering draft lifecycle (5), activation (4), rollback (3), fork (4), variable schema validation (6), test render flag (2), audit log (5), Document Log test-render exclusion (2), permission gates (4), plus SQLite-in-memory fixture extensions. Total: 544 passed, 2 skipped — no regressions. Migration head: `r22_document_template_editing`. Architecture doc `backend/docs/documents_architecture.md` extended with "Template editing (D-3)" section covering draft lifecycle diagram, permission model table, validation semantics, test-render isolation, audit log shape. DEBT.md adds entries for client-side preview simplification and deferred email test sending (D-7).
- **Bridgeable Documents — Phase D-2 Template Registry + Admin Read Surface (complete):** Managed template registry replaces the file-based template loader from D-1. Two new tables (`document_templates`, `document_template_versions`) with hybrid scoping — platform templates have `company_id=NULL`, tenants override per `template_key`. Lookup is tenant-first-platform-fallback. Phase D-1 backbone extended to support `output_format: "pdf" | "html" | "text"` — PDF still creates canonical `Document` + `DocumentVersion` rows via WeasyPrint + R2; HTML and text render Jinja and return a `RenderResult` (no Document row, no R2 upload). `document_renderer.render_html()`, `render_text()`, and `render_pdf_bytes()` are new convenience wrappers. **Migration `r21_document_template_registry`** seeds 18 platform templates: 8 PDF migrated from `backend/app/templates/*.html`, 3 PDF migrated from inline Python strings (`pdf.social_service_certificate`, `pdf.legacy_vault_print`, `pdf.safety_program_base`), and 7 email templates from `email_service.py` + `legacy_email_service.py` (`email.base_wrapper`, `email.statement`, `email.collections`, `email.invitation`, `email.accountant_invitation`, `email.alert_digest`, `email.legacy_proof`). Each seed creates a template row + version-1 active row; partial unique index on `(company_id, template_key) WHERE deleted_at IS NULL` enforces scope uniqueness. **3 inline generators migrated:** `social_service_certificate_pdf.py`'s legacy `generate_social_service_certificate_pdf()` signature preserved (routes through `render_pdf_bytes`), new canonical `generate_social_service_certificate_document()` available for callers wanting a Document row; `legacy_vault_print_service.py::generate()` now produces a canonical `Document` via `document_renderer.render()` + keeps the static-disk secondary write for old URL consumers; `safety_program_generation_service._wrap_program_html` routes through `document_renderer.render_html(template_key="pdf.safety_program_base", ...)` with Claude's generated HTML embedded via `{{ ai_generated_html|safe }}`, and `generate_pdf()` now routes through `document_renderer.render()` to produce canonical Documents (fixes the pre-existing bug where it was inserting legacy Document rows against a canonical FK). **Email templates migrated:** every `EmailService` content-builder now routes through `document_renderer.render_html()` with the appropriate `email.*` template_key. Subject templates render alongside bodies; tenants customize branding by inserting a tenant-scoped row with the same template_key. **Admin UI read surface (4 pages at `/admin/documents/*`):** `DocumentTemplateLibrary` (filters: document_type / output_format / scope / status / search; URL-persistent), `DocumentTemplateDetail` (active version body + subject + variable schema + CSS vars + version history with click-to-view), `DocumentLog` (last-7-day default; filters: document_type / template_key / status / entity_type / intelligence_generated with clickable AI link to the source execution), `DocumentDetail` (full linkage summary, version history with per-version downloads, regenerate dialog). Nav entries added under Platform admin: "Documents" + "Document Log". **API additions on `/api/v1/documents-v2/*`:** `GET /log` (rich Document Log schema), `GET /admin/templates` (with `DocumentTemplateFilterResponse` paginated envelope), `GET /admin/templates/{id}`, `GET /admin/templates/{id}/versions/{version_id}`. Extended existing list endpoint with `template_key` + `intelligence_generated` filters. **Ruff rule tightening (TID251):** `weasyprint` imports forbidden outside `app/services/documents/**`. Permanent allowlist: renderer + `app/main.py` diagnostic import. Transitional allowlist (3 entries queued for post-D-2 migration): `pdf_generation_service.generate_template_preview_pdf`, `quote_service.generate_quote_pdf`, `wilbert_utils` Wilbert form PDF. Enforcement via pytest `test_documents_d2_lint.py` (ruff not installed); test fails if any new weasyprint usage appears outside the allowlist, and if any transitional entry stops using weasyprint (forcing removal). **Tests:** 23 new D-2 tests in `test_documents_d2.py` (template registry scoping, renderer format dispatch, migrated generators, migrated email templates, template_service visibility rules, lint smoke) + 3 lint tests in `test_documents_d2_lint.py`. Total: 508 passed, 2 skipped — no regressions. Migration head: `r21_document_template_registry`. Architecture doc: `backend/docs/documents_architecture.md` updated with template registry + hybrid scoping + seeded-templates table + D-3 roadmap. DEBT.md marked inline-HTML generators + email templates resolved; flagged 3 remaining transitional weasyprint call sites + template-file-system cleanup.
- **Bridgeable Documents — Phase D-1 Backbone (complete):** Canonical `Document` + `DocumentVersion` model replaces ad-hoc PDF generation across the platform. Every template-rendered or AI-generated PDF now flows through `app.services.documents.document_renderer.render()` — Jinja template load → WeasyPrint HTML→PDF → R2 upload at `tenants/{company_id}/documents/{document_id}/v{n}.pdf` → inserts `documents` row + first `document_versions` row with `is_current=True`. Re-renders via `rerender()` flip the prior version's `is_current` and append a new version. The renderer computes a SHA-256 `rendering_context_hash` of the JSON-serialized context dict (stored on each version) for future dedup/change detection. **Migration `r20_documents_backbone`**: renames existing `documents` → `documents_legacy` (renaming its `ix_documents_*` indexes to `ix_documents_legacy_*` to avoid collision), creates the canonical `documents` table with polymorphic entity linkage (`entity_type`/`entity_id`) AND 7 specialty FKs (`sales_order_id`, `fh_case_id`, `disinterment_case_id`, `invoice_id`, `customer_statement_id`, `price_list_version_id`, `safety_program_generation_id`), source linkage (`caller_module`, `caller_workflow_run_id`, `caller_workflow_step_id`, `intelligence_execution_id`), and `document_versions` with a partial unique index on `(document_id) WHERE is_current=true`. Also adds `caller_document_id` FK on `intelligence_executions` for the reverse linkage (which AI call fed which document). **Coexistence with legacy model:** both `app.models.canonical_document.Document` (canonical) and `app.models.document.Document` (legacy, now backed by `documents_legacy`) live in the SQLAlchemy registry — string-based `relationship("Document", ...)` resolution hits a disambiguation error, so code uses direct class reference (`relationship(Document, ...)`) or the fully-qualified string `"app.models.canonical_document.Document"`. `SafetyProgramGeneration.pdf_document` FK rebound to canonical. **4 generators migrated:** `disinterment_pdf_service.generate_release_form_document()`, `pdf_generation_service.generate_invoice_document()`, `price_list_pdf_service.generate_price_list_document()`, and new `statement_pdf_service.generate_statement_document()` (wiring previously-orphaned statement Jinja templates). All legacy byte-returning functions (`generate_release_form_pdf`, `generate_invoice_pdf`, `generate_price_list_pdf`, `generate_release_form_base64`) preserved — they internally call the Document path then fetch bytes from R2, so existing callers in `routes/sales.py`, `routes/price_management.py`, and `docusign_service.py` keep working. **Workflow engine `generate_document` action wired:** previously a stub returning `pdf_url: None`, now `_handle_generate_document()` validates config, resolves `{input.*}`/`{output.*}` variables in context, calls `document_renderer.render()` with workflow linkage auto-populated from `run.trigger_context` (including entity_type→specialty FK routing via `_ENTITY_TYPE_TO_DOCUMENT_KWARG`), returns `{document_id, storage_key, pdf_url, version_number, document_type}` for downstream steps. **API at `/api/v1/documents-v2/*`** (admin-gated, tenant-scoped): GET list with filters (document_type, entity_type/entity_id, status, date range), GET detail with full version history, GET download (307 → presigned R2 URL, 1h TTL), GET version-specific download, POST regenerate. Legacy `/api/v1/documents/*` routes continue to serve the old Document model against `documents_legacy`. **Frontend:** `GenerateDocumentConfig.tsx` replaces the generic JSON editor in WorkflowBuilder when `action_type === "generate_document"` — dropdowns for template_key + document_type, title/description fields, context JSON editor. **Not yet migrated (Phase D-2):** Social Service Certificate inline-HTML generator, Legacy Vault Print inline-HTML, Safety Program runtime Claude-generated HTML, and email templates in `email_service.py` + `legacy_email_service.py`. **Tests:** 18 new Phase D-1 tests in `test_documents_d1.py` covering renderer (creates doc+version, storage_key convention, linkage population, SHA-256 context hash, template/WeasyPrint failure paths), rerender (new version + is_current flip, missing-document error), disinterment generator (produces Document), workflow action (creates Document, linkage from trigger_context, rejects missing template_key), and API (tenant scoping, filtering, detail+versions, soft-delete hiding, require_admin declaration lint). Total: 261 passed, 2 skipped — no regressions. Migration head: `r20_documents_backbone`. Architecture doc: `backend/docs/documents_architecture.md`. Debt tracked in `backend/docs/DEBT.md` → "Legacy document models coexist with canonical Document".
- **Bridgeable Intelligence — unified AI layer (complete):** Every AI call in the platform routes through `app.services.intelligence.intelligence_service.execute(prompt_key=..., variables=..., company_id=..., caller_module=..., caller_entity_*=...)`. The managed prompt library has 73 active platform-global prompts covering Scribe, accounting agents, briefings, command bar, NL Overlay, Ask Assistant, urn pipeline, safety, CRM, KB, onboarding, training, compose, workflows, and vision (check-image + PDF extraction). Every call produces an `intelligence_executions` audit row with prompt_id, model_used, input/output tokens, cost_usd, latency_ms, and typed caller linkage (`caller_fh_case_id`, `caller_agent_job_id`, `caller_workflow_run_id`, `caller_ringcentral_call_log_id`, `caller_kb_document_id`, `caller_price_list_import_id`, `caller_accounting_analysis_run_id`, `caller_command_bar_session_id`, `caller_conversation_id`, `caller_import_session_id`). Vision prompts use `content_blocks=[{type: "image"|"document", source: {type: "base64", media_type: ..., data: ...}}]`; raw base64 is redacted from `rendered_user_prompt` (sha256 + bytes_len only). Migration completed across 9 sub-phases (Phase 1 backbone → 2a/2b initial migrations → 2c-0a prompt batch + linkage columns → 2c-0b multimodal support → 2c-1/2/3/4 caller migrations → 2c-5 final cleanup). 14 direct-SDK callers + ~25 legacy-wrapper callers + 6 architectural-concern callers all migrated. `ai_service.py` legacy wrapper deleted. `/ai/prompt` endpoint deprecated (sunset 2027-04-18), internally routed through `legacy.arbitrary_prompt` managed prompt. TID251 ruff rule + pytest-based lint gate forbid any new `anthropic` SDK or `call_anthropic` imports outside the Intelligence package. Admin API at `/api/v1/intelligence/` exposes prompts/versions/executions/experiments/models/conversations CRUD. Migration head: `r18_intelligence_vision_support` (r16 backbone + r17 linkage columns + r18 vision columns). Audit artifact: `backend/docs/intelligence_audit_v3.md` (2,559 lines, every call site documented verbatim). Pre-existing bugs uncovered during migration tracked in `backend/docs/BUGS.md`. Intelligence tests: 154 passing. Total seed prompts: 73 platform-global (30 Phase 1 + 1 Phase 2a + 2 Phase 2b + 40 Phase 2c-0a + 3 Phase 2c-5).
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
