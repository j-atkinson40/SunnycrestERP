# CLAUDE.md — Bridgeable Platform

## 1. Project Overview

**Bridgeable** (getbridgeable.com) is a multi-tenant SaaS business management platform for the death care industry, specifically Wilbert burial vault licensees and their connected funeral homes. The platform manages the full operational lifecycle: funeral order processing, delivery scheduling, inventory, AR/AP, monthly billing, cross-licensee transfers, safety compliance, and financial reporting.

**Company context:**
- **Sunnycrest Precast** — the first customer and development partner (vault manufacturer in Auburn, NY)
- **Able Holdings** — the holding company that owns the Bridgeable platform
- **Wilbert** — national franchise network of ~200 burial vault licensees. Bridgeable targets this network as its primary market.
- **Strategic goal:** Demo at the September 2026 Wilbert licensee meeting. Multi-vertical SaaS expansion planned beyond death care.

**4 tenant presets:** `manufacturing` (primary, most features), `funeral_home`, `cemetery`, `crematory`

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
- **Database:** PostgreSQL on Railway (production), local PostgreSQL 16 (development)
- **File storage:** Railway persistent volume
- **No query library** — data fetching is plain Axios via `frontend/src/lib/api-client.ts`

### Third-Party Integrations
- **Claude API** (Anthropic) — AI briefings, content generation, collections drafts, product extraction
- **Google Places API** — funeral home discovery, cemetery geocoding
- **QuickBooks Online** — OAuth accounting sync (QBO provider in `backend/app/services/accounting/`)
- **Sage 100** — CSV export accounting sync
- **Twilio** — SMS delivery confirmations
- **Stripe** — payment processing (configured but not fully wired)

## 3. Architecture

### Multi-Tenant SaaS
- Tenants are `companies` records. All tenant-scoped tables have a `company_id` or `tenant_id` FK.
- Subdomain routing: `{slug}.getbridgeable.com` → tenant app, `admin.getbridgeable.com` → platform admin
- `isPlatformAdmin()` in `frontend/src/lib/platform.ts` detects `admin.*` subdomain
- Tenant isolation is enforced at the service layer — all queries filter by `company_id`

### OperationsBoardRegistry Pattern
Singleton registry (`frontend/src/services/operations-board-registry.ts`) where features register as `BoardContributor` objects. The board reads from the registry at render time and builds itself dynamically. Core features register as permanent contributors (`requires_extension: null`). Extensions register with their extension key and only render when that extension is active. Same pattern used for `FinancialsBoardRegistry`.

### AI Patterns
- **AIService** (`backend/app/services/ai_service.py`): Single `call_anthropic()` function, uses `claude-sonnet-4-20250514` by default. Forces JSON-only responses.
- **AICommandBar**: Frontend component for natural language input on various pages
- **ConfirmationCard**: Shows AI-extracted data for human review before saving
- **Briefing Service**: Uses `claude-haiku-4-5-20250514` for cost-effective daily briefings

### Extension System
Product line extensions (Wastewater, Redi-Rock, Rosetta) are tracked in `tenant_extensions`. When enabled, they register contributors to the Operations Board registry, add navigation items, and unlock additional features. Core modules are always available; extensions are per-tenant opt-in.

### Settings Pattern
Tenant settings are stored as a JSONB field on the `companies` table (`settings_json` column), accessed via `company.settings` property and `company.set_setting(key, value)` method. **Note:** A `tenant_settings` database table also exists (created by migrations) but is orphaned — application code uses `Company.settings_json` exclusively.

## 4. Database

- **234 tables** (232 with ORM models, 2 extension tables via catch-up migration)
- **Current migration head:** `r7_create_missing`
- **110 migration files** in `backend/alembic/versions/`
- **Single root:** `e1e2120b6b65` (create_users_table)

### Running Migrations Locally
```bash
cd backend && source .venv/bin/activate
DATABASE_URL=postgresql://localhost:5432/bridgeable_dev alembic upgrade head
```

