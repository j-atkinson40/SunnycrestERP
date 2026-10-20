# A model behind the Opas bar — investigation

James's dispatch of 2026-10-20. **No code, no migration.** Every figure says which
environment it came from.

---

## 0. First, a source the executor cannot reach

> "We'd already agreed a plan on Oct 10. … I've updated it in the project with today's
> additions."

⚠️ **That plan is not in this repository.** Searched: every `*.md` for "rulebook",
"decision log", "engine decides", "model behind", "promptfoo", "Duckling", "Grok"; every
file for the last three; `docs/design`, `docs/specs`, `docs/design-archive`; and
`git log --since=2026-10-08 --until=2026-10-12 -- '*.md'`, which touched only `STATE.md`
and two unrelated investigations. The only repo hits are `promptfoo`/`Grok` inside
`docs/prototypes/2026-09-call-to-print.html` — a prototype, not a plan — and
`docs/investigations/2026-10-20-opas-talks-back.md`, which is mine from this morning.

This is the fourth instance of the class CLAUDE.md §11 records: *"A dispatch may only cite
sources the executor can reach… The fix is always the same: move the bytes into the repo,
with digests, before the dispatch references them."*

**What this cost and did not cost.** The dispatch's own RULES block is self-contained, so
the investigation is executable and is below. What I cannot do is check this design
against the Oct 10 plan's specifics — whether it already named a request shape, a table
layout, or a provider decision. **If Parts 2 and 4 disagree with that plan, the plan is
right and I could not see it.** Paste it into `docs/design/` and I will reconcile.

---

## PART 1 — How the bar understands text today, by measurement

### 1.1 The path from a keystroke to an action

Everything below is `frontend/src/components/opas/` unless stated.

| step | file:line | what it is |
|---|---|---|
| a printable key, nothing focused | `OpasHost.tsx:699-717` | redirects into the bar, appending the character |
| ⌘K | `OpasHost.tsx:423-436` | capture-phase toggle; takes the key from the command bar |
| typing | `OpasHost.tsx:1900-1915` | `onChange` → `setText` or `opas.setEntryText` |
| Enter | `OpasHost.tsx:1916-1983` | entry mode → `requestComplete()`; else → `submit()` |
| ⌘1-9 / bare digit on a reply question | `OpasHost.tsx:597-612` | `answerOption` |
| ⌘1-9 on a capture field pick | `OpasHost.tsx:756-771` | `setPickRequest` |
| a bare digit inside order text | `pick-digit.ts:70-98` | `consumePickDigit`, five conditions |
| Escape | `contexts/opas-context.tsx` `onEscape` | cancel question → refocus textarea → tuck |

**`submit()`'s decision chain, in order** (`OpasHost.tsx:1267`):

| # | predicate | file |
|---|---|---|
| 1 | `isCloseRequest` | `close-request.ts:33-39` — an exact phrase list |
| 2 | `matchAnswer` against the outstanding question's options | `reply.ts:160-179` |
| 3 | `opensCapture` = `CAPTURE_START` ∪ `startsCaptureWithParty` | `opas-routing.ts:24,56-70` |
| 4 | `isCatalogRequest` | `opas-routing.ts:95-97` — 10 exact phrases |
| 5 | `contextIntent`, gated on an order being in front | `context-phrases.ts:122-124` |
| 6 | `contextIntent` with no order in front → "Which order?" | `OpasHost.tsx` |
| 7 | `isOrderListPhrase` / `isOrderRefinement` → `POST /order-list/ask` | `order-list/order-list-routing.ts:34-47,50-61` |
| 8 | fall-through → `POST /catalog-pane/resolve` → `routeResolution` | `opas-routing.ts:140-160` |

