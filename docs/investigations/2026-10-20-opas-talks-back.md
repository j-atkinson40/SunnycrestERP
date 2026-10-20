# Opas talks back — what was built, and three defects found building it

James's dispatch of 2026-10-20. Four rules, all in the bar, deterministic, no model calls.

---

## 0. The prototype already had most of this, and it is quoted rather than reinvented

`docs/prototypes/2026-10-01-opas-overlay.html` (93177 bytes, md5
`a52a1e95153bd5c686b88d0acffc31e6`) carries the whole shape the dispatch describes:

```js
.said{position:fixed;z-index:44;right:24px;width:min(600px,calc(100vw - 48px));
      display:flex;flex-direction:column;align-items:flex-end;gap:6px;…}
function placeSaid(){const r=line.getBoundingClientRect();
                     said.style.bottom=(innerHeight-r.top+10)+'px'}
function show(chips){ … if(pending){ … p.className='pick';
    pending.opts.forEach((o,i)=>{ … b.innerHTML=`<kbd>${i+1}</kbd>${o.name}
                                   <span>· ${o.city}</span>`; …}) …}
  said.classList.add('on');
  if(!pending)saidTimer=setTimeout(()=>said.classList.remove('on'),4200)}
function choose(i){ … pending=null; … p.then(o); show([{t:o.name}]); input.focus()}
```

Four things come straight out of that and are not choices made here:

| | measured from the prototype |
|---|---|
| the voice sits **10px above the bar's top edge** | `placeSaid` |
| options render **below** the sentence, in the same stack | `show` appends `.pick` after the chips |
| a reply **with** options never fades; one without fades after **4200ms** | `if(!pending)saidTimer=…4200` |
| answering ends with the **cursor back in the bar** | `choose` ends `input.focus()` |

The last of those is dispatch item 1, which the prototype had and this app had lost.

---

## 1. The bar keeps focus

`focusBar()` is called from one place per action rather than per exit: `openSalesOrder`,
`closeFrontPane`, `answerOption`, a click inside a pane, and **`submit`'s `finally`** —
which covers all eleven of its exits at once, because eleven focus calls would be eleven
chances to miss one.

**The printable-key redirect is the part that needed care.** `focus()` during a keydown
does not deliver that keydown to the newly-focused element — the browser has already
routed the event — so a handler that only focused would swallow the first letter of every
sentence typed after a click. It `preventDefault`s and appends the character itself, so
exactly one copy lands. `e.key.length === 1` is the printable test, which is what leaves
Enter, Tab, Escape, the arrows and the F-keys untouched: all of those have multi-character
names.

**The exception is enforced in two places**, and that turned out to matter — see §5.2.

---

## 2. One voice above the bar

`said: string | null` became `reply: Reply | null`, where `Reply` carries a `kind`
(`question` / `miss` / `ack`), the sentence, and — when it is a question — its options.

**It moved out of the glass pill.** The old `opas-said` was a child of
`opas-command-line`, below the input. That is where a hint can live and a question cannot:
a question needs its options underneath, and the pill is the thing they have to sit above.

**What the `kind` decides** is whether the line fades. A miss and an acknowledgement fade
after 4200ms; a question does not, because the director is mid-answer and a question that
vanished would take its options with it.

