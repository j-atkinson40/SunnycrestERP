# The Opas overlay — investigation Parts 1, 2, 3, 5

**2026-10-06. READ-ONLY. No code written.** Part 4 is
`2026-10-06-product-pane-part4-data-inventory.md`, and ⚠️ **one of its verdicts is
corrected below.**

---

## PART 1 — sources into the repo

### Done

| File | size | md5 |
|---|---|---|
| `docs/prototypes/2026-10-01-opas-overlay.html` | 93177 | `a52a1e95153bd5c686b88d0acffc31e6` |
| `docs/prototypes/2026-10-03-product-pane.html` | 81464 | `d6ca8a967a615d53fbd24b5610290528` |

sha256 and the full caveat are in `docs/prototypes/PROVENANCE-2026-10-06.md`.

⚠️ **THE DIGESTS COVER THE ARTIFACT AS SERVED, NOT THE AUTHORED SOURCE.** 39,424 bytes of
each — 42% of the overlay, 48% of the product pane — is the `<!-- frame-runtime -->` block
claude.ai injects at serve time, byte-identical in both. A platform runtime update will
change the digest of an unchanged prototype. The digest proves which bytes a finding came
from; it is not a version identifier for the design.

⚠️ **I ALSO GOT THIS WRONG MID-TASK AND THE CORRECTION IS THE USEFUL PART.** I reported
that the artifacts were unreachable for copying, because WebFetch is documented as
converting to markdown and answering a prompt. It also saves the full response body to
disk, which I only noticed in its output. The claim was wrong for one step; the files are
real.

### Not done — blocked

`docs/specs/2026-10-06-notion-product-pane-spec.md` **is not in the repo.** Nothing to
verify against md5 `18b562e2cae09fe71efc3cc68fd35193` / size 2425. Part 4's section list
therefore still rests on dispatch text.

---

## PART 2 — what exists today, by measurement

| Canon surface | Verdict | Evidence |
|---|---|---|
| **Command bar** (Cmd/Ctrl+K) | **reachable and used** | `components/core/CommandBar.tsx`, `CommandBarSurfaceHost.tsx`, `core/CommandBarProvider.tsx`; consumed by `components/layout/sidebar.tsx` |
| **Command-bar / Focus exclusivity** | **built** | `CommandBarProvider.tsx:129` — *"Keeps the two surfaces mutually exclusive"*; `CommandBar.tsx:812` names the gate |
| **Focus** | **reachable; partly unexercised** | `<Focus />` mounted at `App.tsx:509`. ⚠️ `contexts/accounting-focus-bindings.test.ts:25` records focuses *"openable only by typing `?focus=` into the URL since it shipped"* — reachable, never entered by a user |
| **Park / floating tablets** | **built, substantial** | `components/park/{ParkHost,ParkCanvas,ParkRelaunchPill,park-summon}.tsx` + three tablets (`AddNote`, `StartQuote`, `ReplyDm`); `contexts/park-context.tsx` with `tablets`, `focusOpen`, `isSuspended`; mounted via `lib/runtime-host/TenantProviders.tsx` |
| **The sphere** | ⚠️ **DOES NOT EXIST** | see below |

⚠️ **THE SPHERE IS ABSENT, AND MY FIRST GREP SAID OTHERWISE.** A case-insensitive search
for `sphere|orb` returned four files. Every hit was a substring — `forbidden`,
`HierarchicalEditorBrowser`, `VendorBill`, `WidgetErrorBoundary`,
`tenantVerticalForButtonPicker`. There is no sphere component, no orb, nothing that
renders one. §11's *false presence from a substring match*, and it would have been
recorded as "the sphere exists" if the pattern had not been re-run bounded.

**So the entrance canon describes — a sphere — has no implementation.** The command bar is
reached by keyboard and by a sidebar affordance.

---

## PART 3 — what the overlay needs that does not exist

Read from the prototype's own CSS (`2026-10-01-opas-overlay.html`), not from a summary.

