# Scoping the one capture engine

**2026-10-02.** Read-only. No files changed outside this document. Scopes the engine bound by
DECISIONS 2026-10-02, "One capture engine, one template per object type, shared with the call
overlay".

**Four headlines.**

1. ⚠️ **One premise in the dispatch is half false.** The captured display is hardcoded; the
   **missing set is not** — it already crosses the wire from the server. That changes the
   first slice and makes it much smaller.
2. ⚠️ **The 51 / 64 / 29 catalog figures do not reproduce.** Measured: **55** and **37**
   sources sharing **9** exact names.
3. ⚠️ **No vault-name → product_id resolver exists, and the live order path proves it** —
   `create_draft_order_from_extraction` creates a sales order **with no lines at all**.
4. **The smallest slice is one function call in one backend file, with no frontend change.**

---

## 0. The two premises, verified first

### Premise A — CONFIRMED

`app/services/capture/` is imported by nothing in `app/`. Measured over every import form
(`from app.services.capture`, `from .capture`, `from ..capture`, `services.capture`), across
`app/`: **0 importers** outside the package itself. Repo-wide, the only references are its own
two modules, `tests/test_capture_schema.py`, and DECISIONS.md.

### Premise B — HALF FALSE AS STATED

The entry says CallOverlay "builds its captured and still-needed display from a hardcoded
per-field list". The captured half is hardcoded. The still-needed half is not.

`CallOverlay.tsx:226-239`:

```js
  // Collect what we've heard so far
  const heardFields: { label: string; value: string }[] = [];
  if (extraction) {
    if (extraction.deceased_name?.value)
      heardFields.push({ label: "Deceased", value: extraction.deceased_name.value });
    if (extraction.vault_type?.value)
      heardFields.push({ label: "Vault", value: extraction.vault_type.value });
    if (extraction.burial_date?.value)
      heardFields.push({ label: "Burial date", value: extraction.burial_date.value });
    if (extraction.cemetery_name?.value)
      heardFields.push({ label: "Cemetery", value: extraction.cemetery_name.value });
  }

  const missingFields = extraction?.missing_fields ?? [];
```

Four hardcoded `if` branches for **captured**. One line reading a server-supplied array for
**still-needed**.

⚠️ **This is better news than the entry recorded, and it is why the first slice is small.**
The missing set already has a server-side delivery path and a frontend that consumes it
without knowing where it came from. Nothing in the frontend needs to change to make the
missing set correct.

⚠️ **But its producer is the model.** `call_extraction_service.py:157`:

```python
        missing_fields=result.get("missing_fields", []),
```

`result` is the parsed Claude response. So the missing set is **server-delivered and
model-computed** — exactly the defect "The model extracts; the server decides what is missing"
names, still live, at one line.

**Continuing on the corrected premise, stated here rather than silently:** captured is
hardcoded in the client; missing is model-computed on the server.

## 1. The capture package — a complete, tested, unreachable implementation

381 lines across three files; 27 tests in `tests/test_capture_schema.py`.

```
schema.py   211 lines   VAULT_FIELD_ID · FieldDefinition · FieldNotSwitchable
                        TenantCaptureConfig · ResolvedField · resolve_schema · without_field
                        _personalization_fields
missing.py  140 lines   UnpermittedAnswer · CaptureState · is_answered · evaluate
                        _reject_unpermitted
__init__.py  30 lines   7 exports
```

Not a scaffold and not dead code: it is a **complete implementation behind an unprovisioned
entrance**, the shape CLAUDE.md §11 names. Every read site works; nothing produces its input
in production because nothing calls it.

⚠️ **One structural finding for the entry's "one template per object type".**
`PLATFORM_DEFAULT_FIELDS` is a single flat tuple describing the **funeral sales order**:

```
vault · funeral_home · deceased_name · burial_date · burial_time · cemetery
grave_location · vault_size
```

It is expressed as *the* platform default, not as one template among many. So "one template
per object type" is not satisfied by adding data — it requires a keying change to the package
(object type → template). That is small, and it is a change rather than an addition.

## 2. The four semantic entries — where each is enforced

| Entry | Enforced? | Where |
|---|---|---|
| The model extracts; the server decides what is missing | **NO** | violated at `call_extraction_service.py:157` |
| Required means answered, not filled | implemented, unreachable | `capture/missing.py::is_answered` |
| Capture fields are tenant-configurable over a platform default | implemented, unreachable | `capture/schema.py::resolve_schema` + `TenantCaptureConfig` |
| Conditional requirements determined by the vault, not stored on it | implemented, unreachable | `capture/schema.py::_personalization_fields` |

**STOP condition on drift: not triggered.** No rule is enforced in two places with differing
behaviour, because three are enforced in exactly one place that nothing reaches and the fourth
is enforced nowhere.

⚠️ **One near-miss worth recording as a name collision, not drift.**
`disinterment_service.py:528-541` builds a local `missing_fields` list deterministically and
raises:

```python
    missing_fields: list[str] = []
    if not fh_email or not fh_name:
        missing_fields.append("funeral_home (name + email)")
    ...
    if missing_fields:
        raise ValueError("Cannot send for signatures — missing signer data: " + ...)
```

Same variable name, unrelated subject: e-signature **signer parties**, not capture fields, and
it raises rather than producing a capture state. A search for the rule's implementation finds
it; reading it shows it is not one.