**Server side.** `POST /order-list/ask` (`backend/app/api/routes/order_list_pane.py:38`) →
`order_list/service.py:ask` → `question.py:interpret` (598 lines of regex rules:
`_OPEN_ONE`, `_ORDER_NUMBER`, `_GOING`, `_SINCE`, `_RELATIVE_MONTH`, `_TOTAL`, `_ONLY`,
`_LENS`, `_DEFAULT_PHRASES`) → `_open_one` over four fields
(`service.py:OPEN_ONE_FIELDS`) or `_pack` over `stage.py`'s `matches`/`group_of`.
`POST /catalog-pane/resolve` (`catalog_pane.py:57`) → `product_name_resolver.py` (385
lines: trademark stripping before NFKD, a suffix list, size parsing, and
`platform_product_aliases WHERE is_confirmed`). Capture text →
`capture/typed_extraction.py` (2,775 lines).

### 1.2 Which parts are rules, and whether anything calls a model

**Rules: all of it.** Measured by grep over `frontend/src/components/opas/` for
`anthropic|ai_service|/ai/|claude` — **zero non-test hits**. `order_list_pane.py` and
`catalog_pane.py` contain **zero** references to `ai_service`, `anthropic` or
`call_anthropic`.

⚠️ **AND A MODEL DOOR ALREADY EXISTS, CORRECT AND UNREACHABLE.**
`backend/app/services/order_list/proposal.py` is a complete model door into the
order-list path: called only after the rules decline, through
`intelligence_service.execute` on `claude-haiku-4-5`, with `persist=False` because asking
is a read, returning `None` on no API key or any exception. Its output is validated by
`question.py:accept_model_text` (lines 546-586), which is already the engine-decides gate
the dispatch's rules describe:

- not JSON → `None`
- any banned key, at any depth → `None`. `_BANNED_KEYS = {sql, query, total, amount,
  count, sum, select, numbers}` (`question.py:543`)
- fails `OrderQuestion` validation → `None`
- `unsure: true` → every pick's question validated individually, or `None`

**Measured on production 2026-10-20: `intelligence_prompts` has ZERO rows whose key is
`opas.order_list.interpret` or contains `order_list`.** 20 prompt families exist (`agent`
12, `commandbar` 10, `briefing` 9, …) and none is Opas's. So the door is shut and bolted
from the outside: a complete, tested mechanism behind an unprovisioned entrance — the
exact shape CLAUDE.md §11 names.

`intelligence_executions` on production: **5,565 calls** across 7 caller modules
(`briefings` 3,041; `agents.expense_categorization_agent` 2,017;
`agents.ar_collections_agent` 322; `workflow_authoring` 179; three others ≤ 4).
**`order_list.proposal` appears zero times.**

### 1.3 Every request shape handled today, one example each

| shape | example | route |
|---|---|---|
| close the front pane | `close` | 1 |
| answer an outstanding question | `hart` | 2 |
| open a capture | `order for hopkins monticello friday 11 am church` | 3 |
| the catalog | `the catalog` | 4 |
| act on the front order | `undo confirm` | 5 |
| answer about the front order | `when's the service` | 5 |
| the default order list | `orders` | 7 |
| a filtered list | `Hopkins orders this month` | 7 |
| a day | `going out friday` | 7 |
| a month | `hopkins since september` | 7 |
| a stage pair | `delivered not invoiced` | 7 |
| a refinement | `only hopkins` | 7 |
| a total over the open list | `how much is that` | 7 |
| the glasses | `orders on the lens` | 7 |
| one order by number | `SO-2026-0004`, `0004` | 7 |
| one order by name | `riverside order` | 7 |
| one product | `monticello burial vault` | 8 |
| a numbered pick | `continental` → 2 variants, differs by size | 8 |
| no match | `zzz` | 8 |

### 1.4 The exact phrasings the front-pane context supports

**35 phrasings, 9 intents**, enumerated from `context-phrases.ts` itself:

