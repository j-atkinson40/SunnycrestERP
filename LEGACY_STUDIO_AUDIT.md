# LEGACY STUDIO AUDIT
**Date:** April 16, 2026
**Scope:** Read-only audit per user request — no code changes, no deletions.

---

## TL;DR

Legacy Studio is a **fully-built, currently-live feature** inside the manufacturing vertical. It lets manufacturers generate, review, and approve "Legacy" personalization proofs (TIFF/PDF print artifacts) tied to sales orders. It is **not** the FH Legacy Vault Print feature from the FH-1b build prompt — those are different things that share a name.

- **~7,034 LOC** across backend + frontend
- **5 DB tables in production with data** (9 rows total on Sunnycrest)
- **4 backend route files**, **7 UI pages**, **3 UI components**
- **Wired into**: sales order detail, ops board widget, morning briefing, personalization queue, navigation, permission system, role system
- **Production data exists**: 4 `legacy_proofs`, 1 `legacy_proof_versions`, 1 `legacy_settings` row on Sunnycrest
- **Two migration tables never landed on production**: `legacy_email_settings` + `legacy_fh_email_config` (r42 migration appears not to have been applied)

---

## What it does

Legacy Studio is a proof generation + approval system. Flow:
1. Manufacturer's office staff receives a funeral home's Legacy product order
2. Opens the Proof Generator, loads a template, composites photos + text onto it
3. Generates a watermarked PDF/TIFF proof, emails it to the funeral home
4. Funeral home approves or requests changes via tokenized review link
5. Approved proof is finalized to the print shop (with delivery tracking)

It predates the new FH vertical. It was the first-generation cross-vendor personalization workflow.

---

## Files

### Frontend (9 files, 3,606 LOC)

| File | LOC |
|------|-----|
| `frontend/src/pages/legacy/proof-generator.tsx` | 630 |
| `frontend/src/pages/legacy/proof-generator-mobile.tsx` | 781 |
| `frontend/src/pages/legacy/library.tsx` | 411 |
| `frontend/src/pages/legacy/legacy-detail.tsx` | — |
| `frontend/src/pages/legacy/legacy-proof-review.tsx` | 9 |
| `frontend/src/pages/legacy/legacy-settings.tsx` | 51 |
| `frontend/src/pages/legacy/template-upload.tsx` | 229 |
| `frontend/src/pages/legacy/settings/{delivery,email,general}.tsx` | — |
| `frontend/src/components/legacy/LegacyCompositor.tsx` | 552 |
| `frontend/src/components/legacy/LegacyCompositorMobile.tsx` | 755 |
| `frontend/src/components/legacy/LegacyProofStatusCard.tsx` | 188 |

### Backend (13 files, 3,428 LOC)

Models (3):
| File | LOC |
|------|-----|
| `app/models/legacy_proof.py` | 81 |
| `app/models/legacy_settings.py` | 48 |
| `app/models/legacy_email_settings.py` | 50 |

Services (7, excluding `legacy_print_service.py` which is unrelated):
| File | LOC |
|------|-----|
| `app/services/legacy_service.py` | 276 |
| `app/services/legacy_compositor.py` | 239 |
| `app/services/legacy_templates.py` | 192 |
| `app/services/legacy_watermark.py` | 88 |
| `app/services/legacy_r2_client.py` | 106 |
| `app/services/legacy_delivery.py` | 306 |
| `app/services/legacy_email_service.py` | 276 |

Routes (4):
| File | LOC |
|------|-----|
| `app/api/routes/legacy.py` | 409 |
| `app/api/routes/legacy_studio.py` | 429 |
| `app/api/routes/legacy_delivery.py` | 279 |
| `app/api/routes/legacy_email.py` | 232 |

> **Note:** `backend/app/services/legacy_print_service.py` and `backend/app/models/program_legacy_print.py` are **NOT** part of Legacy Studio. They belong to the new per-program Legacy Prints catalog feature built in the most recent commits (`vault_06_legacy_prints` migration).

---

## Database migrations

| Migration | Creates | Status |
|-----------|---------|--------|
| `r39_legacy_proof_fields` | Adds 6 columns to `order_personalization_tasks` (`proof_url`, `tif_url`, `default_layout`, `approved_layout`, `approved_by`, `approved_at`) | Applied ✓ |
| `r40_legacy_studio` | `legacy_proofs`, `legacy_proof_versions`, `legacy_proof_photos` | Applied ✓ |
| `r41_legacy_settings` | `legacy_settings`, `legacy_print_shop_contacts` | Applied ✓ |
| `r42_legacy_email_settings` | `legacy_email_settings`, `legacy_fh_email_config` | **Never applied to prod** |
| `r43_seed_new_system_roles` | Seeds `legacy_designer` role + legacy_studio permissions | Applied ✓ |

The r42 tables don't exist on production — the migration chain continued past it to a later revision before those tables were created. The backend model files (`legacy_email_settings.py`) exist but the tables don't. This is a latent bug — any code that queries `legacy_email_settings` in production will error.

---

## Production data (Sunnycrest)

| Table | Rows |
|-------|------|
| `legacy_proofs` | 4 |
| `legacy_proof_versions` | 1 |
| `legacy_proof_photos` | 0 |
| `legacy_settings` | 1 |
| `legacy_print_shop_contacts` | 0 |
| `legacy_email_settings` | **table missing** |
| `legacy_fh_email_config` | **table missing** |

Total: 6 rows. Real but small — looks like demo/test data from early development.

---

## API routes registered

In `backend/app/api/v1.py`:
```python
legacy.router          prefix="/legacy"         tags=["Legacy"]
legacy_delivery.router prefix="/legacy"         tags=["Legacy Delivery"]
legacy_email.router    prefix="/legacy"         tags=["Legacy Email"]
legacy_studio.router   prefix="/legacy-studio"  tags=["Legacy Studio"]
```

