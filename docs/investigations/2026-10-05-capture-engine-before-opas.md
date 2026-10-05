# The capture engine, before Opas is built on it

**Read-only investigation. No code, no migrations, no tests. 2026-10-05.**

Subject: `backend/app/services/capture/` — three files, **420 lines**
(`__init__.py` 36, `missing.py` 140, `schema.py` 244).

⚠️ *This line first read "553 lines" over the same three correct components.
36 + 140 + 244 = 420; 553 was arithmetic I did not check against the parts I had
already written down. Corrected 2026-10-05. The figure is load-bearing for
nothing in this report, which is exactly why it survived being written.*

---

## Premise check first

Every premise in the dispatch exists. Three carry corrections, none fatal:

| dispatch | actual |
|---|---|
| canon dated **2026-10-01** | **2026-10-02** — `DECISIONS.md:2310` |
| `resolve_schema:182-184` skips conditionals when `vault_product_id is None` | the behaviour is real, at **`schema.py:215-217`**. Line 184 is where `resolve_schema` *begins*; 182-184 is the end of `ResolvedField` |
| canon says template carries a **summary layout** | canon says **"review layout"** (`DECISIONS.md:2318`). Neither exists in code |

⚠️ **And the canon entry's own measured-state paragraph is now stale.** It reads
*"app/services/capture/ is imported by nothing in app/"* — true on 2026-10-02,
false since `27d4fe46`. It also says *"the call overlay's hardcoded list is the
copy to retire"*; it is not retired, and there are **two** of them (Part 4).

---

## PART 1 — What the engine does, by edge

**EDGES INSPECTED: 17 real call edges** — 2 in `app/`, 15 in `tests/`. Resolved
by import binding across **1,794 files**; 3 files import the package (1 `app/`,
2 `tests/`, 0 `scripts/`).

⚠️ **MY FIRST PASS REPORTED THREE `app/` CALLERS AND WAS WRONG.** It matched the
last segment of each callee name, so `tier_1_rules.evaluate(db, email_message)`
in `classification/dispatch.py` and `note/service.py`'s own two-argument
`template_for(vertical, role_slug)` both counted. They are unrelated functions
sharing a name with a capture export. **The dispatch's "first and only caller" is
correct**; my correction to it was a false-presence defect, and it is recorded
here because it nearly travelled.

### The exported surface — 15 names, 2 reached from `app/`

| name | kind | `app/` edges | `tests/` edges |
|---|---|---|---|
| `evaluate` | function | **2** (`call_extraction_service.py:204`) | 8 |
| `template_for` | function | **1** (`call_extraction_service.py:186`) | 1 |
| `FUNERAL_ORDER` | str `"funeral_order"` | 1 (attribute read, same line 186) | — |
| `VAULT_FIELD_ID` | str `"vault"` | 1 (attribute read, in the adapter) | 1 |
| `resolve_schema` | function | **0** — reached only *through* `evaluate` | 1 |
| `is_answered` | function | 0 | 2 |
| `TenantCaptureConfig` | dataclass | 0 | 3 |
| `PLATFORM_DEFAULT_FIELDS` | tuple of 11 | 0 | 1 |
| `CaptureState` | dataclass | 0 | type-only |
| `FieldDefinition` | dataclass | 0 | type-only |
| `CAPTURE_TEMPLATES` | dict, 1 entry | **0 anywhere** | 0 |
| `FieldNotSwitchable` | exception | 0 | 1 |
| `UnpermittedAnswer` | exception | 0 | 1 |
| `ResolvedField` | dataclass | 0 | 0 |
| `without_field` | function | **0 anywhere** | 0 |

### Signatures and returns

```
template_for(object_type: str)              -> tuple[FieldDefinition, ...]
resolve_schema(*, vault_product_id: str|None,
                  personalization_config: dict|None,
                  tenant_config: TenantCaptureConfig|None = None,
                  platform_fields: tuple[FieldDefinition,...] = PLATFORM_DEFAULT_FIELDS)
                                            -> tuple[ResolvedField, ...]
evaluate(extracted: dict[str,object], *, <same four kwargs>)
                                            -> CaptureState(answered, missing, not_applicable)
is_answered(value: object)                  -> bool
without_field(fields, field_id)             -> tuple[FieldDefinition, ...]
```

Two notes that matter downstream:

- **`without_field` is a declared test helper living in production code** — its
  own docstring says so. Zero callers, including tests.
- **`evaluate` ignores unknown keys in `extracted`** by design (docstring): the
  schema decides what is required, so an extra key is noise. This is what makes
  a template swap safe on the input side.