### Idempotent Migrations
`backend/alembic/env.py` monkey-patches `op.add_column`, `op.create_table`, and `op.create_index` to be idempotent. This allows the same migration chain to run on both fresh databases and databases where tables were created outside the migration chain.

### Table Name Conventions
These are the **correct** table names (migrations were fixed from incorrect names):
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

## 5. Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app, middleware, startup/shutdown
│   ├── config.py             # pydantic-settings, reads .env
│   ├── database.py           # SQLAlchemy engine + SessionLocal
│   ├── scheduler.py          # APScheduler with 13 registered jobs
│   ├── worker.py             # Background job queue worker (polls DB/Redis)
│   ├── models/               # 155 SQLAlchemy model files
│   │   ├── __init__.py       # 170 model exports
│   │   ├── user.py, company.py, customer.py, ...
│   ├── services/             # 111 service files (business logic)
│   │   ├── ai_service.py     # Claude API wrapper
│   │   ├── agent_service.py  # AR/AP/Collections agents
│   │   ├── briefing_service.py
│   │   ├── onboarding_service.py  # MANUFACTURING_CHECKLIST_ITEMS
│   │   ├── accounting/       # QBO + Sage providers
│   │   └── ...
│   ├── api/
│   │   ├── v1.py             # Route aggregator (100 modules)
│   │   ├── deps.py           # Auth dependencies (get_current_user, require_admin)
│   │   ├── routes/           # 101 route files
│   │   └── platform.py       # Platform admin routes
│   ├── core/
│   │   └── security.py       # JWT + bcrypt utilities
│   └── jobs/
│       └── __init__.py       # Job handler registry
├── alembic/
│   ├── env.py                # Idempotent op wrappers
│   ├── idempotent_ops.py     # Helper module (not currently used — env.py patches instead)
│   └── versions/             # 110 migration files
├── data/
│   ├── us-county-tax-rates.json    # 452 county tax rate records
│   └── us-zip-county-mapping.json  # 107 zip-to-county mappings
├── static/safety-templates/        # Generated safety training PDFs
└── .env                            # LOCAL DATABASE ONLY

frontend/
├── src/
│   ├── App.tsx               # 180 routes, platform admin detection
│   ├── contexts/
│   │   └── auth-context.tsx  # JWT auth state, token refresh
│   ├── lib/
│   │   ├── api-client.ts     # Axios with token refresh interceptor
│   │   ├── platform.ts       # isPlatformAdmin(), platform mode
│   │   └── utils.ts          # cn() for tailwind class merging
│   ├── components/
│   │   ├── ui/               # shadcn/ui v4 components
│   │   ├── morning-briefing-card.tsx
│   │   ├── contextual-explanation.tsx
│   │   ├── confirmation-card.tsx
│   │   └── protected-route.tsx
│   ├── pages/                # Page components organized by feature
│   ├── services/
│   │   ├── navigation-service.ts        # Preset-driven nav
│   │   ├── operations-board-registry.ts # Board contributor registry
│   │   └── board-contributors/index.ts  # Core contributor registrations
│   └── types/
│       └── operations-board.ts
├── Dockerfile                # Node build → nginx serve, port 8080
├── nginx.conf
└── package.json
```

## 6. Environment Setup

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

### Required Environment Variables
**Backend** (`backend/.env`): `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `CORS_ORIGINS`

**Optional**: `ANTHROPIC_API_KEY`, `GOOGLE_PLACES_API_KEY`, `REDIS_URL`, `STRIPE_SECRET_KEY`, `QBO_CLIENT_ID`, `QBO_CLIENT_SECRET`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `PLATFORM_ADMIN_EMAIL`, `PLATFORM_ADMIN_PASSWORD`

### CRITICAL RULE
**Never point local `DATABASE_URL` at Railway production.** Production credentials live exclusively in the Railway dashboard.

