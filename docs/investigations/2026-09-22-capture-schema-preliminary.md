# Capture schema preliminary

**2026-09-22.** Investigation only. No code. Production read-only, through a
connection opened with `default_transaction_read_only=on`; credentials never
printed, host/port/db only via `urlparse`. Builds on
`2026-09-22-call-to-print-gap-map.md` and re-derives rather than inherits every
claim it carried forward.

---

## 1. Personalization in the product catalog

> **The per-tenant, per-vault, per-option model already exists in code — and holds
> nothing in production. Every table it needs is empty, `personalization_tier` is
> null on all 33 products across all three tenants, and the function that answers
> "does this tenant offer this option on this vault" returns an empty list for
> every product today.**

So this is neither "the schema is mostly a settings page" nor "the catalog is the
first item." It is a third thing: **the catalog is the first item, and it is a
seeding and wiring problem rather than a modelling one.**

### What is modelled

Four layers, all present:

| layer | where | what it holds |
|---|---|---|
| Product → tier | `models/product.py:82` `personalization_tier` (varchar, nullable), plus `has_personalization` (bool) | which personalization tier a vault belongs to |
| Tier → options | `services/personalization_config.py:41` `PERSONALIZATION_TIERS` | 4 tiers → available option types **and mutual-exclusion groups** |
| Platform option master | `ConfigurableItemRegistry` where `registry_type='personalization_option'` | 5 seeded item keys with `tier` and `default_config` |
| Tenant override | `WilbertProgramEnrollment.personalization_config` (json) | per option: `is_enabled`, **`applicable_product_ids`**, `price_addition`, `price_overrides_by_product` |

And the reader the capture schema would call already exists:

```
PersonalizationConfigService.get_applicable_options_for_product(
    db, company_id, program_code, product_id) -> list[dict]
```
`services/personalization_config_service.py:275`. It filters master options by
`is_enabled`, then by `product_scope == "all" or product_id in product_scope`.
**Tenant × vault × option is expressible today**, which is exactly the shape the
Monticello-nameplate example needs.

The four tiers, read rather than summarised:

| tier | available types | mutually exclusive |
|---|---|---|
| `wilbert_standard` | legacy_print, vinyl, physical_nameplate, physical_emblem | 5 pairs |
| `continental` | physical_nameplate | — |
| `salute` | physical_nameplate, physical_emblem | — |
| `urn_vault` | all four, `uses_urn_prints: True` | 5 pairs |

### ⚠️ STOP — measured on production, 2026-09-22 ~09:35 ET

| table | exists | rows |
|---|---|---|
| `configurable_item_registry` | yes | **0** |
| `tenant_item_config` | yes | **0** |
| `wilbert_program_enrollments` | yes | **0** |
| `program_legacy_prints` | yes | **0** |
| `legacy_settings` | yes | **0** |
| `legacy_email_settings` | yes | **0** |
| `legacy_print_shop_contacts` | yes | **0** |
| `legacy_proofs` | yes | **0** |
| `ringcentral_call_extractions` | yes | **0** |
| `ringcentral_call_log` | yes | **0** |
| `products` | yes | 33 |

`personalization_tier` is non-null on **0 of 33** products. `has_personalization`
is `False` on **all 33**. The column exists (`character varying`, nullable) and
has simply never been written.

**Sunnycrest's actual products, read unbounded — this is an absence claim so the
query carries no `LIMIT`:**

| name | sku | tier | active |
|---|---|---|---|
| Continental Burial Vault | `DEMO2-P002` | null | true |
| Graveside Setup Service | `DEMO2-P004` | null | true |
| Monticello Burial Vault | `DEMO2-P001` | null | true |
| Urn Vault - Standard | `DEMO2-P003` | null | true |

Four rows, all `DEMO2-*`. The Monticello from the worked example is there — as
demo data with a null tier. Production holds 33 products total: testco 25,
sunnycrest 4, st-marys 4.

### ⚠️ And the failure mode is silent in the wrong direction

