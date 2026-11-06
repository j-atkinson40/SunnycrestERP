# What a payroll-limited user can actually reach on production

**2026-11-06. Read-only probe against production, as the real Payroll-role user
James created. Deployed commit `5b2a8b22`.**

Raised because production did not match the staging check: the staging run
reported "nav renders the Payroll item alone", and on production James sees
Home, Bridgeable Map, Payroll, Financials, Agents, Production, Resale,
Knowledge Base, Settings, a pinned Home, Pin widget, Get started and the search
bar.

James's framing, which set the priority: *"the landing page and the menu are
cosmetic, as long as the server refuses everything outside payroll. Step 1 is
the part that matters. If anything returns real data, that's a leak, and it
gets fixed before anything else."*

## Verdict

**No leak.** No endpoint outside payroll returned tenant business data. Every
200 is either the shell boot chain James already approved as the 7-entry common
allowlist, her own payroll area, or her own second-factor status.

## Method, and what bounds it

- **Exhaustive over parameterless GETs, not a sample of the nav items.** 568
  routes — every `GET` under `/api/v1/` with no path parameter. Probing the
  thirteen things James listed would have been a claim about a sample reported
  as a claim about the surface.
- **GET only.** No `POST`/`PATCH`/`DELETE` was issued against a live tenant.
  Write exposure was therefore established by READING the dependency tree, not
  by probing — stated separately below so the two kinds of evidence are not
  confused.
- **Routes needing a path parameter were skipped, not guessed.** A guessed id
  returns 404 and tells you nothing about authorization.
- ⚠️ **The token was minted inside the probe process and never left it.** Not
  printed, not written to disk, not passed in argv. The standing rule is that
  no credential transits a session; the restructure that satisfies it is to
  mint and spend inside one process whose only output is status codes.
- ⚠️ **No `mfa` claim on the token, deliberately.** She signed in with a
  password and the tenant's two-step requirement is off, so that models her
  real session. Adding the claim would have minted a stronger token than she
  holds and could only have made the result look safer than it is.

## Result

    status distribution    403: 551     200: 14     422: 3
    403 detail code        area_restricted, on all 551

The three 422s are reachable endpoints missing a required query parameter —
`/themes/resolve` and `/edge-panel/resolve` (both common set) and
`/payroll-reports/reports/monthly-dues-remittance` (her own area). Reachable,
and correctly so.

### All 14 of the 200s

| path | why reachable | what came back |
|---|---|---|
| `/auth/me` | common | her own identity |
| `/edge-panel/preferences` | common | her own overrides |
| `/edge-panel/tenant-config` | common | `enabled`, `width` |
| `/feature-flags/me` | common | her own flags |
| `/locations` | common | **list len=0** |
| `/locations/overview` | common | `locations`, `total_locations`, `totals` |
| `/locations/users` | common | **list len=1 — see the finding below** |
| `/notifications` | common | items 0, total 0, unread 0 |
| `/notifications/unread-count` | common | 0 |
| `/spaces` | common | her own workspace config |
| `/spaces/affinity/count` | common | 0 |
| `/payroll-reports/formats` | **her area** | format list |
| `/payroll-reports/weeks` | **her area** | count 0 |
| `/two-step/status` | `mfa_enroll`, unioned into every limited role by design | `enrolled`, `required`, `unused_recovery_codes` |

**No business numbers anywhere.** Locations empty, notifications empty, payroll
weeks zero, affinity zero.

### The nav items James asked about

Every data endpoint behind them returns **403 `area_restricted`**:

- **Financials** — `/financials/ar/*`, `/financials/ap/*`, `/finance-charges/*`
- **Agents** — `/agents/accounting`, `/agents/jobs`, `/agents/alerts`, `/agents/activity-log`
- **Production** — `/production/production-log*`, `/operations-board/production-log/today`, `/widget-data/production/daily-summary`
- **Resale** — urn endpoints, `/journal-entries/*`
- **Knowledge Base** — `/knowledge-base/*`
- **Settings** — `/companies/settings`, `/companies/tenant-settings`, `/briefings/*settings`
- **Home / the note** — `/briefings/*` (which is the error James saw, behaving correctly)
- **Search bar** — `POST /command-bar/query` is untagged and not in the common
  set, so the guard refuses it. Established from the route table rather than by
  firing a POST; corroborated by two sibling GETs
  (`/core/command-bar/recent`, `/nl-creation/entity-types`) measuring 403 in
  the probe.