## 7. URLs and Domains

| Environment | Frontend | Backend | Platform Admin |
|-------------|----------|---------|----------------|
| **Production** | app.getbridgeable.com | api.getbridgeable.com | admin.getbridgeable.com |
| **Local** | localhost:5173 | localhost:8000 | admin.localhost:5173 |

Tenant pattern: `{slug}.getbridgeable.com`

## 8. Key Features and Modules

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
| Tax System (jurisdictions, exemptions) | Built | `tax.py`, county_geographic_service.py` |
| Cross-Tenant Billing | Built | `cross_tenant_statement_service.py` |
| Financial Reports (13 types) | Built | `financial_report_service.py` |
| Audit Packages | Built | `report_intelligence_service.py` |

### Operations
| Feature | Status | Key Files |
|---------|--------|-----------|
| Operations Board (registry-driven) | Built | `operations-board.tsx`, `operations-board-registry.ts` |
| Financials Board (5 zones) | Built | `financials-board.tsx` |
| Order Management | Built | `sales_order.py`, `sales_service.py` |
| Delivery Scheduling | Built | `delivery.py`, `delivery_service.py` |
| Cross-Licensee Transfers | Built | `licensee_transfer.py`, `licensee_transfer_service.py` |
| Inter-Licensee Pricing | Built | `inter_licensee_pricing.py` |
| Delivery Intelligence | Built (schema) | `delivery_intelligence_service.py` |

### Safety & Compliance
| Feature | Status | Key Files |
|---------|--------|-----------|
| Safety Training (12 OSHA topics) | Built | `safety_training_system_service.py` |
| Equipment Inspections | Built | `safety_service.py` |
| Toolbox Talks + Suggestions | Built | `toolbox_suggestion_service.py` |
| OSHA 300 Log | Built | `osha_300_entry.py` |
| Compliance Score | Built | `safety_service.py` |

### Intelligence Layer
| Feature | Status | Key Files |
|---------|--------|-----------|
| Financial Health Scores | Built | `financial_health_service.py` |
| Cross-System Insights | Built | `cross_system_insight_service.py` |
| Behavioral Analytics | Built | `behavioral_analytics_service.py` |
| Network Intelligence | Built | `network_intelligence_service.py` |
| Report Commentary (AI) | Built | `report_intelligence_service.py` |

### Training System
| Feature | Status | Key Files |
|---------|--------|-----------|
| Curriculum Tracks | Built | `training_service.py`, `training_content_seed.py` |
| Procedure Library | Built | `procedure-library.tsx` |
| Contextual Explanations (25) | Built | `contextual-explanation.tsx` |
| AI Training Assistant | Built | `training_service.py` |

### Onboarding
25 checklist items for manufacturing preset. Key steps: company info → accounting connection → tax rates → tax jurisdictions → products → price list → financial accounts → team → safety training → scheduling → purchasing → network config → team intelligence.

## 9. Agent Jobs

### Implemented (13 scheduled)
| Job | Schedule | Function |
|-----|----------|----------|
| ar_aging_monitor | Daily 11:00pm | Checks aging thresholds, creates collection sequences |
| collections_sequence | Daily 11:05pm | Processes due sequences, drafts emails |
| ap_upcoming_payments | Daily 11:10pm | Tracks upcoming vendor payments |
| receiving_discrepancy_monitor | Daily 11:15pm | Flags unresolved receipt discrepancies |
| balance_reduction_advisor | Daily 11:20pm | Pre-collections balance suggestions |
| missing_entry_detector | Daily 11:25pm | Finds missing recurring entries |
| tax_filing_prep | Daily 11:30pm | Tax filing preparation alerts |
| uncleared_check_monitor | Daily 11:35pm | Flags checks not cleared in 45+ days |
| financial_health_score | Daily 5:03am | Calculates 5-dimension health score |
| cross_system_synthesis | Daily 6:07am | Detects cross-system insights |
| reorder_suggestion | Monday 6:12am | Vendor reorder suggestions |
| network_snapshot | 1st of month 2:17am | Platform health snapshot |
| onboarding_pattern | 1st of month 4:13am | Onboarding timeline predictions |

### Not Yet Implemented (30)
`CREDIT_MONITOR`, `PAYMENT_MATCHER`, `1099_MONITOR`, `VENDOR_STATEMENT_RECONCILIATION`, `STATEMENT_RUN_MONITOR`, `RECONCILIATION_MONITOR`, `ABANDONED_RECONCILIATION_MONITOR`, `PO_DELIVERY_MONITOR`, `THREE_WAY_MATCH_MONITOR`, `RECURRING_ENTRY_RUNNER`, `REVERSAL_RUNNER`, `STALE_DRAFT_MONITOR`, `FINANCE_CHARGE_CALCULATOR`, `FINANCE_CHARGE_REMINDER`, `EXEMPTION_EXPIRY_MONITOR`, `DELIVERY_INTELLIGENCE_JOB`, `DELIVERY_WEEKLY_REVIEW`, `SEASONAL_PREP_JOB`, `NETWORK_ANALYSIS_JOB`, `NETWORK_READINESS_JOB`, `EMPLOYEE_COACHING_MONITOR`, `COLLECTIONS_INSIGHT_JOB`, `PAYMENT_PREDICTION_JOB`, `VENDOR_RELIABILITY_JOB`, `VENDOR_PRICING_DRIFT_JOB`, `FINANCE_CHARGE_INSIGHT_JOB`, `DISCOUNT_UPTAKE_JOB`, `RELATIONSHIP_HEALTH_JOB`, `PROFILE_UPDATE_JOB`, `OUTCOME_CLOSURE_JOB`, `FORECAST_UPDATE_JOB`, `BALANCE_SHEET_ADVISOR`, `NEW_EMPLOYEE_UPDATER`

## 10. Current Build Status

| Metric | Count |
|--------|-------|
| Database tables | 234 |
| ORM models | 170 exports |
| API endpoints | 904 across 100 modules |
| Frontend routes | 180 |
| Backend service files | 111 |
| Agent jobs (scheduled) | 13 |
| Agent jobs (not built) | 30 |
| TypeScript errors | 0 |
| Backend import errors | 0 |
| Migration chain | Single head, no broken links |

## 11. Coding Conventions

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
    # Always filter by company_id for tenant isolation
    return db.query(Model).filter(Model.company_id == current_user.company_id).all()
```
Register in `backend/app/api/v1.py`:
```python
v1_router.include_router(module.router, prefix="/module", tags=["Module"])
```

