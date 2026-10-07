# Order capture by typing, in Opas — investigation

**2026-10-07.** Read-only. Nothing built. Every claim carries `file:line`.

---

## 1. Prototype — three artifacts contribute, not one

| artifact | md5 | what it holds |
|---|---|---|
| `docs/prototypes/2026-10-01-opas-overlay.html` | `a52a1e95153bd5c686b88d0acffc31e6` | **the capture pane**, working, with JS |
| `docs/prototypes/2026-09-call-to-print.html` | `56e1e24c3a4a873e1ef6d45fc58ba18e` | the approve summary (screen 2) |
| `docs/prototypes/2026-09-22-capture-schema-prototype.html` | `5d286c79a855f7397a8d62f3ad983228` | `.cap.unconfig` — the NOT_CONFIGURED state, **absent from the Opas overlay** |

Measured: the Opas overlay has 0 occurrences of `unconfig` or "not configured";
the capture-schema prototype has 8 and 4. `surfaces.py:10-17` already cites the
second and third for exactly this reason.

### Where the pane anchors

`addPane` sets `className='win entering'+(w.kind==='capture'?' wide':'')`
(`L431`), and a new capture **un-anchors every other capture** before anchoring
itself: `wins.forEach(x=>{if(x.kind==='capture')x.anchored=false});w.anchored=true;anchor(w)`
(`L434`). So at most one capture is anchored at a time. The pane's `.kind` chip
reads `SCHEMAS[w.type].label` rather than the generic kind label (`L440`).

### The capture schema — 7 fields, against the engine's 20

`L288-293`:

```
order: label 'New order', capLabel 'Order capture',
       verb 'Approve and create sales order', fields:
  ['customer','Funeral home',true] ['decedent','Decedent',true]
  ['vault','Vault',true]           ['extras','Personalization',true,'vault']
  ['date','Delivery',true]         ['cemetery','Cemetery',true]
  ['equip','Cemetery equipment',true]
```

⚠️ **All seven are required and the engine's template has twenty fields.** The
prototype has no `funeral_home` vs `customer` distinction, no `service_date`,
`service_time`, `eta`, `service_location`, `grave_location`, `cemetery_city`,
`date_of_birth`, `date_of_death`, `nameplate_date_format`, `legacy_series` or
`legacy_print_name`. Its `date` is labelled **Delivery**, which is not a template
field under any name.

### `dependsOn` is the prototype's name for INDETERMINATE

`L287`, verbatim: *"field: [key, label, required, dependsOn] — a field with
dependsOn is unknown, not missing, until that answer arrives"*. Only `extras`
uses it, depending on `vault`, and `dependsLabel={vault:'Depends on the vault'}`
(`L294`).

### Row markup — four states, and the fifth is missing

State function, `L406`:

```js
const state=f=>{const [k,,isReq,dep]=f;
  if(v[k]!=null)return 'done';
  if(dep&&v[dep]==null)return 'unknown';
  if(isReq&&w.flagged)return 'needed';
  return 'open'};
```

Text per state, `L409`:

| state | renders | engine set |
|---|---|---|
| `done` | the value via `show_()` | `answered` |
| `unknown` | `dependsLabel[dep]` → "Depends on the vault" | `indeterminate` |
| `needed` | "Still needed" | `missing` |
| `open`, required | "Not mentioned yet" | `missing` |
| `open`, optional | "Optional" | `unanswered_optional` |
| — | **nothing** | **`not_applicable` / NOT_CONFIGURED** |

Row markup, `L410`:
`<div class="cap {state}{' fresh' if just changed}"><span class="mark">✓</span><div><div class="k">{label}</div><div class="v">{shown}</div></div></div>`

⚠️ **`needed` only appears after `w.flagged`.** Until the director signals done,
an unanswered required field reads "Not mentioned yet", not "Still needed". The
pane does not nag.

⚠️ **`fresh` marks what just changed** (`L410`, set at `L531`), and the echo list
names each newly captured field: `out.push({t:'${def[1]}: ${show_(...)}'})`
(`L530`). When nothing landed: *"Didn't catch anything new for this order"*,
class `miss` (`L532`).

### Header and counts

`L413`: `{sc.label}` + `<b>{captured}</b> captured` + `<b>{needed}</b> needed`,
the needed pill taking class `need` only when `w.flagged&&needed`.
`captured` = count of `done` (`L411`); `needed` = required fields in `open`
or `needed` (`L412`).
`L414`: a column header `<span>{sc.capLabel}</span><span class="ai">AI ASSIST</span>`.
`L416`: `Review` button, `disabled` while `needed`, plus a `Cancel` link.

