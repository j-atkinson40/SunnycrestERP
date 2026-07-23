# FH Case Table Split — Phase 1 Investigation (READ-ONLY)

**Date:** 2026-07-23 · **Trigger:** S-1 e2e tail finding — resolver's `fh_case`
entry searches `fh_cases` while peek/portal read `funeral_cases` + `case_deceased`.
**Scope:** findings only. No code changed, no schema changed, no migration authored,
nothing pushed.

---

## Verdict up front

`fh_cases` is the **first-generation FH case system (March 17, 2026, commit
`47462f40`)**, superseded a month later by the canonical FH-1 14-table model
(`funeral_cases` et al., April 17, `4289e212`) that FUNERAL_HOME_VERTICAL.md
documents — `fh_cases` does not appear in that canon inventory.

It is **NOT inert, and NOT deprecatable in this fix** — it is load-bearing for a
still-mounted parallel legacy stack (§1.3). **But it is empty of organic data
everywhere we can query** (dev: 49 rows, all test-fixture litter; staging: exactly
the 3 e2e-tail mirror rows; production unqueryable from here but has no FH tenant).
The resolver repoint is **separable and safe**: none of the load-bearing consumers
read through the resolver. Two distinct pieces of work fall out:

1. **The repoint** (S-1 follow-up, one commit) — move the resolver's `fh_case`
   branch to `funeral_cases ⋈ case_deceased`, new r144 trigram index, fix the
   `/cases/{id}` url_template to `/fh/cases/{id}`, update 4 command-bar test
   fixtures. Latency-proven safe (§3).
2. **Legacy FH-v1 retirement** (its own future arc — NOT this fix) — the `/cases`
   UI + router + 13 sibling tables + FK anchors + nav/pin targets (§1.3, §4.5).

Per the dispatch's STOP line: **STOPPING LOUDLY** on the deprecation half —
`fh_cases` is load-bearing for things other than the resolver, so "delete/deprecate
the table" is a real reconciliation, not part of the repoint. The repoint itself
does not require it.

---

## Job 1 — What is `fh_cases`?

### 1.1 Origin

- Created by migration `v4w5x6y7z8a9_add_funeral_home_tables` (13 `op.create_table`
  calls: `fh_cases`, `fh_case_contacts`, `fh_case_activity`, `fh_services`,
  `fh_documents`, `fh_invoices`, `fh_payments`, `fh_obituaries`,
  `fh_portal_sessions`, `fh_vault_orders`, `fh_price_lists`,
  `fh_manufacturer_relationships`, +1), commit `47462f40` **2026-03-17** — "Add
  Funeral Home vertical — complete case management from first call through final
  invoice." This was the whole FH vertical, v1.
- `funeral_cases` arrived in `fh_01_case_model`, commit `4289e212` **2026-04-17** —
  "FH-1a backend foundation: case model + staircase + scribe + story thread." The
  canonical rebuild. The two systems have coexisted since.

Schema (model `FHCase`, `app/models/fh_case.py`): denormalized single-row case —
`case_number`, `status`, `deceased_{first,middle,last}_name`,
`deceased_date_of_death` (+ ~20 more deceased/disposition/service/visitation
columns), FKs to `fh_case_contacts` and `users`. i.e. exactly the flattened shape
the canonical model splits into `funeral_cases` + `case_deceased` + satellites.

### 1.2 Writers

| Writer | Status |
|---|---|
| `app/services/case_service.py:123` (`FHCase(...)`) via `POST /api/v1/cases` (old router) | **Live code path** — fires only if someone uses the legacy UI |
| Test fixtures (`test_command_bar_{resolver,retrieval,query_api,latency}.py`) | Active in CI (source of all 49 dev rows) |
| `scripts/seed_nl_demo_data.py` | **Does NOT write fh_cases** — despite its own line-13 comment ("so the fh_case resolver has something to hit"), it creates `FuneralCase` rows (line 161). The comment is stale — and is direct evidence the resolver entry was mispointed from Phase 1: even the resolver's demo seed went to the canonical table, and nobody noticed because the legacy `/core/command-bar/search` endpoint was masking case lookups. |
| `seed_fh_demo.py`, NL creation `_create_case` | Canonical tables only (`FuneralCase` + `CaseDeceased` + `CaseInformant` + `FuneralCaseNote`) |

### 1.3 Readers — the load-bearing census (why deprecation is a separate arc)

Genuine `FHCase` ORM consumers (grep `FHCase\b`, all verified real usage, not
name collisions):

