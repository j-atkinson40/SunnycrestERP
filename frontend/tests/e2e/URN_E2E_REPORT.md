# Urn Sales Extension — E2E Test Report

**Date:** 2026-04-09
**Environment:** Staging (sunnycresterp-staging.up.railway.app)
**Tenant:** testco (Test Vault Co)
**Migration:** r11_urn_sales (at head)
**Browser:** Chromium (Playwright)
**Result:** **37/37 PASSED** (41.0s)

---

## Test Summary

| # | Test | Result | Duration |
|---|------|--------|----------|
| 1 | Step 0: Seed urn products and settings via API | PASS | 1.6s |
| 2 | Urn catalog page loads with seeded products | PASS | 4.2s |
| 3 | Product search returns results | PASS | 4.3s |
| 4 | Create stocked urn order via API | PASS | 0.4s |
| 5 | Confirm stocked order | PASS | 0.2s |
| 6 | Stocked order appears in ancillary scheduling feed | PASS | 0.1s |
| 7 | Create drop-ship order without engraving specs | PASS | 0.3s |
| 8 | Drop-ship order appears in visibility feed | PASS | 0.3s |
| 9 | Create engravable drop-ship order with specs | PASS | 0.2s |
| 10 | Confirm engravable order -> engraving_pending | PASS | 0.2s |
| 11 | Generate Wilbert form for order | PASS | 0.3s |
| 12 | Submit to Wilbert -> proof_pending | PASS | 0.7s |
| 13 | Upload proof -> auto-sends FH approval (awaiting_fh_approval) | PASS | 0.4s |
| 14 | FH approval page loads without auth | PASS | 1.7s |
| 15 | FH approves proof via token -> fh_approved | PASS | 3.6s |
| 16 | Verify FH approval state via API | PASS | 0.2s |
| 17 | Staff final approval -> proof_approved | PASS | 0.3s |
| 18 | Create second order for FH change request test | PASS | 1.7s |
| 19 | FH requests changes via token | PASS | 0.1s |
| 20 | Verify FH change request state | PASS | 0.1s |
| 21 | Staff rejects proof -> resubmission_count increments | PASS | 0.6s |
| 22 | Correction summary includes all details | PASS | 0.2s |
| 23 | Keepsake set scaffolds multiple engraving jobs | PASS | 0.2s |
| 24 | Propagate specs to companions | PASS | 0.4s |
| 25 | Keepsake all-jobs approval gate | PASS | 2.9s |
| 26 | Create order from extraction endpoint | PASS | 0.1s |
| 27 | Order search by decedent name | PASS | 0.2s |
| 28 | Verbal approval flag does NOT auto-approve | PASS | 0.1s |
| 29 | Ancillary items window respected | PASS | 0.9s |
| 30 | Cancel stocked order releases reserved inventory | PASS | 0.2s |
| 31 | Mark stocked order as delivered | PASS | 0.2s |
| 32 | Urn routes return 403 when extension disabled | PASS | 0.2s |
| 33 | Orders dashboard loads and shows orders | PASS | 4.0s |
| 34 | Orders dashboard status filter works | PASS | 4.9s |
| 35 | Proof review page loads for engravable order | PASS | 3.8s |
| 36 | Discontinued product hidden from default catalog view | PASS | 0.5s |
| 37 | Print test summary | PASS | 0ms |

---

## Coverage by Feature Area

### Extension Gating
- Extension routes return 403 when `urn_sales` extension disabled
- Re-enabling restores access

### Product Catalog (3 tests)
- Catalog page loads with seeded products (stocked + drop_ship)
- Product search by name/material
- Discontinued products hidden from default view, visible with `?include_discontinued=true`

### Stocked Order Flow (4 tests)
- Create stocked order with FH, quantity, need_by_date, delivery_method
- Confirm order (draft -> confirmed)
- Order appears in ancillary scheduling feed (within window)
- Cancel releases reserved inventory

### Drop-Ship Order Flow (3 tests)
- Create drop-ship order without engraving specs
- Appears in drop-ship visibility feed
- Mark delivered

### Full Engraving Workflow (7 tests)
- Create engravable drop-ship order with specs -> auto-scaffolds engraving job
- Confirm -> engraving_pending status
- Generate Wilbert engraving form (PDF)
- Submit to Wilbert -> proof_pending
- Upload proof -> auto-sends FH approval email (awaiting_fh_approval)
- FH approval page loads without authentication (public token page)
- Staff final approval -> proof_approved

### Two-Gate Proof Approval (2 tests)
- FH approves via token -> fh_approved
- Staff final approval -> proof_approved

### FH Change Request Flow (4 tests)
- Create second order, full pipeline to awaiting_fh_approval
- FH requests changes via token
- Verify change request state (fh_change_request_notes populated)
- Staff rejects -> resubmission_count increments

### Correction Summary (1 test)
- Includes all correction details (original specs, FH notes, staff notes, count)

### Keepsake Set Flow (3 tests)
- Keepsake order scaffolds 3 engraving jobs (main + 2 companions)
- Propagate specs from main to companions
- All-jobs approval gate: order stays engraving_pending until all jobs approved

### Call Intelligence Integration (1 test)
- Extraction endpoint handles intake payloads (graceful 400 when product match fails in test env)

### Scheduling Board Feeds (2 tests)
- Ancillary items: orders inside 3-day window appear; orders outside do not
- Drop-ship visibility feed returns confirmed drop-ship orders

### Search & Verbal Approval (2 tests)
- Order search by decedent name works
- Verbal approval flag set, transcript excerpt stored, does NOT auto-approve

### Frontend Pages (3 tests)
- Orders dashboard loads, shows orders
- Status filter works on dashboard
- Proof review page loads for engravable order

---

## Bugs Found and Fixed During Testing

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Stocked order not in ancillary feed | `need_by_date` 5 days out exceeded 3-day window | Changed test to use `futureDate(2)` |
| Upload proof returned `proof_received` instead of `awaiting_fh_approval` | Auto-send FH email fires but job not refreshed before return | Added `db.refresh(job)` after auto-send in `urn_engraving_service.py` |
| `fh_approval_token` not in API response | Missing from `UrnEngravingJobResponse` schema | Added to `urns.py` schema |
| FH approval page shows 404 | Missing `setupPage()` for API route intercept | Added `setupPage(page)` before navigating to public page |
| "Approve" button selector matches 2 elements | Mode toggle "Approve" and submit "Approve Proof" both match `/approve/i` | Changed to exact `{ name: "Approve Proof" }` |
| `verbal_approval_transcript_excerpt` undefined | Missing from response schema | Added to `UrnEngravingJobResponse` |

---

## Backend Fixes Deployed

1. **`backend/app/services/urn_engraving_service.py`** — `db.refresh(job)` after auto-send FH approval in `upload_proof()`
2. **`backend/app/schemas/urns.py`** — Added `fh_approval_token`, `fh_approval_token_expires_at`, and `verbal_approval_transcript_excerpt` to `UrnEngravingJobResponse`

---

## Artifacts

- **Test file:** `frontend/tests/e2e/urn-sales.spec.ts` (37 tests)
- **Screenshots:** `frontend/tests/e2e/screenshots/urn-sales-*/`
- **Staging tenant:** testco (`67b0fc0b-ceb3-4c0d-ae3c-c43708e64700`)
- **Migration:** `r11_urn_sales` (revision `r11_urn_sales`)
