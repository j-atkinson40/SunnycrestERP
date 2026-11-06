# What actually authorizes a tenant route — a census

**2026-11-06. Read-only. No fixes.** Item 3 from the 2026-11-06 security
sequence, promoted after `POST /auth/register` showed that an account was easy
to obtain and unconstrained once obtained. Closing registration removed the
easy way to GET such an account and changed nothing about what one reaches.

## The headline, measured rather than reasoned

**A zero-permission account reaches exactly what an office user reaches.**

    role        group-3 GETs served 200 (of 348 probed)
    employee                 274          permissions: []
    office                   274          permissions: a full office set
    driver                   275

    served by office but NOT by the zero-permission employee:  0
    served by employee but NOT by office:                      0
    driver-only:                   /api/v1/delivery/drivers

The two served sets are **identical**, not merely the same size. Permissions are
not what gates this surface. Being signed in is.

⚠️ **THE CONTROL IS WHAT MAKES THAT READABLE.** All 12 group-1 routes probed as
controls returned **403 for all three roles**. So the probe held a real
credential and the guard machinery works; 274 × 200 is not "the probe was
unauthenticated and everything 401'd into a 200-shaped hole".

## The census

Classification is by code: the full FastAPI `Dependant` tree for signatures, AST
over the handler body for in-handler checks. Method stated so it can be
disagreed with.

| group | pairs | % | what gates it |
|---|---|---|---|
| 1 | 360 | 18.8% | `require_admin` / `require_permission` in the tree, **or** an `area:` tag |
| 2 | 496 | 25.9% | an explicit check in the handler body |
| 3 | **1,012** | **52.8%** | nothing beyond "signed in" |
| 0 | 50 | 2.6% | no authenticated user at all |

Total tenant method+path pairs under `/api/v1`: **1,918**. Portal realm (7) and
platform realm (8) excluded and counted separately.

⚠️ **MY EARLIER FIGURE OF 1,027 WAS PRODUCED BY A WORSE METHOD AND THE
AGREEMENT IS A COINCIDENCE.** That one read endpoint SIGNATURES only. Signatures
miss dependencies attached at `include_router(dependencies=[...])` or inherited
through a nested router — which put the **entire `/urns/*` module**, 40-odd
routes including order creation and pricing imports, into "no authenticated user
at all". False, and a spectacular thing to have reported. The pre-existing sweep
`test_no_tenant_route_resolves_a_company_without_requiring_a_user` says so in
its own docstring: walk the tree, not a grep. 1,027 and 1,012 landing near each
other is **two offsetting errors adding up**, not corroboration.

### Group 3 by router — 1,012 pairs, 111 routers, **532 of them writes**

    44 /companies   43 /urns      36 /onboarding   29 /fh        28 /widget-data
    27 /tenant-onboarding  27 /work-orders  25 /extensions  25 /programs
    21 /tax         21 /moc       20 /statements   19 /email     19 /price-management
    19 /capture     18 /onboarding-flow  17 /reconciliation  16 /agents
    15 /ai          15 /legacy    14 /spaces       14 /driver    13 /briefings
    13 /operations-board  13 /reports  12 /journal-entries  ... (86 more)

### What a zero-permission account actually reads — a sample of the 274

    /agents/accounting              /agents/alerts          /agents/periods/locked
    /agents/activity-log            /ai/agents/runs         /ai/duplicates
    /billing-groups                 /briefings/briefing     /briefings/v2
    /behavioral/insights            /announcements/my       /announcements/permissions

⚠️ **`GET /api/v1/ai/agents/run-nightly` IS IN THE SERVED SET.** A GET that
reads as triggering work, reachable by an account with no permissions. Not
investigated further here; flagged because a GET that acts is a different kind
of problem from a GET that discloses.

### Harmless vs not

Of the 274, the clearly harmless are own-profile, health, static catalogues and
shell configuration — the `/auth`, `/health`, `/feature-flags/me`,
`/edge-panel`, `/themes`, `/spaces`, `/permissions`, `/locations` shapes, which
is roughly 20–30 pairs. **The rest read tenant business data**: accounting agent
output and anomalies, billing groups, briefings composed from real orders and
invoices, behavioural insights, statements, tax, price management, reconciliation.

⚠️ That split is a **judgement I made from router and handler names**, not a
measurement of response contents, and it is the weakest claim in this document.
A per-route content classification is real work and was not done.

## Group 0 — 50 routes with no authenticated user

Almost all legitimate and intentional: token-as-auth (`/sign/{token}/*`,
`/invites/{token}*`, `/urns/proof-approval/{token}*`, `/portal/family/{token}*`,
`/intake/{token}`, `/agents/approve/{token}`, `/calendar/actions/{token}`,
`/email/actions/{token}`), OAuth callbacks (QBO, RingCentral, Dropbox, GDrive),
webhooks (DocuSign, Gmail, MS Graph, Twilio, RingCentral), `/auth/login`,
`/auth/refresh`, the portal's own login/branding/recovery, `/companies/register`,
and the CAPTCHA-gated intake adapters.

