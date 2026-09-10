# What the §1a and §3 rewrites must say

**Date:** 2026-09-10 · **Author:** executor · **For:** James to author from.

Per the steps 4–5 dispatch: this session may not author `CLAUDE.md` or
`PLATFORM_ARCHITECTURE.md`. **No replacement text is drafted below.** For each
site: what is now true in code, what the current text asserts that is false, and
what the markers themselves now get wrong.

Measured against the working tree with Pulse removed — 35 files deleted, backend
and frontend, migration `r182` applied.

---

## 0. The markers are now wrong in three places, and they are the newest text

This matters more than any individual site, because a marker is what a reader
trusts when they distrust the section under it.

| Marker | Claim | Now |
|---|---|---|
| CLAUDE.md §1a | "`/home` serves the Pulse surface to every authenticated tenant user today (`frontend/src/components/root-redirect.tsx`), **across 115 code files**" | `/home` serves the note. `root-redirect.tsx` is unchanged and still correct as the redirect's location. **The 115 figure was never re-derived and should not be inherited into the rewrite** — this session deleted 35 files; the remainder were references, not implementation. |
| CLAUDE.md §1a | "The rewrite ships with the implementation, not before it." | Satisfied. This is the commit it ships in. |
| PLATFORM_ARCHITECTURE §3 | "Pulse is shipped across 115 code files **and is the tenant front door**." | Neither half holds. |

**Both markers come down in the same commit as the rewrite.** They describe a
future that has arrived; leaving them is the same defect in the other direction.

---

## 1. CLAUDE.md §1a — the nine sites

What is true in code, for all nine: **there is no hub dashboard.** `/home` renders
`NotePage`. Monitoring is a per-user per-day note — a configured, positionally
stable **standing set** (label + live count, no badges, no affordances) plus
**composed prose fragments** that appear only when there is something to say.
Widgets still exist and are still composed, but on **Focus accessory layers,
Space pins, command-bar surfaces and park tablets** — never on a monitoring hub.

### Site 1 — the section title
"Monitor through hubs. Act through the command bar." The Act half is untouched.
The Monitor half names a surface that no longer exists.

### Site 2 — MODE 1 — MONITORING (Hub Dashboards), in full
Every clause is now false as written: "Hub dashboards are role-aware", "Widgets
are the unit of monitoring", "A user scanning their hub". The *intent* survives
exactly — information comes to the user, they do not hunt for it, and a user
should know their day without clicking. Only the vehicle changed.

⚠️ One clause needs care rather than substitution: **"Widgets are the unit of
monitoring."** The note's unit is a **fragment** (prose + typed links) over a
**standing line** (label + count). Those are two units, not one, and the note
arc's central claim is that the split is load-bearing — the standing set is the
floor, prose is the exception layer.

### Site 3 — Decision Framework Question 1
"Does the user need to NOTICE this without asking? → it belongs in a hub
dashboard widget." The question stands; the destination is now the note, and the
answer forks: **ambient and referenced most days → a standing line; needs saying
today → a prose fragment.** The admission test for the standing set is
"referenced most days", capped at 7 per role.

### Site 4 — the "if a feature is both" block
"Put a summary widget on the hub. The widget has a quick-action button." No hub,
and ⚠️ **no quick-action either**: a standing line carries a count and
deliberately carries no affordance — a standing line does not open a Focus on
click (ruled 2026-09-04, re-ruled after session 3's bridge was reverted on
operator review). Where a fragment opens a Focus it does so **scoped**, carrying
its predicate.

### Site 5 — the INCOMPLETE clause
"has no command bar workflow or hub widget entry point". The shape survives; the
second entry point is now a declared fragment or a standing line.

### Site 6 — the COMPLETE clause
"Monitoring aspects surface in the appropriate hub."

### Site 7 — Rule 2
"Never design a monitoring feature as page-only… must have a hub widget
representation."

### Site 8 — Rule 3 ⚠️ THE ONE THAT CHANGES STATE
The four-leg completeness test is **SUSPENDED**, not shortened, and has been
since 2026-09-04. Its first leg is "which hub(s) get a widget". Every feature
designed since has passed a three-leg gate.