`get_config` returns `{"error": "No active enrollment found", "options": []}` when
there is no enrollment, and `get_applicable_options_for_product` turns that into
`[]`. With zero enrollment rows in production, **every product of every tenant
currently answers "no personalization options offered"** — which is
indistinguishable from a true negative. A capture schema that asks "is
personalization required for this vault?" would today be told *no* for every
vault, correctly according to the data and wrongly according to the world.

This is the §11 unprovisioned-entrance shape, and the read-site check confirms
it: `get_applicable_options_for_product` has exactly **one caller**, the HTTP route
at `routes/programs.py:373`. Its own docstring says *"Used by Composer."* The
Composer does not call it.

### ⚠️ Two option vocabularies, and they do not map one-to-one

This is a real fork and the schema has to pick a side.

| static canonical (`personalization_config.py`) | registry (`configurable_item_service.py:124`) |
|---|---|
| `legacy_print` | `personalization.legacy_photo` (tier 2) |
| `physical_nameplate` | — collapsed into `personalization.emblems_nameplates` (tier 2) |
| `physical_emblem` | — collapsed into the same key |
| `vinyl` | *no counterpart* |
| — | `personalization.standard_colors` (tier 1) |
| — | `personalization.custom_paint` (tier 3) |
| — | `personalization.specialty_finish` (tier 3) |

The canonical four are stored verbatim in `case_merchandise.vault_personalization`
and `order_personalization_tasks.task_type`. The registry five are what
`applicable_product_ids` is keyed by. **They are different key spaces**, and the
availability question is answered in the registry space while the order is
recorded in the canonical space.

⚠️ The static file states its own reasoning: *"Wilbert option lists below are
canonical Wilbert standard options that change infrequently. No database storage
needed — the option lists are defined here."* That is a deliberate decision, not
an oversight, and it is the one the per-tenant requirement pushes against.

---

## 2. What capture produces today

**The required list already exists — as prose inside a prompt.** Moving it
server-side is a transcription, not an invention.

`backend/scripts/seed_intelligence_phase2c.py`, prompt
`calls.extract_order_from_transcript`:

> *"A complete vault order requires: Funeral home name · Deceased name · Vault
> type/model (e.g. Triune, Monticello, Venetian, Triune Stainless) · Size
> (standard adult, oversize, infant) · Cemetery name · Burial date · Burial time ·
> Grave section/lot/space (if known) · Any personalization or special requests"*

Nine items. Note two of them already carry conditionality in English — *"(if
known)"* on grave location, and *"any"* on personalization — which is precisely
what the schema has to express in code.

**⚠️ The STOP about raw model output does not fire.** Captured values are stored
in **typed columns**, not a blob: `funeral_home_name`, `deceased_name`,
`vault_type`, `vault_size`, `cemetery_name`, `burial_date`, `burial_time`,
`grave_location`, `special_requests`, with `confidence_json` and `missing_fields`
as JSONB alongside (`models/ringcentral_call_extraction.py`). The extraction JSON
returns a per-field confidence tier as well.

What does **not** exist is the deterministic comparison: `call_extraction_service.py:157`
stores `result.get("missing_fields", [])` — whatever the model said.

---

## 3. The required-fields precedent — read as a body, not a signature

```python
# nl_creation/types.py
@property
def required_fields(self) -> list[str]:
    return [e.field_key for e in self.field_extractors if e.required]

# nl_creation/extractor.py:256
def _missing_required(config, extractions) -> list[str]:
    extracted_keys = {e.field_key for e in extractions}
    return [fk for fk in config.required_fields if fk not in extracted_keys]
```

That is the whole mechanism. Consequences, stated plainly:

| question | answer |
|---|---|
| Can it express "required only if another field has a given value"? | **No.** `required` is a static bool on the extractor; nothing sees sibling values |
| Can it read product-catalog data? | **No.** `_missing_required` takes only the config and the extractions; no db session, no product id |
| Can it express "answered with none" as distinct from "not mentioned"? | **No.** The test is key-presence in a set. Whether a "none" answer registers depends on whether the producer emits a `FieldExtraction` for it — a producer-side accident, not a modelled state |
| Is there a third state for "depends on an answer not given yet"? | **No.** The return is one flat list of keys |

So the precedent gives the **shape** — a declared set, a deterministic diff,
computed server-side — and none of the three things the ruling needs. It is worth
copying as a pattern and cannot be extended in place.

