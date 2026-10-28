/**
 * What the Opas pane says when no question is outstanding — the idle and done states.
 *
 * James's dispatch of 2026-10-28, clauses 1 and 2. Quoted from the prototype saved at
 * `docs/prototypes/2026-10-27-guided-order-capture.html` (92,138 bytes, sha256
 * 34b3938d9a2dcedca7fce8f15f14c7ba62fc37a80da86d4b2ba6b58bcacd09f3), lines 535-536,
 * verbatim:
 *
 *   if(S.mode==='idle')return {ask:'What do you need?',
 *     hint:'Or just type it: “order for hopkins monti thursday 10am”.',
 *     options:[{act:'order',label:'New order'},{act:'quote',label:'New quote'}]};
 *   if(S.mode==='done')return {ask:S.type==='quote'?'Quote saved.':'Order confirmed.',
 *     hint:'Type the next one, or pick below.',
 *     options:[{act:'order',label:'Start another order'},{act:'quote',label:'New quote'}]};
 *
 * ⚠️ THE DISPATCH'S ARTIFACT URL DOES NOT RESOLVE — the same short id as the three
 * dispatches before it — so these strings come from the file in the repo with a digest
 * rather than from a description. Every string the dispatch names was found in it.
 *
 * ⚠️ WHY THESE LIVE ON THE CLIENT WHILE THE CAPTURE'S QUESTIONS DO NOT. James ruled on
 * 2026-10-27 that "the next question comes from the engine, not the client", and that
 * still holds for every question inside a capture. These two are not questions inside a
 * capture: IDLE is the state with NO SESSION, so there is nothing for the server to
 * read, and DONE follows an approval that — by his ruling of 2026-10-19, "the capture
 * closes and the new order's pane opens in its place" — has already closed the session's
 * pane. Neither has a session to be served from.
 *
 * ⚠️ AND THE DONE STRINGS ARE ALSO IN `schema.py`, FOR THE ONE CASE WHERE THE PANE DOES
 * STAY. `onApproved` keeps the capture pane open when the server returns no
 * `sales_order_id` — a state `CapturePane` already guards for — and then the session is
 * readable and its own done state is served. The duplication is real and is held by
 * `test_the_done_strings_AGREE_across_the_two_surfaces`, a backend test that reads this
 * file, rather than by anyone remembering.
 */

/** ⚠️ MIRRORS `schema.NEW_ORDER_ACTION`. The act vocabulary is already mirrored this
 *  way — `PILL_ACT_REVIEW` against `schema.REVIEW_ACTION` — because the server emits
 *  the act and the client performs it. */
export const PILL_ACT_NEW_ORDER = "new_order"

export const IDLE_QUESTION = "What do you need?"
export const IDLE_HINT = "Or just type it: “order for hopkins monti thursday 10am”."
export const IDLE_PILL_LABEL = "New order"

export const DONE_QUESTION = "Order confirmed."
export const DONE_HINT = "Type the next one, or pick below."
export const DONE_PILL_LABEL = "Start another order"

/**
 * ⚠️ NO `New quote` PILL IN EITHER STATE, AND NO "Quote saved." — the dispatch's own
 * clause 3: "if quotes can't be created through capture yet, say so and leave the pill
 * out rather than offering one that fails."
 *
 * MEASURED, AND THEY CANNOT. `capture_sessions.object_type` has exactly ONE writer,
 * `session_service.start`, hard-coded to `SALES_ORDER`; that is the only template
 * constant the capture schema defines; `approve` constructs SalesOrder/SalesOrderLine
 * and branches on nothing; and production holds 25 capture sessions, every one
 * `'sales_order'`. Quotes are created by `sales_service.create_quote`, a separate path
 * with its own schema and its own `convert_quote_to_order`.
 *
 * So the pill is absent rather than disabled. A disabled pill still occupies a number
 * the office would reach for, and the dispatch asked for it left out.
 */
export const QUOTES_THROUGH_CAPTURE = false
