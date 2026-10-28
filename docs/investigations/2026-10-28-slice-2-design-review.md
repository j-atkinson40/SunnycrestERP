# Slice 2, "words leave the bar" — design review before building

**2026-10-28.** James's dispatch says: *"If anything below conflicts with capture's
existing rules (last mention wins, claimed spans, durable picks), report the design
before building."*

**It conflicts in five places, and one of them changes a ruled behaviour that is
visible on every keystroke.** Nothing is built yet. Everything below is measured against
HEAD (`289f6da1`) and, where stated, against production read-only.

The prototype is the one already in the repo —
`docs/prototypes/2026-10-27-guided-order-capture.html`, 92,138 bytes, sha256
`34b3938d9a2dcedca7fce8f15f14c7ba62fc37a80da86d4b2ba6b58bcacd09f3`. ⚠️ The dispatch's
artifact URL does not resolve, for the fifth dispatch running.

---

## C1 — ⚠️ Clause 1 vs "resolutions outrank the text". The pane stops following the bar.

**The rule, quoted from `typed_extraction.extract_text`:**

```
⚠️ THREE TIERS SINCE 2026-10-24, AND `prefill` IS THE ONE BELOW THE TEXT:
    prefill       a pane's choice made BEFORE any text...
    text          last mention wins, as below.
    resolutions   the director's decision ABOUT ambiguous text. Outranks it.

⚠️ RESOLUTIONS OUTRANK RE-EXTRACTION, BY RULING.
```

Clause 1 makes a typed-past term **"a durable answer (like a pick)"** — a resolution —
and removes it from the bar. Clause 1 also says **"A new mention of an answered field
replaces it, as today."**

**Those two cannot both hold under the current precedence.** Once `hopkins` is a
resolution, typing `riverside` puts Riverside in the TEXT, and the resolution outranks
the text — so the row keeps saying Hopkins. The replacement only happens when Riverside
*itself* becomes typed-past and overwrites the resolution.

⚠️ **So "last mention wins" stops being a live behaviour and becomes a deferred one.**
Today the row changes on the keystroke; under slice 2 it changes when the word is typed
past. That is a real, visible change to a ruled behaviour, not an implementation detail.

**Options:**

1. **Accept the deferral** (my recommendation). A term replaces the previous answer when
   it is typed past, by the same mechanism that placed the first one. Consistent with
   clause 1's own model — the bar holds only what is still being typed — and needs no
   change to the precedence. Cost: a half-typed correction does not show in the row yet,
   which is arguably *better* than today, where "riv" briefly blanks the row.
2. **Make the text outrank resolutions that came from typing-past**, keeping clicked
   picks on top. Preserves live last-mention-wins. Cost: a third rank inside
   `resolutions`, and the "re-reading raises the same question again" problem the
   original ruling exists to prevent.
3. **Keep the word in the text and only hide it visually.** Preserves every existing
   rule exactly. Cost: the bar's value and its rendering diverge, and every caret
   calculation, the mirror, the ghost and the span offsets then work on a string the
   director cannot see. I would not do this.

**Needs James's ruling.** My recommendation is option 1, stated as a supersession of the
live half of last-mention-wins rather than a silent consequence.

---

## C2 — ⚠️ The animation's start point cannot come from a server span.

`spans_for_text` gives character offsets into the text the server was handed. Clause 1
removes the word from that text in the same gesture that animates it. So at the moment
the animation needs a rectangle, the span that would locate it is about to describe a
string that no longer contains the word.

**This is not a conflict so much as a constraint:** the flight must start from a rect
measured **client-side, before the removal**, off the existing mirror (`MIRROR_BOX`,
which already lays out an exact copy of the bar for the tint). The server span is what
identifies *which* word and *which* field; it cannot be what positions the animation.

The claimed-spans rule itself (`_free`, half-open, "abutting is not overlapping") is
unaffected — it governs extraction of whatever text remains.

**No ruling needed.** Recorded so the implementation is not attempted the other way.

---

## C3 — Clause 1's waiting rule does not exist, and `tail_open` is not it.

Clause 1: *"wait on `st marys ` because `st marys skaneateles` exists"*.

⚠️ There is an existing gate that looks like this and is not. `GATING_TAIL_OPEN` is the
**abbreviation** gate — its comment reads *"is the last word of this line also the last
word the director has typed... See the abbreviation pass for why the final word is left
alone"* — and it exists so `Hopk` does not resolve to Hopkins mid-word. That is an
INCOMPLETE word. Clause 1 is about a COMPLETE known term that is a prefix of a longer
known term.

**New rule, and buildable:** `build_vocabulary` already returns the tenant's terms and
`prefix_resolve` already walks multi-word runs. The test is "does any known term start
with this one and extend past it", which is a lookahead over the same vocabulary.

**No ruling needed.** Flagged because reusing `tail_open` would look right and be wrong.

---

## C4 — ⚠️ Clause 5's "Did you mean" collides with an existing question, in the same slot.

Measured: `session_service.DID_YOU_MEAN_BY = "Which one did you mean by “{phrase}”?"`,
already used for **ambiguous picks** — the candidate-set question — and `_guided` gives
the pick branch priority over everything:

