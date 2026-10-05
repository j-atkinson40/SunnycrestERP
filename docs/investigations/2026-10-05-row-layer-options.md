# The three options, against the two-layer leaning

**Report only. Nothing built. 2026-10-05.** Measured from
`docs/prototypes/2026-09-call-to-print.html` (1,072,184 / `56e1e24c…`).

## First, two corrections to my own previous report

**1. (d) is TWO fields, not three.** I listed `burial_date` as having no row. It
has one — composed:

```
screen 1   Cemetery    "Forest Lawn · Thu 11:30 AM"
screen 2   Burial      "Forest Lawn Cemetery" / "Thu, Sep 17 · 11:30 AM"
```

`"Thu, Sep 17"` appears 6 times. I counted a field as homeless because it had no
row *of its own*, which is the one-row-per-field assumption the finding was about,
applied to my own count. Only **`vault_size`** and **`grave_location`** are absent.

**2. The two screens compose DIFFERENTLY**, which I had not established:

| | screen 1 (capture) | screen 2 (summary) |
|---|---|---|
| rows | **9** | **6** + a subject header |
| deceased name | a row | subject **primary line** |
| dates | a row | subject **sub-line** |
| contact | a row | **secondary line** of `Funeral home` |
| cemetery | row labelled `Cemetery` | row labelled **`Burial`** |
| counts | `N captured` / `N needed` | `9 captured` / `0 missing` |

So the same facts are composed into different rows, with different labels, under
different count vocabulary, on the two screens. **Any option that assumes one row
set for both surfaces is already contradicted by the file.**

⚠️ And screen 2's count is **9**, which is screen 1's row count, not its own 6. The
counts are over the CAPTURE rows and travel with the capture, not over whatever
the surface renders.

---

## The four questions, answered by measurement

**(c) which are missing fields vs read from a record** — measured, and it splits:

| row | verdict | evidence |
|---|---|---|
| **Contact** | **read from a related record** | `customers.contact_name` exists. The earlier capture prototype sourced it from `CUSTOMER = {… contact:"Tom Harding" …}`. ⚠️ But the *caller* need not be the record's default contact, and the call knows who spoke — so this may be *captured, defaulting to the record*, which is a third category. |
| **Dates** | **missing capture field** | `sales_orders` has **no** dob/dod columns (only `deceased_name`). `fh_cases` has them — but that is the funeral home's record in a different tenant, so a manufacturer has nowhere to read from. It is spoken on the call and stored nowhere. |
| **Cemetery Equipment** | **missing capture field** | the catalog sells **5 `equipment` products**, and the template has no equipment field at all. Capture cannot ask for something the catalog sells. Its value becomes order *lines*, like `vault`. |

**(d) `vault_size` and `grave_location` — my read, and they differ:**

- **`vault_size` — probably the TEMPLATE is stale, not the design incomplete.**
  Since 2b-3, `template_id` is a **variant** id and variants *are* sizes —
  `BV-CON34`, `GL-34`, `GL-38` exist precisely as odd-size variants. Choosing the
  product determines the size, so a separate required `vault_size` is plausibly a
  pre-repoint remnant. The design showing `Vault / Product` → `"Wilbert Bronze"`
  with no size is then correct and the field is redundant. **Needs a ruling, not a
  row.**
- **`grave_location` — probably belongs to a surface this prototype does not
  cover.** Its label is "Grave section / lot / space"; the people who need it are
  the delivery crew, not the funeral home approving an order. This prototype is
  call→print across 8 screens and none is the driver's. ⚠️ I cannot verify that:
  the driver prototype is a separate artifact I cannot reach. So this is a
  hypothesis, not a measurement — and the honest version is *"absent from these
  screens does not establish absent from the design."*

⚠️ The general point, which is why (d) splits: **"a field with no row" has at least
three causes** — redundant field, wrong surface, genuine oversight — and they need
opposite fixes. Treating them as one bucket would have deleted a real requirement
or kept a dead one.

---

## The three options, each answering (a)–(d)

### (a) ONE LAYER — the template declares ordered display rows, each composed from zero or more fields

| | how |
|---|---|
| composition | native — a row lists several source fields |
| collapse | native — one row lists the three personalization fields |
| row with no field | a row may have **zero** fields and a literal/record source |
| field with no row | **unexpressible** — a field not named by any row is silently invisible, with nothing reporting it |

**Against it:** the two screens compose differently, so "the" row list cannot be
one list — this option needs a row set per surface anyway, at which point it *is*
option (b) with the layers merged. And it makes (d) undiagnosable: `vault_size`
would simply never appear and nothing would say so.

### (b) TWO LAYERS — fields (capturable) and rows (displayable), rows cite sources

Your leaning. Fields keep id/required/conditional; rows carry
id/label/order/group/sources, where a source is a field, several fields, or a path
into a related record.

| | how |
|---|---|
| composition | a row with several field sources |
| collapse | same mechanism, no special case |
| row with no field | a **record-path source** — exactly the `Contact` case |
| field with no row | **detectable**: fields minus rows' sources is computable, so `vault_size` and `grave_location` surface as a *reported set* rather than silence |

**For it:** it is the only option that makes (d) a *measurement*. It also lets the
two surfaces hold different row sets over one field set, which the file requires.
**Against it:** two things to keep in step, and a row-set-per-surface means
"template" now means three things.

### (c) PART 1 ONLY FOR THE 1:1 ROWS, composition deferred

| | how |
|---|---|
| composition | **not expressible** — `Service` degrades to location, `Burial`/`Cemetery` loses its time |
| collapse | **not expressible** — three personalization rows where the design has one |
| row with no field | **not expressible** |
| field with no row | moot; every field gets a row, so the display is 12 rows against the design's 9 and 6 |

**Against it:** it ships a display that visibly differs from the approved one, and
every later step replaces it. The only argument for it is speed, and the cost is
the shape-that-ships-then-gets-replaced this whole detour exists to avoid.

---

## What I would say if asked

**(b), and the decisive reason is (d) rather than composition.** All three express
the display somehow; only (b) makes "a captured field with nowhere to show it" a
computable set instead of silence. Given that (d) already turned out to contain a
probably-redundant field *and* a probably-wrong-surface field, a design that cannot
report that class will accumulate it.

The second reason is the two screens. One row list cannot serve both, measured —
so the layering is forced; (b) only names it.

⚠️ **One thing (b) as stated does not yet cover:** `Contact` may be
*captured-with-a-record-default* rather than either captured or read. If that
category is real, a source needs a precedence — *this field, else this record
path* — and that is worth deciding before the shape is fixed rather than after.

**Still not mine to rule:** whether `vault_size` is redundant, where
`grave_location` belongs, and whether `Dates` and `Cemetery Equipment` become
capture fields. Four product questions, and the shape should follow them rather
than the reverse.