```
ACT     vault         "the vault" · "vault" · "open the vault" · "show the vault"
ACT     customer      "the funeral home" · "the customer" · "open the funeral home"
                      · "open the customer"
ACT     cemetery      "the cemetery" · "open the cemetery"
ACT     undo-confirm  "undo confirm" · "undo the confirm" · "unconfirm"
                      · "make it a draft"
ANSWER  service       "when's the service" · "when is the service" · "when"
                      · "the service" · "service" · "what's the service"
ANSWER  total         "what's the total" · "what is the total" · "the total" · "total"
                      · "how much" · "how much is it"
ANSWER  who           "who's it for" · "who is it for" · "who is it"
ANSWER  where         "where is it going" · "where's it going"
ANSWER  status        "where is it" · "where's it at" · "what stage"
                      · "what's the status"
```

---

## PART 2 — The request shape

One type. Five kinds. **Every target either names an existing validated type or an id the
engine looks up.**

```python
OpasRequest =
  | Open    { target: Target }
  | Answer  { about: Target, question: Field }
  | Capture { fields: dict[str, str] }          # the capture's own answer keys
  | Act     { action: Action, on: Target }      # ALWAYS requires Enter
  | Unsure  { picks: list[{ label: str, request: OpasRequest }] }

Target =
  | { type: "order",      by: ByNumber | ByDecedent | ByFuneralHome | ByCemetery | ByVault | ById }
  | { type: "order_list", question: OrderQuestion }   # ← the EXISTING pydantic model
  | { type: "customer",   by: ByName | ById | FromFrontOrder }
  | { type: "cemetery",   by: ByName | ById | FromFrontOrder }
  | { type: "product",    by: ByPhrase | ByVariantTemplateId | FromFrontOrder }
  | { type: "product_list" }
  | { type: "front" }                                  # whatever pane is in front

Field  = "service" | "total" | "who" | "where" | "status"
Action = "undo_confirm" | "approve" | "complete_capture" | "close_front_pane"
```

⚠️ **THE ONE DESIGN DECISION WORTH ARGUING ABOUT: `order_list` CARRIES THE EXISTING
`OrderQuestion` RATHER THAN A NEW SHAPE.** `OrderQuestion`
(`backend/app/services/order_list/question.py:60`) is already the validated structured
type the engine executes, and `accept_model_text` already validates a model's attempt at
one. Inventing a parallel list-request type would mean a second validator, a second thing
for the engine to translate, and two places to teach a new filter. The envelope is new;
the thing inside it is what already ships.

⚠️ **AND NO FIELD IN THIS TYPE CAN CARRY A NUMBER, A FACT OR A QUERY.** `Answer` names a
`Field` to look up, never a value. `Open` names a target to fetch, never rows. That is
`_BANNED_KEYS` expressed as a type rather than as a filter — the model cannot produce a
total because there is nowhere to put one.

### The dispatch's six examples, mapped

| typed | request |
|---|---|
| `hopkins order` | `Unsure{picks:[Open{order by decedent:"smith", number:"SO-2026-0001"}, Open{…0003}]}` — measured: Hopkins has two |
| `when's the service` | `Answer{about: {type:"front"}, question:"service"}` |
| `Monticellos since June` | `Open{order_list, question: OrderQuestion(vault="monticello", service_from=2026-06-01, when_label="since June")}` |
| `what's going out Friday` | `Open{order_list, question: OrderQuestion(going_out=True, service_from=…, service_to=…, title="Going out Friday")}` |
| `order hopk monti thursday 10 st marys` | `Capture{fields:{funeral_home:"Hopkins Funeral Home", vault:"Monticello Burial Vault", cemetery:"St. Mary's Cemetery", service_date:"2026-10-22", service_time:"10:00"}}` |
| `the vault` | `Open{product by from_front_order}` → resolves to the front order's vault row's `variant_template_id` |

---

## PART 3 — Where the model plugs in

### 3.1 Rules first, model on the fall-through or on Enter

The insertion point already exists and is used once: **`propose` at
`service.py:ask`**, called only when `interpret` returns `unrecognized`. Two more are
needed, in the same shape:

