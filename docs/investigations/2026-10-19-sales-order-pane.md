# Sales Order Pane, slice 1 — what was built, measured, and found

James's dispatch of 2026-10-19. Every figure below says which environment it came from.

---

## 0. The prototype the dispatch cited does not resolve, and the one used instead

The dispatch cites `https://claude.ai/artifact/39R6gdLS6PrrAPWr4GmjBh`.

- That URL shape is **not fetchable** — only `claude.ai/code/artifact/{uuid}` is — and it
  returns the SPA shell, not content.
- The short id `39R6gdLS6PrrAPWr4GmjBh` **does not appear in James's artifact listing**.
  30 artifacts enumerated; no match.
- The only "Sales Order Pane" in that listing is
  `claude.ai/code/artifact/115f1411-7c22-4983-91e4-6dca3d99fcc4`, **updated 2026-10-04**.

That one was fetched and is now in the repo, with digests, per the CLAUDE.md §11 remedy
("The fix is always the same: move the bytes into the repo, with digests, before the
dispatch references them"):

| File | bytes | md5 |
|---|---|---|
| `docs/prototypes/2026-10-04-sales-order-pane.html` | 81544 | `1fe0b3083812cb92ed0975f8c17c5926` |

**How it was verified to be the right document, since the cited id could not confirm it.**
The dispatch names five things to leave OUT of slice 1. All five are present, which is what
a superset of slice 1 should look like: `proof` 37 hits, `Driver` 36, `Office` 21,
`contact` 12, `Scheduling` 5, `Accounting` 4, `"Right now"` 1.

**Two dispatch items are NOT in the prototype, and for those the dispatch wins.**
`Confirmed` — 0 hits; the prototype's progress steps are **Proof → Scheduled → Delivered
→ Invoiced** against the dispatch's **Confirmed → Delivered → Invoiced**. `Undo confirm` —
0 hits. Both are consistent with the artifact predating the confirm step by twelve days
(updated 2026-10-04; Approve began confirming orders 2026-10-16).

**A confirmed instance of the 2026-10-06 provenance caveat.** That file warned that a
whole-file digest covers the artifact *as served*, so a platform runtime update would
change the digest of an unchanged prototype. It has now happened: the injected
`<!-- frame-runtime -->` block is **40448** bytes here against **39424** in the October 6
pair, and no longer byte-identical. The authored remainder is digested separately in
`PROVENANCE-2026-10-19-sales-order-pane.md`.

---

## 1. What production actually holds, and what the pane therefore cannot show

All measured on **production**, 2026-10-19, read-only.

| Fact | Measured | Consequence for the pane |
|---|---|---|
| `products.variant_template_id` | **NULL on all 39 products, every tenant** | The order LINE carries no link to the platform catalog. The vault link is resolved from the line's **name**, through the same `product_name_resolver` the command line uses. |
| `order_personalization_tasks` for Sunnycrest | **0 rows**; `products.has_personalization` False on all 10 | The Personalization row is coded and **renders for no order today**. |
| `customers.invoice_delivery_preference` | **`statement_only` on all 22 platform-wide** | "Invoiced after delivery" is coded and **unreachable with today's data**. |
| `customers.payment_terms` | **NULL on all 22** | The prototype's "Hopkins is Net 30" clause is **omitted** — it would be invented. |
| `sales_orders.eta` | **NULL on all orders** | The cemetery-ETA clause appears only for a non-graveside service that carries one. |
| `deliveries` on Sunnycrest orders | **0 rows** | No Delivery row. The dispatch's row list omits it too. |
| `invoices.sales_order_id` | **NULL on all 8 Sunnycrest invoices** | No order is invoiced. "Not invoiced yet" is the real state. |
| `audit_logs` for `sales_order` | **3 `created` with a `changes` JSON; 2 `updated` with `changes` NULL** | History ships. An `updated` entry says **"no fields recorded"** — `sales_service.update_sales_order` calls `log_action` without `changes`. |
| `service_location` platform-wide | NULL ×37, `church` ×2, `graveside` ×1 | — |

**The resolver, measured over Sunnycrest's own catalogue.** `Monticello Burial Vault` → 1
candidate (`8a3c6253-…`). `Continental Burial Vault` → **2**, differing by size. The eight
equipment and urn names → 0. So a vault links only when its name reaches exactly one
variant; an ambiguous name gets no link rather than an arbitrary one, which is the rule the
bar already follows.

---

## 2. The dispatch's premise about the data had moved

> "DATA: Sunnycrest only has one real draft and one cancelled order."

True when written. At the moment this ran there were **three** orders, and the third is a
**confirmed Hopkins order with a service date next week** — `SO-2026-0003`, created
2026-10-19 12:03 UTC by `jim.atkinson@sunnycrest.com` through capture session
`b99c4498-a300-41bc-8dba-a85a56d83fe6`, text: *"order for hopkins Funeral Home monticello
Burial Vault full equipment friday 11 am church st.. Mary's Cemetery for smith family"*.
That is James's own step-3 retest from this morning.

**So the Hopkins half of "create two demo orders" was already satisfied and only the
Riverside one was written.** Writing a second Hopkins order would have duplicated what
James made an hour earlier.

### The orders, named so they can be cancelled later

| Number | Who | Service | State | Provenance |
|---|---|---|---|---|
| `SO-2026-0003` | Hopkins Funeral Home · smith | Fri **2026-10-23** 11:00 AM church | confirmed | **James's**, 12:03 UTC today |
| `SO-2026-0004` | Riverside Memorial Chapel · hart | Wed **2026-10-28** 10:00 AM graveside | confirmed | **written by this dispatch**, 13:22 UTC, $1,705 |

`SO-2026-0001` (draft) and `SO-2026-0002` (cancelled) were not touched.

**How SO-2026-0004 was written.** Through `session_service` — the same
start → set_text → complete → approve path the pane drives — rather than a raw INSERT,
because "through Opas capture" is what the dispatch says. The HTTP layer was skipped
because reaching it needs a user's password and no credential passes through a session
(CLAUDE.md §7); same code, no credential. It ran twice: a dry run that printed the Review
and **abandoned** the session, then the approving run.

The Review, verbatim, from the dry run:

```
  blockers       []
  can_approve    True
  total          1705.00
  approve_effect 'Confirms the order · Delivered Wed Oct 28 · Invoiced at month end (Riverside)'
  lines:
    Monticello Burial Vault            x1 @ 1405.00 = 1405.00
    Full Equipment                     x1 @ 300.00 = 300.00
```

⚠️ **The first dry run reported the order as NOT APPROVABLE and was wrong.** It read the
state while the session was still `capturing`, where the summary surface is empty:
`can_approve=False`, `blockers=None`, `total=None`, no lines. Nothing was wrong with the
order. `complete` has to run first — it is still abandonable and writes no sales order.
Recorded because "not approvable" is exactly the reading that would have stopped the write
for no reason.

---

## 3. The three opening paths, measured on production data

```
  'riverside order'                  -> OPEN SO-2026-0004
  'SO-2026-0004'                     -> OPEN SO-2026-0004
  '0004'                             -> OPEN SO-2026-0004
  'hart order'                       -> OPEN SO-2026-0004
  'hopkins order'                    -> PICK ['smith · SO-2026-0001 · Fri Oct 16',
                                              'smith · SO-2026-0003 · Fri']
  'smith order'                      -> PICK (the same two)
  '0002'                             -> OPEN SO-2026-0002   (cancelled, opens saying so)
  '0404'                             -> no  ("No order numbered 0404.")
  'monticello burial vault order'    -> PICK (all three live orders)
  "st. mary's order"                 -> PICK (all three live orders)
```

**`"riverside order"` returned "No order for Riverside" before this.** `_open_decedent`
matched the DECEDENT and nothing else, so a funeral home's name — which is how the office
refers to most orders — found nothing. It is now `_open_one` over four fields in a declared
order (decedent, funeral home, cemetery, vault), live orders first and cancelled only if
nothing live matches. James's own walk line is `type "riverside order"`, so the narrowness
was the first thing it would have hit.

**Order numbers were not an opening path at all.** `SO-2026-0004` and `0004` matched no
rule, fell through to the catalog resolver, matched no product, and opened an unfiltered
catalog. Both the server rule (`question.order_number_query`) and the frontend gate
(`order-list-routing.isOrderNumber`) are new. The bare form needs **3–4 digits**: a 1–2
digit line is what the bar's ⌘1..9 pick settles, and routing `"2"` here would collide with
answering "which one?".

---

## 4. What 4+ panes do on a 1440px screen

Asked for, not redesigned. The arithmetic:

```
  order list      min(37rem, 100vw-32)   = 592px
  sales order     min(390px, 100vw-32)   = 390px
  product         min(390px, 100vw-32)   = 390px
                                   panes = 1372px
  + right anchor 24 + two 16px gaps + 16px left pad = 1444px needed
```

**1444 > 1440, so the order list plus two 390px panes does not fit, by 4px.** The third
pane finds no gap and takes the module's fallback cascade, overlapping. Two order panes
*without* the list open fit with room to spare (asserted). The four-pane case is recorded
as a test (`opas-multipane.test.tsx`, "⚠️ FOUR PANES ON A 1440px SCREEN") so that a future
change to the widths or the anchor shows up there rather than on James's screen.

The old behaviour was worse and unconditional: anchored panes were positioned at
`right: 24 + i * 18, top: 72 + i * 22`, so a second 390px pane sat 18px from the first and
covered 372px of it **even on a screen with room for both**.

---

## 5. Three defects found by building this, none of them in the dispatch

### 5.1 Two deferred `setPanes` writers dropped a pane entirely

`openPane` deduped against a ref mirror of the pane list; `closePane` wrote that ref inside
a `setPanes` updater. React runs an updater **at render time**, so when both deferred — the
shape the code had — the close's updater overwrote the ref after the open's lazy read
resolved from it, and the newly-opened pane was **dropped**. Measured: "approve closes the
capture and opens the order's pane" rendered an **empty desk**.

The invariant is now: *every writer of `panes` writes the ref at CALL time and hands
`setPanes` a value.* All four writers do.

⚠️ **The first comment explaining this named the wrong cause** — it blamed `openPane`'s
laziness alone. A break test reverting each writer in turn showed that with `closePane`
eager and `openPane` lazy the suite stays **green**; the failure needs both. Corrected in
place, quoting itself.

### 5.2 A test claiming to pin that bug did not

Two versions of a probe test were written believing they caught the both-lazy case. The
first yielded between the two writes, so they were never in one tick. The second calls the
context directly in one synchronous handler and **still** does not reproduce it — measured,
with the pane count printed. The only test that goes red under both-lazy is
`capture-pane.test.tsx`'s "WITH AN ORDER ID THE CAPTURE CLOSES". The probe test is kept as
coverage of a real path and its docstring now says plainly that it is **not** the pin.

### 5.3 `include_cancelled=False` is not what keeps cancelled orders out of the list

A test docstring claimed the pane's `include_cancelled=True` and the list's exclusion were
"one decision". Break test: flipping the default to `True` turned only the test that
asserts the default red, and left every list test green. The list is protected **three
times over** and `load_facts` is the weakest of the three:

```
  load_facts(include_cancelled=False)   excludes them in SQL
  stage.group_of                        `if facts.cancelled … return None`     <- what fires
  stage.matches                         `if facts.cancelled and not include…`
```

Each alone is sufficient. The SQL exclusion is **defensive, not load-bearing**, and both
the docstring and `load_facts`'s own docstring now say so. `group_of` is now asserted
directly, because nothing was asserting the guard that actually fires.

---

## 6. What was deleted rather than left behind

**`capture-approved-link`** — the anchor added 2026-10-14 on James's ruling "the order
number links to the order". It required `sales_order_id`, and an id is exactly the
condition under which the host now closes the capture pane, so the anchor had become
**unreachable in the app**: dead machinery behind a live-looking guard. What the ruling
asked for is better served by the order's own pane opening by itself and carrying "Open the
full order". The no-id fallback still prints the number as plain text.

**The `openSalesOrder` dedupe and the two "close every other sales-order pane" loops.** The
dedupe moved into `openPane` so every caller gets it — the Product pane had none, so one
vault opened from two orders made two identical panes. The closing loops belonged to the
one-order-beside-the-list arrangement; closing the order you came from is the opposite of
chaining.

---

## 7. Gates, with denominators

| Gate | Result | Of what |
|---|---|---|
| backend pytest, `tests/ci_gate.txt` | **3639 passed, 4 skipped, 0 failed** | **234 of 512** test files (45.7%) — `test_sales_order_pane.py` added to the manifest |
| frontend vitest | **4852 passed, 5 skipped, 1 todo, 0 failed** | **365 of 365** test files |
| `tsc -b --noEmit` | exit 0 | whole frontend |
| `npm run build` | exit 0 | — |

**Bundle, measured against a `git worktree` build of HEAD rather than remembered:**

| | HEAD (`d280f1d7`) | after | delta |
|---|---|---|---|
| `index.js` | 6,742.67 kB | 6,750.25 kB | **+7.58 kB (+0.11%)** |
| `index.js` gzip | 1,631.68 kB | 1,633.49 kB | +1.81 kB |
| `index.css` | 241.61 kB | 241.55 kB | −0.06 kB |

**New tests: 44 backend + 65 frontend.** Re-pointed rather than deleted: 4 drag tests in
`opas-slice.test.tsx` (they asserted `style.left === ""` to mean "not dragged", which
anchored panes now also carry), 1 tuck assertion that had become unfailable, and 2
capture-approve tests.

### Break tests — 18 applied, each naming the assertion it had to turn red

16 were caught by the named assertion on the first attempt. The two that were not are
§5.1–5.3 above: **B6** (flip `include_cancelled`) exposed a false claim in a test docstring
rather than a gap, and **B15** (revert `openPane` to a lazy updater) exposed a false claim
in a code comment. Both were corrected, and B15 was re-run with **both** writers reverted,
where it does go red.

| | Break | Caught by |
|---|---|---|
| B1 | `findDuplicate` always returns undefined | "clicking the same order row twice leaves one pane"; "THE SAME VAULT OPENED FROM TWO ORDERS IS ONE PRODUCT PANE" |
| B2 | placement returns the index cascade | "two order panes do not overlap"; "scans left until the gap clears" |
| B3 | `isCloseRequest` always false | "closes the pane in front and leaves the rest"; the phrase table |
| B4 | drop `openSalesOrder` from `onApproved` | "WITH AN ORDER ID THE CAPTURE CLOSES" |
| B5 | first step becomes `Proof` | `test_a_confirmed_order_renders_the_whole_pane` |
| B6 | `include_cancelled` defaults True | `test_include_cancelled_is_off_by_default` **only** — see §5.3 |
| B7 | `OPEN_ONE_FIELDS` back to decedent-only | `test_a_funeral_homes_name_opens_its_one_order`; the cemetery/vault test |
| B8 | order-number regex requires the `so` prefix | `test_every_shape_of_an_order_number_names_the_same_order` |
| B9 | billing month reads the clock | `test_the_month_is_the_SERVICE_month_not_this_one` |
| B10 | render the inert cemetery as a control | "THE CEMETERY IS INERT AND SAYS WHY" |
| B11 | `_row` returns "—" for an absent fact | `test_an_absent_fact_hides_its_row_and_a_present_one_shows` |
| B12 | drop the graveside exclusion on the ETA | `test_the_cemetery_eta_appears_only_for_a_service_away_from_the_grave` |
| B13 | link the first of several candidates | `test_the_vault_links_only_when_its_name_reaches_exactly_one_variant` |
| B14 | drop `detail_absent` | `test_history_reads_the_created_row_and_says_an_update_recorded_nothing` |
| B15 | `openPane` lazy again | **nothing** alone; with `closePane` lazy too → "WITH AN ORDER ID THE CAPTURE CLOSES". See §5.1 |
| B16 | title not title-cased | `test_a_confirmed_order_renders_the_whole_pane` |
| B17 | hardcode the equipment labels | `test_the_equipment_labels_come_from_the_capture_schema` |
| B18 | remove the order-number gate | "a typed number opens the order's pane and never reaches the catalog"; "the short form works too" |

---

## 8. One thing worth knowing that nobody asked about

Typing **"close it out"** — the wording on the order list's own `close` flag action
("Delivered, not closed out" → "Close it out") — is not a close phrase, contains no order
word, falls through to the catalog resolver, matches nothing, and **opens an unfiltered
catalog** with "no match for…" on the said line. Pre-existing behaviour for any unmatched
phrase, not changed here, and harmless because "Close it out" is a button on a row rather
than something anyone types. It is the reason `close-request.ts` is an exact phrase list
and not a `\bclose\b` test; recorded because the first version of a test asserted the pane
count was unchanged and went red — a pane did arrive, just not by closing anything.
