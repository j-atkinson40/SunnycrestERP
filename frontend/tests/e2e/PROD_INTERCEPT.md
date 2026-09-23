# The production intercept, and why it must fail closed

Every browser-based e2e spec installs a route intercept that rewrites
`https://api.getbridgeable.com/**` to the staging backend. **That intercept is the only
thing standing between this suite and the production API.**

## Why the intercept exists at all

The staging frontend is built with `VITE_API_URL=https://api.getbridgeable.com` — the
**production** API (`frontend/Dockerfile` takes it as a build arg; recorded in
`E2E_REPORT.md:14`). So the staging bundle asks for production by default, and the specs
rewrite each call to staging at test time.

A human opening the staging URL in a browser gets no rewrite.

## ⚠️ The rule: the catch aborts, it never continues

```js
await page.route(`${PROD_API}/**`, async (route) => {
  const url = route.request().url().replace(PROD_API, STAGING_BACKEND)
  try {
    const response = await route.fetch({ url })
    await route.fulfill({ response })
  } catch {
    await route.abort()   // ← NOT route.continue()
  }
})
```

`route.continue()` forwards the **original** request — original host, method and body — to
production. `route.abort()` kills it: the spec fails, and nothing leaves.

**The catch fires when staging is unreachable**, which is the condition under which sending
the request anywhere is least defensible.

## What was measured, 2026-09-23

Every one of **42 sites** routing the production host ended in `catch { route.continue() }`.
**Zero** used `route.abort()`. Two are shared helpers (`runtime-editor/_shared.ts`,
`intelligence/auth-setup.ts`); forty are per-spec copies of the same block.

Observed against a local sink standing in for production, so the test could not send the
request it was checking for:

```
fail-closed (abort)     sink received 0 requests
fail-open   (continue)  sink received 1:  REACHED POST /api/v1/write
```

⚠️ **A POST with a body arrives.** And in the failing run the page itself reported the fetch
as blocked — a CORS rejection of the *response* — while the request had already landed. **The
page-level symptom does not indicate the request was prevented.**

⚠️ **THIS HAD NOT FIRED ONLY BECAUSE OF AN UNRELATED OUTAGE.** Since 2026-05-11 every
Playwright run died at `loginAsPlatformAdmin` with a 401 before any navigation. No login, no
page, no intercepted traffic — the dead CI credential was the safety mechanism. Fixing it
without this change would have made the path live.

## The guard

`prod-intercept-fail-closed.spec.ts` parses every `.ts` file under `tests/e2e/` and fails if
any production-host route handler has `route.continue()` in its catch. It is a source scan,
not a runtime test — it needs no browser and no network.

It matches on structure rather than on the literal text, because the same defect can be
written several ways (`await route.continue()`, `return route.continue()`, a different
catch binding) and because a literal search for the pattern finds the guard itself.

## If you are adding a spec

Copy the block above, or import `setupPage` from `runtime-editor/_shared.ts`. Do not write
your own fallback.