### SQLAlchemy Models
```python
# backend/app/models/{entity}.py
class Entity(Base):
    __tablename__ = "entities"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    # ... columns
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```
Import in `backend/app/models/__init__.py` and add to `__all__`.

### Frontend Pages
```tsx
// frontend/src/pages/{feature}/{page}.tsx
export default function FeaturePage() {
  const [data, setData] = useState(null)
  useEffect(() => { apiClient.get("/endpoint").then(r => setData(r.data)) }, [])
  return <div className="space-y-6">...</div>
}
```
Register route in `frontend/src/App.tsx`. Add nav item in `frontend/src/services/navigation-service.ts`.

### Agent Jobs
Add job function in the appropriate service file. Register in `backend/app/scheduler.py` with `scheduler.add_job()`. Add to `JOB_REGISTRY` dict for manual trigger API. Per-tenant jobs use `_run_per_tenant()` wrapper.

### Navigation
Add items to the appropriate preset function in `navigation-service.ts`. Items can be gated by `permission`, `requiresModule`, or `functionalArea`.

## 12. Business Context

### Tenant Types
- **Manufacturer** (Wilbert licensee) — produces burial vaults, manages deliveries, bills funeral homes monthly
- **Funeral Home** — orders vaults, pays on charge account, receives monthly statements
- **Cemetery** — orders cemetery products, interacts with manufacturers
- **Crematory** — specialized funeral service operations

