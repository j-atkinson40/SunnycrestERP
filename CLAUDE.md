# CLAUDE.md — Bridgeable Platform

## 1. Project Overview

**Bridgeable** (getbridgeable.com) is a multi-tenant SaaS business management platform for the death care industry, specifically Wilbert burial vault licensees and their connected funeral homes. The platform manages the full operational lifecycle: funeral order processing, delivery scheduling, inventory, AR/AP, monthly billing, cross-licensee transfers, safety compliance, and financial reporting.

**Company context:**
- **Sunnycrest Precast** — first customer and development partner (vault manufacturer in Auburn, NY); live at `sunnycrest.getbridgeable.com`
- **Able Holdings** — holding company that owns the Bridgeable platform
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

## 3. Architecture

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
Extensions (Wastewater, Redi-Rock, Rosetta, NPCA Audit Prep) are tracked in `tenant_extensions`. When enabled, they register contributors to the Operations Board registry, add navigation items, and unlock features. Core modules are always available; extensions are per-tenant opt-in.

**NPCA:** `npca_audit_prep` is a proper extension. All dashboard elements and nav items are gated by `hasModule("npca_audit_prep")`. Auto-enables when `npca_certification_status = "certified"` is set during platform admin tenant setup.

### Settings Pattern
Tenant settings are stored as a JSONB field on the `companies` table (`settings_json` column), accessed via `company.settings` property and `company.set_setting(key, value)` method. A `tenant_settings` database table also exists (migrations create it) but is orphaned — application code uses `Company.settings_json` exclusively.

## 4. Database

- **~235 tables** (ORM models for all but the orphaned `tenant_settings` table)
- **Current migration head:** `r10_agent_infra`
- **112 migration files** in `backend/alembic/versions/`
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

## 5. Project Structure

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
│   │   └── ...
│   ├── api/
│   │   ├── v1.py            # Route aggregator (92 modules registered)
│   │   ├── deps.py          # Auth dependencies (get_current_user, require_admin)
│   │   ├── routes/          # 102 route files, 904 total endpoints
│   │   └── platform.py      # Platform admin routes
│   ├── core/
│   │   └── security.py      # JWT + bcrypt utilities
│   └── jobs/
│       └── __init__.py      # Job handler registry
├── alembic/
│   ├── env.py               # Idempotent op wrappers
│   └── versions/            # 112 migration files
├── data/
│   ├── us-county-tax-rates.json
│   └── us-zip-county-mapping.json
├── static/safety-templates/ # Generated safety training PDFs
├── .env                     # LOCAL only — points to bridgeable_dev
└── .env.example             # All env vars documented

frontend/
├── src/
│   ├── App.tsx              # 146 route definitions, platform admin detection
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

## 7. URLs and Domains

| Environment | Frontend | Backend | Platform Admin |
|-------------|----------|---------|----------------|
| **Production** | `app.getbridgeable.com` | `api.getbridgeable.com` | `admin.getbridgeable.com` |
| **Local** | `localhost:5173` | `localhost:8000` | `admin.localhost:5173` |

Tenant pattern: `{slug}.getbridgeable.com`
First live tenant: `sunnycrest.getbridgeable.com`

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

### Safety & Compliance
| Feature | Status | Key Files |
|---------|--------|-----------|
| Safety Training (12 OSHA topics) | Built | `safety_training_system_service.py` |
| Equipment Inspections | Built | `safety_service.py` |
| Toolbox Talks + Suggestions | Built | `toolbox_suggestion_service.py` |
| OSHA 300 Log | Built | `osha_300_entry.py` |
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

## 9. Agent Jobs

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

All jobs use `_run_per_tenant()` or `_run_global()` wrappers with per-session DB isolation and error logging. All are manually triggerable via `JOB_REGISTRY` dict and the agent trigger API endpoint.

### Not Yet Implemented (~30 jobs)
`CREDIT_MONITOR`, `PAYMENT_MATCHER`, `1099_MONITOR`, `VENDOR_STATEMENT_RECONCILIATION`, `STATEMENT_RUN_MONITOR`, `RECONCILIATION_MONITOR`, `ABANDONED_RECONCILIATION_MONITOR`, `PO_DELIVERY_MONITOR`, `THREE_WAY_MATCH_MONITOR`, `RECURRING_ENTRY_RUNNER`, `REVERSAL_RUNNER`, `STALE_DRAFT_MONITOR`, `FINANCE_CHARGE_CALCULATOR`, `FINANCE_CHARGE_REMINDER`, `EXEMPTION_EXPIRY_MONITOR`, `DELIVERY_INTELLIGENCE_JOB`, `DELIVERY_WEEKLY_REVIEW`, `SEASONAL_PREP_JOB`, `NETWORK_ANALYSIS_JOB`, `NETWORK_READINESS_JOB`, `EMPLOYEE_COACHING_MONITOR`, `COLLECTIONS_INSIGHT_JOB`, `PAYMENT_PREDICTION_JOB`, `VENDOR_RELIABILITY_JOB`, `VENDOR_PRICING_DRIFT_JOB`, `FINANCE_CHARGE_INSIGHT_JOB`, `DISCOUNT_UPTAKE_JOB`, `RELATIONSHIP_HEALTH_JOB`, `PROFILE_UPDATE_JOB`, `OUTCOME_CLOSURE_JOB`

## 10. Current Build Status

| Metric | Count |
|--------|-------|
| Database tables | ~250 |
| ORM model files | 157+ |
| ORM model exports (`__init__.py`) | 170+ |
| API route files | 102+ |
| API endpoints | 904+ |
| Route modules registered in v1.py | 92+ |
| Frontend routes | 146+ |
| Backend service files | 109+ |
| Migration files | 112+ |
| Migration head | `r10_agent_infra` |
| Agent jobs (scheduled) | 13 |
| Agent jobs (not yet built) | ~30 |
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
- `backend/app/services/agents/approval_gate.py` — Token-based email approval workflow
- `backend/app/services/agents/period_lock.py` — Financial period locking service
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
- **NPCA Audit Prep** (extension) — compliance and audit readiness; auto-enabled when `npca_certification_status = "certified"`

### Key Business Workflows
1. **Monthly Statement Billing** — funeral homes get consolidated statements, not individual invoices
2. **Finance Charges** — calculated on overdue balances, reviewed before posting
3. **Early Payment Discounts** — 2% if paid by 15th of month
4. **Cross-Licensee Transfers** — NY licensee transfers burial to NJ licensee; billing chains automatically
5. **Spring Burial Season** — March–May peak, requires delivery capacity management

## 13. Recent Changes

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

## 14. Known Issues and Tech Debt

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

## 15. Next Priorities

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

## 16. Recent Build Sessions

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
- Migration head: `z9g4h5i6j7k8`

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

**Next build focus:** Funeral Home vertical — Phase FH-1 prompts ready. Key dependency: 70-field case file data model (design with AI Arrangement Scribe in mind from day one).