---

## 4. Tenant configuration patterns

Candidates only; not chosen.

| pattern | where | cascade | granularity |
|---|---|---|---|
| Registry + tenant override rows | `ConfigurableItemRegistry` + `TenantItemConfig` | platform default → tenant, via `is_enabled` | per item key; **no product FK** |
| Enrollment JSON blob | `WilbertProgramEnrollment.personalization_config` | platform master merged with tenant override at read time | per option key, **and per product via `applicable_product_ids`** |
| Standing-set cascade | `StandingSetConfig` | code role template → tenant → user | per entry, three tiers |
| Three-scope visual-editor cascade | `platform_themes`, `component_configurations`, `focus_compositions` | platform_default → vertical_default → tenant_override, resolved at READ time, write-side versioned | per key, with a `vertical` tier the others lack |
| Settings JSON on the company | `Company.settings_json` (text, not jsonb) | single tier | free-form; already used for `personalization_display_labels` |

Two observations worth carrying rather than conclusions:

- Only **one** of these expresses per-product scoping today, and it is the
  enrollment JSON — the same row that is empty in production.
- Only the visual-editor cascade has a **vertical** tier and write-side
  versioning. If capture fields ever need to differ by vertical, the other four
  cannot say so.

**Existing settings surfaces.** Personalization options have full CRUD already:
`routes/programs.py:264` update, `:291` create-custom, `:317` delete,
`:363` applicable-options-for-product. Legacy has three settings pages
(`pages/legacy/settings/{general,delivery,email}.tsx`). **No settings page exists
for call handling, order intake or capture fields** — enumerated by directory
walk, not by name guess.

---

## 5. The Legacy delivery step

**The Dropbox step is not hardwired into a workflow, and the seam is one function.**

`routes/legacy_studio.py:236` `approve_legacy` does the status write, then:

```python
try:
    from app.services.legacy_delivery import run_auto_delivery
    run_auto_delivery(db, legacy_id, current_user.company_id)
except Exception:
    pass  # Non-blocking — delivery failures don't block approval
```

⚠️ **That is a whole-body swallower on the delivery path** — the exact class this
arc spent several commits removing from scheduled jobs. A delivery that fails
leaves the proof marked approved with no record that nothing was delivered.
`run_auto_delivery` itself also logs-and-continues per provider. Surfaced, not
fixed.

**Inside the seam**, `legacy_delivery.py:255` fetches the TIF from R2, builds the
filename from `settings.tif_filename_template`, then runs an **if-chain**, not a
registry:

```
if settings.dropbox_connected and settings.dropbox_auto_save:  → dropbox_upload_tif
if settings.gdrive_connected  and settings.gdrive_auto_save:   → gdrive_upload_tif
```

So there are already **two** implementations behind one call site. A third is a
branch, not an architecture change — and the honest description is that the seam
exists and the plugin contract does not.

**Download-to-device is closer than "first implementation" suggests.**
`proof.tif_url` is already returned to the client at `routes/legacy_studio.py:92`
and `:172`. The object is in R2 and the URL is in the payload; what is missing is
a UI affordance, not a delivery step.

**Attachment versus link — already a modelled setting, already answered.**
`legacy_settings.print_shop_delivery` is `String(20)` defaulting to **`"link"`**,
with a radio UI at `pages/legacy/settings/delivery.tsx` offering:

| value | label | the UI's own copy |
|---|---|---|
| `link` *(default)* | Link | — |
| `attachment` | Email attachment | **"TIF attached directly (50-200MB)"** |
| `both` | Both | Link and attachment |

⚠️ **And no print-shop email is ever sent.** `legacy_email_settings` carries
`print_email_subject` (default `'Legacy Ready — {name}, needed by {deadline}'`)
and `print_email_body`; the only readers are the settings route at
`routes/legacy_email.py:67`. `legacy_email_service.py` defines
`send_proof_email` and **no print-shop equivalent** — enumerated across the
module's function list, not by grepping one name. The proof half sends and
attaches a flattened JPEG; the print half is configured and unwired.