So the menu items render chrome and then error. **None of them shows a number.**

## ⚠️ The one finding: `/locations/users` is not caller-scoped

Below STOP level — it is not business data and not payroll data — but real, and
it is an over-grant rather than a cosmetic issue.

    GET /locations/users
      own gate:  get_current_user + company_id
      docstring: "List all user-location access assignments for the company"
      returned:  1 row, belonging to A DIFFERENT USER, access_level='admin'

The allowlist entry that admits it reads:

> `/locations` — `LocationProvider` is in the boot chain above the route tree.
> Returns the tenant's facility list — organisational configuration, not
> business records.

That justification describes `GET /locations`. It does not mention the per-user
access table, which the same prefix also admits. **The allowlist granted more
than its own stated reason covers** — the hazard `is_common`'s segment-boundary
comment worries about, arriving through prefix BREADTH rather than through
sloppy matching.

Today's exposure is one row disclosing that another user holds admin-level
location access. Tomorrow's is however many rows that table grows.

### What the `/locations` prefix admits, and what saves it

Ten routes, four of them writes. **All four writes carry `require_admin`**, so
a payroll-limited user cannot write — the area guard lets them past and the
endpoint's own gate refuses them. Defence in depth, working as designed, and
the reason this is a finding rather than an incident.

    DELETE  /locations/users/{access_id}      require_admin      refused
    DELETE  /locations/{location_id}          require_admin      refused
    PATCH   /locations/{location_id}          require_admin      refused
    POST    /locations                        require_admin      refused
    POST    /locations/users                  require_admin      refused
    GET     /locations                        get_current_user   company-wide
    GET     /locations/overview               get_current_user   company-wide
    GET     /locations/users                  get_current_user   company-wide ⚠️
    GET     /locations/{location_id}          get_current_user   company-wide (no ids exist today)
    GET     /locations/{location_id}/summary  get_current_user   company-wide (no ids exist today)

⚠️ **Established by reading the dependency tree off the live app, NOT by
probing** — no write was issued. That is weaker evidence than a measurement and
is labelled as such.

## Why staging showed only Payroll and production does not

`navigation-service.ts::filterByPermission`:

```js
// Functional area filtering — only applied when areas are configured
if (item.functionalArea && areas && areas.size > 0) {
```

`areas` is `employee_profiles.functional_areas`. For this user on production it
is **`[]`**. So `areas.size === 0`, the whole branch is skipped, and every item
gating on `functionalArea` passes unfiltered. **Empty is read as "unrestricted"
rather than "restricted to nothing".**

- `Financials`, `Agents`, `Production` declare `functionalArea`, not
  `permission` — nothing else stops them.
- `Resale` declares `requiresExtension: "urn_sales"`, and `urn_sales` is active
  on sunnycrest.
- Modules enabled on sunnycrest: `core`, `daily_production_log`,
  `driver_delivery`, `inventory`, `purchasing`, `safety`, `safety_management`,
  `sales`. Extensions: `disinterment_management`,
  `funeral_home_coordination`, `funeral_kanban_scheduler`,
  `legacy_print_generator`, `urn_sales`.

⚠️ **AND THE DEEPER FAULT IS THAT THESE ARE TWO DIFFERENT LISTS.**
`filterByPermission` never consults `limited_to_areas` at all. The server
refuses by `roles.limited_to_areas`; the sidebar decides by
`employee_profiles.functional_areas` — a different concept, on a different
table, written by a different code path. Staging and production disagreeing is
a symptom of that, not of one of them being stale. Any fix that populates
`functional_areas` to match would be a second copy of the truth that drifts
again; the fix is for the frontend to read the allowed areas the server
actually enforces.
