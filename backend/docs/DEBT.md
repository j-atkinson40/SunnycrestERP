# Platform Debt Tracking

This document tracks known technical debt, architectural concerns, and
deferred improvements that don't rise to the level of active bugs (see
`BUGS.md`) but should be addressed eventually.

When a debt item is resolved, move the entry from **Active debt** to
**Resolved debt** with a date and a link to the fix.

---

## Active debt

### Intelligence stats endpoints perform live aggregation

**Discovered:** Phase 3a (April 2026)

**Current state:** `GET /intelligence/stats/prompt/{id}` and
`GET /intelligence/stats/overall` compute 30-day aggregates via live SQL
queries on `intelligence_executions`. With 300 seed executions, this is
fast. At production scale (projected: tens of thousands to millions of
executions per year), these queries will become slow — especially the
daily-breakdown group-by-date query and the per-prompt error-rate
aggregate that runs once per prompt on the list endpoint.

**Eventual fix:** Materialized daily rollup table
`intelligence_execution_daily_rollup` with columns:

- `date` (DATE, PK)
- `prompt_id` (FK, PK)
- `execution_count`
- `success_count`
- `error_count`
- `total_input_tokens`
- `total_output_tokens`
- `total_cost_usd`
- `avg_latency_ms`
- `p95_latency_ms` (optional — harder without percentile-cont)

Nightly job populates the table (or rolls forward from the previous day's
high-water mark). Stats endpoints query the rollup table instead of the
live executions table. Live table still used for queries scoped to
< 24 hours (today's partial-day window).

**Threshold for action:** when a single stats endpoint query exceeds
500ms on production data.

---

### Frontend has no unit test framework

**Discovered:** Phase 3a (April 2026)

**Current state:** `frontend/package.json` has no vitest, jest, or
testing-library. Frontend changes are validated via `tsc` compile and
manual testing only. Playwright E2E coverage is planned in Phase 3c but
doesn't replace unit tests — it's slower, flakier, and doesn't cover
pure-logic components (formatters, URL-state helpers, parsers like
`VisionContentBlock`'s block detection).

**Eventual fix:** add `vitest` + `@testing-library/react` +
`@testing-library/jest-dom` to `package.json`. Establish testing patterns
in a dedicated build. Priority candidates for first tests:

- `components/intelligence/VisionContentBlock` — the JSON-parse fallback
  logic is exactly the kind of code that breaks silently
- `components/intelligence/formatting` — pure functions, highest ROI
- URL-state helpers (to be extracted) from PromptLibrary / ExecutionLog

**Threshold for action:** when a bug escapes to production that component
tests would have caught, or when Phase 3b's editing features ship without
adequate manual QA coverage.

---

### Local-dev E2E harness

**Discovered:** Phase 3c (April 2026)

**Current state:** `frontend/tests/e2e/` (including the new
`intelligence/` folder) targets the staging deployment
(`determined-renewal-staging.up.railway.app`). There is no local-dev
Playwright harness — running tests requires staging to be up and
deployed with the expected migration head. This delays verification
during Phase 3c/3d builds where staging may be behind `main`.

**Eventual fix:** Add a `webServer` block to `playwright.config.ts` that
spins up backend + frontend locally (uvicorn + vite) for a local-dev
project. Seed an ephemeral SQLite/Postgres at test start. Either a
separate project in the existing config (e.g. `chromium-local`) or a
separate `playwright.local.config.ts` invoked via a new npm script.

**Threshold for action:** when a Phase 3d-or-later build requires E2E
verification before staging deploy is viable.

---

### AICommandBar frontend refactor

Tracked in `BUGS.md` → "Out-of-scope for cleanup". The component uses
the deprecated `/ai/prompt` endpoint with arbitrary `systemPrompt` prop,
defeating managed-prompt A/B testing and per-tenant overrides. Migration
to a dedicated `catalog.product_search` managed prompt + endpoint is
pending. Sunset date 2027-04-18.

---

## Resolved debt

_(empty — populate as debt items are addressed)_
