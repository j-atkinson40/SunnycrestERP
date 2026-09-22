# Proposed stored shape for personalization availability

**2026-09-22.** Reported before any schema migration, as the dispatch requires.
⚠️ **The proposal is ADDITIVE and needs no migration at all** — see below.

## The shape

A new `availability` key inside the existing
`wilbert_program_enrollments.personalization_config` JSONB column. The existing
`options` key is untouched.

```json
{
  "options": { "…": "unchanged" },
  "availability": {
    "<product_id>": {
      "<question_id>": ["<permitted answer>", "…"]
    }
  }
}
```

## Why additive, and what that means

| | |
|---|---|
| new column | none |
| new table | none |
| new constraint | none |
| altered column | none |
| existing key changed | none — `options` is read and written exactly as before |

The column is already `JSONB` and already nullable. Adding a key to a JSON
document is not a schema change, so **no migration is required for Part 3**, and
the r185 migration in this commit is for the *order record*, not for this.

⚠️ That also means this shape can be adopted incrementally: a tenant with no
`availability` key reads as NOT_CONFIGURED for every product, which is the
correct answer for a tenant nobody has configured, and is what all of them are
today.

## The three states, and why the shape has to be this way

| stored | state |
|---|---|
| product id absent from `availability` | `NOT_CONFIGURED` |
| product present, question key absent | `NOT_CONFIGURED` (partial configuration) |
| product present, question maps to `[]` | `NOT_OFFERED` |
| product present, question maps to a non-empty list | `OFFERED`, with those answers |

⚠️ **An empty list is the only way to say "not offered", and it has to be typed
deliberately.** That is the whole design: silence and refusal must not have the
same representation, because today they do — a missing enrollment errors to
`{"options": []}` and every caller reads it as "nothing offered".

`none` is never stored in a permitted set. It is permitted wherever the question
is offered at all, because a family may always decline, and storing it would let
someone write a set that forbids declining.

## The four reference cases, expressed

```json
"availability": {
  "<premium vault id>":  {"nameplate_cover_emblem":
                            ["nameplate_only", "nameplate_and_cover_emblem"]},
  "<continental id>":    {"nameplate_cover_emblem": ["nameplate_only"]},
  "<salute id>":         {"nameplate_cover_emblem":
                            ["nameplate_only", "cover_emblem_only",
                             "nameplate_and_cover_emblem"]},
  "<monticello id>":     {"nameplate_cover_emblem": []}
}
```

All four are expressible, and Salute — the only one permitting emblem without
nameplate, and the case most likely to be lost by a shape designed around the
premium vaults — needs no special case. It is just a longer list.

## What this shape does NOT do

- It does not validate stored orders. `availability.py` has no
  `validate_record_against_availability`, deliberately: the one production
  record is an emblem on a vault that offers nothing, and no read path may fail
  because of it.
- It does not replace `PERSONALIZATION_TIERS`. Those become seed defaults for
  configuring a new licensee and are no longer consulted at read time.
- It does not express price. `price_overrides_by_product` already exists beside
  `options` and is out of scope here.