### The done-signal

`L539`, verbatim regex:

```
/^(that'?s (it|everything|all)|that should be everything|done|review( it)?|looks good|ready)$/
```

Two outcomes (`L540-542`): with required gaps → `cur.flagged=true` and
*"Still needed: "* + the missing labels, class `miss`; otherwise
`cur.stage='review'` and *"Ready for your approval"*.

### The summary (review stage)

`L389-404`. Subject `sum-name` = decedent, `sum-sub` = `Sales order · {customer.name}`
(`L394`). A six-cell `sgrid` of `sf(key,label)` cells, each with an edit button
(`L391,L395`). Then **line items with prices and a total** (`L396-397`) from
`VAULTS[v.vault]` and `EXTRAS` — hardcoded price tables in the prototype. A
`Notes` textarea (`L401`). Header reads `Review`, `{n} captured`, **`0 missing`
hardcoded** (`L402`). Actions: primary `{sc.verb}` = "Approve and create sales
order", plus a `Back to capture` link (`L404`).

### What Approve does

`act(w,'approve')` — reachable by button (`L404`) or by typing
`/^(approve|create it|send it|yes|go)$/` at review (`L544`). In the prototype it
sets `stage='done'` and renders a tick plus `{w.result}` and an "Open order" link
(`L386-387`). **No write of any kind — it is a prototype.**

---

## 2. Entrance

`startIntent(s)`, `L296`:

```
/\b(new|create|start|make|enter|put in|take)\b.*\border\b|^order for\b/
```

Routed at `L567-568`: `startCapture(intent)`, then **`feed(w,raw,s,out)` with the
same raw text**.

⚠️ **So yes — the funeral home can be named in the opening phrase**, and is: the
opening line is run through extraction immediately, and `extract` looks for a
customer first (`L304`). "Start an order for Hopkins" captures `customer` on the
same keystroke that creates the pane.

**What the rule-based classifier would need.** `command_bar/intent.py` already
has create-verb detection, and `nl_creation/detectNLIntent.ts` mirrors it
frontend-side. The prototype's regex is narrower than either. Nothing routes to a
*capture pane* today — `intent.py` classifies into navigate/search/create/action/empty
and the create path goes to `NLCreationMode`, not to Opas.

---

## 3. Typed text → fields

### The prototype: regex, no model

`extract(kind,s,raw)` at `L301-317` is **pure regex over hardcoded tables** —
`VAULTS` (`L305`), `EXTRAS` (`L311`), `PEOPLE` (`L319`), plus `dayFrom`/`timeFrom`.
⚠️ The `AI ASSIST` label at `L414` is a column header and nothing else. The
prototype calls no model.

### Production: one model call per transcript

`call_extraction_service.py:281-285` → `intelligence_service.execute(prompt_key="calls.extract_order_from_transcript")`.
Seeded at `scripts/seed_intelligence_phase2c.py:1560-1575`:
`model_preference "extraction"`, `temperature 0.2`, `max_tokens 1024`,
`force_json True`.

`extraction` resolves (measured on dev, `intelligence_model_routes`) to
**`claude-sonnet-4-6`**, fallback `claude-haiku-4-5-20251001`, at **$3.00/M in,
$15.00/M out**.

**Cost and latency — measured, with its denominator.** `calls.extract_order_from_transcript`
has **0 executions on dev** (`intelligence_executions` joined to
`intelligence_prompts`), so there is no direct figure. The nearest comparable is
`scribe.extract_case_fields`, also a field-extraction prompt:

| prompt | n | avg latency | avg cost | max latency |
|---|---|---|---|---|
| `scribe.extract_case_fields` | 33 | **6,336 ms** | **$0.0220** | 53,917 ms |
| `email.classify_into_taxonomy` | 31 | 3,184 ms | $0.0024 | 46,219 ms |
| `triage.task_context_question` | 39 | 2,584 ms | $0.0025 | 51,538 ms |

⚠️ These are dev figures from a different prompt. Treat ~6 s / ~$0.02 as an
**order of magnitude, not a measurement** of the capture prompt.

### Can typed lines go through `resolve_and_evaluate` unchanged?

**Yes, and that is the one clean part.** `resolve_and_evaluate(db, result, *, tenant_id)`
(`call_extraction_service.py:30`) takes a **plain dict** keyed by extraction-payload
names and returns `(resolution, CaptureState)`. It calls no model. Every
evaluation in this arc's reports went through it. A typed pane can call it per
line with no change to the function.

