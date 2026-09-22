# Dry-runs for review: the seeder, DEMO2, and a mapping that STOPs

**2026-09-22, 15:57–16:05 UTC.** Read-only throughout. **Nothing applied.**
Part 3's mapping hits a listed STOP, so it is reported rather than authored.

---

## 1.1 The idempotency key — no collision, and the feared mechanism cannot occur

`_product_exists(db, company_id, name)` matches on **exact `Product.name`
equality**, scoped to the company. And the loop **skips** — it never updates.

⚠️ **So a name collision could not have given a demo product a real price.** The
worse-than-expected outcome was available though: a collision would have caused
the seeder to *skip creating the real vault*, leaving only the demo row under
that name. That is the hazard worth naming, and it does not occur.

**Measured by a second method** — running the seeder's own predicate against
production for all 55 names rather than diffing two lists I built:

| | |
|---|---|
| seeder names that already exist on Sunnycrest | **0 of 55** |
| control: the predicate returns true for an existing name | `Continental Burial Vault` → **True** |

The four existing rows are `Monticello Burial Vault`, `Continental Burial
Vault`, `Urn Vault - Standard`, `Graveside Setup Service`. None equals a seeder
name. **No STOP.**

⚠️ **But after a run, production holds both `Monticello` (real) and `Monticello
Burial Vault` (demo), live, under names a human would read as the same vault.**
That is precisely why 1.2 and Part 2 matter.

## 1.2 The seeder's list against the current one

**In the seeder, not on the list:**

| | |
|---|---|
| burial | **Tribute**, **Pine Box**, Graveliner (SS), **Continental 34"**, **Graveliner 34"**, **Graveliner 38"** |
| urn | Salute Urn Vault, Cream & Gold Urn Vault, White & Silver Urn Vault |
| other | 9 P-series urns, 6 equipment items, 6 fees — outside the list's scope |

**On the list, not in the seeder:**

| | |
|---|---|
| bought-in | **Monticello 34", Large 34", Large 36", Large 40", Youth MT, Youth GL** |
| urn | **Universal (P400WS)**, **Basic Gray (P410)** |

⚠️ **THE BOUGHT-IN SET IS ENTIRELY DIFFERENT, NOT MERELY RENAMED.** The seeder
offers `Continental 34"`, `Graveliner 34"`, `Graveliner 38"`; the list names six
sizes none of which appear. That is not a naming drift — it is a different set of
products, and seeding it would put vaults on a live catalog that may no longer be
sold.

**Same product, different name** — the mapping cannot use names:

| seeder | current list |
|---|---|
| `SST Triune` | Stainless Steel Triune |
| `Veteran Triune` | Veteran |
| `Graveliner` | Grave Liner |
| `SST Triune Urn Vault` | Stainless Steel Triune (urn) |

## 1.3 Prices — the part only James can check

The seeder would **create 55, update 0, delete 0**. Every price it would write:

| product | price | wilbert_sku |
|---|---|---|
| Wilbert Bronze | 13452.00 | BV-WBR |
| Bronze Triune | 3864.00 | BV-BTR |
| Copper Triune | 3457.00 | BV-CTR |
| SST Triune | 2850.00 | BV-STR |
| Cameo Rose | 2850.00 | BV-CR |
| Veteran Triune | 2850.00 | BV-VTR |
| Tribute | 2570.00 | BV-TRB |
| Venetian | 1934.00 | BV-VEN |
| Continental | 1607.00 | BV-CON |
| Salute | 1475.00 | BV-SAL |
| Monticello | 1405.00 | BV-MON |
| Monarch | 1176.00 | BV-MCH |
| Graveliner | 996.00 | BV-GL |
| Graveliner (SS) | 880.00 | BV-GLSS |
| Continental 34" | 2179.00 | BV-CON34 |
| Graveliner 34" | 1492.00 | BV-GL34 |
| Graveliner 38" | 2060.00 | BV-GL38 |
| **Pine Box** | **none** | BV-PB |
| Loved & Cherished 19" / 24" / 31" | 239 / 374 / 452 | BV-LC19/24/31 |
| Bronze / Copper / SST Triune Urn Vault | 855 / 835 / 822 | UV-BTR/CTR/STR |
| Cameo Rose / Veteran Triune Urn Vault | 822 / 822 | UV-CR / UV-VTR |
| Venetian / Monticello / Salute / Graveliner Urn Vault | 616 / 493 / 436 / 284 | UV-VEN/MON/SAL/GL |
| Cream & Gold / White & Silver Urn Vault | 510 / 510 | UV-CG / UV-WS |
| P445 / P440 / P440A / P440B / P363 / P600 | 151 / 142 / 142 / 142 / 212 / 462 | — |
| P300 / P300WS / P300P | 124 / 110 / 113 | — |
| P310 / P310WS / P310P | 135 / 111 / 118 | — |
| Full Equipment · Lowering Device & Grass · Lowering Device Only | 300 / 185 / 140 | — |
| Vault Placer · Tent Only · Extra Chairs (over 8) | **0.00** / 225 / 5 | — |
| Sunday & Holiday · Saturday Spring Burial | 550 / 200 | — |
| Late Arrival per ½hr after 4pm · Legacy Rush Fee · Late Notice | 75 / 100 / 250 | — |