| Prototype behaviour | Prototype's mechanism | Against Part 2 |
|---|---|---|
| sphere, fixed bottom-right, breathing | `.orb` 56px at `right:24px;bottom:24px`, `@keyframes breathe`, `.orb .halo/.ball/.tint/.spec/.rim` | **NEW** — nothing exists |
| sphere absorbs into the command line | `.orb.absorbed{opacity:0;transform:scale(.7)}` + `.line` animating `clip-path` | **NEW** |
| sphere marks a live session | `.orb.session .halo` — colour change, animation stopped | **NEW** |
| page blurs behind | `.veil{backdrop-filter:blur(7px) saturate(.9)}`, `.veil.on` | **NEW** as a veil. Park has a comparable idea; the command bar does not dim the page |
| a command line out of the sphere | `.line` glass pill, `.field input` in IBM Plex Mono, `.ghost em` for inline completion | **CHANGE** — the command bar has an input; it is not a floating glass pill and has no ghost completion |
| "what it understood" chips | `.said`, `.chip`, `.chip.ref/.close/.miss` (dashed = reference, terracotta = miss) | **CHANGE/NEW** — NL creation has field chips; nothing renders an understood/missed chip set for a general request |
| disambiguation picker | `.pick` + `.pick button` rows | **REUSE** — `product_name_resolver` already returns a candidate set plus a discriminator; no UI exists |
| each request → its own glass pane | `.win` 390px (`.wide` 440px), `--glass` + `--glass-blur`, `::before`/`::after` edge light | **REUSE the machinery, NEW the look** — Park's tablets are the same primitive |
| panes draggable | `.win{cursor:grab;touch-action:none}`, `.win.dragging` | **REUSE** — Park rides WidgetChrome's @dnd-kit drag/resize/8px-grid |
| focus ring among panes | `.win.focused` stronger shadow, unfocused bodies to `opacity:.8` | **NEW** |
| Esc tucks away, session persists | `.win.tucked{opacity:0;transform:translateY(12px) scale(.96);pointer-events:none}` + `.orb.session` | **CHANGE** — Park is session-scoped and has `ParkRelaunchPill`; tuck-and-restore is not the same gesture |
| pane header | `.whead` with `.kind` (uppercase eyebrow), `.num` (mono, hover-only), `.x` (hover-only) | **NEW** |

**Summary: one genuinely new primitive (the sphere and its absorb/session states), one new
treatment (glass, edge light, focus ring, tuck), and one substantial reuse (Park's drag
machinery and session model).** The riskiest item is not the sphere — it is the veil, because
blurring the page behind interacts with the command-bar/Focus exclusivity gate that already
exists, and nothing in Part 2 currently dims anything.

---

## PART 5 — the smallest walkable slice

### ⚠️ First: a correction to Part 4, and James caught it

Part 4 said Specs renders nothing, citing `product_variant_templates` — inside 3/52,
weight 0/52. **That was measured at the wrong tier.** r193 writes to
`product_templates`, with `spec_source` as its membership marker:

    product_templates     29 rows
      spec_source         15      <- r193's own marker
      inside_length_in    14
      outside_length_in   13
      weight_lb            8

**Specs is real for roughly half the platform catalog.** The verdict "renders nothing" was
true of the variant tier and false of the product tier, and I reported the tier I happened
to query.

### a. Which records the two panes read

⚠️ **The two populations are DISJOINT, and nothing joins them.** Measured:

    products.variant_template_id       0 of 27 populated
    products.sku = variant.sku         0 matches
    products.wilbert_sku = variant.sku 0 matches (wilbert_sku is 0-populated)
    any price column on the platform catalog tiers   NONE

So:

| | tenant `products` (27) | platform catalog (29 / 52) |
|---|---|---|
| name, SKU | yes | yes |
| kind | `category_id` | `product_templates.form`, 29/29 |
| current price | **`price` 26/27** | **none — no price column exists** |
| specs | none | **`spec_source` 15/29, dimensions 13–14/29** |
| personalization availability | keyed on `variant_template_id` → **unreachable** | keyed on variant id → **works** |
| confirmed aliases | platform-side | **`platform_product_aliases` 5/5 confirmed** |

**Recommendation: the panes read the PLATFORM CATALOG, through `product_templates` →
`product_variant_templates`.** It is the only source that carries kind, specs,
personalization availability and aliases together, and "ask for the catalog" is a request
about the catalog. Reading tenant products would yield a price and nothing else the pane
wants.

⚠️ **AND THAT MEANS THE APPROVED FIELD LIST IS NOT SATISFIABLE FROM ONE SOURCE.** The
ruling said: name, kind, SKU, **current price**, Personalization pill, aliases, Catalog
action. Price lives only on tenant products; everything else only resolves on the platform
catalog. The slice must drop one or the other, and that needs a ruling — see (c).

