# The Sunnycrest ordering portal — what James's flow encodes

**2026-10-07.** Read-only investigation. Nothing in the portal was modified,
installed, built or run.

## Provenance

A **separate codebase**, not in the Bridgeable repo and not a subdirectory of it.

| | |
|---|---|
| source | `/Users/Jimmy1/Downloads/sunnycrest-orders-main.zip` |
| md5 | `694e1947fefceae8ffd9a7e35d6fc5a1` |
| bytes | 140,935 |
| files | 41, every mtime 2026-03-13 (GitHub snapshot stamps the last commit) |
| package | `sunnycrest-orders` 0.1.0 — Next.js 14.2.5, next-auth 4, airtable 0.12, @vercel/blob |
| deploy target | Vercel → `https://orders.sunnycrest.com` (`SETUP.md:115,120`) |

Extracted to a session scratchpad, never into either repository. ⚠️ `.env.local.save`
is present in the archive and was NOT read (CLAUDE.md §7 — credentials do not transit
a session).

⚠️ Whether `orders.sunnycrest.com` is serving today was NOT determined — that needs a
network request this investigation had no authorization to make.

Bridgeable references the portal in exactly one place — the earlier investigation
`docs/investigations/2026-09-22-ordering-portal-personalization.md`. No code
reference, no import, no reachable surface.

## Storage

**Airtable, not Postgres.** Tables "Funeral Homes" / "Orders" / "Cremation Orders"
(`lib/airtable.ts:10,13,16`). Auth is a next-auth session; the funeral home is
identified by session email and never asked (`app/api/orders/route.ts:10-14,49-50`).
Legacy images go to Vercel Blob with `access: "public"` (`route.ts:25`).

⚠️ **Personalization and equipment are persisted as flattened STRINGS**
(`lib/airtable.ts:99-100`, built at `route.ts:59-64`). The question structure is lost
at write time: `personalizationDetails` is newline-joined `"key: value"` lines or
`"None"`, `equipmentList` is comma-joined item names or `"None"`, and `legacyDates` is
`"{dob} - {dod}"`.

## The flow, in order

Steps are dynamic (`components/OrderFlow.tsx:57-59`) — the personalization step
appears only when the chosen vault has personalization.

**Step 0 — Vault Selection.** `vaultId` required (`L121`). `socialServicesOrder`
yes/no required **only** when `vaultId == "concrete-graveliner"` (`L117,L122`).

**Step 1 — Personalization** (only if `hasPersonalization`, `L54`).

**Step 2 — Equipment.** `equipmentIds: string[]`, no validation, wholly optional
(`L142`).

**Step 3 — Service Details** (`components/ServiceDetailsForm.tsx`):

| # | field | input | required |
|---|---|---|---|
| 1 | `deceasedName` | text | yes (`L47`) |
| 2 | `cemetery` | text | yes (`L66`) |
| 3 | `cemeteryCity` | text | yes (`L85`) |
| 4 | `serviceDate` | **date** (`L99`) | yes (`L103`) |
| 5 | `serviceTime` | **time** (`L117`) | yes (`L121`) |
| 6 | `serviceLocation` | select: Church / Funeral Home / Graveside / Other (`L141-144`) | yes (`L138`) |
| 7 | `gravesideEta` | text, "e.g. 10:30 AM" (`L155-157`) | no |
| 8 | `notes` | textarea | no |

**Step 4 — Review & Submit.**

⚠️ Choosing "Other" for service location gives **nowhere to name the place** — no
other-text field exists anywhere in the portal (verified with a positive control).

## Personalization

**The rule store is a code constant** — `wilbertPersonalizationFields` at
`lib/products.ts:9`, assigned per vault via `personalizationFields:`. Not a table, not
config.

**27 vaults: 17 get all three questions, 3 bespoke, 7 none.**

The three shared questions (`products.ts:11-45`), all `required: false`:

- `legacy_print` — "Legacy Series™ (standard)" | "Legacy Custom Series™ (custom artwork)"
- `nameplate_cover_emblem` — "Nameplate Only" | "Nameplate & Cover Emblem" — ⚠️ only two; **no emblem-only**
- `lifes_reflections` — Cross, Star of David, Praying Hands, Floral, Patriotic / American Flag, Masonic, Dove, Other (specify in notes)

The bespoke three:

| vault | fields | expresses |
|---|---|---|
| `continental` (`L145`) | `nameplate` No/Yes | nameplate only, **no emblem** |
| `salute` (`L162`) | `nameplate` + `cover_emblem`, independent No/Yes | **emblem without nameplate** |
| `salute-urn` (`L345`) | same as salute | same |

No personalization (`hasPersonalization: false`): `monticello`, `monarch`,
`concrete-graveliner`, `other`, `monticello-urn`, `universal-urn`, `cremation-other`.