## 3. Inbound call → sales order, end to end

```
RingCentral webhook
  → call_extraction_service.extract_from_transcript
      Claude extraction  →  result dict
      missing_fields = result["missing_fields"]        ← MODEL decides      :157
      RingCentralCallExtraction row written            (missing_fields JSONB)
  → after_call_service.process_call_after_end          :106
  → call_extraction_service.create_draft_order_from_extraction  :211
  → GET /api/v1/call-intelligence/calls/{id}           exposes missing_fields  :54
  → CallOverlay.tsx  reads extraction.missing_fields   :239
```

`call_intelligence.py` has **4 endpoints**, all read-only plus `reprocess`. There is **no
approve-and-create endpoint** — the draft order is created automatically after the call ends,
not on approval. So DECISIONS "A call ends in a summary… approving it creates the order"
describes a ruling from the prototype, **not the shipped path**.

## 4. The vault-name → product_id resolver — does not exist

`create_draft_order_from_extraction` (`call_extraction_service.py:211-275`) resolves a
customer (`_resolve_customer_id`) and a cemetery (`_resolve_cemetery_id`). It uses
`vault_type` **only as a gate**:

```python
    if not extraction.vault_type and not extraction.deceased_name:
        return None
```

and then creates `SalesOrder(...)` with `deceased_name`, `cemetery_id`, `scheduled_date`,
`service_time`, `notes` — **and no line items at all.** The vault never becomes a product.

⚠️ So the order the shipped path creates is a **header with no product on it**, and the
absence of a resolver is why. This is the single most build-relevant finding: an order
template cannot be "filled" until a name resolves to a product, and nothing resolves it today.

## 5. The catalog figures — NOT reproduced

The dispatch carried "two product sources of 51 and 64 entries disagreeing on 29". Measured
against the two sources I can find, each with its population stated:

```
app/services/sunnycrest_product_seeder.py:90   55 entries   (population: that one list literal)
app/services/catalog_template_seeder.py        37 entries   (population: its 3 module-level
                                                             lists — 19 burial vaults,
                                                             12 urn vaults, 6 cemetery equipment)
products table, bridgeable_dev                 26 rows      (population: all tenants; all 26 testco)

exact-name intersection of the two code sources     9
only in sunnycrest_product_seeder                  46
only in catalog_template_seeder                    28
```

**Neither 51 nor 64 appears, and 29 does not either.** I could not determine what the prior
pass measured; its populations were not recorded, so the figures are not correctable, only
replaced. Reported rather than quietly adjusted.

⚠️ **The disagreement is worse than a count — it is a naming convention.** The dispatch's own
example resolves in one source and not the other:

```
"Bronze Triune"             in sunnycrest_product_seeder    NOT in catalog_template_seeder
"Bronze Triune Urn Vault"   in BOTH
```

`catalog_template_seeder` appends the product class; `sunnycrest_product_seeder` carries bare
names alongside suffixed ones. **9 of 55 names match exactly.** An exact-match resolver built
against either source fails on the other.

**Which is authoritative: neither is established.** `sunnycrest_product_seeder` writes the
real tenant's catalogue and is the larger set; `catalog_template_seeder` seeds
`product_catalog_template`, a platform-tier artifact. Deciding between them is a ruling, not a
measurement, and the resolver is blocked until it is made.

## 6. A second consumer's object types

Exactly **one** object type has a server-side capture schema anywhere: the funeral sales
order, in the unreferenced package. Quotes, purchase orders, emails, text messages and
calendar events have **no capture schema** — all five would be new templates. Each has a
persistence model; none has a field/required/conditional declaration.

## 7. The smallest first slice that retires rather than duplicates

**Replace one expression in one backend file.** `call_extraction_service.py:157`:

```python
missing_fields=result.get("missing_fields", []),        # model decides
```

becomes the deterministic evaluation against the resolved schema — `capture.resolve_schema()`
plus `capture.evaluate()` over the values the model extracted.

Why this is the right first slice:

- **It retires the violation rather than adding a copy.** The model stops deciding; the one
  line that let it stops existing.
- **It gives the unreferenced package its first production caller**, closing the
  unprovisioned-entrance defect in §1 at the same time.
- **Zero frontend change.** `CallOverlay.tsx:239` already reads `extraction.missing_fields`
  and does not care who computed it.
- **It does not need the product resolver.** The missing set is about field presence, not
  product identity, so §4's blocker does not gate it.
- **It is testable against the 27 existing tests** plus a parity test over stored extractions.

Then, in order and separately:

1. **The captured display.** Retiring the four hardcoded `if` branches needs the schema's
   labels on the wire — a response-shape change, so it is a second slice, not this one.
2. **Per-object-type keying.** `PLATFORM_DEFAULT_FIELDS` → a template registry (§1).
3. **The vault → product resolver.** Blocked on §5's authority ruling.

## 8. What this does not establish

- Which product source is authoritative (§5). A ruling, not a measurement.
- What the prior pass's 51/64/29 measured. Its populations were not recorded.
- Whether production's `products` table agrees with either code source — dev only was read.
- Whether any tenant has a `TenantCaptureConfig` persisted anywhere. The class exists; no
  table or column was traced for it in this pass.
