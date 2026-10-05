# Does the server distinguish NOT_CONFIGURED? Measured.

**Read-only. 2026-10-05.** Asked before building Part 1's fourth state.

## Answer: it computes the distinction, carries it one function, then discards it

| layer | does it distinguish? | how |
|---|---|---|
| `read_availability` | **yes** | returns `AvailabilityState.OFFERED` with permitted answers, vs `NOT_CONFIGURED` with none |
| `resolve_schema` → `ResolvedField` | **yes** | a *conditional* field with `permitted_answers == ()` **is** NOT_CONFIGURED |
| `evaluate` → `CaptureState` | **no — discarded** | three tuples of field ids: `answered`, `missing`, `not_applicable` |

Measured with two vaults and the same unanswered question:

```
read_availability(vault-all-three    ) -> OFFERED         permitted=('legacy_series','legacy_custom_series')
read_availability(vault-unconfigured ) -> NOT_CONFIGURED  permitted=()

resolve_schema(vault-all-three    ) -> present=True  permitted_answers=('legacy_series','legacy_custom_series')
resolve_schema(vault-unconfigured ) -> present=True  permitted_answers=()

evaluate(...) for BOTH vaults:
    answered       = ()
    missing        = (… 'legacy_print', 'nameplate_cover_emblem', 'lifes_reflections')
    not_applicable = ()
```

**The two `CaptureState`s are identical.** `'legacy_print' in missing` is `True` for
the offered vault and `True` for the unconfigured one. A client cannot tell them
apart from the server's output, so the fourth state is currently **not
renderable** — not because the engine does not know, but because the output type
has no room for it.

⚠️ **The loss is at one boundary and it is one line wide.** `resolve_schema`
returns `tuple[ResolvedField, ...]`, which carries availability. `evaluate`
reduces that to three id-tuples. The richer value exists and is thrown away by
the next function.

**And the derivation needs no new computation.** On a `ResolvedField`,
`is_conditional and not permitted_answers` is unambiguously NOT_CONFIGURED:
`read_availability`'s own contract sends `NOT_OFFERED` (question present, empty
list) down the `continue` branch, so it never becomes a `ResolvedField` at all.
Conditional + empty permitted has exactly one meaning.

## So: it collapses. The fix is server-side.

Per the dispatch's own branch — *"If it collapses: the fix is server-side, same as
Piece 2, and the client gets a third set rather than deriving a fourth state from
two."*

⚠️ **But a third set is the wrong shape, and Part 1 already says why.** The client
is not assembling lists; it renders the template's fields **once**, each row in a
state. Four id-sets to join into rows is the same join the 3b decision refused —
one more set makes the client's work harder, not easier.

The shape both halves of Part 1 want is the same one: **ordered rows, each with a
label and a state.** `answered` / `missing` / `not_applicable` / `not_configured`
are then *derivable from the rows* rather than being four parallel collections, and
the header counts derive from them too. That is one output type replacing
`CaptureState`'s three tuples, not an addition to them.

## The pattern, now at three instances

The capture engine has repeatedly been **the only thing that knows, and the thing
that does not say**:

| what the server knew | where it went |
|---|---|
| `capture_state.answered` | computed, written to one log line, discarded (fixed by r197) |
| each field's **label and order** | `FieldDefinition.label`, never serialized — Part 1 |
| `NOT_CONFIGURED` | computed in `read_availability`, carried on `ResolvedField`, dropped by `CaptureState` |

Same mechanism every time: **the engine's internal representation is richer than
its output type**, and the client then either re-derives badly or cannot render at
all. Twice it produced a hardcoded client list; once it produced a state nothing
can show.

⚠️ Worth stating as the thing to check rather than the thing to remember: when an
engine's output type is narrower than the values it computed, name what was
dropped and why — or the next surface will re-derive it from whatever it can see.

## Method

Constructed inputs against `tests/_capture_fixtures.py`'s existing vault configs
(`VAULT_ALL_THREE`, `VAULT_UNCONFIGURED`), which already model exactly these two
cases. Control reported first: 12 template fields, probing `legacy_print`. No DB
write, no Claude call. The comparison is between two `CaptureState`s, so it cannot
pass by a shared mistake in how either was built.
