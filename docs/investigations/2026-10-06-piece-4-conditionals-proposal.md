# Piece 4 — conditional fields: design proposal

**2026-10-06. PROPOSAL ONLY — nothing built.** Origin: James's dispatch of 2026-10-06.

---

## 0. The inventory does not reconcile with its own count

Read from `app/services/capture/schema.py:163-184` rather than inherited.

The comment enumerates **five** value-dependent conditions:

| field | slot | condition |
|---|---|---|
| `date_of_birth` | **required when** | any personalization is chosen |
| `date_of_death` | **required when** | any personalization is chosen |
| `nameplate_date_format` | **applies when** | any personalization is chosen |
| `service_location_other` | **applies when** | `service_location == "other"` |
| `eta` | **applies when** | `service_location != "graveside"` |

Plus **three** availability-gated fields (`legacy_print`, `nameplate_cover_emblem`,
`lifes_reflections`), which the comment calls the exception.

**Derived total: 8 field-level conditions. Not 7.**

⚠️ And `schema.py:177` says *"FIVE OF THE SEVEN HANG OFF ONE CHOICE —
personalization"*. Of the five enumerated, **three** hang off personalization; the
other two hang off `service_location`. Counting the three availability questions as
personalization-related gives six of eight, not five of seven.

**This is not a quibble about a number — it decides whether the design covers
everything.** Two numbers are in play (7 and 8) and two groupings (5-of-7 and
6-of-8), and the comment is the artifact Piece 4 was told to derive from. I am
proposing against the **enumeration**, which is unambiguous, and flagging the count
for ruling. Per §11 the count travelled separately from the list, which is how both
came to be wrong at once.

**Also noted:** `eta` is not a `FieldDefinition` in `PLATFORM_DEFAULT_FIELDS` today —
it appears in the inventory and in `rows.py`'s prototype comments. The design below
treats it as a field to be added, not an existing one.

---

## a. How a field declares a condition — and why availability is the exception, not the model

Replace `question_id: str | None` with two optional condition slots. A condition is a
**declarative node**, not a callable: a callable cannot be inspected, cannot declare
its own edges, and cannot be tested apart from the engine.

```python
@dataclass(frozen=True)
class EqualsValue:      field_id: str; value: object
@dataclass(frozen=True)
class NotEqualsValue:   field_id: str; value: object
@dataclass(frozen=True)
class AnyAnswered:      field_ids: tuple[str, ...]; ignoring: frozenset[str]
@dataclass(frozen=True)
class AvailabilityOffered: question_id: str      # ← THE EXCEPTION
@dataclass(frozen=True)
class Always: pass
@dataclass(frozen=True)
class Never: pass
```

Every node exposes two things and nothing else:

```python
node.depends_on -> tuple[str, ...]        # field ids it reads. THE EDGE SET.
node.evaluate(ctx) -> TRUE | FALSE | INDETERMINATE
```

**The availability lookup fits by declaring a field dependency, not a new kind.**

```python
AvailabilityOffered.depends_on == (VAULT_FIELD_ID,)
```

The lookup's *input source* is external (the licensee's `personalization_config`),
but its *dependency* is a captured field — the vault, because you cannot look up
availability without knowing which vault. So it is an ordinary node over an
extended context:

```python
@dataclass(frozen=True)
class ConditionContext:
    answers: Mapping[str, object]          # the capture payload
    decided: Mapping[str, Applicability]   # fields already resolved this pass
    vault_product_id: str | None           # DERIVED from answers, see (f)
    personalization_config: dict | None    # licensee config
```

Most nodes read `ctx.answers`. `AvailabilityOffered` reads
`ctx.personalization_config` keyed by `ctx.vault_product_id`. Same protocol,
different source — which is the precise sense in which availability is *the
exception, not the model*: it is one node type among six, and the load-bearing shape
is value-dependence, as `schema.py:177` insists.

**What a third shape costs, stated rather than assumed free.** A tenant setting, a
user role, a time of day, another object's state: **one new node type + one field on
`ConditionContext`**. Two edits, bounded, no change to `evaluate`'s order or to the
partition. If a proposed third shape cannot be expressed that way, that is a finding
about this design and should stop it.

---

## b. The new evaluation order, and what it costs

**Resolve-then-compare cannot survive.** `resolve_schema` resolves applicability once,
up front, from configuration; value conditions are answerable only from the answers.

**And the dependency is not flat — it chains.** Availability decides whether the three
personalization questions apply; their answers decide whether the dates are required.
So condition inputs can themselves be conditional fields. A two-pass design would
cover exactly this depth and fail on the next one — the single-instance generalisation
this arc has spent three days catching. The design is therefore a **DAG walk**:

