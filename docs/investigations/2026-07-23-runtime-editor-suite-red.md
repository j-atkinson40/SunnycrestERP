# Runtime-Editor Playwright Suite Wholesale Red — Investigation (READ-ONLY)

**Date:** 2026-07-23 · **Trigger:** the runtime-editor staging CI suite is
wholesale red (specs 01–09 + 11 ✘, spec 10 ✓) and has been for weeks, masked
behind the job's 20-minute timeout. **Scope:** findings only — no code, no
fixes, no push. Every staging query was a read-only SELECT / GET; one
self-contained local FastAPI repro (in-memory, no DB).

---

## Headline

- **Regression pinned to exactly two commits** — `18ed66ca` + `323a35d4`, the
  "map-performance" arc of 2026-07-20 (~17–18 UTC). **NOT the chrome/steel
  pivot** (that landed 07-21, *after* the suite was already red — my first
  instinct, wrong).
- **The differentiator (why 10 survives):** specs 01–09/11 do
  **impersonation → `/bridgeable-admin/runtime-editor/` shell mount**; spec 10
  (and the *passing* Claude-API suite) do not. CI-bot auth, platform API, and
  tenant `/api/v1` are all **proven working** — ruled out.
- **The actual error is genuinely un-surfaced** and *cannot* be read from CI:
  the list-reporter prints per-failure detail only in the end-summary, which the
  cancellation truncates; and the artifact-upload steps are `if: failure()`,
  which a **cancelled** job never satisfies. Local run is blocked
  (`STAGING_CI_BOT_PASSWORD` is a GitHub Secret, absent locally). §Job 3 gives
  the precise plan to surface it.
- **Suite-red and job-timeout are ONE problem** — the slow failures (30 s × 2
  retries × ~10 specs) consume the budget. Green → ~12 min.
- **Blast radius is CONTAINED** to the runtime-editor suite. **No STOP
  condition** — the failing dependency (impersonation + shell) is used by no
  other suite.

---

## Job 1 — Dating the regression

The funeral_home vertical_default theme table (each version = one successful
spec-07 commit) — **newest version v254 @ 2026-07-20 16:09:23 UTC**. Writes were
regular through then, then stopped dead. But the theme-write bisect is
confounded: the runtime-editor job is *cancelled* (timeout) on **every** run in
the window — including the run that wrote v254 — so "no v255" could mean spec 07
failed *or* was never reached. The theme table dates the boundary; the per-spec
CI logs pin it.

**Per-spec bisect (spec 01, the simplest failing spec):**