⚠️ Two worth a second look regardless of age: **Pine Box has no price at all**,
and **Vault Placer is 0.00**.

⚠️ **"Made or bought in" is not encoded.** The extras carry `wilbert_sku`,
`sku`, `product_line` and pricing flags — there is no source or manufactured
field, so that column of the dispatch cannot be filled from the seeder. The
closest signal is `product_line`.

⚠️ **The seeder was NOT run on dev.** It targets `slug='sunnycrest'`, and the
development database's Sunnycrest rows are not production's. Running it there
would have proved the code executes while telling us nothing about what it
creates here, and it would have written 55 products to dev for no gain. The
dry-run above is read from the source and checked against production's actual
rows instead.

---

## 2. DEMO2 — the dry-run

| sku | name | is_active now | after |
|---|---|---|---|
| DEMO2-P001 | Monticello Burial Vault | true | **false** |
| DEMO2-P002 | Continental Burial Vault | true | **false** |
| DEMO2-P003 | Urn Vault - Standard | true | **false** |
| DEMO2-P004 | Graveside Setup Service | true | **false** |

Reversible; the undo is the same four rows back to `true`. **Not applied.**

⚠️ The behavioural confirmation the dispatch asks for — calling
`ImportAliasService.match_products` and `GET /products/` after a local apply —
is **not done**, because the local database's Sunnycrest is not production's and
a local apply would prove the filter works there, not here. What is established
by reading is that both paths filter (`match_products` on
`Product.is_active == True`, the endpoint on `include_inactive=Query(False)`);
the call-it-and-see step belongs with the real apply.

---

## 3. ⚠️ STOP — the mapping resolves ambiguously, exactly as warned

**The stable key exists**: the seeder sets **`wilbert_sku`** (`BV-MON`,
`UV-SAL`, …) — 32 of 55 products, all vaults among them — deterministically and
independently of display name.

⚠️ **And it excludes the demo products structurally rather than by filter**: all
four DEMO2 rows have `wilbert_sku = NULL`, so a mapping keyed on `wilbert_sku`
**cannot express** a demo product. That is stronger than an `is_active` filter,
which can be forgotten.

But authoring the mapping hits the STOP. Of 27 portal vaults:

| portal id(s) | seeder product | problem |
|---|---|---|
| `white-tribute` **and** `gray-tribute` | `Tribute` (BV-TRB) | **two vaults → one product** |
| `white-venetian` **and** `venetian` | `Venetian` (BV-VEN) | **two vaults → one product** |
| `white-venetian-urn` **and** `venetian-urn` | `Venetian Urn Vault` (UV-VEN) | **two vaults → one product** |
| `universal-urn` | `Cream & Gold Urn Vault` (UV-CG) **or** `White & Silver Urn Vault` (UV-WS) | **one vault → two candidates** |

The first three are the hazard named in the dispatch, confirmed. The fourth is
its mirror and was not anticipated: `universal-urn` has two equally plausible
targets, both `product_line: Universal`, and the current list calls the product
`Universal (P400WS)` — a fifth name for the same thing.

**Seventeen vaults map cleanly**; `other` and `cremation-other` map to nothing by
design; four are ambiguous. Authoring the ambiguous four would be guessing which
vault a nameplate is permitted on, which is the failure the mapping exists to
prevent.

---

## 4. Not produced

Part 4's dry-run points at the Salute row Part 1 would create, and Part 1 is
unapplied. It also needs an answer the repo has not yet been asked for — whether
a funeral-home case can hold a manufacturer's `product_id` or only a name — which
is worth establishing once the catalog question is settled rather than twice.

---

## What is needed

1. **The bought-in set**: the seeder's three sizes or the list's six?
2. **The prices**, and specifically Pine Box (none) and Vault Placer (0.00).
3. **Tribute and Venetian**: one product each, or two (white/gray, white/plain)?
4. **`universal-urn`**: Cream & Gold, White & Silver, or a product that does not
   exist yet under the name `Universal (P400WS)`?
5. Whether `Tribute` and `Pine Box` are still sold at all.