```
1. normalise answers, keyed by field_id
2. derive vault_product_id from answers (see (f)) — the input to availability
3. build the dependency graph: edge f -> g for each g in (applies_when ∪
   required_when).depends_on of f
4. topologically sort. ⚠️ RAISE ON CYCLE — a cycle is a template defect, and a
   silent tie-break would make it unobservable
5. walk in topo order; for each field:
     tenant switched it off              -> NOT_APPLICABLE
     applies_when is None or Always      -> APPLIES
     applies_when evaluable              -> APPLIES / DOES_NOT_APPLY
     applies_when INDETERMINATE          -> INDETERMINATE          (see (d))
   then, for fields that APPLY and are unanswered:
     required_when TRUE                  -> missing
     required_when FALSE                 -> unanswered_optional
     required_when INDETERMINATE         -> unanswered_optional     (see (d))
6. partition
```

Step 4 is what makes this honest: the edges are **declared** by each node, so the
graph is derived from the template rather than from the author's memory of which
field reads which.

### What it costs the existing personalization path

1. **`resolve_schema`'s signature changes.** It can no longer be called without
   answers. Every caller that passes `vault_product_id` explicitly changes:
   `evaluate`, `resolve_and_evaluate` in `call_extraction_service`, the surface
   resolution in `rows.py`/`surfaces.py`, and the `_capture_fixtures` helpers.
2. **⚠️ A SHIPPED BEHAVIOUR CHANGES, and this is the real cost.** Today
   `resolve_schema`'s docstring rules that with `vault_product_id=None` the three
   conditional questions are **omitted** — "applicability is UNKNOWN until a vault is
   named, and unknown is not shown" (ruled 2026-09-22, *The capture list shows only
   the questions that apply*). Under this design that case becomes `INDETERMINATE`,
   a state the engine now distinguishes from NOT_OFFERED.

   **Proposed resolution: keep the display ruling, gain the internal distinction.**
   The capture surface still renders nothing for an INDETERMINATE field, so the
   2026-09-22 ruling stands unamended at the surface. What changes is that
   `CaptureState` can now tell "this vault does not offer it" from "we cannot know
   yet" — which today are the same silence. ⚠️ If James would rather the ruling be
   revisited so unknown becomes visible, that is a separate ruling and this proposal
   does not assume it.
3. **The three personalization fields lose `question_id`.** `is_conditional` becomes
   `applies_when is not None`. `_personalization_fields()` emits
   `applies_when=AvailabilityOffered(q.question_id)` instead.

---

## c. "Required when" vs "prompted when" — one machinery, two slots

**Two slots, one evaluation mechanism.** Not one, and not two mechanisms.

The inventory itself proves two slots are needed: it says **required when** for the
dates and **applies when** for `nameplate_date_format`. Those are different claims.
The dates are always *shown*; they become a *gap* only under personalization.
Collapsing them into one condition would hide the dates until personalization was
chosen, which the inventory does not say and which would be a display regression.

```python
FieldDefinition("date_of_birth",   applies_when=Always(),
                                   required_when=AnyAnswered(PERSONALIZATION, ignoring={"none"}))
FieldDefinition("nameplate_date_format",
                                   applies_when=AnyAnswered(PERSONALIZATION, ignoring={"none"}),
                                   required_when=Always())
FieldDefinition("service_location_other",
                                   applies_when=EqualsValue("service_location", "other"),
                                   required_when=Always())
FieldDefinition("eta",             applies_when=NotEqualsValue("service_location", "graveside"),
                                   required_when=Never())          # ← PROMPTED, never required
```

`required: bool` is retired in favour of `required_when=Always() | Never()`. One field,
one spelling, no second way to say the same thing.

**`eta` lands in `unanswered_optional`** — applicable, unanswered, not a gap. That set
was added 2026-10-05 and `is_complete` deliberately ignores it, so `eta` is asked for
and cannot block approval, which is exactly the dispatch's requirement. ⚠️ This is the
set's first population by a *value*-conditional field, and that it fits without
amendment is evidence the 2026-10-05 partition was drawn in the right place.

---

## d. A field whose condition cannot be evaluated yet

Canon's name: *depends on an answer not yet given.*

**How it is computed.** A node returns `INDETERMINATE` when any field in its
`depends_on` is **applicable and unanswered**. It does *not* return INDETERMINATE
when the dependency is:

- answered — including answered `"none"`, which is an answer (see (e));
- `NOT_APPLICABLE` — there is nothing to wait for, so the node resolves definitively.

Topo order guarantees every dependency's applicability is already `decided` when a
node is evaluated, which is what makes the second bullet computable at all.

**Which set it lands in — and the partition is preserved by splitting on the slot.**

| indeterminate slot | lands in | why |
|---|---|---|
| `applies_when` | **new set `indeterminate`** | membership itself is unknown: not answered, not a known gap, and *not* `not_applicable` — we have not established that it doesn't apply |
| `required_when` | existing **`unanswered_optional`** | the field *applies* and is unanswered; only its gap-ness is unknown |

