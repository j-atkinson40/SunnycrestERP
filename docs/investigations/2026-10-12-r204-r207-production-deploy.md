# Deploy record — r204 / r205 / r206 / r207 to production, 2026-10-12

Push `34723cef..7cd4dbd8`. CI run `38247717501` (CI) + `38247717535` (Seed Idempotency Gate),
both **success**. Production health reported `commit: 7cd4dbd8`, `db: connected`.

⚠️ COMMITTED HERE RATHER THAN LEFT IN A SCRATCHPAD. Five days earlier a 64-run
dataset was lost to `/private/tmp` rotation — see
`2026-10-07-vitest-worker-starvation.md`. These are the readings that justify
the deploy, so they live in the repository.

All readings are READ-ONLY at the connection level
(`default_transaction_read_only=on`) and print host/port/database only.
Reproduce with `backend/scripts/preflight_r204_r207.py` (two modes) and
`backend/scripts/check_resolver_against_db.py`.

## Pre-flight, BEFORE the push

```
MODE:   PRE-FLIGHT
TARGET: host=shuttle.proxy.rlwy.net port=57253 db=railway
MODE:   read-only at the connection level

[control] tables visible: 497
[head] alembic head: r203_capture_sessions
[r205] server_version_num: 170011 (needs >= 150000)
[catalog] active variant templates: 52 (needs > 40)
[r204] rows it will write: 40
[r204] SKUs absent (must be none): none
[r204] platform_personalization_availability already exists: False
[r206] rows it will write: 48
[r206] SKUs absent (must be none): none
[r207] rows it will write: 3
[r207] urn SKUs absent (must be none): none
[alias] platform_product_aliases rows now: 5
[r207] existing 'Veteran' -> BV-VTRI: 1 (needs exactly 1)
[r207] existing 'SST' -> BV-SSTRI: 1 (needs exactly 1)
[r207] existing 'Cameo Rose' -> BV-CRTRI: 1 (needs exactly 1)
[r205] unique constraints on cemeteries now: {
  "uq_cemetery_company_name": "UNIQUE (company_id, name)"
}
[r205] NULL/empty-city duplicates (must be none): none

[cemetery report] total rows: 3
[cemetery report] rows with NULL or empty city: 0
[cemetery report] names matching a disambiguation pattern ( '(' | ' - ' | ',' | ' in ' ): 0
[cemetery report] names held by more than one row: 0

PRE-FLIGHT: PASS — the deploy should apply all four
```

## Post-deploy report, AFTER

```
MODE:   POST-DEPLOY REPORT
TARGET: host=shuttle.proxy.rlwy.net port=57253 db=railway
MODE:   read-only at the connection level

[control] tables visible: 498
[head] alembic head: r207_form_counterpart_aliases
[r205] server_version_num: 170011 (needs >= 150000)
[catalog] active variant templates: 52 (needs > 40)
[r204] rows it will write: 40
[r204] SKUs absent (must be none): none
[r204] platform_personalization_availability present: True
[r204] rows in it: 40 (expect 40)
[r204] distinct question_ids: 1 (expect 1: personalization)
[r206] rows it will write: 48
[r206] SKUs absent (must be none): none
[r207] rows it will write: 3
[r207] urn SKUs absent (must be none): none
[alias] platform_product_aliases rows now: 56
[r206] alias rows attributable to r206: 48 (expect 48)
[r207] alias rows attributable to r207: 3 (expect 3)
[r207] existing 'Veteran' -> BV-VTRI: 1 (needs exactly 1)
[r207] existing 'SST' -> BV-SSTRI: 1 (needs exactly 1)
[r207] existing 'Cameo Rose' -> BV-CRTRI: 1 (needs exactly 1)
[r205] unique constraints on cemeteries now: {
  "uq_cemetery_company_name_city": "UNIQUE NULLS NOT DISTINCT (company_id, name, city)"
}
[r205] NULL/empty-city duplicates (must be none): none
[r205] uq_cemetery_company_name_city present: True
[r205] its definition: UNIQUE NULLS NOT DISTINCT (company_id, name, city)
[r205] old uq_cemetery_company_name gone: True

[cemetery report] total rows: 3
[cemetery report] rows with NULL or empty city: 0
[cemetery report] names matching a disambiguation pattern ( '(' | ' - ' | ',' | ' in ' ): 0
[cemetery report] names held by more than one row: 0

POST-DEPLOY: PASS
```

## The real resolver, run against production's own catalog

```
TARGET: host=shuttle.proxy.rlwy.net port=57253 db=railway (read-only)
[control] surface forms indexed: 207   alias rows read: 56
  'oversized'                n=3 ['BV-CON34', 'GL-34', 'GL-38'] disc=['form', 'line', 'size']   <- the walk, line 6
  'OS'                       n=3 ['BV-CON34', 'GL-34', 'GL-38'] disc=['form', 'line', 'size']
  'O/S'                      n=3 ['BV-CON34', 'GL-34', 'GL-38'] disc=['form', 'line', 'size']
  'OVS'                      n=3 ['BV-CON34', 'GL-34', 'GL-38'] disc=['form', 'line', 'size']
  'oversized Continental'    n=1 ['BV-CON34'] disc=[]
  'oversized graveliner'     n=2 ['GL-34', 'GL-38'] disc=['size']
  'Continental 34'           n=1 ['BV-CON34'] disc=[]   <- a bare number
  '34 inch Continental'      n=1 ['BV-CON34'] disc=[]   <- the pre-existing form
  'Veteran urn vault'        n=1 ['UV-VET'] disc=[]   <- the bug James wanted gone
  'SST urn vault'            n=1 ['UV-SSTRI'] disc=[]
  'Cameo Rose urn vault'     n=1 ['UV-CRTRI'] disc=[]
  'Veteran burial vault'     n=1 ['BV-VTRI'] disc=[]   <- the other direction
  'Veteran'                  n=2 ['BV-VTRI', 'UV-VET'] disc=['form']   <- now ASKS
  'oversized urn vault'      n=0 [] disc=[]   <- must be NO MATCH
  'Continental urn vault'    n=0 [] disc=[]   <- must be NO MATCH
  'Boston'                   n=0 [] disc=[]   <- word-boundary control
  'cosmos'                   n=0 [] disc=[]
  'Rosewood'                 n=0 [] disc=[]
  'graveliner'               n=5 ['GL-34', 'GL-38', 'GL-SS', 'GL-STD', 'UV-GL'] disc=['form', 'size']   <- bare family word keeps UV-GL
```

## Production tenants and the cemetery denominator

⚠️ This is the reading that corrects the premise of the cemetery question.

```
TARGET: host=shuttle.proxy.rlwy.net port=57253 db=railway (read-only)
companies: 4
  testco                 vertical=manufacturing  cemeteries=3
  hopkins-fh             vertical=funeral_home   cemeteries=0
  st-marys               vertical=cemetery       cemeteries=0
  sunnycrest             vertical=manufacturing  cemeteries=0
cemetery rows with a non-empty city: 3
    name='Lakeview Memorial Gardens' city='Syracuse'
    name='Oakwood Cemetery' city='Auburn'
    name="St. Mary's Cemetery" city='Skaneateles'
```

All three cemetery rows belong to `testco`, the synthetic tenant
`railway-start.sh` seeds. **Sunnycrest has zero cemeteries on production.** So
"how have your real cemeteries been worked around so far" answers "there are
none yet": the zeroes in the cemetery report are an EMPTY dataset, not a clean
one, and r205 is pre-emptive rather than remedial.
