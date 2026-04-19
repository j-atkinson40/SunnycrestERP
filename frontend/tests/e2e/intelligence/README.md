# Intelligence Admin E2E Tests

Playwright end-to-end tests for the Intelligence admin surface
(PromptLibrary, PromptDetail, ExecutionLog, ExecutionDetail, editing,
Experiments). Added in Phase 3c — protect these flows from regression as
the admin surface evolves.

## Scope

18 tests across 6 files:

| File | Tests | Covers |
|---|---|---|
| `prompt-library.spec.ts` | 3 | Library loads, search narrows, click → detail |
| `prompt-detail.spec.ts` | 3 | Sections render, version swap, edit-button gating |
| `execution-log.spec.ts` | 3 | Log loads, status filter + URL persistence, drill-in |
| `execution-detail.spec.ts` | 2 | Summary + rendered content, linkage section |
| `prompt-editing.spec.ts` | 3 | Activation dialog validation, super_admin tooltip, rollback button |
| `experiments.spec.ts` | 4 | Library, status filter, create form, detail page |

## Running locally

Playwright is already installed at the repo root
(`@playwright/test@1.59.1`). Config lives at `frontend/playwright.config.ts`.
Tests target **staging** by default (`determined-renewal-staging.up.railway.app`),
with API calls intercepted to the staging backend
(`sunnycresterp-staging.up.railway.app`).

```bash
cd frontend

# First time only — install the browser binary
npx playwright install chromium

# Run only the Intelligence tests
npx playwright test tests/e2e/intelligence --project=chromium

# Run a single file
npx playwright test tests/e2e/intelligence/prompt-library.spec.ts

# Run with UI (interactive)
npx playwright test tests/e2e/intelligence --ui

# Debug a single test (headed, paused at start)
npx playwright test tests/e2e/intelligence/prompt-library.spec.ts --debug
```

### Auth

`auth-setup.ts` exports `loginAsAdmin`, `openPromptLibrary`,
`openExecutionLog`, and `openExperimentLibrary`. Each spec imports what
it needs. Credentials come from the staging seed
(`backend/scripts/seed_staging.py`) — `admin@testco.com` / `TestAdmin123!`.

### Target environment

Phase 3b + Phase 3c must be deployed to staging for these tests to pass.
Before running locally:

1. Verify `backend/alembic` head on staging is `r19_intelligence_test_execution_flag`
   or later.
2. Verify `scripts/seed_intelligence.py` + `scripts/seed_intelligence_dev_executions.py`
   have run on staging so there's data to interact with.

If staging hasn't been deployed with Phase 3b/3c, expect failures on
`prompt-editing.spec.ts` and `experiments.spec.ts`. Smoke tests in
`tests/e2e/smoke.spec.ts` use the same staging infrastructure, so if
those pass the base stack is healthy.

## Running in CI

Existing CI (see Railway workflows) runs the full E2E suite. The
Intelligence specs are picked up automatically by
`playwright.config.ts`'s `testDir: "./tests/e2e"`.

### Skipping dependent tests

Several tests call `test.skip(condition, reason)` when the expected
staging state isn't present (e.g. no platform-global prompts visible,
no running experiment to drill into). This keeps CI green on
environments with partial data while still exercising the happy path
where data exists.

## Debugging failures

Playwright writes traces + screenshots on first retry. Outputs land in:

- `tests/e2e/report/` — HTML report (open `index.html`)
- `tests/e2e/screenshots/` — screenshots on failure
- Traces are inline in the HTML report when `trace: "on-first-retry"` triggers

```bash
npx playwright show-report tests/e2e/report
```

## Adding a new test

1. Pick the right file — or create a new one under
   `tests/e2e/intelligence/` if the feature doesn't fit existing files.
2. Use `loginAsAdmin(page)` + navigate to the target URL. Don't assume
   state from a previous test; tests run serially but each should be
   independent.
3. Prefer `data-testid` attributes for selectors over CSS classes or
   text regex. Add them to the UI component if missing.
4. Use `test.skip(condition, reason)` for environments where the
   expected data isn't present, rather than leaving the test flaky.

## Known limitations (Phase 3c)

- Tests target staging — no local dev-server harness wired in yet.
  Tracked as "local-dev E2E harness" in `backend/docs/DEBT.md`.
- No test writes mutations that would persist across runs. Phase 3b
  features (draft creation, activation, test-run) are exercised only
  up to dialog open — not submit — to avoid polluting staging data.
  Backend unit tests cover the write paths.