⚠️ **What it will NOT do is turn prose into that dict.** `_captured_from_result`
(`:122`) is a key *rename* map, not an extractor. Something must produce
`{"vault_type": "...", "deceased_name": "..."}` from "Hopkins, John Smith, bronze
triune". Today only the Claude prompt does that, and only from a transcript.

### Per line or with the session so far?

The prototype extracts **the current line alone** and merges into `w.values`
(`L516-531`), so earlier answers persist and are never re-derived. Production
extracts **the whole transcript at once**, one call. Neither does
line-with-history.

**Exists / new:**

| | |
|---|---|
| exists | `resolve_and_evaluate`, the whole condition engine, the vault resolver, the print resolver, the Claude extraction prompt (transcript-shaped, 0 runs) |
| new | a typed-line → field-dict step; per-line or per-session extraction policy; anything that holds a part-built capture between keystrokes |

---

## 4. Server contract

⚠️ **There is no endpoint.** Measured: no file under `app/api/routes/` references
`CaptureState`, `capture.evaluate` or `resolve_and_evaluate`. The engine is
reachable only from `call_extraction_service`, which is driven by the RingCentral
webhook path.

**Smallest endpoint set the pane needs** — three:

1. `POST /capture/sessions` → `{session_id, surface}` — start, optionally seeded
   with the opening phrase.
2. `POST /capture/sessions/{id}/say` → `{answered_delta, CaptureState, rows, resolution?}`
   — one typed line in, the new state out. This is the hot path and the only one
   that might call a model.
3. `POST /capture/sessions/{id}/approve` → writes, returns the order ref.

A fourth, `GET /capture/sessions/{id}`, is needed only if the pane must survive a
reload.

**Where an in-progress capture lives: nowhere today.** The call path persists to
`ringcentral_call_extractions` because a call has a row to hang off (`:1-20`).
A typed session has no such row. ⚠️ `ringcentral_call_extractions` holds **0 rows
on production** and requires a `call_log_id` FK (`models/ringcentral_call_extraction.py:18`),
so reusing it for typed capture means either a synthetic call-log row per typed
order or a new table. That is a design decision, not a detail.

---

## 5. Surface

Two surfaces exist and both are the call overlay's: `id="capture"`
(`surfaces.py:68`) and `id="summary"` (`:199`), registered under `SALES_ORDER`
(`:285`).

⚠️ **A typed pane does not obviously need a third.** The existing `capture`
surface already declares 9 rows over the 20 fields, worded "needed", and the
`summary` surface declares 6 rows plus subject/notes/footer, worded "missing" —
which is exactly the prototype's two stages. The honest finding is that the
**row layer is reusable as-is**, and what is missing is not a surface but a
NOT_CONFIGURED *renderer* in the Opas pane.

**Orphan check if a third surface were added:** orphans are computed over the
UNION of surfaces (`rows.py::orphan_field_ids`), so adding a surface can only
*shrink* the orphan set, never grow it. Current set, measured today:
`{grave_location, nameplate_date_format}`. A third surface that declared neither
would leave it unchanged.

---

## 6. Approve — Piece 5's gap, measured

`create_draft_order_from_extraction` (`call_extraction_service.py:455+`).

**Guards.** Returns early unless `call_type == "order"` (`:462`). ⚠️ **Raises** if
no customer matches the funeral home (`:483-489`) — a loud failure, not a silent
one.

**What it writes** (`:491-513`): `company_id`, `number` (via `next_document_number`),
`customer_id`, `status="draft"`, `order_date`, `order_type="funeral"`,
`deceased_name`, `cemetery_id`, `scheduled_date` ← `burial_date`, `service_time`,
`eta`, `service_location`, `service_location_other`, `notes`.

**What it would write on production:** one `sales_orders` row, status `draft`,
plus `extraction.draft_order_created=True` and `draft_order_id` (`:519-520`).

### ⚠️ It does not understand the new fields, and the columns do not exist

Measured against `information_schema` on dev:

| capture field | `sales_orders` column | mapped by the writer |
|---|---|---|
| `service_time`, `eta`, `service_location`, `service_location_other` | EXISTS | ✅ yes |
| `personalization` | **ABSENT** | no |
| `legacy_series` | **ABSENT** | no |
| `legacy_print_name` | **ABSENT** | no |
| `lifes_reflections_symbol` | **ABSENT** | no |
| `service_date` | **ABSENT** | no |
| `cemetery_city` | **ABSENT** | no |
| `nameplate_date_format` | **ABSENT** | no |
| `date_of_birth`, `date_of_death` | **ABSENT** | no |