| today's dead end | file:line | what the model would be asked |
|---|---|---|
| `interpret` → `unrecognized` | `service.py` (`propose` already wired) | produce an `OrderQuestion` |
| `routeResolution` → `product-list-unmatched` | `OpasHost.tsx` fall-through | produce a `Target{product}` or `Unsure` |
| capture extraction leaves `unrecognized` spans | `typed_extraction.py` | produce `Capture{fields}` for the leftover words only |

⚠️ **AND NOT BEFORE THE RULES, EVER.** Measured below: the rules resolve 95% of the
phrasings people actually type, at a p50 the command bar's own gate holds under 100 ms.
A model in front of that is 350-450 ms added to 95% of requests to improve 5%.

### 3.2 Context passed

| what | where it comes from | size at Sunnycrest (measured) |
|---|---|---|
| front pane | `OpasHost.frontOrder` / `frontPane.kind` | 1 line |
| open panes | `opas.panes` | ≤ 5 lines |
| tenant vocabulary | `GET /capture/vocabulary`, already fetched on open | **5 customers, 1 cemetery, 10 products** |
| platform catalog | `product_templates` | **29 variants** |
| confirmed aliases | `platform_product_aliases WHERE is_confirmed` | **56 rows** |
| rulebook | Part 4's new table | 0 today |
| today's date, tenant-local | `tenant_clock.tenant_today` | 1 line |

So the whole context is **~100 names**. That is small enough to send in full rather than
retrieve — no embedding store, no RAG, nothing to keep in sync.

### 3.3 How a model answer is validated before anything shows

`accept_model_text` already does this for the list path and is the template:

1. **Parse.** Not JSON → `None`.
2. **Banned keys, recursively.** `sql, query, total, amount, count, sum, select, numbers`
   at any depth → `None`.
3. **Validate against the pydantic model.** `OrderQuestion.model_validate` →
   `ValidationError` → `None`.
4. **Re-derive the computed fields.** `about_money`, `is_default` and `title` are
   **overwritten** from the question, not taken from the model.
5. **Resolve every name against the tenant's own tables.** A funeral home the model
   proposed becomes an id through `_customer_by_exact_name`, or the request is refused.
6. **`None` means the rules stand.** No fallback guess.

Steps 4 and 5 are the ones to extend: a model naming "Hopkins" must produce a row id or
nothing, which is what makes "answers are quoted from looked-up records" structural
rather than a prompt instruction.

### 3.4 Latency, caching, cost

**Budgets.** The rules path keeps its own: `test_command_bar_latency.py:59-60` holds
p50 ≤ 100 ms / p99 ≤ 300 ms; `test_typed_capture_latency.py:76` holds a 150 ms
re-extraction budget. **Neither can absorb a model call.** A separate budget for the
model path: **p50 ≤ 900 ms, p99 ≤ 2,000 ms**, as its own BLOCKING gate, with the rules
gates untouched. (CLAUDE.md records Haiku adding ~350-450 ms to the NL-creation path.)

⚠️ **CACHING: THERE IS NONE TODAY, AND `input_hash` IS NOT IT.**
`intelligence_service.execute` computes `input_hash` (`:374`) and uses it **only for
experiment variant assignment** (`:280-282`). No code reads a prior execution to reuse a
response. So a cache is work to be added, not a thing to lean on. Where it would go: a
lookup on `(prompt_version_id, input_hash, company_id)` over `intelligence_executions`
before the call, with the tenant vocabulary folded into the hash so a new customer
invalidates it.

**Cost.** The `simple` route is `claude-haiku-4-5` at **$1.00/M in, $5.00/M out**
(measured from `intelligence_model_routes` on production).

| | tokens | cost |
|---|---|---|
| system prompt + rulebook | ~800 in | |
| vocabulary (~100 names) | ~250 in | |
| front pane + open panes + date | ~150 in | |
| the phrase | ~20 in | |
| the request out | ~150 out | |
| **per call** | 1,220 in / 150 out | **$0.0020** |