```
⚠️ AN AMBIGUITY OUTRANKS A GAP... A pending pick is the one thing that needs the
director's hand
```

Clause 5 wants **"Did you mean Monticello?" / Yes / No** for a **typo**. Two different
questions, nearly identical wording, competing for one slot in one pane.

**They are different in kind and should read differently.** A pick says *"your words
matched several things, choose"*; a typo suggestion says *"your word matched nothing,
did you mean this"*. One is a choice among the tenant's data; the other is a correction
of the director's spelling.

**Needs James's ruling on two points:**
- **Wording**, so the two are not confusable. The pick keeps "Which one did you mean
  by…"; the typo could be the dispatch's "Did you mean Monticello?" unchanged, which is
  already distinguishable — I think this one is fine as written, but it should be a
  decision rather than an accident.
- **Ordering** when both are outstanding. My recommendation: the **pick wins**, as
  today. A pick blocks the order (it is an unresolved ambiguity in data the office
  typed); a held word does not — clause 4 says approving is still allowed with words
  held. The lower-stakes question should not displace the blocking one.

---

## C5 — ⚠️ Clause 3 gives Tab a second job, and Tab carries a ruling.

Measured, in `OpasHost`:

```
⚠️ TAB ACCEPTS THE GHOST AND NEVER LEAVES THE BAR WHILE CAPTURING, by ruling.
`preventDefault` is the whole mechanism... It is called even when there is NO
ghost, because a Tab that sometimes moves focus and sometimes does not is worse
than either
```

Clause 3: *"Tab places what's typed and moves on"* + *"Tab never leaves the bar during
capture"*. The second half agrees exactly. The first half adds a job, and clause 1 keeps
the ghost: *"Ghost completion still works on the word under the caret."*

**So what does Tab do when a ghost is showing?** Complete the word, or place what is
typed?

**Needs James's ruling.** My recommendation: **accept the ghost, and let the completed
term fly in the same gesture** — one key, two effects, in the order the director would
expect ("monti" + Tab → completes to Monticello → flies to the Vault row). Tab with no
ghost places what is typed. That keeps both rulings true and makes Tab mean one thing:
"finish this word and put it away".

---

## C6 — Held words need their own column. `unrecognized` cannot hold them.

⚠️ I expected to be able to reuse `unrecognized` and it is measurably the wrong home.

```
unrecognized: tuple[str, ...]          -- plain strings, NO position, NO state
```

and it is **recomputed from the text on every read**. Measured on production, five
sessions with non-empty values:

```
text='order for hopkins monticello for smith friday at 1 chu'
  unrecognized = ['smith', '1', '1 oclock church', 'friday']
text="order for hopkins monticello going to St. Mary's"
  unrecognized = ["St Mary's"]
```

Two things follow. It is **transient** — held words must survive the next keystroke,
be retried after each answer, be dragged and edited. And once words LEAVE the bar
(clause 1), a list computed from the text **cannot see them at all**.

**So: a new column, which the dispatch already authorises** ("expand-only migration if
needed, James's go"). Shape it needs, from clauses 4, 5 and 6: the word as typed, where
it came from, whether a suggestion has been declined for it (clause 5's "never asks
about that word again"), and enough to retry it.

**No ruling needed beyond the go already given.** Recorded because "reuse `unrecognized`"
is the obvious wrong turn.

---

## C7 — Clause 2 needs to exclude the noise list.

Clause 2: unknown words right before a recognized term become the Deceased name.

`_NOISE_WORDS` (in `typed_extraction`) contains, among others: `service`, `burial`,
`cemetery`, `funeral`, `home`, `decedent`, `deceased`, `print`, `date`, `time`, `day`.
Their comment: *"Label words a director says around a value rather than as one."*

So "**service** monti" must not make *Service* the deceased's name. Clause 2's rule has
to skip noise words, which is a one-line condition but is not stated in the dispatch.

⚠️ And clause 2's "within 2 letters of a known term → it's a typo, hold it" uses the same
distance as clause 5's "within 2 letters of exactly one known term → Did you mean". Those
agree, which is worth saying explicitly: **one distance, two uses** — holding and
suggesting — so they must come from one function or they will drift.

**No ruling needed.**

---

## What I can build without any of the above

- **C2's span/rect mechanics** (client-side rect before removal) — constrained, not contested.
- **C3's lookahead** ("is a longer known term still forming") — new, uncontested.
- **C6's column + the held-word model** — authorised.
- **C7's noise exclusion and the single edit-distance function** — uncontested.
- **Clause 6's log verbs** — `decision_log` already has `record_ask` / `record_resolve` /
  `record_capture_open`; held/dragged/edited/suggested/accepted/declined are additions in
  the same shape. The alias candidates (`montcello -> Monticello`, recorded not applied)
  are a new table or a JSON list; **that one wants a shape decision** but no behaviour ruling.

## What is blocked

- **C1** — the core mechanic. Everything in clause 1 depends on which option is taken,
  and option 2 would change `extract_text`'s tiers for every caller.
- **C4** — the ordering of the two "did you mean" questions.
- **C5** — what Tab does when a ghost is showing.

Three decisions. I have a recommendation for each and have not acted on any of them.
