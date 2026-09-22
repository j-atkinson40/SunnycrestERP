# The ordering portal's personalization model

**2026-09-22.** Investigation only, read-only. The portal was read from
`~/Downloads/sunnycrest-orders-main.zip`, extracted to a scratchpad directory —
**not** into either repository. It is a GitHub source snapshot of `main` with no
`.git` directory, so it is a separate codebase from Bridgeable by construction,
not a subdirectory of it. 41 files, last modified 2026-03-13. Nothing in it was
modified, installed, built or run.

---

## 6. Against Bridgeable — the mapping, first, because it decides the re-key

> **The portal has THREE personalization fields. Bridgeable's canonical vocabulary
> has four and its registry vocabulary has five, and the portal maps cleanly onto
> NEITHER — but it maps almost perfectly onto Bridgeable's `PERSONALIZATION_TIERS`,
> because Bridgeable's tier names are the portal's vault names.**

| portal field (`lib/products.ts:9`) | label | Bridgeable canonical | Bridgeable registry |
|---|---|---|---|
| `legacy_print` | Legacy Series™ Print | `legacy_print` ✅ clean | `personalization.legacy_photo` ✅ clean |
| `nameplate_cover_emblem` | Nameplate & Cover Emblem | ⚠️ **splits into two** — `physical_nameplate` + `physical_emblem` | `personalization.emblems_nameplates` ✅ clean |
| `lifes_reflections` | Life's Reflections® Vinyl | `vinyl` ✅ clean | ⚠️ **no counterpart** |
| — | — | — | `personalization.standard_colors`, `.custom_paint`, `.specialty_finish` — no portal counterpart |

**Neither Bridgeable vocabulary is a superset.** The canonical four split what the
portal joins; the registry five join what the portal splits and add three the
portal has never heard of. ⚠️ **STOP as the dispatch defined it: the portal's
option set does not fit either Bridgeable vocabulary.**

### What neither Bridgeable vocabulary can express

1. **The two-valued nameplate/emblem field.** The portal asks one question with
   the answers *"Nameplate Only"* / *"Nameplate & Cover Emblem"*. The canonical
   four make these two independent booleans, which admits *emblem without
   nameplate* — a combination the portal cannot express and which may not be a
   real product.
2. **Legacy Series versus Legacy Custom Series as variants of one option**
   (question 3a, below).
3. **Per-vault option sets that are neither "all" nor "none."** Continental and
   Salute each carry a bespoke field list. Bridgeable's `applicable_product_ids`
   inverts this — it scopes an option to products, rather than giving a product
   its options — which is expressible but is the opposite direction of travel.

### ⚠️ The finding that matters more than the mapping

**Bridgeable's `PERSONALIZATION_TIERS` is a generalisation of this portal.** Its
four tier names are `wilbert_standard`, **`continental`**, **`salute`**,
`urn_vault` — and `continental` and `salute` are *vault names in the portal*, with
exactly the option sets the portal gives those two vaults:

| Bridgeable tier | Bridgeable's `available_types` | portal vault | portal's fields |
|---|---|---|---|
| `continental` | `physical_nameplate` | Continental® | `nameplate` |
| `salute` | `physical_nameplate`, `physical_emblem` | Salute® | `nameplate`, `cover_emblem` |
| `wilbert_standard` | all four | 10 premium/standard vaults | `wilbertPersonalizationFields` |
| `urn_vault` | all four, `uses_urn_prints` | 8 urn vaults | `wilbertPersonalizationFields` |

These are not two independent models that happen to agree. One was derived from
the other. That makes the re-key far cheaper than the vocabulary table suggests —
and it also means **the drift has already started**, which is the next section.

### ⚠️ The same catalog, transcribed twice, already diverged

Compared structurally — parsing each `prints: [...]` block rather than scraping
quoted strings, because a flat scrape counts category labels too:

| | distinct prints | categories |
|---|---|---|
| portal `legacySeriesPrints` | **51** | 4 |
| portal `urnLegacySeriesPrints` | **48** | 4 |
| Bridgeable `LEGACY_SERIES_PRINTS` | **64** | 4 |

**43 in both. 8 portal-only. 21 Bridgeable-only.** And the disagreements are
mostly not different prints — they are the *same* prints split or joined
differently:

| portal | Bridgeable |
|---|---|
| `Jewish` | `Jewish 1`, `Jewish 2` |
| `Sunrise`, `Sunset` | `Sunrise-Sunset`, `Sunrise-Sunset 2` |
| `Field and Barn` | `Green Field & Barn` |
| `Forever in God's Care — Cross`, `— Sunset` | `Forever in God's Care` |
| `Forever in Our Hearts — Cloud`, `— Sunset` | *(absent)* |
| *(absent)* | `Cross — Gold`, `— Silver`, `— White Horizontal` |