- **Legacy UI stack, still mounted and nav-linked today**: `App.tsx` mounts
  `/cases`, `/cases/new`, `/cases/:id` → `pages/funeral-home/*` →
  `funeralHomeService` → `/api/v1/cases` (router `app/api/routes/cases.py`) →
  `case_service.py` → `fh_cases`. `navigation-service.ts` lines 461/565 point
  "Active Cases"/"Cases" at `/cases`, and **the seeded FH Arrangement space pins
  `/cases`** — Hopkins' sidebar today links the legacy list (which shows zero
  canonical cases). The FH-1 UI is separately mounted at `/fh/cases…`.
- `obituary_service.py` — reads FHCase by id.
- `portal_service.py` — family-portal sessions resolve FHCase (+
  `fh_portal_sessions` FK).
- `ftc_compliance_service.py`, `fh_invoice_service.py`, `vault_order_service.py`.
- `saved_views/registry.py:258` — the saved-view executor's `fh_case` entity type
  queries FHCase (seeded director views "my_active_cases" etc. read the legacy
  table — empty for Hopkins).
- Calendar services (4 files), `platform/action_registry.py`,
  `personalization_studio/*`, email activity feed.
- **FK anchors from newer substrates**: `canonical_document.fh_case_id → fh_cases.id
  (ondelete SET NULL)` (r20 documents backbone) and `intelligence.py:260 →
  fh_cases.id` (r17) — the documents-arc mention substrate and intelligence linkage
  target LEGACY case ids.
- `core/permissions.py` — the `fh_cases.*` permission KEYS (view/create/edit/
  delete/aftercare). These are permission strings, not table reads; both routers
  gate on them. Unaffected by a repoint.
- Resolver `fh_case` entry + r31 trigram index (the subject of this fix).

### 1.4 Row counts (read-only)

| Environment | `fh_cases` | `funeral_cases` | `case_deceased` |
|---|---|---|---|
| dev | 49 — ALL test litter (13 `cb-*`/`cb-api-*`/`cb-ret-*` @1 each, 9 `lat-*` @4 each; no organic tenant) | 1 | 1 |
| staging | 3 — **exactly the disclosed e2e-tail mirror rows** (hopkins-fh) | 3 | 3 |
| production | not queryable from this session; no FH tenant exists in prod (Hopkins is staging-only), so expected 0 | — | — |

---

## Job 2 — The canonical path

### 2.1 Confirmation

