# Capture templates: the two-layer shape

**Specification. No code. 2026-10-05.** Ruled shape (b) with both amendments. The
four template changes land *after* this is agreed, not alongside it.

---

## ⚠️ First: one ruling's precondition fails, so that change is NOT specified below

The dispatch required, before removing `vault_size`: *"confirm the resolver can
take a size in the vault phrase before removing it — if it cannot, that is the real
gap and report it instead of removing."*

**It cannot, and not because it mishandles sizes. There is no resolver.**

| measured | result |
|---|---|
| any vault-name → variant/product resolver in `app/` | **none** |
| `platform_product_aliases` — the substrate for one | **exists**, right columns (`variant_template_id`, `alias_text`, `alias_text_normalized`, `source`, `is_confirmed`), **5 rows** |
| readers of that table outside `app/models/` | **zero** — references are 1 model, 1 `__init__`, and 4 migrations (r189 created it, r190/r191/r194 touched it) |

So the table is **seeded and unread** — a fifth instance of the
complete-machinery-behind-an-unprovisioned-entrance shape, this time with rows
present and nothing consuming them.

**The ruling's premise is nevertheless correct.** Size *is* a variant
discriminator where it varies — three families differ only by size:

```
continental          BV-CON, BV-CON34
graveliner           GL-34, GL-38  (of 5)
loved-and-cherished  LC-19, LC-24, LC-31
```

and six variants carry the size in the display name (`Continental 34"`,
`Graveliner 34"/38"`, `Loved & Cherished 19"/24"/31"`). The other families differ
by material, colour or form, not size.

**So `vault_size` is genuinely redundant — and removing it today would leave the
size neither captured nor recoverable**, because nothing can turn "Continental, 34
inch" into `BV-CON34`. The honest sequence is: build the resolver on the alias
table, *then* remove the field. Reported rather than removed, as instructed.

The other three changes are unaffected and specified in §5.

---

## 1. The two layers

**A FIELD is what can be captured.** One fact, one answer.

```
field:
  id          str          stable, referenced by rows and by the extraction adapter
  label       str          fallback only — rows carry their own labels
  required    bool         "must be ANSWERED", never "must be non-empty"
  switchable  bool         may a tenant turn it off (false only where structurally required)
  condition   <see Piece 4> absent = unconditional
```

Unchanged from `FieldDefinition` except that `label` demotes to a fallback and
`question_id` generalises to `condition` when Piece 4 lands.

**A ROW is what is shown, on one surface.**

```
row:
  id          str                    unique within its surface
  label       str                    the visible label; may differ per surface
  order       int                    position within group
  group       str | null             section heading, or null for ungrouped
  sources     [source, ...]          ORDERED. First yielding a value wins.
  secondary   [source, ...] | null   the sub-line, same rules
  edit_target field_id | null        which field this row's edit affordance opens
```

**A SURFACE is a named row set.**

```
surface:
  id     str                 "capture" | "summary" | "driver" | …
  rows   [row, ...]
  subject {primary: [source,...], secondary: [source,...]} | null
```

`subject` exists because the summary's decedent header **is not a grid row** —
measured: `John Smith` / `March 14, 1948 — September 14, 2026` sit above the rows.

---

## 2. Sources — the one thing that must be right

```
source = field_source | composed_source | record_source | literal_source
```

| kind | shape | example |
|---|---|---|
| field | `{field: "cemetery"}` | `Cemetery` → `"Forest Lawn"` |
| composed | `{compose: [src, ...], join: " · "}` | `Burial` → `"Forest Lawn · Thu 11:30 AM"` |
| record | `{record: "customer", path: "contact_name"}` | `Contact` → `"Tom Harding"` |
| literal | `{literal: "Full setup"}` | a fixed caption |

**Amendment 1 — `sources` is ordered, first match wins.** Costs nothing when a row
has one source, and expresses the case that forced it:

```
Contact.sources = [ {field: "contact_name"},
                    {record: "customer", path: "contact_name"} ]
```

The call knows who actually spoke; that beats the record's default. ⚠️ **"First
yielding a value" must mean `is_answered`, not truthiness** — the engine already
has exactly one definition of answered (`none` is an answer, blank is not), and a
second notion of "has a value" inside the row layer would be the drift this whole
shape exists to prevent.

---

## 3. Row state — derived, never stored

A row's state is a function of its sources' fields:

```
all sources' fields answered                     -> done
any required source field unanswered             -> not_mentioned  (default)
   … and the done-signal has been given          -> needed
every source field not_applicable                -> hidden (row absent)
any conditional source field NOT_CONFIGURED      -> ⚠️ see below
```