---

## PART 2 — Is it general, or one type wearing a generic name?

**Both, on two different axes, and the inconsistency is the finding.**

- **The FIELD SET axis is genuinely parameterised.** `CAPTURE_TEMPLATES` +
  `template_for` + the `platform_fields` keyword form a real registry. This is
  *better* than the prediction expects.
- **The CONDITIONAL axis is hardcoded to personalization-on-a-vault**, and not in
  a cosmetic way — it is in the signature of both public entry points.

### (a) Genuinely generic, parameterised by the template

- `FieldDefinition` — `field_id`, `label`, `required`, `switchable`,
  `question_id`. No type-specific shape.
- `CaptureState` — `answered` / `missing` / `not_applicable`.
- `is_answered` — the one place deciding what "answered" means; pure.
- `template_for(object_type)` — raises on an unregistered type rather than
  falling back, deliberately.
- `CAPTURE_TEMPLATES` — the registry itself.
- `platform_fields` keyword on `resolve_schema` and `evaluate`.
- `TenantCaptureConfig.disabled_field_ids` — the delta-overlay *shape*.
- `evaluate`'s ignore-unknown-keys contract.

### (b) The template's data leaking into the engine

- **`PLATFORM_DEFAULT_FIELDS` (`schema.py:92-101`)** — the funeral-order field
  list, defined inside the engine module **and used as the default value of
  `platform_fields` on both public entry points.** So the engine's default
  behaviour is "funeral order": a caller who omits the keyword silently captures
  a funeral order.
- **The eight field literals and their labels** (`schema.py:93-100`): `vault`
  /"Vault", `funeral_home`/"Funeral home", `deceased_name`/"Deceased name",
  `vault_size`/"Size", `cemetery`/"Cemetery", `burial_date`/"Burial date",
  `burial_time`/"Burial time", `grave_location`/"Grave section / lot / space".
- **`VAULT_FIELD_ID = "vault"` (`schema.py:49`)** — module-level constant,
  exported in `__all__`, consumed by the one caller's adapter.
- **`FUNERAL_ORDER = "funeral_order"` (`schema.py:114`)** — the template's
  registry key living in the engine module.
- **`_personalization_fields()` (`schema.py:74-88`)** — derives three capture
  fields from `QUESTIONS` and appends them to `PLATFORM_DEFAULT_FIELDS`. Deriving
  rather than typing them out is right; the three fields are vault concepts
  regardless.

### (c) Hardcoded for the one type — structural, not incidental

- **`vault_product_id` is a REQUIRED keyword on `resolve_schema`, and a required
  keyword on `evaluate`.** The general entry point cannot be called without
  naming a vault-domain identifier. A quote capture must pass
  `vault_product_id=None` — which is not "no vault", it is the sentinel that
  *silently drops every conditional field* (see below).
- **`personalization_config` is a parameter on both entry points.**
- **Three imports bind the engine to the personalization package**:
  `missing.py:31` `ANSWER_NONE`; `schema.py:42` `AvailabilityState`,
  `read_availability`; `schema.py:46` `QUESTIONS`.
- **`resolve_schema:219-229` — the entire conditional mechanism** is
  `read_availability(personalization_config, vault_product_id, question_id)`.
  There is no other way to express "this field applies conditionally".
- **`_reject_unpermitted` (`missing.py:119-140`)** — guards a conditional answer
  against "the vault's permitted set"; the error text reads *"is not permitted on
  this vault"*. `UnpermittedAnswer`'s docstring: *"An answer the vault does not
  permit"*.
- **`TenantCaptureConfig.__post_init__` (`schema.py:152-162`) validates against
  `PLATFORM_DEFAULT_FIELDS`, not against the template in use.** Hardcoded. For a
  second type this is wrong in both directions: a quote template's own
  unswitchable field would be unprotected, and funeral-order's `vault` would be
  protected on a quote that has no vault.

⚠️ **And `vault_product_id=None` means two different things.** `resolve_schema`'s
docstring defines it as "applicability unknown, a vault is about to be named",
and omits conditionals *temporarily*. At the only real call site
(`call_extraction_service.py:188-203`) the comment states it is **permanent** —
no vault name resolver exists anywhere — so the three personalization questions
are omitted from both `answered` and `missing` on **every** call, forever. The
caller documents this and logs the count. A second object type passing `None`
because it has no vault inherits a sentinel that means neither of those things.

---

## PART 3 — What a template actually is today