This is the two-copies problem you named, **already in progress, before anyone
decided to keep two copies.** Whichever way the relationship goes, one of these
lists has to stop being authoritative.

⚠️ **And Bridgeable's own prose disagrees with its own list.**
`personalization_config.py:4` says *"91 named Wilbert prints"*; the list holds
**64**. A count quoted beside the data it describes and not matching it.

---

## 1. The options

Three fields, defined once at `lib/products.ts:9` as
`wilbertPersonalizationFields`, plus two bespoke fields used only by the basic
tier. Enumerated from the definitions, not from UI labels:

| id | label | type | options | required |
|---|---|---|---|---|
| `legacy_print` | Legacy Series™ Print | select | `Legacy Series™ (standard)`, `Legacy Custom Series™ (custom artwork)` | false |
| `nameplate_cover_emblem` | Nameplate & Cover Emblem | select | `Nameplate Only`, `Nameplate & Cover Emblem` | false |
| `lifes_reflections` | Life's Reflections® Vinyl | select | Cross · Star of David · Praying Hands · Floral · Patriotic / American Flag · Masonic · Dove · Other (specify in notes) | false |
| `nameplate` | Nameplate | select | `No`, `Yes` | false |
| `cover_emblem` | Cover Emblem | select | `No`, `Yes` | false |

⚠️ **Every field is `required: false`.** The portal never requires a
personalization answer. Under the ruling that *"required" means must be ANSWERED,
not must be non-empty*, the portal has no equivalent concept — a field the user
skips is simply absent.

⚠️ **The eight Life's Reflections symbols are byte-identical to Bridgeable's
`VINYL_SYMBOLS`**, including the final `"Other (specify in notes)"`. That list was
already copied once.

---

## 2. Availability per vault — hardcoded, per vault, and it answers the example

Recorded as a property of each vault object in a **hardcoded TypeScript array**,
`lib/products.ts`. No database, no config file, no admin surface. Two fields do
the work: `hasPersonalization: boolean` and `personalizationFields: [...]`.

**All 16 burial vaults, enumerated:**

| tier | vault | personalization |
|---|---|---|
| Premium | The Wilbert Bronze®, Bronze Triune®, Copper Triune® | all three fields |
| Standard | Stainless Steel Triune®, Cameo Rose® Triune®, Veteran Triune®, White Tribute, Gray Tribute, White Venetian®, Venetian® | all three fields |
| Basic | **Continental®** | `nameplate` only |
| Basic | **Salute®** | `nameplate` + `cover_emblem` |
| Basic | **Monticello®** | ⚠️ **`hasPersonalization: false`** |
| Basic | Monarch®, Concrete Graveliner, Other | `hasPersonalization: false` |

**The worked example is confirmed from the portal's own model rather than from
Wilbert's marketing: the Monticello offers no personalization at Sunnycrest.**

**All 10 cremation/urn vaults:** seven carry all three fields; `Basic Gray /
Salute® Urn Vault` carries `nameplate` + `cover_emblem`; **`Monticello® Urn
Vault`** and `Universal® Urn Vault` are `hasPersonalization: false`.

---

## 3. The three specific questions

**(a) Legacy Series and Legacy Custom Series are ONE option with two values** —
`legacy_print` with `options: ["Legacy Series™ (standard)", "Legacy Custom
Series™ (custom artwork)"]`. Not two options. Bridgeable has a single
`legacy_print` type and a separate 64-entry print catalog, with no
standard-versus-custom axis; `program_legacy_prints` distinguishes
Wilbert-catalog rows from tenant-custom rows by `wilbert_catalog_key`, which is
adjacent but is about *who supplied the artwork*, not about which product the
family bought.

**(b) Yes — and the correspondence is explicit in the label.** The field is
`lifes_reflections`, labelled **"Life's Reflections® Vinyl"**. Bridgeable's
canonical type is `vinyl`, and its own comment says the Wilbert tenant displays
"Life's Reflections" while Sunnycrest displays "Vinyl". The portal, which *is*
Sunnycrest, displays "Life's Reflections® Vinyl" — so ⚠️ **Bridgeable's recorded
assumption about which tenant uses which label is contradicted by the tenant's own
portal.**

**(c) Memorialization Plus does not appear.** Eight forms searched —
`Memorialization`, `memorialization`, `Memorialisation`, `capsule`, `Capsule`,
`MemPlus`, `mem_plus`, `keepsake` — zero files each, across the whole snapshot.

---

## 4. Per-licensee or single-tenant — single, conclusively

