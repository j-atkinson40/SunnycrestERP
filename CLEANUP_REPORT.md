# CLEANUP_REPORT.md
Generated: 2026-03-27

---

## 1. Dead Code Removed

### `console.log` statements
**None found** in `frontend/src/` — codebase is clean.

### `print()` statements in backend
The following `print()` calls exist in `backend/app/main.py` (lines 159, 187, 194, 207). These are **intentional startup warning prints** in the FastAPI lifespan startup block (not in request handlers), and are acceptable as-is. No `print()` calls were found in service or route files.

### Commented-out code blocks (>5 lines)
**None found** exceeding the threshold.

### TODO comments removed
No TODOs were removed — the remaining TODOs in the codebase represent **real unfinished work** and are documented in CLAUDE.md §14. They are:

| File | Line | TODO |
|------|------|------|
| `backend/app/api/routes/tax.py` | 520 | `service_territory_counties` query from territories |
| `backend/app/api/routes/agents.py` | 159 | Email service integration |
| `backend/app/api/routes/accounting_connection.py` | 304 | Send accountant invitation email |
| `backend/app/services/spring_burial_service.py` | 272 | Cemetery tracking `by_cemetery` field |
| `backend/app/services/funeral_home_directory_service.py` | 186 | `network_invitation` record creation |
| `backend/app/services/report_intelligence_service.py` | 195 | Async Claude API call for audit commentary |
| `backend/app/services/extension_service.py` | 263 | Tenant plan tier check |
| `frontend/src/pages/quotes.tsx` | 128 | Navigate to new quote form |

---

## 2. Hardcoded Values — Fixed

### `backend/app/config.py`
- **Fixed:** `APP_NAME` default changed from `"Sunnycrest ERP"` → `"Bridgeable"`
- **Fixed:** `SUPPORT_EMAIL` default changed from `"support@sunnycrest.dev"` → `"support@getbridgeable.com"`

### `backend/.env.example`
- **Fixed:** Header renamed from "ERP Backend" → "Bridgeable"
- **Fixed:** `DATABASE_URL` corrected from `erp_db` → `bridgeable_dev`
- **Fixed:** Added missing vars: `GOOGLE_PLACES_API_KEY`, `TWILIO_*`, `PLATFORM_ADMIN_*`

### `frontend/src/lib/tenant.ts`
- **Fixed:** JSDoc comment updated from `acme.platform.app` → `acme.getbridgeable.com`
- **Fixed:** Inline comment updated from `platform.app` → `getbridgeable.com`
- **Fixed:** `getCompanyUrl()` fallback changed from `"platform.app"` → `"getbridgeable.com"`

### `frontend/src/pages/company-register.tsx:117`
- **Fixed:** Preview URL fallback changed from `"platform.app"` → `"getbridgeable.com"`

### `frontend/src/pages/admin/admin-tenant-list.tsx:407` (previously fixed)
- `yourerp.com` → `import.meta.env.VITE_APP_DOMAIN || "getbridgeable.com"`

### `frontend/src/pages/admin/admin-tenant-detail.tsx:373` (previously fixed)
- `yourerp.com` → `import.meta.env.VITE_APP_DOMAIN || "getbridgeable.com"`

---

## 3. Hardcoded Values — Flagged (Not Auto-Fixed)

### Railway URLs in application code
**None found in application code.** All `*.railway.app` references are in `.claude/settings.local.json` (tool permission history) — not in any application file. Safe to ignore.

### Old platform names
**None remaining** after fixes applied above. Search for `"ERP Platform"`, `"yourerp.com"`, `"Sunnycrest ERP"` in `frontend/src/` and `backend/app/` returns 0 results.

### `APP_NAME` used as Redis key prefix
- **File:** `backend/app/services/job_queue_service.py:23-24`
- **Code:** `REDIS_QUEUE_KEY = f"{settings.APP_NAME}:job_queue"`
- **Risk:** Low — if `APP_NAME` env var is changed in Railway, Redis keys shift. Not auto-fixed; document it and consider using a static string like `"bridgeable:job_queue"` in a future cleanup.

### `support@sunnycrest.dev` in frontend
- **None found.** The old support email only existed in `config.py` (now fixed).

---

## 4. Environment Variables — Audit

