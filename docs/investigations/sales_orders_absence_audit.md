# S-1 — absence re-read of the Sales & Orders census

> ## ⚠️ RECONSTRUCTED FROM CONTEXT AFTER /tmp LOSS — 2026-09-03
>
> The original lived at `/tmp/sales_orders_absence_audit.md` (306 lines, written
> 2026-09-03). `/tmp` was wiped at that day's 11:47 boot.
>
> **This reconstruction is partial and its shape differs from the original.**
> The original's primary structure was a *classification table covering every
> absence claim in the census* — each claim marked as observed-absent,
> looked-up-absent, or re-derived — and that table is gone along with the census
> it indexed (see `sales_orders_census.md`, which is a stub).
>
> What survives is the part that became canon: the five false absences, **with
> their derivations**, and the false positive. Those are restated below and
> their file:line anchors were **re-verified against HEAD during this rescue**
> rather than recalled — marked **VERIFIED 2026-09-03**.
>
> §4 lists what is LOST. It is the larger half.

---

## 1. The question this audit asked

The census asserted a number of absences. An absence is only a finding if the
query that produced it could not have missed a thing that exists. So: for every
absence claim, *how was it established* — by observation, or by a lookup that
returned nothing?

Looked-up absences were re-derived by **enumeration**, using a different method
than the one that produced the original null.

---

## 2. THE TEST that came out of this

Applied to every negative result before it is reported:

> **"Could this query have returned nothing while the thing exists?"**

If yes, the null is uninformative. Re-derive by enumeration: enumerate the app's
route table rather than grepping path strings; query `information_schema` rather
than guessing pluralization; read `__tablename__` off the model; walk the
directory tree rather than matching a naming convention.

⚠️ **A filesystem walk can still fail this test** — see false absence #4. The
question tests the QUERY, not the querier, which is why it works where care does
not. No amount of attention distinguishes a constructed name from a real
enumeration at the moment of writing it.

Landed in CLAUDE.md §11 as **"False absence from a constructed name."**

---

## 3. The five false absences

Five distinct false absences across four namespaces. **None was caught by
review.** Each was caught only by re-deriving with a different method.

### #1 — "No UI path can produce an invoice"

**How the null was produced:** searched for `POST /sales/orders` and for
`createSalesOrder` callers. Both returned nothing.

**Why it was wrong:** the Order Station does not use that route. It posts to
`POST /order-station/quotes` with `mode="order"`, and converts inline.

**VERIFIED 2026-09-03:** `app/api/routes/order_station.py:412` (`create_quote`),
`:443` (`if data.mode == "order"`), `:447` (`quote_service.convert_quote_to_order`).

> ⚠️ **Correction to the original.** The original cited `order_station.py:411`
> and `:447`. `:447` is exact; the handler is at `:412`, not `:411`, and the
> mode branch is at `:443`. Either the original was off by one or the file
> drifted. Cite the numbers above.

This led §0 of the census — it invalidated the census's opening framing.

### #2 — `ringcentral_call_logs` (plural)

**How the null was produced:** queried the table; got "relation does not exist."

**Why it was wrong:** the table is **`ringcentral_call_log`, singular**, with all
26 columns present and deployed. **VERIFIED 2026-09-03:**
`app/models/ringcentral_call_log.py:14`.

This was nearly reported as an undeployed table. The fix is to read
`__tablename__` off the model rather than guess pluralization.

### #3 — "Twenty test files in the territory, zero gated"

**How the null was produced:** a **filename keyword filter**.

**Why it was wrong:** the "twenty" was itself a name-filter result. Re-derived by
content: **420 files total, 72 in the territory by content, 4 gated, and only 1
asserting area behaviour.**

> **UNCERTAIN:** the exact predicate behind "by content" — which symbols or
> imports counted as being in the territory — is lost. The four numbers are
> restated at the confidence held when written, but the classification rule that
> produced them cannot be reproduced, so they are not independently re-derivable
> from this document. Re-derive before citing.

This finding is what reframed the S-2 floor dispatch: the measurement axis had
to be content, not filename.

### #4 — `app/services/focus*/`

**How the null was produced:** a **prefix glob** over the filesystem.

**Why it was wrong:** `app/services/focus*/` walks the filesystem and never
enters a directory that does not start with "focus".

**VERIFIED 2026-09-03** — the glob matches `focus`, `focus_compositions`,
`focus_template_inheritance` and **misses `coordination_focus` and
`generation_focus`**, both of which exist.

⚠️ **This is the instance that changed how the campaign read everything else.**
The claim the glob supported happened to be **correct by luck**, on evidence
that was falsified. A conclusion that is right for a bad reason is invisible to
outcome-checking — nothing downstream contradicts it, so it is never
re-examined, and it gets cited later by people with no way to know what it rests
on.

Landed in CLAUDE.md §11 as **"Conclusion survives, derivation falsified."**
Its consequence: **verify derivations on claims you agree with.**

### #5 — `head -10` truncation

**How the null was produced:** output piped through `head -10`.

**Why it was wrong:** falsely claimed `order_created` / `order_id` had "four
readers, zero writers." The writer exists.

**VERIFIED 2026-09-03:** `app/services/call_extraction_service.py:275-276` —
`call_log.order_created = True` and `call_log.order_id = order.id`.

Same shape as an earlier `tail -30` truncation in the same campaign.

> **NOTE ADDED 2026-09-03:** a third instance of this mechanism appeared after
> the original was written — `npx tsc -b` piped to `tail`, where `$?` returned
> tail's exit status (0) while tsc exited 2. Three instances, one mechanism: **a
> pipe destroys the property being read while leaving a plausible-looking
> result.** The general form is *never read a status or a completeness claim
> through a transform you did not account for.* Queued for arc-close canon.

---

## 4. The one false POSITIVE

`"ring"` matched inside `"spring_burial*"`. A substring filter producing a false
presence — the mirror of the five above, and a reminder that the mechanism is
the constructed name, not the direction of the error.

---

## 5. What is LOST

The larger half of this document.

- **The classification table itself** — every absence claim in the census,
  marked observed vs. looked-up vs. re-derived. This was the document's primary
  structure and its main deliverable. Gone.
- **The count of absence claims audited.** I recall the census carrying
  substantially more absence claims than the five that proved false; I cannot
  state how many, nor how many were confirmed sound.
- **The re-derivation record for the claims that SURVIVED.** These are the
  dangerous ones now: absences that were checked and held, whose checking is no
  longer citable. A later arc has no way to distinguish "audited and sound" from
  "never audited" for any census absence not listed in §3.
- **UNCERTAIN:** whether the audit surfaced any absence that was *true but
  established by a bad method* — sound conclusion, unsound derivation, the §4
  shape. I believe it did and cannot restate which.

**What the next arc should re-derive rather than inherit:** every absence claim
attributed to the Sales & Orders census that is not one of the five in §3. None
of them can be cited from this document, and the census that stated them no
longer exists.