### Product Lines
- **Funeral Service** (core) — burial vaults, urn vaults, cemetery equipment
- **Wastewater** (extension) — septic tanks, precast wastewater products
- **Redi-Rock** (extension) — retaining wall blocks for contractors
- **Rosetta Hardscapes** (extension) — hardscape products

### Key Business Workflows
1. **Monthly Statement Billing** — funeral homes get consolidated statements, not individual invoices
2. **Finance Charges** — calculated on overdue balances, reviewed before posting
3. **Early Payment Discounts** — 2% if paid by 15th of month
4. **Cross-Licensee Transfers** — NY licensee transfers burial to NJ licensee, billing chains automatically
5. **Spring Burial Season** — March-May peak, requires delivery capacity management

### The Wilbert Network
~200 licensees across the US, each serving a geographic territory. Bridgeable enables cross-tenant billing, transfers, and network intelligence between licensees on the platform.

## 13. Recent Changes

- **Migration chain fix:** Renamed 4 duplicate migration revision IDs (p1-p4 → s1-s4), created merge migrations, fixed table name mismatches (`payments`→`customer_payments`, `orders`→`sales_orders`, `bills`→`vendor_bills`)
- **Idempotent migrations:** Monkey-patched `alembic/env.py` so all migrations run cleanly on both fresh and existing databases
- **Environment separation:** Local `.env` points to `bridgeable_dev`, Railway credentials in dashboard only
- **APScheduler:** Installed and configured with 13 jobs on defined schedules
- **CORS:** Configured for `getbridgeable.com` domain with regex matching
- **Platform admin detection:** Fixed `VITE_APP_DOMAIN` not being passed as Docker build arg
- **StatementRunItem model:** Added missing ORM model
- **Checklist sort_order:** Fixed `setup_inter_licensee_pricing` positioning
- **sent_without_edit tracking:** Added to collections sequences for coaching observation

## 14. Known Issues and Tech Debt

### Active Issues
- **Orphaned `tenant_settings` table** — migrations create and add columns to it, but application code uses `Company.settings_json` JSONB instead. The table exists but is never read/written by application code.
- **30 unimplemented agent jobs** — intelligence layer schemas and services exist but job runners not yet built

### Tech Debt
- `@app.on_event("startup/shutdown")` — deprecated FastAPI pattern, should migrate to lifespan context manager
- No query caching layer — all reads hit PostgreSQL directly
- AIService creates new Anthropic client per call — should use connection pooling
- Some migrations have conditional logic (`if table exists`) that should be removed now that env.py handles idempotency
- `StatementRunItem` model was added retroactively — verify all service code references it correctly

## 15. Next Priorities

### Immediate (fix before go-live)
1. Verify all 234 tables exist on production after `r7_create_missing` runs
2. Test first tenant registration end-to-end on production
3. Verify seed data (modules, extensions, presets, roles) populates on first startup

### Short Term (13 simple agent jobs)
`STALE_DRAFT_MONITOR`, `REVERSAL_RUNNER`, `PO_DELIVERY_MONITOR`, `RECONCILIATION_MONITOR`, `ABANDONED_RECONCILIATION_MONITOR`, `STATEMENT_RUN_MONITOR`, `FINANCE_CHARGE_REMINDER`, `EXEMPTION_EXPIRY_MONITOR`, `1099_MONITOR`, `DELIVERY_WEEKLY_REVIEW`, `FINANCE_CHARGE_INSIGHT_JOB`, `DISCOUNT_UPTAKE_JOB`, `OUTCOME_CLOSURE_JOB`, `NEW_EMPLOYEE_UPDATER`

### Medium Term
- Remaining 17 agent jobs (medium/complex)
- Staging environment on Railway
- End-to-end testing with real tenant data
- Performance optimization for report generation