Four separate routers, two prefixes (`/legacy` and `/legacy-studio`).

---

## Frontend routes registered

In `App.tsx`:
```
/legacy/proof/:orderId        LegacyProofReviewPage
/legacy/generator             ProofGeneratorPage
/legacy/settings              LegacySettingsPage
/legacy/templates/upload      TemplateUploadPage
/legacy/library               LegacyLibraryPage
/legacy/library/:legacyId     LegacyDetailPage
```

Plus nested settings routes `legacy/settings/{delivery,email,general}`.

---

## Navigation integration

`frontend/src/services/navigation-service.ts` (lines 181–230) renders a "Tools" section with Legacy Studio as a collapsible parent nav item with four children:

| Label | Href | Permission |
|-------|------|------------|
| Proof Generator | `/legacy/generator` | `legacy_studio.create` |
| Library | `/legacy/library` | `legacy_studio.view` |
| Settings | `/legacy/settings` | `legacy_studio.create` |
| Template Upload | `/legacy/templates/upload` | `legacy_studio.create` |

The parent is gated by `legacy.view` and only renders if the user has at least one of the child permissions.

---

## Permission + role system integration

**Permission catalog** (`backend/app/core/permissions.py`):
- `legacy.view`, `legacy.create`, `legacy.review` (older, on-order permissions)
- `legacy_studio.view`, `legacy_studio.create`, `legacy_studio.edit`, `legacy_studio.approve`, `legacy_studio.send`, `legacy_studio.delete` (newer, studio-scoped)

**Roles** (seeded via `r43_seed_new_system_roles`):
- `legacy_designer` role — "Full Legacy Studio access with order and customer view only"
- Admin/office/manager roles include legacy_studio permissions by default

---

## Cross-references from elsewhere in the app

These are the integration points that would need to be considered if Legacy Studio were ever removed:

| File | What it does |
|------|-------------|
| `App.tsx` | 6 route definitions, 6 component imports |
| `frontend/src/services/navigation-service.ts` | Tools section nav entries (lines 181–230) |
| `frontend/src/pages/sales-order-detail.tsx` | Imports `LegacyProofStatusCard` — shows proof status on every order detail page |
| `frontend/src/components/dashboard/personalization-queue.tsx` | Reads `legacy_photo_pending`, `is_custom_legacy`, `legacy_proof_id` fields on orders |
| `frontend/src/components/widgets/ops-board/LegacyQueueWidget.tsx` | Ops board widget showing pending legacy proofs |
| `frontend/src/components/morning-briefing-mobile.tsx` | Morning briefing action routing — any briefing item with "legacy" or "proof" in the label routes to `/legacy/library` |
| `frontend/src/components/admin/EmployeeCreationWizard.tsx` | Legacy-related fields in employee setup |
| `backend/app/core/permissions.py` | 9 permission keys + admin role grants |
| `backend/alembic/versions/r43_seed_new_system_roles.py` | Seeds `legacy_designer` role |
| `backend/alembic/versions/r39_legacy_proof_fields.py` | 6 columns on `order_personalization_tasks` (persists even if UI removed) |

---

## Command bar

No Legacy Studio actions are registered in `frontend/src/core/actionRegistry.ts` currently. It is **not** reachable via `Cmd+K`. (Earlier FH-1a command bar completeness work did not add Legacy Studio actions, which aligns with an implicit expectation that it's scheduled for replacement.)

---

## Relationship to the new FH work

This matters for the FH-1a build:

- **Legacy Studio (existing)** is a **manufacturer-side** proof generation system for funeral-home orders. Lives inside the Sunnycrest manufacturing tenant.
- **FH Legacy Vault Print (FH-1b)** is a **funeral-home-side** PDF keepsake generated at the end of the Story step. Different tenant type, different purpose.
- **Per-program Legacy Prints catalog (just built)** is a tenant-level catalog of print designs shown in the Personalization Tab. Also different.

All three happen to have "Legacy" or "Legacy Print" in their names but they are three separate systems. Legacy Studio is the oldest.

---

## Assessment

**Legacy Studio is live, integrated, and has real production data (4 proofs on Sunnycrest).** Removing it is not a trivial cleanup — it touches order detail, morning briefing, ops board, permissions, roles, navigation, and migrations.

**Architectural conflicts with FH-1a:** Low. Legacy Studio is manufacturer-side, FH-1a is funeral-home-side. They could coexist. The naming overlap is confusing but functionally separable.

**Conflicts to watch:**
1. `r42_legacy_email_settings` migration was authored but never applied to prod — code paths that touch `legacy_email_settings` or `legacy_fh_email_config` will 500 on prod. This is a pre-existing bug worth fixing regardless.
2. Morning briefing action-routing (`morning-briefing-mobile.tsx:105`) auto-routes anything with "legacy" in the label to `/legacy/library`. When FH briefings get "Legacy Vault Print ready" items, they'll misroute unless the rule is tenant-type aware.
3. Permission namespace collision: `legacy.view` / `legacy_studio.view` in the existing catalog could conflict with any future FH legacy-print permissions. Worth prefixing new FH permissions with `fh.` to avoid this.

**Recommendation:** Keep Legacy Studio in place for now (as instructed). When building FH-1a, namespace everything under `/fh/*` routes and `fh.*` permissions so there is zero overlap. Handle the morning-briefing routing rule at FH-1a time (add a `vertical: 'manufacturing'` check before routing to `/legacy/library`). The orphan `legacy_email_settings` / `legacy_fh_email_config` tables are a separate issue and don't block FH-1a.
