# What environments exist, and one way the e2e suite can reach production

**2026-09-23.** Read-only. No suite was run against any deployed environment.

**Two answers, and the second is a STOP.**

1. **Staging is real.** The workflow's name is not the evidence — the hosts are, and they are
   distinct from production in every file that names them.
2. ⚠️ **But 44 of 48 e2e files fail OPEN to production.** Every intercept ends
   `catch { route.continue() }`, which sends the *original* request to
   `api.getbridgeable.com`. It triggers exactly when staging is unreachable.

---

## 1. The environments

Established by grepping every `*.up.railway.app` and `*.getbridgeable.com` host named
anywhere in `.github`, `backend/`, `frontend/src` and `CLAUDE.md`:

```
https://sunnycresterp-staging.up.railway.app        12   staging backend
https://api.getbridgeable.com                       12   production backend
https://determined-renewal-staging.up.railway.app    3   staging frontend
https://app.getbridgeable.com                        2   production frontend
```

Four hosts, two environments, each with a separate frontend and backend service — so at
least four Railway services.

⚠️ **NOT ESTABLISHED FROM INSIDE A SESSION: which database each points at.** `DATABASE_URL`
lives in the Railway dashboard by CLAUDE.md §7's rule, and nothing in the repo records it.
Two `-staging` hostnames are strong evidence of a separate environment and are *not* evidence
of a separate database. That is the one part of this question that needs the dashboard.

## 2. What `playwright-staging.yml` targets

Hard-coded literals, not secrets and not variables — `playwright-staging.yml:45-46`, repeated
per job at :161 and :250-251:

```yaml
STAGING_BACKEND:  https://sunnycresterp-staging.up.railway.app
STAGING_FRONTEND: https://determined-renewal-staging.up.railway.app
```

Only the credential comes from secrets (`STAGING_CI_BOT_EMAIL`, `STAGING_CI_BOT_PASSWORD`).
Nothing in `.github/` names a production host.

## 3. The frontend build differs — and staging's bundle points at production

`frontend/Dockerfile` takes `ARG VITE_API_URL` and writes it into `.env.production` at build
time, so each service's bundle carries whatever its Railway build arg supplies.

⚠️ **AND STAGING'S IS SET TO PRODUCTION.** `frontend/tests/e2e/E2E_REPORT.md:14` records it
in terms:

> "The staging frontend has `VITE_API_URL=https://api.getbridgeable.com` (production API),
> but test data lives in the staging database."

Its stated solution, at :16, is the interception in §4: Playwright rewrites every
`api.getbridgeable.com` call to the staging backend.

**So the staging frontend is a production-pointed bundle, made safe only by a test-time
rewrite.** A human opening the staging URL in a browser gets no rewrite at all.

## 4. ⚠️ THE STOP — the intercept fails open

`frontend/tests/e2e/runtime-editor/_shared.ts:89`:

```js
await page.route(`${PROD_API}/**`, async (route) => {
  const url = route.request().url().replace(PROD_API, STAGING_BACKEND)
  try {
    const response = await route.fetch({ url })
    await route.fulfill({ response })
  } catch {
    await route.continue()          // ← sends the ORIGINAL request to production
  }
})
```

`route.continue()` forwards the request **unmodified** — to `api.getbridgeable.com`, with its
original method and body.

```
e2e files installing page.route           48
       ending in route.continue()         44     ← fail open to production
       using route.abort()                 0     ← nothing fails closed
```

**The trigger is staging being unreachable**, which is precisely the condition that has held
for the last 13 days while the staging frontend was stuck. A `fetch` to a down host throws;
the `catch` then replays the call against production.

⚠️ **WHY THIS HAS PROBABLY NOT FIRED YET, AND WHY THAT IS NOT REASSURING.** Since 2026-05-11
every Playwright run has died at `loginAsPlatformAdmin` with a 401 before any page navigation
— the credential failure that has masked everything. No login means no page, no page means no
intercepted traffic. **The 401 has been acting as the safety mechanism.** The moment the
credential is fixed, the specs proceed, and this path becomes live.

So the sequencing matters: **fix the fail-open before, or with, the credential — not after.**

`route.abort()` in the `catch` would fail closed: the request dies, the spec fails, and
nothing reaches production. The current `continue()` is the opposite trade, and it was very
likely written as "be permissive so the test still works" without the production host being
front of mind.

⚠️ **Whether a write would actually land is NOT established.** It depends on production's
auth rejecting a staging-issued token — likely, but that is a claim about production's
behaviour that this investigation did not test and must not assume. The mechanism reaches
production; what production does with it is unmeasured.

## 5. `/version.json`, and why the frontend was stuck for 13 days

Emitted by a vite plugin in `frontend/vite.config.ts`, in `closeBundle`, which fires **only
after a successful `vite build`**. `npm run build` is `tsc -b && vite build`.

The plugin's own docstring states the consequence:

> "a tsc failure (e.g. an unused import) means vite build never runs, closeBundle never
> fires, and version.json never advances… a broken build leaves BOTH stale, so the gate fails
> loudly instead of testing a stale bundle."

**Measured today, and it closes the loop on this arc:**

```
staging frontend stuck at   8fd6fbd   2026-09-10 08:47
TS error introduced in      0b157e5f  2026-09-10 13:27   (+4h40m)
```

The `hasPermission: () => false` mock — one of the three errors fixed in `bc216649` — landed
four hours and forty minutes after the last successful frontend build. `tsc -b` began failing,
`vite build` stopped running, and the frontend froze.

**The cause was in the repo the whole time.** It did not need the Railway dashboard.

## 6. Verified after the push

`bc216649` fixed those three errors. On the run it triggered:

```
CI                  Frontend CI: success    Backend CI: success     ← first green since 2026-05-11
Playwright          deploy-gate TIMEOUTs: 0                         ← the gate PASSED
                    all 86 failures: "Platform admin login failed: 401"
```

The specs now reach the point of logging in, which they have not done since May. **Playwright
is blocked solely on the credential.**

## 7. What this changes

- **"Railway build logs for the stuck frontend" is resolved** and was never a dashboard task.
- **`provision_ci_bot --ensure` is now the only thing between Playwright and green** — and
  per §4 it should not be done before the fail-open is closed.
- **"The jurisdiction conflict exists on staging"** stands as written. Staging is real and
  has its own boot seeds.

## 8. What this does not establish

- Which database each Railway service points at (§1).
- Whether production would accept a staging-issued token (§4).
- Whether any spec drives a write through an intercepted route in practice, as opposed to the
  mechanism permitting one.