**So Approve today would silently drop 9 of the 20 captured fields** — including
every personalization answer the last three dispatches were about. There is no
error; the fields simply have nowhere to go.

**What Piece 5 is missing, precisely:** a capture-field → order-object mapping,
the columns (or a JSONB) to land personalization on, and a decision about whether
personalization becomes `sales_order_lines.personalization_data` (the column
exists and is 0-populated) or new columns on the order.

---

## 7. Funeral home and cemetery resolution

⚠️ **Both take the FIRST match, silently.**

`_fuzzy_match_company` (`:162`): exact `lower(name) = lower(name)` first, then
`LIKE '%name%'`, each `.first()`, else `None`.

`_resolve_cemetery_id` (`:480`): `LIKE '%name%'`, `.first()`, else `None`.

**No candidates. No discriminator. No question.** This contradicts the discipline
applied to vaults (`product_name_resolver` returns a candidate set plus a
`Discriminator`) and to prints (`legacy_print_resolver`, same shape). A cemetery
called "St. Mary's" in two towns resolves to whichever row Postgres returns
first — which is precisely why `cemetery_city` was ruled in (R4), and that field
is currently captured and **not used in resolution at all**.

The prototype, by contrast, does ask: `customerIn(s)` returning >1 sets
`pending={opts,then}` and renders "Two matches. Which one?" (`L583`), picked by
digit key (`L622`) through `choose(i)` (`L606`) — the numbered pick already built
in Opas.

---

## PROPOSAL — the smallest walkable slice

### What James will see

Opens Opas, types *"start an order for Hopkins"*. A wide capture pane anchors,
`Order capture`, with the funeral home already captured from that phrase. He
types *"John Smith, bronze triune, St Mary's in Auburn, service Thursday 10am"*
and rows fill, each newly-captured field echoed in the said-line. The vault
resolves; where it is ambiguous he gets a numbered pick. Personalization appears
as a follow-up once the vault resolves, with only the answers that vault permits.
He types *"that's everything"*; gaps are listed if any, otherwise the pane turns
into the review summary. He types *"approve"* and gets an order reference.

### What he will not see

No prices or line-item totals (the prototype's are hardcoded tables; the catalog
has **no price column on any platform tier**). No notes-to-dispatch round trip.
No reload survival. No NOT_CONFIGURED styling unless it is ported from the
capture-schema prototype. No urn engraving.

### Stop-worthy risks, worst first

1. ⚠️ **A model call per typed line.** ~6 s and ~$0.02 by the nearest comparable.
   At 8 lines that is ~48 s and ~$0.16 for one order, and the pane would feel
   dead between keystrokes. **This is the decision that shapes the slice**, and I
   would not guess it. Options: regex-first like the prototype with the model only
   on an explicit "work it out" (cheapest, least magic); debounce and extract the
   whole session on a pause (one call per pause, re-derives everything); model per
   line (simplest to build, worst to use).
2. ⚠️ **A new write path to `sales_orders` on production.** Approve writes a real
   order. The existing writer drops 9 of 20 fields silently and has never run on
   production (0 extraction rows). I would not wire Approve in the first slice.
3. ⚠️ **Session state has nowhere to live.** `ringcentral_call_extractions`
   requires a `call_log_id`; a synthetic call-log row per typed order would put
   fake calls in the call log.
4. **First-match resolution for funeral home and cemetery** will pick the wrong
   St. Mary's and say nothing. The pane makes this visible for the first time.
5. **Touching the call overlay.** The two surfaces are shared. Any change to
   `surfaces.py` rows changes what the call overlay renders, and that path has 0
   production rows — so a regression there is invisible.

### Build order, riskiest first

1. **Decide the extraction policy** (risk 1). No code until this is ruled.
2. **`POST /capture/sessions/{id}/say` over `resolve_and_evaluate`, in-memory
   session, no model** — regex/structured parsers only. Proves the pane fills,
   the vault resolves, personalization follows, the done-signal works. Walkable,
   writes nothing, costs nothing.
3. **The pane itself**, reusing the existing Opas pane chrome and the `capture`
   surface rows; port the NOT_CONFIGURED state from the capture-schema prototype.
4. **Session persistence**, once the shape is known.
5. **The review summary**, read-only, no Approve button.
6. **Piece 5 and Approve, last**, as its own dispatch with its own migration.
