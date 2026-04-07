# RBAC & Navigation Test Report

**Date:** 2026-04-07
**Environment:** Staging (`determined-renewal-staging.up.railway.app` → `sunnycresterp-staging.up.railway.app`)
**Browser:** Chromium (Playwright)

---

## Summary

| Suite | Passed | Failed | Total |
|-------|--------|--------|-------|
| `rbac.spec.ts` | 3 | 7 | 10 |
| `navigation.spec.ts` | 11 | 3 | 14 |
| **Total** | **14** | **10** | **24** |

---

## rbac.spec.ts — Results

| # | Test | Result | Notes |
|---|------|--------|-------|
| 1 | Admin sees all nav items | PASS | All expected nav items found |
| 2 | Accountant sees financials not operations | FAIL | Login timeout — user doesn't exist on staging |
| 3 | Office staff base sees no financials | FAIL | Office user can access /financials — no permission gate |
| 4 | Office staff with financial toggle | FAIL | Login timeout — `office_finance` user doesn't exist on staging |
| 5 | Production role nav | FAIL | Login timeout — `prodmanager` user doesn't exist on staging |
| 6 | Driver redirected to console | PASS | Correctly redirected to /driver |
| 7 | Admin can view user permissions tab | FAIL | `/admin/users` route not found or no user list rendered |
| 8 | Permission gate hides unauthorized content | FAIL | Office user not denied /financials access |
| 9 | Custom permissions section visible | PASS | Permissions section found on user detail |
| 10 | AccessDenied component renders correctly | FAIL | No AccessDenied shown, no redirect — office sees financials |

## navigation.spec.ts — Results

| # | Test | Result | Notes |
|---|------|--------|-------|
| 1 | Financials hub loads with all tiles | PASS | Hub renders with summary cards and tiles |
| 2 | Financials hub tiles navigate correctly | FAIL | Clicking "Billing" text didn't navigate — matched description text, not the Link |
| 3 | CRM hub loads with all tiles | PASS | All expected tiles found |
| 4 | Production hub loads with all tiles | PASS | Hub renders correctly |
| 5 | Old routes still work | PASS | /calls, /knowledge-base, /price-management all accessible |
| 6 | Breadcrumbs render on sub-pages | PASS | Breadcrumbs found on /billing |
| 7 | Nav active state highlights hub | PASS | Active state detected |
| 8 | Settings section in nav | FAIL | `getByText("Settings").first()` matched wrong element (multiple "Settings" in DOM) |
| 9 | Invoice page accessible from financials | PASS | /ar/invoices loads without error |
| 10 | Dashboard loads without error | PASS | Dashboard renders cleanly |
| 11 | Role-adaptive dashboard widgets | FAIL | Login timeout for accountant and prodmanager — users don't exist |
| 12 | Legacy Studio in nav | PASS | Found in sidebar |
| 13 | Knowledge Base accessible | PASS | Loads without error |
| 14 | Mobile nav works | PASS | Financials hub renders on mobile viewport |

---

## Failed Test Details

### FAIL: rbac 2, 4, 5 / nav 11 — Missing Test Users

**Expected:** Login with `accountant@testco.com`, `office_finance@testco.com`, `prodmanager@testco.com`
**Actual:** Login form times out — credentials not recognized
**Screenshots:** `rbac/02-accountant-nav.png`, `rbac/04-office-finance-nav.png`, `rbac/05-prod-nav.png`
**Severity:** HIGH — blocks 4 tests
**Root cause:** Staging seed script (`seed_staging.py`) only creates admin, office, and driver users. Missing: accountant, office_finance, prodmanager.

### FAIL: rbac 3, 8, 10 — No Permission Gate on /financials

**Expected:** Office staff denied access to `/financials` (AccessDenied component or redirect)
**Actual:** Office user loads the Financials Hub normally — no permission check
**Screenshots:** `rbac/03-office-financials-attempt.png`, `rbac/08-office-financials-denied.png`, `rbac/10-access-denied.png`
**Severity:** HIGH — security gap, blocks 3 tests
**Root cause:** The `/financials` route in `App.tsx` is not wrapped in `<ProtectedRoute>` with financial permission requirements. Hub pages were added without route-level RBAC gating.

### FAIL: rbac 7 — User Permissions Tab Not Found

**Expected:** Navigate to `/admin/users`, click office user, see permissions section
**Actual:** No user list rendered or `/admin/users` route doesn't work as expected
**Screenshots:** `rbac/07-admin-users.png`
**Severity:** MEDIUM — admin feature not accessible at expected route

### FAIL: nav 2 — Hub Tile Click Doesn't Navigate

**Expected:** Clicking "Billing" tile on /financials navigates to /billing
**Actual:** Page stays on /financials after click
**Screenshots:** `navigation/02-billing-from-hub.png`
**Severity:** MEDIUM — UX issue
**Root cause:** `page.getByText("Billing").first()` matches the tile's description text (not the Link wrapper). The tile structure has both a heading and description containing "Billing". Fix: use a more specific selector like `page.getByRole("link", { name: /Billing/i })` or add `data-testid` attributes.

### FAIL: nav 8 — Settings Section Selector Ambiguity

**Expected:** Find and click "Settings" in sidebar
**Actual:** Multiple "Settings" text matches in DOM — wrong element clicked
**Screenshots:** `navigation/08-settings-nav.png`
**Severity:** LOW — test selector issue only
**Root cause:** "Settings" appears in both the collapsible section header and individual nav items (e.g., "CRM Settings", "Email Settings"). Fix: scope selector to sidebar section headers.

---

## Missing Features (Discovered)

1. **Route-level permission gating on hub pages** — `/financials`, `/crm`, `/production-hub` have no `<ProtectedRoute>` wrappers
2. **Staging seed users** — Missing accountant, office_finance, prodmanager roles for testing
3. **`/admin/users` route** — May not exist or may be at a different path

---

## Recommended Fixes (Priority Order)

### P0 — Seed Missing Test Users
Add to `seed_staging.py` or create a separate seed script:
- `accountant@testco.com` (role: accountant) — password: `TestAccountant123!`
- `office_finance@testco.com` (role: office, with financial permission toggle) — password: `TestOffice123!`
- `prodmanager@testco.com` (role: production_manager) — password: `TestProd123!`

### P1 — Add Permission Gates to Hub Routes
Wrap hub routes in `App.tsx` with `<ProtectedRoute>`:
- `/financials` → require financial permissions
- `/production-hub` → require production permissions
- `/crm` → require CRM permissions (or leave open if all roles can access)

### P2 — Fix Test Selectors
- **Nav test 2:** Use `page.getByRole("link", { name: /^Billing$/i })` or add `data-testid="hub-tile-billing"` to tile links
- **Nav test 8:** Scope "Settings" selector: `sidebar.locator('[data-section="settings"]')` or use `getByRole("button", { name: /^Settings$/i })`

### P3 — Verify Admin Users Route
Confirm the correct path for user management (may be `/settings/users` or `/admin/users`) and update test 7 accordingly.