### b. Why Specs renders nothing — and it is the missing link in (a)

Confirmed as James suspected. The specs exist on `product_templates` for 15 products. A
tenant product cannot reach them because `products.variant_template_id` is **0 of 27**
populated — the column r186 added, which nothing could write until r196 gave it an ORM
attribute, and which `import_product_templates` sets for products it creates. That function
has never provisioned a tenant.

**So Specs is not a data gap. It is a link gap.** Read the platform catalog directly and
Specs renders for 15 of 29.

### c. Where "current price" comes from

**It cannot be a keyed read on the platform catalog, because no price column exists there.**
The only keyed price is `products.price` (26/27) on a tenant product row.

Three options, and I lean to the third:

1. **Join tenant price onto the catalog by name/SKU** — ⚠️ reject. Zero SKUs match, so it
   would fall back to name matching, which is the `price_list_items` defect this
   investigation already recorded.
2. **Read tenant products and drop specs** — satisfies the approved list, loses
   personalization and aliases too (both key off the variant id).
3. **Read the platform catalog and DROP PRICE from the first slice.** The slice becomes
   name, kind, SKU, **Specs for the 15**, Personalization, aliases, Catalog action. Nothing
   is name-matched, nothing is invented, and the pane shows MORE than the approved list —
   just not the price.

⚠️ Option 3 inverts Part 4's conclusion: Part 4 had price in and specs out. Measured
properly, it is specs in and price out.

### d. How "ask for the catalog" and a product name resolve without a model call

**Both already have mechanisms, and `product_name_resolver` serves.**

- *"the catalog"* — a fixed phrase, which the command bar's **rule-based** classifier
  handles: `command_bar/intent.py` is explicitly rule-based with no AI, to hold a
  p50 < 100 ms budget. One registry entry, no model.
- *a product name* — `product_name_resolver` normalises (marks stripped before NFKD),
  reads `platform_product_aliases WHERE is_confirmed IS TRUE`, and returns **a candidate
  set plus a discriminator, never a best match**. It resolves to
  `variant_template_id`, which is exactly the key the platform-catalog read needs.

⚠️ **The resolver reinforces (a).** It already resolves to the platform catalog and has no
path to a tenant product, so a pane keyed off its output is keyed off the catalog whether
or not that is chosen deliberately.

### e. What the first slice shows

Per the rulings, with (c) option 3:

- **Header** — name, kind (`form`), SKU. **No made-here/bought-in chip.**
- **Specs** — outside dimensions and weight, **for the 15 products that have them**; the
  section is absent on the other 14 rather than blank.
- **Personalization pill** — live, from `read_availability` on the resolved variant.
- **Other names** — the confirmed aliases.
- **Catalog action.**
- **Price — only if James rules option 1 or 2.** Not in option 3.

No Recent orders. No Order one. No placeholders.

### f. What James will NOT see

| Not shown | Why |
|---|---|
| a photo | `image_url` 0-populated on all three tiers |
| made here / bought in | NULL on all 27 products; ruled out |
| current price | **no price exists on the platform catalog** (if option 3) |
| stock, in production, due out | 1 inventory row; 0 production rows; `deliveries` has no product column |
| low stock, none on hand, pending price change | same inventory row; price versions reachable only by name match |
| price history, last changed | `price_list_items` has no `product_id` |
| cost, supplier, margin | cost 0/27, no product→supplier link |
| lining | **no such column anywhere** |
| specs for 14 of 29 products | r193 covered 15 |
| retired names, usually-ordered-with, truck | do not exist |
| substitute | table exists, 0 rows |
| lead time | exists on suppliers/vendors, unreachable from a product |
| Recent orders, Order one | ruled out of the first slice |
| Send spec sheet | no document template exists |

---

## Owed before the build

1. **Rule (c).** The approved field list is not satisfiable from one source. My lean is
   option 3 — platform catalog, specs in, price out.
2. **Save the spec file.** Part 4 still rests on dispatch text.
3. **The sphere is net-new.** Part 3 has it as the one genuinely new primitive; the
   prototype's CSS is specific enough to build from.
4. ⚠️ **`products.variant_template_id` being 0-populated is the root of (a) and (b).**
   Populating it is not part of this slice, but every pane that wants to show a tenant's
   own product alongside catalog facts is blocked until it is.