**Volume.** Measured on production 2026-10-20: Sunnycrest has **1 active user**, **12
capture sessions in 30 days**, **4 sales orders**. That is a pilot, not a working volume,
so the figure below is **modelled from a stated assumption, not measured**: one director
at **40 bar requests per working day × 22 days = 880/month**, of which the measured 5%
miss rate reaches the model → **44 calls → $0.09/month**. At a full office of eight and a
pessimistic 15% miss rate: **1,056 calls → $2.11/month**. Cost is not a constraint at
this scale; it is a constraint on nothing until Sunnycrest is 100× its current size.

### 3.5 Model-down behaviour

Already correct in `proposal.py` and it is the pattern: no API key → `None`; any
exception → `None`; `accept_model_text` failure → `None`. **`None` means the rules'
answer stands**, which is "Try: Hopkins orders this month · going out Friday". Nothing
degrades except the 5%.

⚠️ One thing to add: **the model path must not be on the keystroke path at all**, so a
hung provider cannot make the ghost or the tinting stutter. Today's `propose` is inside
the `ask` request, which is already Enter-only. The two new insertion points must be too.

### 3.6 Duckling and pg_trgm

**Duckling** (dates/times, self-hosted, no provider). Plugs in **inside
`typed_extraction`**, before the model, as a replacement for the hand-written date and
time parsers. It is the right tool for `k03`'s `thursday 10` and for `wednesday october
28` — which today's rules do get (measured) — and for everything they do not: "a week
from Tuesday", "the 3rd", "next Friday afternoon". **What it replaces:** the date/time
branch of the extractor, not the field routing. **What it must not do:** decide which
FIELD a date belongs to — service date vs date of death vs burial date is a tenant rule,
not a parse.

**pg_trgm** (typos). The extension is **already installed on production, version 1.6**
(measured), with six GIN indexes from `r31_command_bar_trigram_indexes`. It plugs in
**under `product_name_resolver`, after the exact and alias passes fail** — the surface is
the **56 confirmed rows in `platform_product_aliases`** plus the 29 `product_templates`
names. **What it replaces:** nothing. It is a third pass after exact and alias, and it
must return *candidates*, never a choice — `monticelo` → `Monticello Burial Vault` /
`Monticello Urn Vault` is still an `Unsure`, because `monticello` spelled correctly is
also ambiguous (measured).

---

## PART 4 — Rulebook and decision log

### STOP: these are proposals. No migration is written and none should be until the shape is confirmed.

### 4.1 `opas_tenant_rules` — the rulebook

| column | type | why |
|---|---|---|
| `id` | `String(36)` PK | |
| `company_id` | FK `companies.id`, indexed, **not null** | a rule is always one tenant's |
| `scope` | `String(24)` | `vocabulary` \| `routing` \| `default` \| `field` |
| `subject` | `String(120)` | what it is about — a phrase, a field id, a target type |
| `rule_text` | `Text` | the rule in the office's words, as they confirmed it |
| `payload` | `JSONB` | the machine-readable form; **validated by the same pydantic model the engine executes** |
| `source` | `String(24)` | `confirmed_from_change` \| `typed_by_admin` \| `imported` |
| `decision_id` | FK `opas_decisions.id`, nullable | the change it was drafted from |
| `confirmed_by` | FK `users.id`, **not null** | ⚠️ a rule with no confirmer is a guess |
| `confirmed_at` | `DateTime(tz)` **not null** | |
| `retired_at` / `retired_by` | nullable | ⚠️ retire, never delete — a rule that produced a decision must stay readable |
| `is_active` | `Boolean` **not null** | partial unique on `(company_id, scope, subject) WHERE is_active` |

⚠️ **`settings_json` ALREADY HOLDS A PROTO-RULEBOOK AND IT IS EMPTY.**
`order_list/service.py:remember` writes `opas_order_list_phrases` — a per-tenant map from
a normalised phrase to an `OrderQuestion`, capped at 40 (`MAX_TAUGHT`). Measured on
production: **all four tenants have zero taught phrases**. So the mechanism works, has
never been used, and is the thing the table replaces. The migration path is to read both
and write only the table.

### 4.2 `opas_decisions` — the decision log

| column | type | why |
|---|---|---|
| `id` | `String(36)` PK | |
| `company_id` | FK, indexed, not null | |
| `actor_user_id` | FK `users.id`, not null | ⚠️ **of whoever made the change**, per the ruling |
| `created_at` | `DateTime(tz)`, indexed | |
| `input_text` | `Text` | what was typed, verbatim |
| `proposed_request` | `JSONB` | the `OpasRequest` the model or the rules produced |
| `proposed_by` | `String(24)` | `rules` \| `model` \| `rulebook` |
| `model_execution_id` | FK `intelligence_executions.id`, nullable | ⚠️ the existing audit row; do not duplicate tokens or cost here |
| `final_request` | `JSONB` | what was executed after the person's edit |
| `diff` | `JSONB` | field-level, computed; `{}` means approved unchanged |
| `outcome` | `String(16)` | `approved` \| `changed` \| `abandoned` |
| `why_asked` | `Boolean` not null | whether the "Why?" prompt was shown |
| `reason` | `Text`, nullable | what they said |
| `scope_answer` | `String(12)`, nullable | `just_today` \| `always` \| `dismissed` |
| `rule_id` | FK `opas_tenant_rules.id`, nullable | the rule `always` drafted |

### 4.3 How "Why?" is triggered

The ruling, verbatim: *"'Why?' is asked only on a change, never an approval, at the
moment, of whoever made the change, with one tap for 'Just today' or 'Always'; 'Always'
drafts a rule the person confirms."*

The trigger, in the existing machinery:

1. The reply line holds the proposed request. The person presses Enter → `outcome =
   approved`, `diff = {}`, **no prompt**. The row is still written: an approval is
   evidence too, and it is what makes a later "always approved, never changed" readable.
2. The person **edits** before Enter — corrects a field in the capture, removes a pill
   from a list question (`removeOrderPill`, which already passes `teach_phrase`), picks a
   different option. `diff` is non-empty → `outcome = changed`.
3. **At that moment**, the reply line asks `Why? · Just today · Always` as a
   three-option `Reply` — the same `say("question", …, {options})` the bar already has, so
   no new surface. Dismissing is an answer (`scope_answer = dismissed`); the row stands
   without a reason.
4. `always` → draft an `opas_tenant_rules` row with `is_active = false` and show it in
   the reply line as one sentence to confirm. **Confirming sets `confirmed_by` and
   `is_active`.** ⚠️ A drafted-and-unconfirmed rule must never affect routing.
5. ⚠️ **The actor is the person who made the CHANGE, which is not always the person who
   typed.** The log carries both: `actor_user_id` for the change, and the typed text with
   whatever session produced it.

⚠️ **AND THE PROMPT MUST BE RATE-LIMITED OR IT BECOMES A TAX.** Nothing in the ruling
says so and the first week of real use will: a director correcting six fields on one
order must be asked once, about the order, not six times. Proposal: one prompt per
`OpasRequest`, not per field, and at most one per 60 seconds per user — stated here as a
gap for James rather than decided.

---

## PART 5 — Test set, the measured score, and provider choice

### 5.1 File format and location

```
backend/tests/data/opas_requests.jsonl        the set — one JSON object per line
backend/tests/test_opas_request_score.py      a BLOCKING floor on today's rules
tools/opas-eval/                              the provider harness (promptfoo config)
```

**JSONL, not JSON or YAML**, for three reasons: a 500-row set appends without rewriting;
a diff shows one changed case as one changed line; and a malformed row fails one case
rather than the file. One row:

```json
{"id":"o01","text":"riverside order","context":"cold",
 "want":{"kind":"open","target":{"type":"order","by":{"funeral_home":"riverside"}}},
 "source":"STATE 2026-10-19 walk"}