**Three rendered states, confirmed by measurement, not four:** default (grey mark,
italic `"Not mentioned yet"`), `done` (green check, solid value), `needed` (amber,
`animation: needpulse 1.9s`, literal `"Still needed"`). `unconfig` has **zero
hits** in the prototype.

⚠️ **`needed` is presentation, not membership — and that resolves the open
question.** `missing` is the server's answer: required, applicable, unanswered.
`needed` is that same set rendered amber once the user signals done. The client
derives *presentation* from the server's *membership*, so the server never needs
to see the done-signal. The prototype's per-field `flag:8` and
"flag all unfilled required rows" are indistinguishable in that demo — row 8 was
the only unfilled one — so the demo does not discriminate and canon decides:
the done-signal flips the whole unanswered-required set.

⚠️ **NOT_CONFIGURED needs a decision this spec deliberately leaves open.** The
server computes it and `CaptureState` discards it (measured). Under this shape the
natural home is a fourth *derivable* state, since rows already derive state from
field properties — but the approved design has no visual for it, so specifying one
would be inventing. **Recorded as open, not resolved.**

---

## 4. Orphan detection — amendment 2

```
orphans = all field ids  −  ∪ (every surface's rows' source field ids)
```

**Per-surface absence is not orphanhood.** `grave_location` has no row on capture
or summary and belongs on the driver's surface; under the union it is not an
orphan, which is exactly what amendment 2 buys.

⚠️ **This is the decisive property of shape (b) and it should be a test, not a
convention.** "A captured field with nowhere to show it" becomes a computable set,
so the three causes stay distinguishable — redundant field, surface not yet
declared, genuine oversight. A design that cannot report that class accumulates it;
(d) already held one of each.

**Consequence worth stating:** until the driver surface is declared,
`grave_location` *will* read as an orphan. That is correct behaviour and the
remedy is declaring the surface, not suppressing the report.

---

## 5. The measured surfaces

Both are measured from the prototype and **differ**, which is why one row set
cannot serve them.

### `capture` — 9 rows, counts worded "captured / needed"

`Funeral Home` · `Contact` · `Deceased Name` · `Dates` · `Service` · `Cemetery` ·
`Vault / Product` · `Personalization` · `Cemetery Equipment`

### `summary` — 6 rows + subject, counts worded "captured / missing"

subject: `John Smith` / `March 14, 1948 — September 14, 2026`
rows: `Funeral home` (secondary `Tom Harding`) · `Vault` · `Service` (secondary
`Thu, Sep 17 · 10:00 AM`) · **`Burial`** (secondary `Thu, Sep 17 · 11:30 AM`) ·
`Personalization` (secondary `American Flag`) · `Cemetery equipment` (secondary
`Lowering device, tent, chairs`) — each with an `edit` affordance.

Three differences that any single-row-set design would have had to fudge:
`Cemetery` is relabelled **`Burial`**; `Contact` demotes from a row to a
**secondary line**; `Deceased Name` and `Dates` leave the grid for the **subject**.

⚠️ And the summary's count reads **9**, which is the capture row count, not its own
6 — so counts belong to the capture, not to the surface rendering them.

### Keying — resolved on the server, per the dispatch

Rows cite **template field ids**. The adapter that maps extraction payload keys to
field ids already exists server-side (`_captured_from_result`) and already warns
that three of eight names differ and a mismatch fails silently. **Direction: the
extraction adapter normalises into field ids; rows never see extraction names, and
the client never joins.** Chosen because field ids are the stable vocabulary — the
extraction payload's names are one source's accident, and a second source (portal,
email) would otherwise need its own row vocabulary.

---

## 6. The three template changes that are unblocked

Specified, not applied.

| change | shape |
|---|---|
| `grave_location` | **keep**, unchanged. Not an orphan once a `driver` surface is declared. |
| `date_of_birth`, `date_of_death` | **add**, two fields, composed into one `Dates` row (`join: " — "`). ⚠️ Record: these become *required when a Legacy print is chosen* — a second-shape conditional, Piece 4's business, not now. Capture unconditionally until then. |
| `cemetery_equipment` | **add**, a **product reference** resolving to a catalog `equipment` product (5 exist). ⚠️ Record explicitly: its **destination** waits on the graveside-services model, which is deliberately unbuilt — so this is a *known* gap, not a silent one. |

`vault_size` is **not** in this table. See the top of this document.

---

## 7. What this spec does not decide

- the NOT_CONFIGURED visual (§3)
- whether `summary`'s `edit` targets a field or opens the row's whole group
- the notes box and footer hint — in the prototype, not yet assigned to template or surface
- Piece 4's condition shape, which both the Legacy-print link and
  `service_location_other` depend on