**Extra information.** Only `legacy_print` carries any: `legacy_print_design` (one of
51 burial / 48 urn prints, separate selectors), `legacy_full_name`, `legacy_dob`,
`legacy_dod`, plus image upload. None required.

⚠️ **`legacy_dob` and `legacy_dod` are `type="text"`** (`L375,L396`), labelled *"Enter
the date exactly as you would like it to appear on the print"* (`L371,L392`). **No
format is enforced — they are display strings, not dates.** The *service* date, by
contrast, is a real date input.

Typing `legacy_full_name` back-fills `deceasedName` when it is empty or still equal
(`L357-362`).

⚠️ **The three questions are mutually exclusive** (`L80-89`): setting any one clears
the other two, and switching away from `legacy_print` wipes all four sub-fields.

⚠️ **All fields are `required: false`, so the step-1 gate is vacuous** —
`requiredFields` at `L126-127` is always empty, so `canAdvanceFromStep(1)` always
returns true. The machinery exists and nothing uses it.

**Pricing: none.** No `price`/`cost`/`total` identifier exists in `components`, `lib`,
`app` or `types`; the Airtable write has no price field.

## Equipment — four items, not four packages

`products.ts:226-249`: `lowering-device`, `tent-standard`, `grass-mats`, `chairs-10` —
a multi-select of individual items.

⚠️ **The four package names appear in ZERO portal files** (control: "Lowering Device"
found in 1 file) and in 33/19/16/13 Bridgeable files. The packages are a **Bridgeable**
concept — priced catalog products at `sunnycrest_product_seeder.py:222-258`, and there
are **six**, not four:

| product | price | price without our vault | flag |
|---|---|---|---|
| Full Equipment | $300.00 | $600.00 | `is_lowering_device` |
| Tent Only | $225.00 | $557.00 | — |
| Lowering Device & Grass | $185.00 | $487.00 | `is_lowering_device` |
| Lowering Device Only | $140.00 | $487.00 | `is_lowering_device` |
| Vault Placer | $0.00 | — | `is_placer` |
| Extra Chairs (over 8) | $5.00 | $8.00 | — |

**The packages declare no contents**, so portal-items→packages is **inferred**:
Lowering Device Only ← `lowering-device`; Lowering Device & Grass ← `lowering-device` +
`grass-mats`; Tent Only ← `tent-standard`; Full Equipment ← all four.

⚠️ Chair counts disagree three ways: the id says `chairs-10`, its description says
"Set of 4 folding chairs" (`L245-247`), and Bridgeable sells "Extra Chairs (over 8)".

## Legacy print lists — measured, not inherited

| comparison | on both | portal-only | Bridgeable-only |
|---|---|---|---|
| portal **burial** (51) vs Bridgeable (64) | 43 | 8 | 21 |
| portal **urn** (48) vs Bridgeable (64) | 42 | 6 | 22 |
| portal **union** (64 distinct) vs Bridgeable (64) | 50 | 14 | 14 |

⚠️ The widely-quoted **43 / 8 / 21 is the burial list alone.** The portal's burial and
urn lists are NOT identical and use different names for the same print — `Jewish` vs
`Jewish 1`/`Jewish 2`, `Crucifix — Bible` vs `Crucifix on Bible`, `Field and Barn` vs
`Green Field & Barn`, `Tropical` vs `Tropical Island`, `American Flag` vs `U.S. Flag`,
`Motorcycle 1` vs `Motorcycle`, `Sunrise`+`Sunset` vs `Sunrise-Sunset 1`+`2`,
`Farm Field with Tractor` vs `Farm Field & Tractor`. The portal contains two
inconsistent transcriptions of one poster.

## Could the portal's rules populate `personalization_config.availability`?

**Maps cleanly:** the three question ids are identical strings for the 17 shared-field
vaults; the 7 no-personalization vaults map exactly onto NOT_OFFERED (write `[]`, which
`availability.py:95-96` reads as a deliberate refusal); the vinyl answers are already
derived from the same eight strings (`questions.py:65-76`).

**Does not map:**

- ⚠️ **The `product_id` key.** `availability` keys on a Bridgeable product id; the
  portal keys on slugs like `wilbert-bronze`. **No stored mapping column exists.** The
  only mapping artifact is a spreadsheet column for a human to fill, and that sheet
  itself says *"Availability cannot be imported for these"* for the ambiguous
  colour rows (`build_catalog_review_sheet.py:235-236,239-241`).
- `continental` / `salute` / `salute-urn` use `nameplate` and `cover_emblem`, which are
  not question ids.
- `legacy_print` answer labels need a translation table that exists nowhere — unlike
  vinyl, this one is not derived.
- Print selection has no slot: `availability` is answer-level, so which of the 51/64
  prints is permitted cannot be expressed.