**Partly data, partly code, and the review layout does not exist.**

Canon (`DECISIONS.md:2318`) says a template declares four things. Measured:

| canon requires | exists as data? |
|---|---|
| its fields | **yes** — `tuple[FieldDefinition]` in `CAPTURE_TEMPLATES` |
| which are required | **yes** — `FieldDefinition.required` |
| what each field depends on | **partly** — `question_id` names a dependency, but resolving it is hardcoded personalization code reading tenant config |
| its review layout | **no — nothing, anywhere.** `grep -ri "summary_layout\|summary layout\|summaryLayout"` across `backend/app` and `frontend/src` returns zero |

### The one template, written out in full

`CAPTURE_TEMPLATES = {"funeral_order": PLATFORM_DEFAULT_FIELDS}` — 11 fields:

| field_id | label | required | switchable | conditional on |
|---|---|---|---|---|
| `vault` | Vault | yes | **no** | — |
| `funeral_home` | Funeral home | yes | yes | — |
| `deceased_name` | Deceased name | yes | yes | — |
| `vault_size` | Size | yes | yes | — |
| `cemetery` | Cemetery | yes | yes | — |
| `burial_date` | Burial date | yes | yes | — |
| `burial_time` | Burial time | yes | yes | — |
| `grave_location` | Grave section / lot / space | yes | yes | — |
| `legacy_print` | Legacy Series™ Print | yes | yes | `legacy_print` availability |
| `nameplate_cover_emblem` | Nameplate & Cover Emblem | yes | yes | `nameplate_cover_emblem` |
| `lifes_reflections` | Life's Reflections® Vinyl | yes | yes | `lifes_reflections` |

Every field is `required=True`. Only `vault` is unswitchable, for the mechanical
reason the docstring gives: without a vault there is nothing to read conditional
availability from.

### ⚠️ The one template is not one of the types canon names

Canon lists *"sales order, quote, purchase order, email, text message, calendar
event, disinterment case, time-off request"*. The registry holds **`funeral_order`**,
which appears in that list nowhere. So the dispatch's framing — *"quote as a
template alongside sales order"* — presumes a **sales-order template that does
not exist**. Whether `funeral_order` *is* canon's sales order is a naming
decision nobody has recorded, and it needs making before a second template is
written, because the answer decides whether `funeral_order` is renamed or joined.

---

## PART 4 — The frontend half

`CallOverlay.tsx`, 616 lines, 5 components. Only one imports anything
call-specific; the split is clean enough to describe precisely.

### Call-specific — Opas reuses none of it

| lines | what |
|---|---|
| `31-56` | `useCallTimer` — elapsed-time hook off `answered_at` |
| `58-82` | `CallerInfo` — phone number, direction, caller identity |
| `84-155` | `CustomerContext` — resolved funeral-home record for the caller |
| `157-211` | `RingingCard` — pre-answer state, accept/decline |
| `310-334`, `440-466` | action rows: mute (13 refs), hold, hangup |
| `468-564` | `KBPanelCard` — live knowledge-base lookups during a call |

### Capture UI — the part Opas would reuse

| lines | what | reusable as-is? |
|---|---|---|
| `268-290` | "Still Needed" — renders `missing_fields` from the server | **yes**, and it is the only part that already obeys the rule |
| `291-308` | "Heard So Far" | **no** — client-built list |
| `390-412` | "Still Needed (red)" in `ReviewCard` | yes, same server list |
| `413-438` | "Captured (green)" | **no** — second client-built list |

### ⚠️ The violation, and there are TWO of it

`27d4fe46` moved the **missing** set server-side. It left the **answered** set
client-side, and the asymmetry is visible in the service: `capture_state.missing`
is persisted (`call_extraction_service.py:242`), while
**`capture_state.answered` is computed, written to one log line
(`:221`), and discarded.** It never reaches the client. So:

- the client **renders** what the server computed for *missing* — correct;
- the client **re-derives** *captured* from raw extraction columns — the same
  violation as the one fixed at `call_extraction_service.py:157`, one layer up,
  exactly as predicted.

And the two client lists disagree with each other and with the template:

| | fields | names used |
|---|---|---|
| template | **11** | `vault`, `vault_size`, `cemetery`, `funeral_home`, … |
| `ActiveCallCard:227-237` | **4** | Deceased, **Vault** (`vault_type`), Burial date, **Cemetery** (`cemetery_name`) |
| `ReviewCard:349-358` | **10** | + Burial time, Grave location, **Service location, Service date, Service time, Special instructions** |