`funeral_cases` ("The Spine") + `case_deceased` ("Always with case") is what
FUNERAL_HOME_VERTICAL.md specifies and what FH-1 built. Peek's `_peek_fh_case`
(`app/services/peek/builders.py:42-48`) queries `FuneralCase` + `CaseDeceased` +
`CaseService`; S-1's portal wraps exactly that (`portal.py:318
PEEK_BUILDERS[entity_type]`). The staging e2e tail exercised this end-to-end.

### 2.2 The resolver entry as it stands (`resolver.py:90-104`)

```
entity_type="fh_case", table="fh_cases", search_column="deceased_last_name",
primary_label_expr = COALESCE(deceased_last_name,'') || ', ' || COALESCE(deceased_first_name,'')
secondary_expr="case_number", recency_col_expr="COALESCE(updated_at, NOW())",
url_template="/cases/{id}"          ← ALSO mispointed: legacy detail route
```

**Double mispoint**: wrong table AND wrong navigate target. The canonical url is
`/fh/cases/{id}` (what the peek builder emits).

### 2.3 Canonical search columns

Names live on `case_deceased`: `first_name`, `middle_name`, `last_name`, `suffix`,
`preferred_name` (all nullable). The natural repoint:

- `search_column` → `case_deceased.last_name` (trigram; the hot path — decedent
  surname, mirroring r31's rationale).
- `primary_label_expr` → `COALESCE(cd.last_name,'') || ', ' ||
  COALESCE(cd.first_name,'')`.
- `secondary_expr` → `fc.case_number`. `recency` → `fc.updated_at`.
- First/middle as *searchable* columns: possible later (second trigram index or an
  expression index on `first_name`); not needed for the surname hot path. Type B
  (§Type-B-4).

### 2.4 Case-number searchability today

- `intent.py:71 _RECORD_NUMBER_RX = ^(SO|INV|Q|QT|PO|CASE|FH)[- ]?\d{2,4}[- ]?\d{3,5}$`
  — **"FC-2026-0001" does NOT match** (no `FC` alternation; `CASE`/`FH` don't
  cover it). Case numbers fall through to search intent.
- And in search, they still miss: the resolver branch searches only
  `search_column` (a name column). `secondary_expr` is display-only. So case
  numbers are **not findable via `/command-bar/query` at all today** — the FH-1
  seed's own format is `FC-YYYY-NNNN` (`case_number` example "FC-2026-0142" in
  canon). `funeral_cases` has `uq_funeral_cases_company_number (company_id,
  case_number)` btree — exact/prefix lookups are already cheap without a new
  index. Type B (§Type-B-2).

### 2.5 Index state

- r31 trigram GIN: `ix_fh_cases_deceased_last_name_trgm` on
  `fh_cases.deceased_last_name` — orphaned by the repoint (drop candidate in the
  retirement arc; harmless meanwhile).
- Canonical tables today: **NO trigram indexes.** `case_deceased` has pkey +
  `case_deceased_case_id_key` (UNIQUE btree on case_id — the 1:1 join is a unique
  index probe) + `ix_case_deceased_company`. `funeral_cases` has company/status/
  director/location btrees + the unique (company_id, case_number).
- **Head confirmed `r143_sales_tax_filing`** → the new index migration is **r144**.

---

## Job 3 — Latency (measured, not speculated)

Method: session-scoped TEMP tables on dev Postgres 16 (no durable change) shaped
like the real pair — 50,000 cases across 40 tenants, `case_deceased`-like table
with GIN `gin_trgm_ops` on `last_name`, unique `case_id`, realistic surname
distribution. Query = the resolver branch shape (company filter + `last_name % :q`
+ similarity ordering + LIMIT 10) with the 1:1 join:

```
JOIN branch (50k cases, 40 tenants): p50 = 1.63 ms · p99 = 3.19 ms  (n=60, mixed surnames)
```

Plan: Bitmap Index Scan on the trigram GIN (~3.1k candidate rows for 'smith') →
hash join against the company-filtered case set → quicksort of ≤77 rows → LIMIT.
857 buffer hits, all local. At a realistic single-FH scale (hundreds to low
thousands of cases) the branch cost is sub-millisecond.

**Gate verdict: SAFE.** The whole 8-branch UNION currently measures p50 8.6 ms /
p99 10.1 ms server-side (staging, S-1 tail). Adding ~1.6 ms worst-case to one
branch leaves ~10× headroom against the BLOCKING 100/300 gate. **No alternative
fix shape needed; no gate change proposed.** (The "denormalized searchable column
on funeral_cases" alternative — which is indeed what `fh_cases` effectively was —
is unnecessary at these numbers.)

**INNER vs LEFT — largely moot, with one nuance.** Canon says `case_deceased` is
"Always with case," and code enforces it: `app/services/fh/case_service.py`
creates `CaseDeceased` in the same transaction as `FuneralCase` (satellite loop),
as do the NL creator and both seeds. Moreover, since the WHERE predicate lives on
`cd.last_name`, a LEFT join degenerates to INNER semantics anyway — rows without a
deceased record can never match a name search. INNER is the honest spelling. LEFT
only becomes meaningful if `case_number` (a `funeral_cases` column) is added as a
second search signal — then a case with no deceased row should still be findable
by number. Type B (§Type-B-1).

---

## Job 4 — Blast radius of the repoint

### 4.1 Code

- `resolver.py` — the `_SearchableEntity` dataclass is single-table (`table`,
  `search_column`, expressions run against that table). The fh_case branch needs a
  join. Two shapes: (a) add an optional `join_clause`/`label_table_alias` field to
  the dataclass and teach the UNION builder to emit it (only fh_case uses it), or
  (b) hand-write the fh_case branch SQL. (a) is cleaner and stays additive.
- `url_template` → `/fh/cases/{id}`.
- `intent.py` — 1-line regex change **only if** Type-B-2 rules FC- routing in.

### 4.2 Tests (the enumerated update list)

Command-bar suites that seed `FHCase` rows for the fh_case branch — each re-seeds
`FuneralCase` + `CaseDeceased` instead (same assertion shapes):

1. `tests/test_command_bar_resolver.py` (~line 126-146; asserts
   `entity_type=="fh_case"` + "Hopkins" label)
2. `tests/test_command_bar_retrieval.py` (~lines 171-204; two seeding sites)
3. `tests/test_command_bar_query_api.py` (~line 169-198)
4. `tests/test_command_bar_latency.py` (~line 102-164 fixture; NOTE: this fixture
   is also the known pre-existing company-litter offender — the fix session may
   apply the funeral_cases teardown correction proven in
   `test_command_bar_portal_latency.py`, cf. the `fh_cases` → `funeral_cases`
   teardown typo fixed there during the S-1 e2e tail)

**Count assertions: NO change.** The entity-type count stays 8 (repoint, not
add/remove). Recorded count locations verified: `test_documents_arc_4b2a_
mention_substrate.py:238,608` say "8 SEARCHABLE_ENTITIES" — still true after the
repoint. `schemas/document_template.py` comment likewise. No thirteenth-style
recalibration needed.

**Other FHCase-touching tests (documents d1/d5/d7, intelligence 2c0a/2c0b,
personalization studio ×3, workflow_engine, pending_attention ×2) are NOT
affected** — they exercise the FK-anchor consumers (§1.3), not the resolver.

### 4.3 S-1 card — NO change needed (confirmed)

The card chain is `candidateFromResultId` (type/id passthrough) →
`GET /command-bar/portal/fh_case/{id}` → `_wrap_peek("fh_case")` →
`PEEK_BUILDERS` → `FuneralCase`+`CaseDeceased`. Once the resolver emits
`entity:fh_case:{funeral_cases.id}`, the existing card renders correctly — this is
exactly what the staging witness harness proved end-to-end (same ids in both
tables → resolver hit → card hydrated → "Open case" → `/fh/cases/{id}`).
`PORTAL_SUPPORTED_TYPES` already contains `fh_case`. The shipped **peek** feature
is likewise fixed for free by the repoint.

### 4.4 Migration r144 shape (pattern confirmed against r31)

r31's exact pattern holds: `with op.get_context().autocommit_block():` →
`CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_case_deceased_last_name_trgm ON
case_deceased USING gin (last_name gin_trgm_ops)`. Downgrade:
`DROP INDEX CONCURRENTLY IF EXISTS ...` inside the same autocommit_block
construction. pg_trgm extension already installed (r31), no extension step needed.
The orphaned `ix_fh_cases_deceased_last_name_trgm` is left in place (retirement-arc
cleanup; dropping it is not required for correctness).

### 4.5 Staging mirror-row cleanup

Once the repoint deploys to staging, the 3 disclosed `fh_cases` mirror rows
(hopkins-fh, ids shared with `funeral_cases`) become redundant. Cleanup is one
read-safe statement via `railway run`:
`DELETE FROM fh_cases WHERE company_id = (SELECT id FROM companies WHERE slug='hopkins-fh')`.
Sequence it AFTER the repoint lands (before that, deleting them re-breaks the
"Smith" demo path on staging).

---

## Deliverables

### 1. Verdict

`fh_cases` is a **legacy first-generation system that is code-load-bearing but
data-empty**: still mounted (legacy `/cases` UI + router + services + saved-view
executor + family portal + FK anchors from documents/intelligence + seeded nav
pins), yet holding zero organic rows in any queryable environment. It is
**deprecatable in principle but NOT in this fix** — retirement is a separate
reconciliation arc with product decisions (which UI serves FH, nav/pin re-targets,
FK re-anchoring for canonical_document/intelligence, saved-view executor repoint,
13-table drop). The resolver repoint does not depend on any of that.

### 2. Recommended fix shape (with real evidence)

Repoint the resolver's `fh_case` branch to `funeral_cases ⋈ case_deceased`
(INNER, join on unique `case_deceased.case_id`), search `cd.last_name` via a new
r144 trigram GIN, label `last, first`, secondary `case_number`, url
`/fh/cases/{id}`. Measured branch cost at 50k-case scale: **p50 1.63 ms / p99
3.19 ms** — ~10× headroom under the untouched BLOCKING gate. No gate change, no
denormalized-column workaround needed. S-1 card + shipped peek are fixed for free.

### 3. Type B calls for James

1. **INNER vs LEFT**: recommend INNER — canon + code enforce 1:1 at creation, and
   the name predicate makes LEFT equivalent anyway. Revisit only if (2) adds
   number-search on `funeral_cases`.
2. **case_number searchable?** Today `FC-2026-####` matches nothing (regex misses
   FC; search column is a name). Options: (a) 1-line `FC|` addition to
   `_RECORD_NUMBER_RX` (routes to navigate intent), (b) additionally make the
   resolver branch match `case_number` (btree-exact/prefix is free; trigram on
   case_number would need a second index). Recommend (a) now, (b) deferred until
   demand.
3. **Deprecate `fh_cases` now vs stop-reading?** Recommend stop-reading (this
   repoint) + schedule the legacy-FH-v1 retirement arc separately (scope: §1.3
   census + nav/pins + FK re-anchors + r31 index drop + 13-table sunset).
4. **Index target column(s)**: recommend `case_deceased.last_name` only (mirrors
   r31's surname-hot-path rationale). `first_name` searchable is a cheap additive
   follow-up if operators ask.

### 4. LOC floor + commit shape

**Floor ≈ 150 LOC** (not ceiling): resolver join support + entry rewrite ~40;
r144 migration ~50 with docstring; 4 test-fixture updates ~60; url/comment fixes
~5. Plus ~15 if Type-B-2(a) rules in the regex + a test. **One commit** — code +
migration + tests move together (the tests fail against either table alone, so
splitting would break bisectability).

---

*Read-only confirmation: no source files modified, no schema touched, no migration
authored, nothing pushed. The only artifacts of this session are this findings file
and session-scoped TEMP tables that died with the Postgres connection.*