| term | files |
|---|---|
| `tenant` | 0 |
| `licensee` | 0 |
| `company` | 0 |
| `organization` | 0 |
| `dealer` | 0 |
| `workspace` | 0 |
| *(positive control)* `vault` | **14** |

⚠️ **The first run of this check returned zeros that meant nothing.** The command
carried `--include=*.ts` flags; zsh failed to glob them, aborted the command, and
`wc -l` counted an empty pipe as `0`. Six false zeros that looked exactly like six
real ones. Re-run without the flags and with a positive control — `vault` must
match, and does, in 14 files — the zeros are real.

**The portal is single-tenant by construction.** It is Sunnycrest's portal, the
catalog is a literal in source, and the only multi-party concept is a *Funeral
Homes* table — the portal's customers, not its operators. A Monticello offering a
nameplate at another licensee cannot be expressed here; it would be a different
deployment with a different `products.ts`.

**This answers the relationship question.** The portal cannot be a system of
record for a multi-tenant platform. It is a **source to copy from once**, with the
copy re-runnable, not a system to stay in sync with.

---

## 5. Is it live?

**The portal writes real orders to Airtable.** `lib/airtable.ts` opens a base from
`AIRTABLE_BASE_ID` and exposes three tables — `Funeral Homes`, `Orders`,
`Cremation Orders` — with `submitOrder` and `submitCremationOrder` both ending in
`table().create(fields)`. Funeral homes authenticate against the `Funeral Homes`
table by email (`getFuneralHomeByEmail`), and `RecentOrders` reads back per
funeral home.

**Row counts were not read.** They live in Airtable, which this dispatch does not
authorise and which needs `AIRTABLE_API_KEY`. What would be needed: read access to
that base — and per the credential rule, that is James reading it, not a key
passed through a session.

### ⚠️ The shared-system STOP does NOT fire

Checked in the direction that matters: Bridgeable's only references to Airtable
are **two lines of UI copy** on `pages/onboarding/historical-order-import.tsx`,
inviting a CSV export *from* Airtable. Bridgeable has no Airtable client, no key,
no writes. The portal writes to Airtable; Bridgeable writes to Postgres, R2 and
Dropbox. **No overlap** — and Bridgeable already has an import surface pointed at
exactly this situation.

### One hygiene finding, settled without reading a secret

`.env.local.save` is **tracked** in the portal repo. `.gitignore` covers `.env`,
`.env.local` and `.env.*.local` under a comment reading *"NEVER commit these"* —
and does not cover the `.save` variant, so the file slipped past a rule that was
written carefully.

It is **not** a leaked credential: its SHA-256 is identical to
`.env.local.example`, so it is a copy of the placeholder file. ⚠️ That was
established **by comparing hashes, not by opening either file**, so no value
transited this session. The gitignore gap is still worth closing, because the next
`.save` may not be a copy.

---

## What this leaves open — named, not chosen

- **The re-key.** Three ways: adopt the portal's three-field shape as canonical;
  keep Bridgeable's canonical four and split `nameplate_cover_emblem` on import;
  or keep the registry five and drop `vinyl`'s homelessness by adding it. Only the
  second preserves already-stored order data, and there is none in production to
  preserve.
- **Whose print list wins**, and what happens to the 29 that disagree. The splits
  (`Jewish` → `Jewish 1`/`Jewish 2`) are the hard cases, because a merge loses
  information and a split invents it.
- **Direction of scoping.** The portal gives a product its options;
  Bridgeable scopes an option to products. Both express the same facts; the import
  has to invert one of them, and the inversion is where a mistake would be silent.
- **Whether `required: false` everywhere is a fact about the products or about
  the portal.** If a nameplate is genuinely never required, the capture schema's
  conditional-required machinery has nothing to do on this vertical — which would
  be worth knowing before building it.

## Method notes

- The portal repo was never modified: extracted to a scratchpad, read only, no
  install, build, test or commit. It has no `.git`, so it is a snapshot rather
  than a clone.
- ⚠️ A false-zero from a failed command was caught and is recorded above rather
  than quietly re-run. Every later absence claim carries a positive control.
- ⚠️ A first pass at the print counts (55/52/67) used a flat quoted-string scrape
  that also counted category labels. Re-derived structurally: 51/48/64. The first
  numbers were wrong in all three places and would have made the overlap look
  better than it is.
- Name forms were enumerated before searching: 8 for Memorialization Plus, 7 for
  tenancy, 3 for Airtable.
- **Not established:** how many orders the portal has taken, and whether the
  `products.ts` catalog matches what Sunnycrest currently sells. Both need
  Airtable access or James.