⚠️ **Capture's question line is NOT moved, and this is the one place the dispatch was read
narrowly.** Item 2 says "Capture's question line becomes one user of it, with no change in
behaviour". Capture's question is the bar's **placeholder** (`placeholderFor`), not a
visible line, and it is governed by its own ruling of 2026-10-15 ("One question at a time,
in the bar") with four tests. Moving it into the reply line would be a visible change to a
surface James has walked repeatedly — the question would become persistent rather than
disappearing on the first keystroke, which is arguably better and is not what "no change
in behaviour" asks for. **So the reply line is now the one voice for everything OUTSIDE
capture, and capture's placeholder is untouched. If the intent was to move it too, that is
a one-line change and a visible one; say so and it moves.**

---

## 3. Choices sit with the question

**Both floating pick surfaces are gone**, not one:

| was | where | now |
|---|---|---|
| order picks | `<ol data-testid="opas-order-picks">` inside the order-list pane | the option list above the bar |
| catalog picks | a `product-list` pane filtered to `candidateIds`, with a "Which one?" line | the same list |

Both had the bug the dispatch names: choosing opened the thing and **left the list
standing behind it**. `OpasPane.candidateIds`, `ProductListPane`'s `candidateIds` prop and
filter, `OrderListPane`'s whole `picks` body and its `onChoosePick` prop are deleted.

`routeResolution` now carries the whole candidates rather than just their ids — a list of
opaque uuids is not a list of choices, and each row has to say the product's name.
`candidateIds` survives beside it, **derived**, so the two cannot disagree.

**Four ways to answer**, per the dispatch: ⌘1-9, a bare digit, a click, or words.

⚠️ **A bare digit works here and not in capture, and the asymmetry is the data.** In
capture the bar holds an order's text, where "3" may be a grave depth or a vault size —
the ruling of 2026-10-13 that `pick-digit.ts` implements. Here the bar holds a request,
and a request that is only "2" is a choice and nothing else. The guard is that the bar
must be **empty**: mid-phrase, "monticello 2" is the start of a size.

**Word matching is strict, deliberately.** Every typed token must land on the option;
one match answers, several narrow and keep the question, none is a new request.

⚠️ **`FILLER` is deliberately NOT widened with prepositions**, which was the obvious
improvement and the wrong direction. Dropping "in" would make "the smith one on friday"
answerable — a real nuisance — at the price of making **"orders in october"**, a list
question, reduce to `["october"]`, hit both options and be **eaten as an answer**.
Measured both ways. The asymmetry decides it: a question mis-read as a request costs a
retype; a request mis-read as an answer opens the wrong order, silently.

---

## 4. Context from the front pane — the exact phrasings

**35 phrasings, 9 intents**, enumerated from the table itself rather than retyped:

```
ACT     vault         "the vault" · "vault" · "open the vault" · "show the vault"
ACT     customer      "the funeral home" · "the customer" · "open the funeral home"
                      · "open the customer"
ACT     cemetery      "the cemetery" · "open the cemetery"
ACT     undo-confirm  "undo confirm" · "undo the confirm" · "unconfirm"
                      · "make it a draft"
ANSWER  service       "when's the service" · "when is the service" · "when"
                      · "the service" · "service" · "what's the service"
ANSWER  total         "what's the total" · "what is the total" · "the total" · "total"
                      · "how much" · "how much is it"
ANSWER  who           "who's it for" · "who is it for" · "who is it"
ANSWER  where         "where is it going" · "where's it going"
ANSWER  status        "where is it" · "where's it at" · "what stage"
                      · "what's the status"
```

An **exact table**, not a keyword scan, and the dispatch asked for the list for exactly
that reason. A `\bvault\b` rule would swallow "monticello vault" (a catalog request) and
"order for hopkins monticello vault" (a capture opener).

**It is gated on the front pane being an order**, which is the dispatch's own wording and
is what keeps every existing phrase working:

| phrase | order in front | list in front |
|---|---|---|
| "how much" | that order's total | **the list's total, unchanged** |

With no order in front the same phrases **ask** — with the open order panes as options, so
nothing is guessed. ⚠️ **Except where the phrase already means something else**: a context
phrase that is also an order-list phrase falls through, so a shipped behaviour is not
broken to serve a new one.

⚠️ **One edge turns on an apostrophe**, recorded because a reader will hit it. With no
order in front, `"what's the total"` matches `isOrderListPhrase`'s
`/what(?:'s| is) the total/` and goes to the list; `"whats the total"` does not match it
and gets "No order is open" from here. Two spellings, two messages. Left alone: the
alternative was editing a shipped rule with its own tests to improve a sentence in a state
where neither answer is wrong.

**"undo confirm" routes through the pane's own button**, not a second API call, so the
server's refusal message, the re-read and the notice are produced in exactly one place.
Typing it and pressing the button are the same act. The mechanism is a counter-stamped
`undoRequest`, the same shape as `CapturePane`'s `completeRequest`.

---

## 5. Three defects found by building this, none of them in the dispatch

### 5.1 `hush()` at the top of `submit` wiped the answer before it could be used

`submit` opened with a bare `hush()` — inherited from the old `setSaid(null)`, which could
only ever be clearing a hint. `hush()` now also empties `answerActions.current`, so
clearing there **wiped the outstanding question's actions** before the answer check below
could use them.

The symptom was precise and silent: typing "hart" matched one option, consumed the phrase,
closed the list — **and did nothing**. Found by the test asserting the order opened.
Fixed to `if (reply !== null && reply.kind !== "question") hush()`, and pinned by break
test **C9**.

### 5.2 The editable-field exception had two enforcement points and one test

The ruling's exception — "an editable field inside a pane that the user clicked into keeps
focus" — is enforced in the pane's `onClick` **and** in the document `keydown`. The test
exercised only the click. Break test **C3** removed the keydown guard and **everything
stayed green**: a keystroke typed into a pane's own field would have been redirected into
the bar, and nothing said so. A second test now covers that half.

### 5.3 Four of my own tests were not discriminating, and break tests found all four

| test | why it could not fail | fixed by |
|---|---|---|
| "after a pane opens from the bar" | focus was already on the bar — typing never moved it — so neutering `focusBar` changed nothing | blurring mid-flight, so the claim is about focus **returning**; plus a second test that opens a pane from a **click** |
| "a mid-phrase digit is text" | it pressed **"8"** against a 2-option question, which the range check refuses anyway | pressing "2", an in-range choice, so the empty-bar guard is the only thing that can refuse it; plus a control that empties the bar and watches the same key answer |
| "how much with a list in front totals the list" | **no order pane was open**, so a rule that ignored the front pane had nothing to act on and the list answered anyway | a second test with an order open **behind** the list — the only arrangement that distinguishes "gated on the front pane" from "gated on an order existing" |
| "a modifier combination is someone else's" | it pressed **⌘K**, which is Opas's own toggle, and tucked the overlay — the test then failed looking for a bar that had gone | ⌘A and ⌃A, plus a control proving the overlay is still open |

⚠️ Three of those four were green for a reason unrelated to what they named (CLAUDE.md §11
shape 6) and the fourth was asserting against the wrong instrument. None was found by
reading; all four were found by breaking the thing each claimed to guard.

---

## 6. The honest limit, restated

Everything Opas understands is rules. "riverside order" works; "anything going to
St. Mary's this week?" does not, and no amount of table-widening reaches it. This slice
makes the conversation's **shape** right — one voice, choices with the question, context
from what you are looking at — on rules alone. Whether a model goes behind the bar is a
separate decision and is not taken here.

---

## 7. Gates, with denominators

| gate | result | of what |
|---|---|---|
| frontend vitest | **4928 passed, 5 skipped, 1 todo, 0 failed** | **368 of 368** test files |
| `tsc -b --noEmit` | exit 0 | whole frontend |
| `npm run build` | exit 0 | — |
| backend pytest, `tests/ci_gate.txt` | **3639 passed, 4 skipped, 0 failed** | **234 of 512** test files (45.7%) — unchanged, as expected: this slice is frontend-only |

**Bundle**, same instrument and machine as the previous slice's measurement:
`index.js` 6,750.25 → **6,758.63 kB** (+8.38 kB, **+0.12%**); gzip 1,633.49 → 1,635.79 kB;
CSS unchanged at 241.55 kB.

**New: 30 host tests (`opas-talks-back.test.tsx`), 18 matcher tests (`reply.test.ts`), 27
phrase-table tests (`context-phrases.test.ts`).** Re-pointed rather than deleted: the
product-list pick test, the host-level numbered-pick test, one `pane-identity` assertion,
and one wording assertion in `opas-multipane`.

**19 break tests, each naming the assertion it had to turn red. All 19 caught** — five of
them only after the tests they exposed were fixed, which is §5.2 and §5.3.

| | break | caught by |
|---|---|---|
| C1 | `focusBar` does nothing | three focus assertions |
| C2 | the redirect focuses but does not append | "FIRST CHARACTER AND ALL" |
| C3 | the keydown editable guard removed | "A KEYPRESS WHILE A PANE'S FIELD HAS FOCUS STAYS THERE" |
| C4 | the click editable guard removed | "EXCEPT AN EDITABLE FIELD INSIDE A PANE" |
| C5 | questions fade too | "an acknowledgement fades, and a question does not" |
| C6 | nothing fades | the same |
| C7 | `matchAnswer` always `none` | "typed words answer"; "picks the Friday order" |
| C8 | an ambiguous answer takes the first option | "and NARROW when they still do not" |
| C9 | `hush()` unconditional at the top of `submit` | "typed words answer" — §5.1 |
| C10 | the bare-digit empty-bar guard removed | "BUT NOT MID-PHRASE" |
| C11 | context ignores the front pane | "WITH AN ORDER PANE OPEN BEHIND THE LIST" |
| C12 | an answer opens a pane | "is ANSWERED and opens nothing" |
| C13 | the Escape→reply sync removed | "Esc cancels the question and does NOT tuck" |
| C14 | `say` does not set `pendingPick` | the same |
| C15 | order picks routed back to a pane | "the options are numbered, above the bar" |
| C16 | the normaliser spaces apostrophes instead of dropping them | three phrase assertions |
| C17 | prefix matching becomes substring | "IS NOT A SUBSTRING RULE" |
| C18 | the `MIN_PREFIX` floor removed | "MUST REACH" |
| C19 | a table key carries an apostrophe (unreachable) | "every key in the table is already in normal form" |

---

## 8. Not verified: the real-Chrome walk

The dispatch asks for it typed character by character. **The Claude browser extension is
not connected in this environment** — checked at the start and again at the end of this
slice — and Opas is admin-only behind a login, which a password cannot cross
(CLAUDE.md §7). So the walk is James's:

**open Opas, type "hopkins order", answer the question, then keep talking without
touching the mouse.**