```

`source` is **required** — a case with no provenance is a case nobody can check.
`context` is required and is one of `cold | order_in_front | list_open | capture_open`,
because the same text is a different request in each.

### 5.2 The 59 drafted phrasings, and what today's rules score on them

Drafted from `platform_product_aliases` (56 confirmed rows), `question.py`'s own rule
constants, `stage.py`'s footer examples, `context-phrases.ts`, the capture and
order-list test suites, the walks recorded in STATE, and **production
`capture_sessions.full_text`** — 8 phrasings a director actually typed.

Scored by running **the shipped predicates** — the frontend gates bundled with esbuild
and imported, the server rules through `interpret`/`ask`/`resolve`/`EXTRACTOR` against
**production, read-only**.

```
TODAY'S RULES — 59 PHRASINGS, EACH IN THE STATE IT IS TYPED IN
  resolved correctly    56   95%
  not resolved           3    5%

by context:          cold 41/44 · order_in_front 8/8 · list_open 4/4 · capture_open 3/3
by source:           production (measured) 8/8 100% · the repo's own rules/tests 37/38 97%
                     · a dispatch or a walk 11/13 84%
```

**The three the rules do not resolve, and each maps onto one proposed addition:**

| | typed | today | needs |
|---|---|---|---|
| `l18` | `anything going to St. Mary's this week?` | unrecognized → catalog resolver → no match | **the model** — the dispatch's own stated limit |
| `c10` | `monticelo` | resolver: 0 candidates | **pg_trgm** |
| `k03` | `order hopk monti thursday 10 st marys` | **routed to the order list, unrecognized** | see below |

