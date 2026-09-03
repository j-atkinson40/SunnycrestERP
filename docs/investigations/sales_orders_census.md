# Sales & Orders — area census

> # ⚠️ THIS DOCUMENT IS GONE. THIS IS A STUB, NOT A RECONSTRUCTION.
>
> The original lived at `/tmp/sales_orders_census.md` — **568 lines, nine
> sections, a file:line anchor for every claim** — written 2026-09-03 as the
> deliverable of a full investigation session. `/tmp` was wiped at that day's
> 11:47 boot.
>
> It was **not reconstructed**, deliberately. What remains in context is a
> handful of individually memorable findings, not the census. A census is
> valuable precisely because it is *exhaustive and anchored*; a document
> assembled from the six claims that happened to be memorable would have the
> shape and authority of a census while being a highlight reel. Approximating it
> into existence is the more dangerous artifact — it would read as a citable
> inventory and would be one only by accident.
>
> **The fragments in §3 are fragments. Do not cite this file as a census.**

---

## 1. What the document was

An **existence-first** area census of Sales & Orders, per CLAUDE.md §12: *what
exists, by any mechanism, exhaustively.* Not a confirmation of expectations, and
not a verification that two named things compose.

Scope covered the sales-order surface and its neighbours — sales orders, quotes,
the Order Station, invoicing, and the delivery/scheduling seams. It carried a
**file:line anchor for every claim**, which was its defining property and the
reason it took a session to produce.

It was the input to two downstream pieces of work:

1. **S-1, the absence re-read** — audited every absence claim the census made.
   Partially reconstructed at `sales_orders_absence_audit.md`.
2. **S-2, the floor** — the test-inventory and gating work, whose measurements
   the census's §3 claim reframed.

---

## 2. What is LOST

- **The nine sections and their titles.** I cannot state them.
- **The file:line inventory** — the census's entire substance and its only
  reason to exist as a document rather than a memo.
- **The full set of claims**, and therefore the denominator for every "the
  census found N of X" statement anywhere downstream.
- **The list of open questions.** Question **#8** is remembered only because it
  was later settled by name (§3). Questions #1–#7 and any beyond #8 are gone —
  including whether any of them remain open.
- **Every absence claim not listed in the absence audit's §3**, along with the
  record of whether it was audited and held. See that document's §5.

---

## 3. Fragments still held — NOT a census

Individually citable, because each was re-verified or is anchored in STATE.md.
Collectively they are **not** the document and must not be read as its summary.

- **§0 opened with the Order Station finding.** The census's original framing
  ("no UI path can produce an invoice") was wrong and was corrected in place:
  the Order Station posts `POST /order-station/quotes` with `mode="order"` and
  converts inline. Verified 2026-09-03 at `app/api/routes/order_station.py:412`,
  `:443`, `:447`.
- **Open question #8 — are RC tokens stored encrypted? — SETTLED** by S-3a, by
  direct observation at the write site: encrypted from birth, zero rows ever
  written plaintext.
- **The "twenty test files in the territory, zero gated" claim was a filename
  filter result** and is FALSE. Re-derived by content: 420 files, 72 in the
  territory, 4 gated, 1 asserting area behaviour. (The classification predicate
  behind "by content" is itself lost — see the absence audit §3.)
- **A claim about `app/services/focus*/` was correct by luck on falsified
  evidence** — the prefix glob never enters `coordination_focus/` or
  `generation_focus/`. This is the instance that produced CLAUDE.md §11's
  "Conclusion survives, derivation falsified."
- **A claim that `order_created` / `order_id` had "four readers, zero writers"
  was FALSE** — a `head -10` truncation. The writer is at
  `app/services/call_extraction_service.py:275-276`, verified 2026-09-03.
- **A `"ring"` substring match inside `"spring_burial*"`** produced a false
  positive.

Note the composition of that list: **four of six fragments are the census's own
errors.** Errors were memorable because they became canon; the correct bulk of
the census was not. That asymmetry is the clearest evidence that this file
cannot stand in for the original — reconstructing from memory preferentially
recovers what was wrong.

---

## 4. What the next arc should do

**Start from the July audit, which survived.**
`docs/investigations/mfg_area_audit_02_sales_orders.md` (288 lines, 2026-07-18,
HEAD `a6d20089`) is a read-only audit of this same area, anchored and committed.
It is not the census and does not replace it — it predates it by six weeks and
was scoped as a ledger rather than an inventory — but it covers the same
territory with its derivations intact, and its structural finding (two parallel
quote/order-money systems on the same tables: the Order-Station path in
`quote_service.py` and the AR path in `sales_service.py`, with five more creation
paths orbiting them) is the kind of claim the census was rebuilding toward.

It survived for exactly one reason: it was committed to the repository.

**Re-run the census.** Do not inherit from this file, and do not inherit any
claim attributed to the census that is not re-derived. The two downstream
conclusions that survive independently — the corrected 72-file test inventory
(embodied in `backend/tests/ci_gate.txt`) and the five false absences (in the
absence audit and in CLAUDE.md §11) — stand on their own evidence and do not
depend on this document.

Everything else attributed to "the Sales & Orders census" is now a claim with no
auditable basis. That is the condition the deliverables-live-in-the-repository
rule exists to prevent, and this file is the worked example of the cost.