| CI run start (UTC) | head commit | spec 01 result |
|---|---|---|
| 2026-07-20 15:55 | `0294399d` | **✓ PASS** (1 attempt, no retry) |
| 2026-07-20 17:56 | `323a35d4` | **✘ FAIL** (attempt + retry #1) |
| 2026-07-20 18:31 | `796572e5` | ✘ FAIL |

The regression landed in **`0294399d..323a35d4`** — exactly two commits:

- `18ed66ca` "Map performance: profile-first — the purge finally runs, the tripwire lands"
- `323a35d4` "Map cards second profile: the SSE 404 loop dies, Server-Timing lands"

**Full diff of the window** (`git diff 0294399d..323a35d4`):

| file | staging-runtime? | note |
|---|---|---|
| `backend/app/main.py` (+23) | **YES (backend)** | new `@app.middleware("http")` Server-Timing (`BaseHTTPMiddleware`) + CORS `expose_headers:["Server-Timing"]` |
| `frontend/src/contexts/call-context.tsx` (±10) | **YES (frontend)** | `connect()` → `async`, adds `await import("@/lib/api-client")`, SSE URL relative → `resolveApiBaseUrl()` base |
| `backend/scripts/purge_dev_residue.py` (+252) | no | dev script |
| `backend/tests/conftest.py` (+53) | no | test-only |
| `STATE.md` | no | doc |

Only **two** changes reach deployed staging: the Server-Timing middleware
(backend) and the call-context SSE-connect change (frontend). Both are from the
same "map-performance" arc; both sit on the request / SSE path. `CallContextProvider`
is mounted in the shell's provider tree (`lib/runtime-host/TenantProviders.tsx`).

---

## Job 2 — Why spec 10 survives (the prime suspect)

`spec 01` (fails) vs `spec 10` (passes), by opener:

- **01** → `openEditorForHopkins` = `loginAsPlatformAdmin` (CI-bot) → tenant
  lookup → **impersonate** → `page.goto('/bridgeable-admin/runtime-editor/…')` →
  assert `runtime-editor-shell` visible (30 s). All of 01–09/11 share this opener
  (`openEditorForHopkins`/`ForTestco`/`ForStMarys`).
- **10** → `loginAsHopkinsDirector` = a plain tenant login at the tenant origin;
  asserts the runtime-editor test-ids are *absent*. **No platform admin, no
  impersonation, no shell.**

**What 10 avoids = impersonation + the runtime-editor shell mount.** That is the
shared dependency and the prime suspect. Two things sharpen it to *not* be the
obvious culprits:

- **CI-bot auth is NOT the cause.** The *passing* Claude-API suite
  (`workflow-authoring-1b.spec.ts`) imports and calls the **same**
  `loginAsPlatformAdmin`, then hits a platform endpoint with the token — and
  passes 5/5. Platform admin auth + platform API both work under this exact
  middleware.
- **Tenant `/api/v1` is NOT broken.** Spec 10 loads the tenant app; my own
  post-deploy staging checks (S-1 portal, saved-views, latency) all hit
  `/api/v1/*` successfully under the live middleware.

So the failure is specific to **impersonation → SPA shell mount**, the one path
no passing test exercises. The `~32.7 s` failure duration ≈ the 30 s
`toBeVisible`/`goto` timeout — a *hang* (something never resolves), not a fast
auth reject.

**Leading mechanism (hypothesis — needs the actual error to confirm):** the
opener ends with `page.goto(...)` then `waitForLoadState("networkidle")`. A
single perpetually-pending request stalls `networkidle` forever → the shell-visible
wait times out at 30 s. The two window changes both plausibly produce a hung
request:

1. **Server-Timing `BaseHTTPMiddleware`.** `@app.middleware("http")` is
   Starlette `BaseHTTPMiddleware`, which **buffers the response** —
   `await call_next(request)` before returning. A self-contained local repro
   (exact middleware + a `StreamingResponse`) confirms it collapses streaming to
   buffered (`content-length: None`, whole body delivered at once). For a
   **long-lived SSE** (RingCentral events, or any keep-alive stream), the
   generator never ends → `call_next` never returns → the request **hangs
   indefinitely** → `networkidle` never fires. This is the documented
   BaseHTTPMiddleware-vs-streaming failure, and this arc was literally "the SSE
   404 loop dies."
2. **call-context SSE change.** `connect()` became `async` with an inline
   `await import(...)`; it opens `EventSource(${resolveApiBaseUrl()}/…/ringcentral/events)`.
   Mounted in the shell's provider tree. Guarded by `rc_overlay_enabled`, and the
   same user in 01 vs 10 — so it does not *by itself* explain the asymmetry —
   **unless** `resolveApiBaseUrl()` resolves differently under the admin
   (`/bridgeable-admin/…`) origin than under the tenant origin, pointing the SSE
   at a URL that hangs only in the impersonated/admin context.

The asymmetry (10 passes, 01 fails) is not yet fully explained by either change
alone; that is exactly what the actual error will resolve. Both suspects are in
the pinned two-commit window; the middleware is the single backend runtime
change and the strongest candidate.

---

## Job 3 — Getting the actual error (it is hiding, twice over)

**Why no one has seen it:**
- Reporter is `list,html`. The **list** reporter prints each failure's error
  block only in the **final summary**; the job is **cancelled at the 20-min cap
  before that prints**.
- The **html** report + trace/screenshot artifacts upload on `if: failure()` —
  but a timeout makes the job **`cancelled`, not `failed`**, so
  `actions/upload-artifact` **never runs**. No trace has ever been produced.

**Local run — BLOCKED.** Spec 01 needs `STAGING_BACKEND` (fine) +
`STAGING_CI_BOT_PASSWORD` — a GitHub Secret, confirmed **absent** from every
local `.env` and the shell env. Per CLAUDE.md it lives only in GitHub Secrets.
So the suite cannot be run locally as-is.

**Precise plan to surface it (do not run — specify):**

- **Option A (best): reduced-scope CI run.** Run only
  `01-picker-lands-on-dashboard.spec.ts` (workflow_dispatch input, or a one-line
  change to the `run:` step's path). It fails in ~70 s (2 attempts), so the job
  **fails (does not cancel)** → the list summary prints the full error **and**
  the `if: failure()` trace/screenshot/HTML upload fires. The Playwright trace
  shows the exact hung request or failed assertion. This is the unblock.
- **Option B: fix the masking first.** Change the upload steps'
  `if: failure()` → `if: '!cancelled()'` (or `always()`). Then even the current
  timing-out run uploads its partial trace + screenshots. ~2 lines; also the
  permanent fix for "cancellation hides the error" (§Job 4).
- **Option C (local): provide `STAGING_CI_BOT_PASSWORD`** out-of-band and run
  `npx playwright test …/01-*.spec.ts` against staging. Fastest if the secret can
  be shared.

---

## Job 4 — Suite-red vs job-timeout: ONE problem

Measured from the current run's log:

| phase | duration |
|---|---|
| deploy gate (wait for staging to serve the SHA, 2× healthy) | **9 m 59 s** |
| spec run before cancellation (all failing, 30 s × 2 retries) | **9 m 20 s** |
| **total** | **19 m** → hits the 20 m cap |

If the specs **passed** (~12 s each × 11, no retries ≈ 2 min), total ≈ **12 min
< 20**. **So fixing the suite fixes the timeout — one problem, not two.** The
slow failures are what blow the budget.

**Caveat worth flagging:** the **~10-minute deploy gate is a large fixed
overhead**. Even fully green the job runs ~12 min, leaving thin margin; a slower
staging deploy could re-breach the cap independently. Not the current cause, but
a standing fragility. (The timeout is one of the two long-standing known CI
reds; this explains it.)

---

## Job 5 — Blast radius + teardown validation

**Blast radius: CONTAINED — no STOP.** The failing dependency is
impersonation + the runtime-editor shell mount. The evidence bounds it:

- Claude-API suite (`workflow-authoring` + `-1b`): **passes** — uses
  `loginAsPlatformAdmin` + platform/tenant API, **no impersonation, no shell**.
- Spec 10: **passes** — plain tenant app.
- My own staging verification (S-1, portal, saved-views, r145 items 1–4):
  **all passed** — `/api/v1/*` under the live middleware is fine.

No non-runtime-editor suite mounts the runtime-editor shell under impersonation,
so the coverage blackout is limited to this one suite. (The middleware itself
touches every request, but it demonstrably does **not** break the
proven-working paths — so "the middleware" is the trigger, not a
platform-wide breakage.)

**New spec-07 cemetery teardown — BLOCKED, as reported.** `openEditorForStMarys`
+ `resetVerticalThemeOverrides` (this session's residue-hardening) can only be
validated once spec 07 reaches a successful commit, which is gated behind the
suite-wide shell-mount failure. Item 4 of the last verification (cemetery = 0
theme rows *ever*) is *because nothing was ever written*, **not** proof the
teardown works. **What unblocks it:** a green shell mount (this investigation's
fix) → spec 07 commits → the afterEach fires → cemetery resets to `{}`. Until
then the teardown is untested code.

---

## Deliverables

1. **Regression window:** `0294399d..323a35d4` = commits **`18ed66ca` +
   `323a35d4`** (the "map-performance" arc, 2026-07-20 ~17–18 UTC). Pinned by
   spec-01 ✓→✘ across consecutive CI runs. Not the chrome/steel pivot.

2. **Shared dependency 10 avoids (prime suspect):** **impersonation +
   `/bridgeable-admin/runtime-editor/` shell mount.** Ruled out along the way:
   CI-bot auth, platform API, tenant `/api/v1` (all proven working by passing
   tests). The single deployed backend change in the window is the Server-Timing
   `BaseHTTPMiddleware`; the single deployed frontend change is the call-context
   SSE-connect rewrite. Both are on the request/SSE path and both sit in the
   shell's provider tree — the two concrete suspects.

3. **Actual error:** not recoverable from CI (list summary truncated by
   cancellation; artifacts skipped because `if: failure()` ≠ cancelled) and not
   runnable locally (secret absent). **Surface it via Option A** — a
   reduced-scope CI run of spec 01 (fails fast → not cancelled → trace + error
   both fire). Leading hypothesis to confirm: a `BaseHTTPMiddleware`-buffered
   long-lived SSE (or an admin-origin SSE-base misresolve) hangs a request →
   `networkidle` never settles → 30 s shell-mount timeout.

4. **One problem or two:** **ONE.** Fixing the specs (fast pass) drops the job
   to ~12 min and the timeout resolves. Caveat: the ~10-min deploy gate is a
   large fixed overhead worth its own look.

5. **Type B calls + LOC floor** (below).

---

## Type B calls for James

1. **Authorize the unblock.** Either (a) a reduced-scope CI run of spec 01
   (workflow_dispatch or a one-line path change) to capture the trace, or (b)
   share `STAGING_CI_BOT_PASSWORD` for a one-off local run. Nothing else
   progresses without the actual error.
2. **Land the CI-hygiene fix regardless:** upload steps `if: failure()` →
   `if: '!cancelled()'`. ~2 lines. This is *why the suite was invisibly red for
   weeks* — a timed-out job uploaded nothing. Worth doing even before the root
   cause is known; it makes the next failure legible.
3. **Prioritization.** This is a total e2e-coverage blackout on the visual
   editor's only staging gate since 2026-07-20, and it currently blocks
   validating the spec-07 cemetery teardown. But blast radius is contained (no
   other suite, no product-facing surface — the runtime editor is admin
   tooling). Fast-follow vs S-2?
4. **Root-cause fix shape (pending the error), likely one of:** remove the
   Server-Timing middleware (it's a devtools convenience — ~3 LOC delete) or
   rewrite it as pure-ASGI so it doesn't buffer streams (~15 LOC); or fix the
   call-context SSE base-resolution under the admin origin. Decide after the
   trace names the hung request.

**LOC floor to a green suite:** ~2 LOC (CI upload-on-cancel, to see the error) +
the root-cause fix (unknown until the trace; **likely 3–15 LOC** if it's the
middleware) ≈ **a single focused arc, GATED on the reduced-scope run first**.
The floor is small; the gate is diagnostic access, not code volume.

---

*Read-only confirmation: no source changed, no schema, no seed, no commits,
nothing pushed. Staging access was SELECT/GET only; the one code execution was a
self-contained in-memory FastAPI repro under the session scratchpad. Artifacts
of this session: this findings file only.*

---

## Addendum (2026-07-23, second pass) — Part 1 landed, hypothesis SHARPENED and the prime suspect FLIPPED

**Part 1 (CI hygiene) — committed `5c1cf834` (local, not pushed).** All six
artifact/report upload steps across the three Playwright-Staging jobs
(runtime-editor, Claude-API, MoC) changed `if: failure()` →
`if: ${{ failure() || cancelled() }}`. Sibling audit: `ci.yml` and
`seed-idempotency.yml` have no upload steps — nothing to change.
**Correctness note:** the dispatch's suggested `!cancelled()` would be *wrong* —
it is `false` on a cancelled job, so it would still skip the timeout case;
`failure() || cancelled()` fires on both failure and timeout and skips clean
green, and referencing `cancelled()` is required for GitHub to run a step at all
on a cancelled job.

**Part 3 STOP — DECLARED LOUDLY. The shell opens NO streaming request the
director home skips.** The *only* real browser `EventSource` in the entire
frontend is `call-context.tsx:218` (the `delivery.ts` "EventSource" is a string
*type alias*, not a connection). It lives in the **shared** `TenantProviders`
that both the shell (spec 01) and the tenant home (spec 10) mount. No WebSocket,
no `ReadableStream`, no long-poll anywhere in the mount path. **The original
hypothesis — a shell-unique SSE that `BaseHTTPMiddleware` buffers — is broken.**
Empirical confirmation the middleware does *not* buffer the SSE: a live GET to
`/api/v1/integrations/ringcentral/events` returns `200 text/event-stream` with
**headers arriving promptly** and the connection held open — normal SSE, not a
buffered hang.

**But the asymmetry has a stronger, code-consistent explanation that flips the
prime suspect from the middleware to `call-context.tsx`:**

1. `call-context.tsx` (in `323a35d4`) changed its SSE URL from a **relative**
   `/api/v1/integrations/ringcentral/events` (which hit the *frontend* origin →
   404'd fast → no persistent connection) to an **absolute** URL via
   `resolveApiBaseUrl()`.
2. `resolveApiBaseUrl()` returns the **real staging backend** iff
   `localStorage["bridgeable-admin-env"] === "staging"`, else the tenant default
   (`VITE_API_URL`).
3. `loginAsPlatformAdmin` (the shell openers' first step, `_shared.ts:154`)
   **sets `bridgeable-admin-env`**. `loginAsHopkinsDirector` (spec 10) does not.
4. `rc_overlay_enabled` **defaults `true`** (`call-context.tsx:106`).

So in the **shell path only**, the shared SSE resolves to the real staging
backend and **establishes a persistent, long-lived EventSource**. Playwright's
`waitForLoadState("networkidle")` — the last line of every shell opener — treats
an open SSE connection as perpetual network activity and **never settles**,
timing out at ~30 s. That matches the observed 32.7 s failure to the second, and
it fires for *every* shell spec (01–09/11) because they all share the opener.
Spec 10 leaves `admin-env` unset, so its SSE resolves via the tenant default and
does not establish the same persistent backend connection → its `networkidle`
settles → it passes. Before `323a35d4` the SSE 404'd fast in every context → no
persistent connection → `networkidle` fine → suite green (spec 01 ✓ at
`0294399d`).

**The Server-Timing middleware is most likely EXONERATED** for this failure
(proven: it doesn't buffer the SSE headers, and platform + tenant APIs work
under it). It landed in the same commit, which is why it drew first suspicion.

**Residual uncertainty (why the trace is still required):** the exact value of
`VITE_API_URL` baked into the deployed staging frontend, and thus whether spec
10's tenant-path SSE truly fails to establish, is not readable from source. The
mechanism above is inferred from code + one live SSE probe; the Part-2 trace
closes it by showing precisely which request is pending during spec 01's opener
(expected: a pending EventSource to
`https://sunnycresterp-staging.up.railway.app/api/v1/integrations/ringcentral/events`).

**Fix shapes ready (DO NOT commit — the trace decides):**
- If confirmed `call-context`/`networkidle`: the durable fix is in the **test
  opener** (stop using `networkidle`; wait on the `runtime-editor-shell` testid
  directly — `networkidle` is Playwright-discouraged precisely because SSE/poll
  block it), and/or gate the RingCentral SSE off under impersonation/editor
  context. ~5–15 LOC, test-side, no app risk.
- The Server-Timing `BaseHTTPMiddleware` *can* be made non-buffering without
  removal (rewrite as a pure-ASGI middleware that wraps `send` to inject the
  header, instead of `@app.middleware("http")`) — but this is likely unrelated
  to the suite red and should be evaluated on its own merits, not as this fix.

**Part 2 — exact invocation to capture the trace (specified, NOT run):** the
`run:` step (`playwright-staging.yml:99`) hardcodes the full suite; `workflow_
dispatch` exists but has no spec-scoping input. Minimal temporary change (push on
a throwaway branch / temp commit; James triggers) — replace line 99 with:

```
run: npx playwright test tests/e2e/runtime-editor/01-picker-lands-on-dashboard.spec.ts tests/e2e/runtime-editor/10-tenant-operator-regression.spec.ts --project=chromium --reporter=list,html
```

Runs spec 01 (fail control) + spec 10 (pass control). retries=1, workers=1,
per-test timeout=60 s → ~70 s for 01's two attempts + ~10 s for 10 → the job
**fails fast (~2 min), does not cancel** → with Part 1's fix the trace +
screenshots + HTML report upload **and** the list summary prints spec 01's full
error. Download `playwright-artifacts-<run#>`, open the trace, read the pending
request during the opener. **Local execution remains impossible** —
`STAGING_CI_BOT_PASSWORD` is a GitHub Secret, confirmed absent from every local
`.env` and the shell env.
