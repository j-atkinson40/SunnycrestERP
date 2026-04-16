# SUPER ADMIN AUDIT
**Date:** April 16, 2026
**Context:** Pre-redesign audit per Step 1 of BUILD PROMPT — Bridgeable Super Admin Portal Redesign

---

## Existing Backend Infrastructure (KEEPING — extending, not replacing)

### Models
- `platform_users` — separate admin user model (id, email, hashed_password, first_name, last_name, role, is_active, last_login_at) with roles: `super_admin | support | viewer`
- `platform_email_settings`, `platform_notification`, `platform_incident` — operational
- `platform_tenant_relationship` — cross-tenant network
- `platform_fee` — billing infrastructure

### Routes (under `/api/platform/`)
- `platform_auth.py` — separate JWT realm (`realm='platform'`), login/refresh/me
- `platform_tenants.py` — tenant CRUD
- `platform_feature_flags.py` — feature flags exist
- `platform_impersonation.py` — impersonation system exists
- `platform_users_mgmt.py` — admin user management
- `platform_health.py` — health data
- `platform_incidents.py`, `platform_system.py`, `platform_modules.py`, `platform_extensions.py`, `platform_training.py`

### Auth Model
- JWT tokens with `realm='platform'` — isolated from tenant tokens
- `get_current_platform_user` dependency in `deps.py`
- Platform tokens rejected by tenant endpoints; tenant tokens rejected by platform endpoints

---

## Existing Frontend Infrastructure

### `/platform/*` Pages (13) — existing super admin UI
- `login.tsx`, `dashboard.tsx`, `platform-health.tsx`, `system-health.tsx`
- `tenants.tsx`, `tenant-detail.tsx`, `tenant-modules.tsx`, `tenant-onboarding.tsx`
- `platform-users.tsx`, `impersonation-log.tsx`
- `feature-flags.tsx`, `extension-catalog.tsx`, `extension-demand.tsx`

### `/admin/*` Pages (26) — TENANT-scoped admin (not super admin)
These are settings pages within a tenant's platform (e.g., accounting config, user management, billing).
**Not** super admin pages — they live inside the tenant's own app and require tenant admin role.

---

## Naming Decision

This build prompt uses `/admin/*` and `admin_users` — but our existing code uses `/platform/*` and `platform_users`. To avoid massive disruption and preserve the existing split between tenant `/admin/*` settings and platform admin:

**Decision: New super admin code uses `/bridgeable-admin/*` prefix on the frontend and `/api/platform/*` on the backend (extending existing platform routes).**

- Frontend: new redesigned super admin pages live under `/bridgeable-admin/*`
- Backend: new endpoints extend existing `platform_*` modules or add new `platform_*` modules
- Database tables: `admin_*` prefix per build prompt (new tables only) — clearly distinguish from both `platform_*` (legacy) and tenant tables

This preserves the tenant `/admin/*` settings and the legacy `/platform/*` pages (to migrate later) while the new redesigned portal lives at `/bridgeable-admin/*`.

---

## Keeping
- `platform_users` model + `PlatformUser` auth (no migration to `admin_users`)
- Platform JWT realm + `get_current_platform_user` dependency
- Existing `/api/platform/auth/*` login/refresh
- Existing impersonation + feature flag backend endpoints (will be rebuilt on top)

## Replacing (with new `/bridgeable-admin/*` UI)
- Legacy `/platform/dashboard.tsx` → new `/bridgeable-admin` health dashboard (Part 10)
- Legacy `/platform/tenants.tsx` → new kanban board (Part 4)
- Legacy `/platform/feature-flags.tsx` → redesigned Part 9 UI
- Legacy `/platform/impersonation-log.tsx` → absorbed into audit log view
- Legacy `/platform/extension-catalog.tsx` → deprecated entirely (Part 11)

## New
- Admin command bar (Cmd+K) with local fuzzy matching + Claude chat (Part 3, 13)
- Environment toggle (prod/staging) with amber banner (Part 2)
- Tenant kanban with health dots (Part 4)
- Staging tenant creator with vertical presets (Part 6)
- Playwright audit runner with WebSocket streaming (Part 7)
- Migration control panel (Part 8)
- Deployment test tracking + production smoke tests (Part 14)
- Product lines replacing extension library (Part 11)
- `admin_*` database tables — all new (Part 12)