⚠️ *The 10 is correct. A post-commit check reported 9 and the check was wrong —
its `sed` range began at 350 and cut the first entry, at 349. Resolved by reading
the list rather than re-counting it, and the line reference above is corrected
from `350-360` to `349-358`.*

Three different field sets. `ReviewCard` shows four fields the template does not
contain at all. Neither list contains the three personalization questions. And
both read `extraction.<column>`, whose names differ from the template's field ids
— the server has an adapter for exactly this (`_captured_from_result`, which
warns that *"three of the eight names differ and getting one wrong fails
silently"*); the client has no adapter and no test.

⚠️ This is the siblings-in-the-same-file pattern CLAUDE.md §11 names: the fix
landed at one site and the file holds another with the same shape.

---

## PART 5 — What a second template would take

### Additive — a row and a tuple

1. A `FieldDefinition` tuple for the new type.
2. A row in `CAPTURE_TEMPLATES`, and a constant beside `FUNERAL_ORDER`.
3. An adapter mapping that type's extraction keys to its field ids (the
   `_captured_from_result` equivalent), which lives at the caller.

That is genuinely all, **for a type whose fields are unconditional and whose
captured list the client is willing to keep hardcoding.** The registry work on
2026-10-02 earned that.

### Requires reshaping something that exists

4. **`vault_product_id` must stop being a required keyword on the public entry
   points.** Today a quote must pass `None`, which is the sentinel that silently
   drops conditional fields. A second type cannot have conditional fields at all
   until this is parameterised — which is the whole reason the engine exists.
5. **The conditional mechanism must become a template concern.** Today
   "conditional" means exactly `read_availability(personalization_config,
   vault_product_id, question_id)`. A quote conditional on customer terms, or an
   email conditional on recipient count, has no way to be expressed. This is the
   one genuinely structural change: it is the engine's only hardcoded policy.
6. **`TenantCaptureConfig.__post_init__` must validate against the active
   template**, not `PLATFORM_DEFAULT_FIELDS`. As written it enforces
   funeral-order rules on every type.
7. **`capture_state.answered` must be persisted and served.** Until it is, every
   surface re-derives the captured list, and Opas adding a second one makes three.
8. **The two hardcoded client lists must be retired** — canon already says the
   call overlay's list "is the copy to retire". Opas should not be built beside
   them; it should be built on the server-computed pair.
9. **A review-layout representation must be invented.** Canon requires it, it
   does not exist, and the frontend currently encodes it as JSX per card. This is
   net-new design, not a reshape.
10. **The `funeral_order` / "sales order" naming question must be settled**
    (Part 3) before a second template, since it decides rename-vs-add.

### The ordering hazard

⚠️ **Items 4 and 5 are stacked, and 4 alone makes things worse.** Making
`vault_product_id` optional without parameterising the conditional mechanism
leaves a second type passing `None` into a branch that interprets it as
"applicability unknown" and silently omits fields — a quote that quietly stops
asking questions, with no error. Today the required keyword at least forces the
caller to confront it. Same shape as the schema/arity pair in the import route:
repairing the outer layer exposes an inner defect and removes the diagnostic.

---

## The prediction, and where it was wrong

Predicted: *the engine substantially shaped by its single caller, with
sales-order concepts in places that should be generic.*

**Confirmed on the conditional axis, and more sharply than stated** — it is not
"concepts in places", it is the **signature of both public entry points** plus
three imports plus the only conditional branch.

**Wrong on the field-set axis.** `CAPTURE_TEMPLATES`, `template_for` and the
`platform_fields` keyword are a real registry, added 2026-10-02 citing this exact
canon entry. The engine is more general here than predicted, and `template_for`
raising on an unregistered type rather than defaulting is the right call.

**Two things neither of us predicted:**

- **The single template is `funeral_order`, which is not one of the eight types
  canon lists.** "Quote alongside sales order" has no sales order to sit beside.
- **There are two hardcoded client lists, not one**, and they disagree with each
  other as well as with the template — including four fields that exist nowhere
  in the schema.

---

## Standing caveat, carried from the dispatch

The call overlay is **unreachable in production** — no RingCentral OAuth
entrance, no tenant holds a token. This engine has never run against a real call.
Its tests are the whole of the evidence, the same position
`import_product_templates` was in before 2b-3. The engine's own code says so at
`call_extraction_service.py:200-203`, which is why the permanently-dropped
conditional questions were acceptable to land.

**"It works today" is not evidence we have.** What we have is 15 test edges and
two `app/` edges.