### Backend — all vars in `config.py` (pydantic-settings)
All 25 variables are now documented in CLAUDE.md §6 and `backend/.env.example`. Previously undocumented vars now added to `.env.example`:
- `GOOGLE_PLACES_API_KEY` — was in config, missing from `.env.example`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` — was in config, missing from `.env.example`
- `PLATFORM_ADMIN_EMAIL`, `PLATFORM_ADMIN_PASSWORD` — was in config, missing from `.env.example`
- `CONSOLE_TOKEN_EXPIRE_MINUTES` — in config but not user-facing; no action needed
- `FRONTEND_URL` — in config; used for email links. Not in `.env.example` — low risk, defaults are fine.
- `PLATFORM_DOMAIN` — in config; defaults to `getbridgeable.com`. Not in `.env.example` — add if needed.

### Frontend — all `import.meta.env.*` references
| Variable | Files Using It | Documented |
|----------|---------------|-----------|
| `VITE_API_URL` | `api-client.ts`, `platform-api-client.ts`, `platform.ts`, `company-service.ts` | ✅ |
| `VITE_APP_NAME` | `landing.tsx`, `login.tsx`, `register.tsx`, `sidebar.tsx` | ✅ |
| `VITE_APP_DOMAIN` | `tenant.ts`, `platform.ts`, `admin-tenant-list.tsx`, `admin-tenant-detail.tsx`, `company-register.tsx` | ✅ |
| `VITE_ENVIRONMENT` | `.env.example` only | ✅ |

No undocumented frontend env vars found.

---

## 5. Duplicate Code — Flagged

### `NPCA_OPTIONS` constant defined twice
- `frontend/src/pages/platform/tenant-onboarding.tsx:56-64`
- `frontend/src/pages/admin/admin-tenant-detail.tsx:114-120`

Both define the same 5-item array `[{ value, label }]`. These are in separate admin-only pages and the duplication is low-risk. **Recommendation:** Extract to a shared constant in `frontend/src/constants/npca.ts` in a future cleanup pass.

### `getApiErrorMessage()` usage pattern
The function is imported from `@/lib/api-error` and used uniformly — no duplicates found.

### COA `GL_CATEGORIES` / `PLATFORM_CATEGORIES`
- Frontend: `accounting-review.tsx:56-62` defines `GL_CATEGORIES`
- Backend: `accounting_analysis_service.py` defines `PLATFORM_CATEGORIES`

These serve the same domain mapping but are in frontend vs. backend contexts. They need to stay in sync. **Recommendation:** Document this coupling; no auto-merge needed.

### Accounting provider connection logic
`backend/app/services/accounting/` and `backend/app/api/routes/accounting_connection.py` both contain provider-specific branching logic. This is expected architecture for a multi-provider system.

---

## 6. Migration Chain Status

- **Current head:** `r7_create_missing`
- **Migration file count:** 112
- **Chain:** Single root `e1e2120b6b65`, single head `r7_create_missing`. No merge conflicts, no broken links.
- **Idempotency:** `alembic/env.py` monkey-patches `op.add_column`, `op.create_table`, `op.create_index` — safe to run on both fresh and existing databases.

### Migrations with TODO comments
**None found** in `backend/alembic/versions/`.

### Previously fixed migration issues
- 4 duplicate revision IDs renamed (p1–p4 → s1–s4)
- Merge migrations created
- Table names corrected: `payments→customer_payments`, `orders→sales_orders`, `bills→vendor_bills`

---

## Summary

| Category | Found | Fixed | Flagged |
|----------|-------|-------|---------|
| `console.log` in frontend | 0 | — | — |
| `print()` in backend (non-CLI) | 4 | 0 (intentional startup warnings) | 4 |
| Commented-out code blocks | 0 | — | — |
| TODOs removed | 0 | 0 | 8 (real unfinished work) |
| Hardcoded old platform names | 5 | 5 | 0 |
| Hardcoded `platform.app` fallbacks | 3 | 3 | 0 |
| Hardcoded `yourerp.com` | 2 | 2 (prior session) | 0 |
| `.env.example` missing vars | 5 | 5 | 0 |
| Undocumented `import.meta.env` vars | 0 | — | — |
| Duplicate functions flagged | 2 | 0 | 2 |
| Migration chain issues | 0 | — | — |