⚠️ **This adds a FIFTH set, and `CaptureState`'s docstring currently asserts the four
exhaust and are disjoint.** That assertion becomes false the moment this lands —
§"when a file's data changes, its own description of that data is part of the change"
applies, and the docstring is part of the diff, not a follow-up.

Five sets still exhaust and are still disjoint. `is_complete` stays
`return not self.missing`, so:

⚠️ **An indeterminate requirement never blocks approval. That is deliberate and must
be stated.** `date_of_birth` will not block an order while personalization is
unanswered. This is correct rather than lax: *personalization being unanswered is
itself in `missing`*, so the order is already incomplete for the honest reason, and
reporting the dates as missing too would report one gap twice.

---

## e. "Any personalization is chosen" as a predicate

`ANSWER_NONE = "none"` (`app/services/personalization/questions.py:49`), and that
file states: *"none" IS AN ANSWER TO EVERY QUESTION, NOT AN ABSENCE.*

```
AnyAnswered(field_ids, ignoring={"none"}) is

  TRUE           iff ∃ f ∈ field_ids : f APPLIES ∧ f is answered ∧ answers[f] ∉ ignoring
  FALSE          iff ∀ f ∈ field_ids : f does NOT apply, OR (answered ∧ ∈ ignoring)
  INDETERMINATE  otherwise — i.e. some applicable f is unanswered
```

Three consequences, each a case the predicate must get right:

1. **All three answered `"none"` → FALSE.** The dates are not required and
   `nameplate_date_format` does not apply. This is the dispatch's explicit
   requirement and the reason `ignoring` exists rather than a truthiness test.
2. **All three unanswered → INDETERMINATE, not FALSE.** ⚠️ If this collapsed to
   FALSE, an order would not require the dates, and then would *start* requiring
   them the moment someone picked a flag — a requirement appearing mid-flow with no
   explanation. (d) exists for this case.
3. **All three NOT_APPLICABLE (the vault offers none) → FALSE, not INDETERMINATE.**
   There is nothing to choose, so the answer is settled. ⚠️ **This is why the
   quantifier is over APPLICABLE fields and why topo order is load-bearing:** the
   questions' applicability must be decided before the dates' requirement is
   evaluated. A flat two-pass design gets this case wrong.

---

## f. Can `vault_product_id` become optional? And what a second object type declares

**Yes — it stops being a parameter and becomes DERIVED.** Today it is passed in.
Under this design the vault is just another field whose answer feeds a condition
(`AvailabilityOffered.depends_on == (VAULT_FIELD_ID,)`), so the engine resolves it
internally through `product_name_resolver` and
`resolve_schema(vault_product_id=…, personalization_config=…)` collapses to
`resolve_schema(answers=…, context=…)`.

⚠️ **One caveat, and it is a correctness gain.** The resolver returns *a candidate set
plus discriminator, never a best match* (ruled), so `Resolution.variant_template_id`
is `None` when ambiguous. An **ambiguous** vault therefore makes availability
`INDETERMINATE`, not `NOT_OFFERED`. Today ambiguity and absence both omit the
questions — the same silence for two different facts.

**A second object type declares:** its field tuple, as a row in the
`CAPTURE_TEMPLATES` registry — unchanged, because `resolve_schema` already takes
`platform_fields` as a keyword. It declares **nothing further** if its conditions use
existing node types. If it needs a new condition source, it declares one node type and
one `ConditionContext` field, per (a).

**That is the test of whether this generalises**, and it should be applied before
building: take `quote` or `email` — both named in the registry docstring as having no
template anywhere — and write their conditions against this algebra on paper. If
either needs a change to `evaluate`'s order or to the partition, the design is wrong.

---

## Open, for ruling — not assumed

1. **The count.** 7 or 8 (§0). I propose against the enumeration; the comment's
   figures need correcting either way, and the correction belongs in `schema.py`
   with the original preserved.
2. **Whether INDETERMINATE is shown.** I propose keeping the 2026-09-22 display
   ruling and gaining only the internal distinction (b.2).
3. **`eta` does not exist as a field yet.** It is in the inventory and in the
   prototype comments; adding it is part of Piece 4 or is separate.
4. **The fifth set.** It amends a docstring that asserts four exhaust (d).
5. **Where the resolver is called.** Deriving `vault_product_id` inside the engine
   puts a DB-reading resolver inside what is currently a pure function over config
   and answers. Alternative: the caller resolves and passes a `Resolution`, keeping
   `evaluate` pure. ⚠️ **I lean to the second** — purity here is what makes the
   engine testable without a database, and `resolve_and_evaluate` already exists as
   the impure seam for exactly this reason.