Three more were checked individually and are fine:
`/integrations/ringcentral/events` (JWT in the query string, because EventSource
cannot send headers — documented at the site), `/vault/calendar.ics`
(`calendar_token`), `/personalization/config` (static platform config, no DB, no
tenant).

### ⚠️ One finding: `GET /website-intelligence/debug-network`

`app/api/routes/website_intelligence.py:161`. Unauthenticated. Takes an
arbitrary `url` query parameter and, by its own docstring, runs *"the FULL
intelligence pipeline synchronously"* against it. Self-described as *"Temporary
endpoint"*.

That is **server-side request forgery** — anyone can make the production server
fetch a URL of their choosing — plus an uncapped scrape-and-AI run per request,
which is a cost and availability surface as well as a security one.

Measured on production **without triggering a fetch**: no params → **422**, so it
is reachable with no credential and validation refused before the scrape;
`?url=` empty → **200**, so the handler does execute. **No real URL was
supplied, so production made no outbound request on my account.**

## Proposed shape — deny by default, using the area mechanism

Not built, not started. The mechanism already exists and is proven: 551 of 568
routes refused for the payroll role, verified on production.

### Why the area mechanism rather than adding 1,012 permission checks

`enforce_area_limit` is one dependency on `v1_router`. It already refuses
**untagged** routes for a role with a non-NULL `limited_to_areas` — so coverage
is a property of the guard rather than of 1,012 individual edits, and a new
endpoint is denied the day it ships instead of being open until someone
notices. The asymmetry points the right way: forgetting to tag costs a 403 and
a bug report; forgetting a permission check costs a disclosure nobody sees.

### Why it does not already work

⚠️ **`limited_to_areas` IS NULL FOR EVERY ROLE EXCEPT `payroll`, AND A NULL
LIMIT MAKES THE GUARD EARLY-RETURN.** This is the part that gets misread,
including in my own earlier reporting: "the guard closed 551 of 568 routes" is
true **of an area-limited user only**. For `office`, `employee`, `driver`,
`admin` it closes nothing, by design — it is an additional restriction on a
narrow role, never a replacement for per-endpoint authorization.

### The order, and why this order

**Phase A — expand the area vocabulary and tag routers. No behaviour change.**
`KNOWN_AREAS` holds two entries (`payroll`, `mfa_enroll`). Tags do nothing until
a role is limited, so this phase is inert and reviewable. Tag the riskiest data
first so its area membership is explicit rather than inherited from
untagged-denial: `/financials`, `/agents`, `/journal-entries`, `/statements`,
`/tax`, `/price-management`, `/purchasing`, `/reconciliation`,
`/inter-licensee-pricing`, `/finance-charges`.

**Phase B — one role, on a throwaway tenant, with the set comparison as the
gate.** For each role, derive its area list **from its measured before-set**,
not from a guess about what the role is for. Then:

    after_set  ⊇  before_set  −  intended_removals

A route lost that was not on the intended-removals list is a lockout and the
phase reverts. This is the only thing that protects today's users, and it is why
the before-sets were captured in this census rather than later: **a set
comparison needs the earlier set to exist, and after the change it cannot be
obtained.**

**Phase C — roll per role, least-privileged first:** `driver` (reaches 275, and
its one distinctive route is `/delivery/drivers`), then `employee`, then
`office`, then the specialist roles. `admin` last, or deliberately left NULL
with that decision recorded — an unlimited admin is a choice, and it should read
as one.

**Phase D — the writes.** 532 of group 3 are non-GET and this census did not
probe a single one of them, because probing a write mutates the database it is
probing. They are the sharper risk: a GET discloses, a write changes the books.
They need their own method — a staging tenant that can be discarded, or
per-route reading rather than probing.

### What this census does not establish

- **The 532 writes are unmeasured.** Stated as unmeasured, not assumed benign.
- **Group 2's 496 are classified by the presence of a check, not its
  correctness.** A handler that calls `user_has_permission` and ignores the
  result would land in group 2 and be wrong. Nobody read 496 handler bodies.
- **Parameterless GETs only** — 348 of group 3's 480 GETs. Routes needing a path
  parameter were skipped rather than guessed, so the probe covers 72% of the
  GET surface and none of the rest.
- **The harmless/business-data split is a judgement**, as noted above.
- **Dev, not production.** The roles and route table are the same; the data is
  not. 11 exceptions and 4 × 500 in the probe are dev-data artifacts, not
  findings, and were not chased.