⚠️ **`k03` IS A REAL GAP IN A LIVE FEATURE AND IT IS THE DISPATCH'S OWN EXAMPLE.** The
forgiving opener (`startsCaptureWithParty`) requires the words after "order" to prefix a
funeral home's name, **as the whole remainder**: `"hopkins funeral home".startsWith("hopk
monti thursday 10 st marys")` is false, and so is the reverse. So `order hopk` opens a
capture and `order hopk monti thursday 10 st marys` does not — it contains "order", so
`isOrderListPhrase` claims it and the list says it understood nothing. A director typing
the whole order in one breath gets a dead end. Two further facts about the same phrase,
measured: `monti` resolves to **0** catalog candidates, and `thursday 10` needs a date
parser. Fixing the opener is a one-line change and is **not** this investigation's to
make.

### 5.3 ⚠️ Three errors in my own first version of this test set

Stated because the first number I computed was **61%**, and the gap between that and 95%
is entirely my test set rather than the rules.

| what I got wrong | how it showed | the measurement that corrected it |
|---|---|---|
| expected `monticello`, `SST`, `cameo rose`, `oversize graveliner` to resolve to ONE product | 4 false misses | each resolves to **2** variants (burial vs urn vault, or two sizes) — asking is correct |
| scored the 8 context phrases with **no order in front** | 8 false misses | they are typed with an order in front, which is the whole point of them |
| scored `that's everything`, `approve`, `monticello no personalization` down the `submit` chain | 3 false misses | in capture mode the bar never reaches `submit` — those go through `is_done_signal` and the extractor |
| took `penn order` and `fort hill order` from TEST fixtures | 2 false misses | neither exists on production; "unrecognized" is the correct answer there |

⚠️ **The first three are the same defect: an expected value derived from the hypothesis
rather than from the world** (CLAUDE.md §11). A 61% score would have justified the model
far more comfortably than 95% does, which is exactly why it needed checking.

### 5.4 The harness, and what it must not be

**promptfoo** (`tools/opas-eval/promptfooconfig.yaml`) scores any provider on the same
JSONL. Shape:

- `providers:` `anthropic:claude-haiku-4-5`, `anthropic:claude-sonnet-5`,
  `xai:grok-…` — one entry per candidate, same prompt, same context block
- `tests:` generated from the JSONL, one per row
- `assert:` **`python` assertions that call `accept_model_text` itself**, so a provider is
  scored on whether the ENGINE accepts its answer, not on string similarity. A provider
  that produces plausible prose scores zero.