**Size limits: none encoded anywhere.** `MAX_ATTACHMENT`, `max_attachment`,
`attachment_size`, `size_limit` are all 0 files. The only evidence about size is
the UI's own copy, 50–200MB. ⚠️ Whether the configured provider accepts an
attachment that large is **not established here** — it is a provider-documentation
question, not a repo question, and it should be answered before `attachment` or
`both` is offered as a working mode rather than a stored preference.

---

## Design options each finding leaves open — named, not chosen

**On availability (Q1).**
- (a) Seed the registry and per-tenant enrollment, backfill `personalization_tier`
  on products, and let the schema call `get_applicable_options_for_product`.
  Smallest code change; largest data change; needs a real product catalog for
  Sunnycrest, which production does not have.
- (b) Make availability a property of the product row (a JSONB of allowed option
  types) and drop the enrollment indirection. Fewer moving parts, loses the
  platform-default layer and the price overrides.
- (c) Leave tier-based availability platform-wide and add only a per-tenant
  *subtraction* list. Matches the worked example exactly — Sunnycrest subtracts
  nameplate on the Monticello — and is the smallest expressible change.
- ⚠️ Under every option, the empty-means-none failure has to be closed first, or
  the schema inherits a silent false negative.

**On the option vocabulary.**
- (d) Schema points at the canonical four, and the registry becomes a display
  layer. (e) Schema points at the registry keys, and the canonical four become a
  view. (f) Reconcile them into one space. Only (f) removes the mapping, and only
  (f) touches stored order data.

**On the schema mechanism (Q3).**
- (g) Copy the `nl_creation` shape and extend the field declaration with a
  predicate — `required_when: (field, value)` — evaluated server-side.
- (h) Make the declaration a three-valued function returning
  `answered | missing | unknown`, with `unknown` returned when a predicate's input
  is itself unanswered. This is the only option that expresses the third state the
  ruling asks for without special-casing it at the call site.
- (i) Store "none" as an explicit sentinel value rather than an absence, so the
  key-presence test keeps working unchanged.

**On tenant configuration (Q4).**
- (j) Registry + `TenantItemConfig`, adding a product-scope column.
- (k) Reuse the enrollment JSON, which already has product scope.
- (l) A new capture-field table on the three-scope visual-editor pattern, which is
  the only one that would let capture fields differ by vertical.

**On delivery (Q5).**
- (m) Turn the if-chain into a registry with `download`, `dropbox`, `drive` as
  three implementations. (n) Leave the if-chain and add a branch. (o) Ship
  download-to-device as a UI affordance over the existing `tif_url` and change no
  backend code at all.
- Independently: the swallowed exception on approve, and the unwired print-shop
  email, are both real and neither is a design choice.

---

## Method notes

- ⚠️ **A constructed name produced a false absence and was caught.** The first
  probe asked for `ringcentral_call_logs` and got a `ProgrammingError`, which
  would have read as "the table does not exist." Re-derived by pattern —
  `table_name ILIKE '%ringcentral%'` — the real table is **`ringcentral_call_log`**,
  singular. It exists and holds 0 rows. Two different facts that look identical in
  a report.
- ⚠️ **The zeros were too clean and were re-derived by a second method.** Nine
  empty tables in a row is a claim about the instrument. `information_schema.tables`
  separates "absent" from "present and empty" — all nine are present and empty,
  and the one genuinely absent name was the constructed one above.
  `personalization_tier` was checked three ways: distribution by tenant, a direct
  non-null count (0 of 33), and `information_schema.columns` to confirm the column
  exists at all.
- ⚠️ **A probe defect, recorded.** The first enrollment query used
  `jsonb_array_length` on `personalization_config`, which is `json` not `jsonb`,
  and whose `options` is an object keyed by option key rather than an array. Two
  wrong assumptions in one expression; the type error caught the first and reading
  the service caught the second.
- Every production read was one statement per connection, through an engine opened
  read-only. `SHOW transaction_read_only` returned `on` before any query ran.
- Name forms were enumerated before searching: 19 forms for personalization
  availability, 8 for attachment size limits, 5 for a tier column.
- **Not established here:** whether Sunnycrest has a real product catalog anywhere
  outside this database, and whether the configured email provider accepts a
  50–200MB attachment. Both are outside the repo.