**The rewrite un-suspends it.** That is the single highest-value line in this
report: the arc has been running with a stated design gate switched off, and
nothing but the marker records that. The replacement fourth leg is whatever the
note's equivalent is — which register the feature lands in, and under what
condition.

### Site 9 — Rule 4
"When writing a build prompt, always include: the hub widget if the feature has
a monitoring aspect."

**Unaffected and explicitly in force: Rules 1, 5, 6 and MODE 2**, per the marker.
Nothing in the removal touches the command bar.

---

## 2. PLATFORM_ARCHITECTURE §3

### §3.1 The Monitor Reframe — rewrite the last sentence only
The dashboard-list critique is the document's best passage and is **untouched by
the removal**: filing systems fail at discovering what is relevant now, surfacing
what changed, adapting to role and time of day. The note arc agrees with all of
it and goes further.

Only the final sentence is superseded: *"Each Space has one composed Monitor
surface (the Pulse / Home), not a sidebar list of destinations."* Now: **one note
per user per day**, with Space acting as a **filter on which fragments appear**
rather than as a surface boundary. The human has one day; cross-day questions
live above the Space boundary.

### §3.2 What Monitor Should Actually Do — NOT SUPERSEDED, and worth saying so louder
Its five obligations remain the test. The note answers all five: 1/3/5 in prose,
2 in the standing set, 4 in peeks and scoped Focus entrances. §3.2's own closing
line — *"A static dashboard list does maybe 30% of #4 and nothing else"* —
indicts the dashboard on the document's own terms, which is why the thesis
survives its execution.

### §3.3 The Pulse Surface (per Space) — superseded, plus a stale code reference
The four layers (Personal / Operational / Anomaly / Activity) are gone as a
composition model. "When a user enters a Space, they land on its Pulse" is false.

⚠️ **§3.3 also carries a "Task substrate consumption (v1.5)" subsection that
points at deleted code**: `_build_tasks_item` at
`backend/app/services/pulse/personal_layer_service.py:111`, and the
`pulse_invalidator` subscriber. Both are removed. The task substrate is
unaffected — it now has **7 subscribers, and every one of the 7 event types
still has at least one**, verified by enumeration and by a new invariant test.
This subsection needs deleting or repointing, and it is easy to miss because it
reads as task-substrate canon rather than as Pulse canon.

### §3.4 Components of the Monitor Surface — superseded, but one line survives
The eight-component list is Pulse's assembly model.

⚠️ Its closing line is the one thing here worth carrying forward:
*"saved views are components on the Pulse, not separate destinations. The user
shouldn't have to remember 'is that thing a dashboard or a saved view or a
report?'"* That argument is about **not making the user classify surfaces**, and
the note honours it more strongly than Pulse did.

### §8.2 Naming of the Pulse Surface — delete rather than rewrite
"'Pulse' is the working name… Decide before building." The thing is retired; the
naming question is moot. Already marked; the marker can go with the section.

### §8.4 Monitor's Default Landing per Space — superseded
"Each Space's Pulse should be role-defaulted… Configurable per-user."

⚠️ Note the tension for the rewrite: Spaces **do** still carry
`default_home_route`, and the Home system space still points every user at
`/home`. What is gone is *per-Space Pulse composition*, not per-Space landing.

---

## 3. Two things this report cannot settle

1. **`types/fragments.ts` has zero importers and is stale in two ways** — it
   still declares `EndTransition.past_tense` (replaced by per-outcome
   `outcomes`) and `FragmentInstance.scope` (split into `predicate` /
   `expansion`). A mirror nothing imports, describing a contract that moved
   twice. Surfaced in the file itself; not decided.
2. **The `pulse_signals` table is now orphaned.** The model is deleted; `r182`
   does not drop the table, because the dispatch scoped the migration to the two
   CHECK constraints and a table drop is a different act. 0 rows in production
   and dev. Leaving it reproduces the `tenant_settings` debt the codebase
   already carries and documents.