- two scores per provider, reported separately: **accepted-and-correct** and
  **accepted-but-wrong**. The second is the dangerous number and an average hides it.

⚠️ **AND THE HARNESS MUST SCORE THE RULES AS A PROVIDER TOO.** A `rules-only` provider
entry that runs `interpret`/`resolve` and nothing else gives every model run a baseline
in the same table. Without it, "the model scores 92%" is unreadable — today's rules score
95% on this set.

⚠️ **THE SET MUST GROW FROM THE DECISION LOG, NOT FROM IMAGINATION.** Part 4's
`input_text` + `final_request` is exactly a test case. The 59 here are a seed; the real
set is what directors type.

### 5.5 Provider data terms — what I can and cannot tell you

⚠️ **I CANNOT VERIFY ANY PROVIDER'S CURRENT TERMS FROM THIS REPOSITORY**, and the
dispatch asks what they say. What I can state:

- **Anthropic is already in use on production**, with a signed arrangement implied by
  5,565 `intelligence_executions` rows carrying tenant data since 2026-05-15. Whatever
  the terms are, they already cover Sunnycrest's data — so Anthropic adds **no new data
  question**, which is itself a selection criterion.
- **xAI/Grok is not used anywhere in this codebase** (grep: zero non-prototype hits), so
  sending tenant data there is a **new** processor relationship: a new sub-processor
  disclosure, a new DPA, and a new entry in whatever Sunnycrest tells funeral homes about
  where their decedents' names go.
- ⚠️ **AND THE DATA IS UNUSUALLY SENSITIVE FOR THIS DECISION.** The context block
  contains a deceased person's name, their funeral home, their cemetery and their service
  date. That is not a product SKU. **Any provider evaluation must state whether prompts
  are retained, for how long, and whether they train on them** — and I should not
  summarise anyone's policy from memory. Fetch the current terms, put the two relevant
  paragraphs in `docs/` with a date, and decide against those bytes.
- **A cheap structural mitigation worth considering regardless:** the context block does
  not need the decedent's name to route a request. `Open{order by decedent}` needs the
  SURNAME to match; `Answer{about: front}` needs no name at all. Sending initials or an
  opaque id for anything the model does not need to match on would narrow what leaves the
  tenant to almost nothing — and it is a design choice available now, before a provider
  is picked.

---

## What I would build first, and why

**1. Fix `startsCaptureWithParty` so `order hopk monti thursday 10 st marys` opens a
capture.** One line, no model, no provider, no table. It is a live dead end on the
dispatch's own example phrase, found by measuring, and every later layer sits on top of
the capture opening at all.

**2. Seed `opas.order_list.interpret`.** The door, the validator, the model-down path and
the no-key path all exist and are tested. The prompt is the only missing piece, and
seeding it turns 1 of the 3 misses into a measurable experiment at a cost of ~$0.002 a
call and no new table, no new surface, and no new provider.

**3. Then the decision log — before the rulebook.** The log is pure observation: it
records what was proposed and what the person did, and it needs no new UI beyond the
"Why?" question the reply line can already render. **It is also how the test set grows.**
The rulebook needs the log's data to be worth anything; built first, it is a table of
rules nobody has evidence for.

**4. pg_trgm under the resolver.** Extension present, indexes present, 56 aliases to sit
under, no provider, no model. It converts `monticelo` into an `Unsure` rather than a dead
end.

**5. Duckling last of the five.** It is a self-hosted service to run and monitor, and the
dates the rules already parse are the dates people actually type — measured: all three
production capture phrases had their dates and times extracted correctly.

⚠️ **AND WHAT I WOULD NOT BUILD FIRST: the provider bake-off.** It is the most
interesting question and the least urgent. Today's rules score 95% on the set; the model
is for 3 phrasings, one of which is a one-line rules fix. **Score the rules, seed one
prompt, watch the log for a month, and pick a provider against a test set made of what
directors actually typed** — rather than against 59 phrasings I drafted from the code
that already handles them.
