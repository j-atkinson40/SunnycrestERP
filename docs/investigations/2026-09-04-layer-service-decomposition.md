# Layer-service decomposition, and two STOPs from session 1

**Date:** 2026-09-04 · **Read-only.** No code written this pass — session 1's
build is held on the first STOP below.

Session 1 asked for `operational_layer_service` decomposed against the two
registers. That is delivered in §1. Two STOP lines from the dispatch were hit;
both are in §3 and §4, surfaced rather than decided.

---

## 1. The decomposition — all four layer services, not just the one asked for

The dispatch said to enumerate rather than inherit, so all four were measured.
Counted as occurrences of `kind="…"` in each service, which is the emitted item
kind:

| layer service | LOC | `kind="stream"` | `kind="widget"` | → fragments | → standing entries |
|---|---:|---:|---:|---:|---:|
| `anomaly_layer_service` | 264 | 2 | 1 | 2 | 1 |
| **`operational_layer_service`** | **291** | **0** | **1** | **0** | **1 site, 8 widgets** |
| `personal_layer_service` | 310 | 4 | 0 | 4 | 0 |
| `activity_layer_service` | 187 | 1 | 1 | 1 | 1 |

⚠️ **`operational_layer_service` produces ZERO fragments.** It is entirely
widgets — a `work_area → widget` mapping with a vertical-default fallback. It
maps wholly into the standing-set register and contributes nothing to prose.

This is the mirror of the anomaly discriminator and it changes the arc's shape:
the two registers are not fed evenly by the four services. Prose comes almost
entirely from `personal` (4) and `anomaly` (2); the standing set comes from
`operational`.

### Answering session 1's three reporting questions

**How many fragments, how many standing entries** — 0 and 1-site/8-widgets, above.

**Were queries reused verbatim** — not applicable, and that is the finding.
There are no queries to reuse. `operational_layer_service` performs no data
access of its own: it emits `component_key`s and each widget self-fetches
through its own tenant-scoped endpoint (the file states this explicitly as the
canonical Phase W-3 pattern, and it is why the service has no tenant-isolation
burden). Decomposing it is a mapping-table move, not a query move.

**Did the synthesis move behave as it did for anomaly_layer_service** —
**the question does not arise.** Synthesis was the expensive, non-amortising part
of the anomaly decomposition because prose had to move server-side to carry
entity ids. `operational_layer_service` emits no prose, so there is nothing to
move.

### ⚠️ Consequence for the 5-session estimate

The estimate was built on the anomaly discriminator, where per-fragment synthesis
was the cost that does not amortise. Two of the remaining three services
(`personal` at 4 streams, `activity` at 1) will pay that cost. **One —
`operational`, the largest at 291 LOC — will not pay it at all.**

So 5 sessions still looks right, but for a different reason than assumed: the
largest service is the cheapest, and the cost concentrates in `personal_layer_service`,
which has more streams than the anomaly service that set the estimate. Recommend
`personal` as the confirmation rather than `operational`, since it is now the
one carrying the risk.

---

## 2. Distinct-subject counting is already necessary at the first entry

The dispatch added distinct-subject counting to the standing set and called it
concrete. It is more concrete than that: the operational layer maps
`"Accounting"` to the `anomalies` widget, and a count over that widget's source
is a count over `agent_anomalies`.

Measured on production earlier today: 2,084 unresolved rows, of which
`expense_no_gl_mapping` is 1,825 rows carrying **one** distinct description and
`expense_classification_failed` is 192 rows carrying **one**. A raw row count
renders **~2,084**; a distinct-subject count renders **~50**.

So the first standing entry the operational layer produces is already one where
the two counts differ by roughly forty-fold. This is not a future hazard.

---

## 3. ⚠️ STOP 1 — the Focus layout-state pattern has no role tier

The dispatch: "Three-tier configuration matching the Focus layout-state pattern:
tenant default, per-role, per-user override."

Measured. `app/models/focus_session.py:14-17` states the cascade:

```
active user session → recent closed user session → tenant default → null
```

implemented in `focus_session_service.resolve_layout_state`. The three tiers are
**two user-scoped tiers plus a tenant baseline.** The second tier is a
resume-window nicety — "recent closed session" — not a configuration layer.

**There is no role tier, and the pattern cannot supply one.** Reusing it as
named would produce tenant → user, with the role tier invented.

**A role-keyed precedent does exist, elsewhere and in a different medium.**
`spaces/registry.py::SEED_TEMPLATES` is keyed on `(vertical, role_slug)`, as is
the saved-views seed. Those are **code-declared templates**, not stored config —
the same code-declared/config-enabled split the fragment registry follows.

**Proposed resolution, not adopted:** role tier as code-declared templates
following the spaces precedent; tenant default and per-user override as stored
rows following the Focus precedent. That composes two existing in-repo patterns
rather than inventing a tier, and it puts the role layer on the side of the split
where "referenced most days" is a design decision rather than tenant data.

Surfaced rather than decided, per the STOP line. **Session 1's items 1 and 2 are
held on this**, because the note-shell storage and the standing-set storage want
one migration between them, and that migration's shape depends on the answer.

---

## 4. ⚠️ STOP 2 — the operational layer's widget set exceeds the cap

Eight distinct widget keys, read from `WORK_AREA_WIDGET_MAPPING`
(`operational_layer_service.py:64`) rather than from the docstring table above
it: `anomalies`, `ar_summary`, `line_status`, `recent_activity`,
`scheduling.ancillary-pool`, `today`, `urn_catalog_status`, `vault_schedule`.

**Eight distinct widgets against a standing-set cap of seven per role.**

A user holding several work areas — the dispatcher composition alone maps
Delivery Scheduling to three — can be entitled to more standing entries than the
cap permits.

This is **not** a case for raising the cap. DECISIONS 2026-09-04 is explicit:
"a role approaching 7 is a signal about that role's design, not grounds to raise
the cap." So the finding is that the operational layer's mapping is too broad
for the standing register as canon defines it, and the excess has to go
somewhere — prose, peek payloads, or simply not surfacing.

That is a design question about which widgets earn permanence, and it is the
operator's, not the investigator's. Surfaced under "any layer-service output
that fits neither register": eight fit the register individually, and
collectively they do not fit.

---

## 5. Method notes

- All four layer services enumerated from the directory; the dispatch's figure of
  291 LOC for `operational_layer_service` was verified, not taken.
- Widget keys read from the code's mapping dict, not from the docstring table
  above it — the two agree here, but the docstring is prose and the dict is what
  runs.
- `kind=` counts are occurrences, not lines. ⚠️ The single `kind="widget"`
  occurrence in `operational_layer_service` is inside a loop over the mapping,
  so it emits many items from one site — an occurrence count of emission sites,
  not of emitted items. Stated because reading it as "one widget" would be the
  signatures-are-not-implementations error.
- Production figures in §2 are from `2026-09-04-approval-queue.md`, measured
  earlier today, and are marked there as measured.
