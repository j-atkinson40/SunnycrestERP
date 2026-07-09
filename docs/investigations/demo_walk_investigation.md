# The Demo-Walk Rehearsal — Script + Gap List

**Date:** 2026-07-08 · **HEAD at read:** `93e1fb2a` · **Read-only — nothing built, seeded, or authored.**

The September Wilbert presentation (~250 licensees) runs on ONE deeply-composed
walk — the case-comes-in flow across Hopkins (FH) + St. Mary's (cemetery) +
the manufacturer — not feature coverage. This scripts that walk beat-by-beat
against what exists at `93e1fb2a`, maps each beat to the Monitor / Act /
Decide thesis, and produces the gap list. Written as a presenter reads the
platform, not as an engineer reads code.

**The thesis the walk embodies:** the HIERARCHY is the Monitor story (the
platform map → vertical maps → tenant destinations — awareness without
hunting); the COMMAND BAR + NL creation is Act (one sentence becomes a case);
the TRIAGE FOCUS is Decide (bounded approve/reject, the run advances). The
walk crosses both app trees deliberately — the admin hierarchy is James's
operator view ("this is how I run the platform"), the tenant app is the
licensee's daily view ("this is your Monday morning").

---

## 1. The script (beat by beat)

### ACT I — The platform, whole (Monitor · admin tree)

**Beat 1 — the platform map.** *Surface:* `admin → /` (the MoC landing).
*Happens:* nothing clicked yet — the room breathes. *Demonstrates:* the whole
platform at a glance: four verticals (Manufacturing + Funeral Home open,
Cemetery + Crematory honestly "map coming"), the six core workflows in their
canonical home, the Focuses card with three distinct family marks
(scale/kanban/sparkles), the recent-fires pulse. *Exists today:* fully.
*Presenter line:* "every vertical, every default, and what fired overnight —
one screen."

**Beat 2 — descend to Funeral Home.** *Surface:* `/maps/funeral_home`.
*Happens:* click the FH card. *Demonstrates:* a vertical's whole operational
vocabulary — 15 workflows (the case spine visible by name), Cemetery Triage
wearing its family mark, the task table. *Exists:* fully (the FH stamp).
*Gap touched:* the task table's descriptive cells are em-dash — **the
case-spine enrichment (operator move, G-4)** is what makes this beat read as
a run-book instead of a skeleton.

**Beat 3 — Hopkins as a destination.** *Surface:*
`/maps/funeral_home/hopkins-fh`. *Happens:* search "hopkins" in the Tenants
card (P-1 makes the list FH-only), click through. *Demonstrates:* the same
map, tenant-scoped — "this is what YOUR page looks like"; breadcrumb
Platform › Funeral Home › Hopkins. *Exists:* fully.

### ACT II — The case comes in (Act · tenant tree, Hopkins)

**Beat 4 — the Cmd+K moment.** *Surface:* the Hopkins tenant app, logged in
as `director1@hopkinsfh.example.com`. *Happens:* Cmd+K → type
`new case Robert Chen DOD tonight daughter Emily wants Friday service` →
the NL overlay populates fields live → Enter → the case exists.
*Demonstrates:* THE Act thesis — one sentence, five seconds, no form (the
canonical Phase-4 demo moment from the platform canon). *Exists:* the NL
creation platform layer shipped Phase 4. *Gaps touched:* **G-2** (rehearse
the extraction quality against Hopkins' data; `seed_nl_demo_data` targets
testco — verify the resolver has Hopkins-side candidates or seed them) and
**G-1** (the beat that would SING: the admin fires log lighting up because
`case.opened` fired a task — see the live-fire plan below).

**Beat 5 — the worked case.** *Surface:* Hopkins case detail, FC-2026-0001
(John Michael Smith). *Happens:* open the SEEDED case — the rich one: veteran,
Mary Smith informant (signed), the Story step content, the arrangement
vocabulary. *Demonstrates:* the case spine mid-flight — First Call done,
Arrangement scheduled, the Scribe's structured output. The fresh Chen case
from Beat 4 shows creation; FC-2026-0001 shows depth. *Exists:* seeded richly
(`seed_fh_demo`).

**Beat 6 — the St. Mary's seam.** *Surface:* FC-2026-0001's Cemetery step —
`CemeteryPlotMap`. *Happens:* the visual plot map of St. Mary's (40 seeded
plots), section A row 4 plot 1 selected for John. *Demonstrates:* the
cross-tenant seam AS THE DIRECTOR LIVES IT — the cemetery is a party to the
case, not another app. *Exists:* St. Mary's is a real seeded cemetery tenant
+ plots + map config + the case linkage. **Verdict on the seam: §2.**

**Beat 7 — the scheduling Focus.** *Surface:* the funeral-scheduling Focus
(the real kanban dispatcher with composed accessories). *Happens:* the
service lands on the board; drag to the day. *Demonstrates:* Focus as the
work surface — the core-plus-accessories composition the visual editor
authored. *Exists:* the May runtime work; **rehearse against Hopkins' data
(G-5)** — the board needs believable neighboring services, not one lonely
card.

### ACT III — The manufacturer's side (Decide · tenant tree, the vault order)

**Beat 8 — the order lands at the manufacturer.** *Surface:* the
manufacturer tenant's ops view (order/sales surfaces). *Happens:* the vault
order for the Smith case exists on the manufacturer's side
(`vault_manufacturer_company_id` is seeded on FC-2026-0001). *Demonstrates:*
the network: Hopkins' case became the manufacturer's work without an email.
*Gaps touched:* **G-3 — WHO plays the manufacturer on screen** (the identity
decision) and **G-6** (the order artifact's believability — inventory below).

**Beat 9 — the proof, the family, the decision.** *Surfaces:* the
Personalization Studio legacy document (seeded for FC-2026-0001) → the
family-approval portal (`FamilyPortalApprovalView`, token URL — the Phase 1E
surface) → the Decision Triage FOCUS. *Happens:* show the generated legacy
proof; the family's approval portal (on a phone, ideally — tenant-branded);
then the manufacturer's triage queue: the proof pending decision → APPROVE →
the item clears, the run advances. *Demonstrates:* Decide — bounded
decisions over the triage substrate, inside a Focus. *Exists:* the studio
content + document + portal are seeded (Phase 1G/1E); **TriageQueueCore is
REAL** (3a.1-B mounts the Phase 5 triage workspace in the Focus shell by
queueId) — the Decide-as-Focus loop is demoable, **but the specific
queue+item choreography needs a rehearsal pass (G-6)**: which queue, which
seeded pending item, and does approving visibly advance something on screen.

### ACT IV — Back up the hierarchy (the close)

**Beat 10 — the fires log as the walk's footprint.** *Surface:* back to the
admin platform map. *Happens:* the recent-fires card shows what the walk
itself fired (the live-fire beat's run; the dry-run pulses). *Demonstrates:*
the Monitor closes the loop — everything that happened is legible on the map
that opened the show. *Exists:* the unified fires log. *Depends on:* the
live-fire plan (below) having fired something during the walk.

**Beat 11 (flourish, optional) — the platform as a product.** *Happens:*
the fork menu on a core (blast radius legible), or a pending V-2 update
badge accepted live. *Demonstrates:* templates fork and improve by consent —
the licensee-facing governance story. *Exists:* fully (V-1/V-2). Keep in the
pocket for Q&A rather than the main line.

### The live-fire plan (Beat 4's theater, made safe)

The beat that would sing: the director creates a case → within a minute the
admin fires log shows `First Call Intake` fired for Hopkins, event-sourced.
What it needs, honestly:

- **The matcher is presenter-friendly** (1-minute cadence — emit → the log
  shows it before the sentence finishes). The 15-minute SCHEDULE sweep is
  not; no beat should depend on it.
- **Nothing emits `case.opened` today** — T-2.2d (the emitter pass) is
  deferred. Without it, the "case created → task fired" beat requires a
  backstage manual emit (the witness.marker pattern) — workable but it's
  presenter sleight-of-hand, not the product. **Recommendation: a minimal
  T-2.2d cut — ONE emitter, `case.opened` at case creation — turns Beat 4
  into the real thing** (the case the director just created IS the event).
  A trigger on First Call Intake (event `case.opened`, tenant_override →
  Hopkins) does the matching; §6/is_live discipline applies.
- **Live vs dry-run:** dry-run is ALREADY the show — the fires log renders
  dry-run rows with full provenance ("Dry-run · First Call Intake · event ·
  case.opened"). Recommend the demo trigger stays DRY-RUN (zero risk, the
  log is the theater) unless the fired effect is itself benign-visible
  (the witness-marker class); nothing in the walk needs a live effect.

---

## 2. The St. Mary's verdict — no third stamp required (the seam is case-embedded)

The walk does NOT need the cemetery vertical map. The beat's job is "the
cemetery is a party to the case," and that lives in Hopkins' case flow: the
`CemeteryPlotMap` over St. Mary's real seeded plots, the reserved plot on
FC-2026-0001, the Plot Reservation workflow ON THE FH MAP (it's an FH
workflow — correctly, per operator-vertical canon). Visiting an admin
cemetery map would add a surface without adding meaning — and the platform
map's honest "map coming" on Cemetery reads as roadmap, not absence.

**Polish-tier option:** the cemetery stamp is now a cheap proven exercise
(the FH stamp's parameterized scripts; St. Mary's exists as a destination
target). If a spare session exists pre-September, stamping it makes the
platform-map opening show THREE open verticals — nice, not needed. Sized:
one short session (fewer artifacts than FH: Plot Reservation is FH-owned;
the cemetery inventory is thin — the honest stamp may be mostly the page +
tenants card + St. Mary's as a destination).

---

## 3. The touched-artifact inventory (believability)

| Artifact | State | Believable? |
|---|---|---|
| Hopkins FH tenant + director1 login | seeded (`seed_fh_demo`) | ✅ |
| FC-2026-0001 (John Michael Smith) | seeded RICH: veteran, informant signed, Story content, arrangement vocab, plot linkage | ✅ the depth beat |
| St. Mary's + 40 plots + map config | seeded | ✅ |
| The fresh-case beat (Robert Chen) | created live via Cmd+K each run | rehearse extraction (G-2) |
| The FH map + case-spine tasks | stamped; cells em-dash | **G-4 (operator)** |
| FH scheduling Focus | machinery real; **the FH-scoped variation is the operator's V-1 move (G-5a)**; board data thin | **G-5** |
| Personalization Studio legacy doc + family portal | seeded for FC-2026-0001 (Phase 1G/1E) | ✅ verify the token flow in rehearsal |
| The manufacturer tenant | **Sunnycrest does NOT exist on dev/staging (by design)** — testco plays the part | **G-3 (decision)** |
| The vault order on the mfg side | `vault_manufacturer_company_id` seeded; the ORDER artifact's visibility on mfg surfaces needs a rehearsal pass | **G-6** |
| Decision Triage Focus | TriageQueueCore is REAL (mounts Phase 5 triage by queueId) | choreograph queue+item (G-6) |
| The event catalog | 8 curated keys incl. `case.opened`, `order.created` | ✅ |
| Emitters for those events | **NONE (T-2.2d deferred)** | **G-1** |
| Family icons / fork menu / V-2 badges | live | ✅ flourish-ready |

---

## 4. The gap list (demo-blocking → polish)

**DEMO-BLOCKING (dispatches):**
- **G-1 — the minimal `case.opened` emitter (T-2.2d-min).** One emitter at
  case creation + one event trigger on First Call Intake (tenant_override →
  Hopkins, dry-run). Turns the walk's best beat from sleight-of-hand into
  the product. Sized: ONE short session (the outbox + matcher + trigger
  machinery all exist; this is one `emit_event` call site + a seed).
- **G-6 — the manufacturer-side choreography pass.** A rehearsal-driven
  session: make the Smith vault order visible on the manufacturer's
  surfaces, pick the triage queue + seed the pending proof item, and verify
  approve-advances-something-visible. Part build (small seed additions),
  part rehearsal. Sized: one session, shaped by the first rehearsal's
  findings.

**DEMO-BLOCKING (decisions, the operator's):**
- **G-3 — who plays the manufacturer on screen.** Options: (a) create the
  REAL `sunnycrest` tenant on staging (the demo seed's Hopkins↔Sunnycrest
  connection then wires itself — it queries for the slug); (b) accept
  "Test Vault Co" on screen (weak for this audience); (c) rename testco for
  demo week (**hazard: `seed_staging` re-runs clean+re-seed per deploy —
  the rename is clobbered by any deploy; only safe under the deploy
  freeze**). Recommend (a) — it's also the first step of Sunnycrest's real
  onboarding.
- **G-4 — the case-spine five's enrichment** (operator content, the editable
  table; the shared vocabulary is waiting). Hours, not sessions.
- **G-5a — the FH scheduling variation via the fork menu** (the operator's
  V-1 dogfood move; it surfaces on the FH card automatically). Minutes.

**POLISH:**
- **G-2 — NL-extraction rehearsal on Hopkins** (+ resolver candidates seeded
  Hopkins-side if needed; `seed_nl_demo_data` currently targets testco).
- **G-5 — scheduling-board believability** (a handful of neighboring
  services seeded so the kanban isn't one lonely card).
- **G-7 — the cemetery stamp** (three open verticals on the opening screen;
  cheap now, not needed).
- **G-8 — dev fixture-tenant noise (P-2)** — irrelevant on staging if the
  demo runs there; skip unless demoing from dev.

---

## 5. Reliability + reset (the demo-day discipline)

- **REPEATABILITY:** rehearsals accumulate: the Chen cases (one per run),
  workflow runs / fires rows (the log grows — actually GOOD for the fires
  beat until it's noise), matcher-processed events, triage decisions.
  **Recommend a small `demo_reset` script as part of G-6's session**: delete
  Chen-pattern cases + the rehearsal's runs/events (company-scoped, the
  established teardown patterns), re-run `seed_fh_demo --force` for
  FC-2026-0001 state. The seeds are already idempotent; the reset script is
  the complement (remove what the walk CREATED).
- **TIMING:** only Beat 4's fire depends on a cadence — the 1-min matcher is
  acceptable live ("by the time I've told you what happened, the map knows
  too"), with the backstage manual-emit as the fallback if the minute feels
  long on stage. NOTHING in the walk may depend on the 15-min schedule sweep.
- **DEMO-WEEK RISK:** recommend a **deploy freeze** for demo week (staging
  IS the demo environment unless decided otherwise). The seed sweep is at
  ~9 minutes and growing — a hotfix during demo week pays that latency;
  freeze + a rehearsed rollback plan beats hotfixing. (The seed-duration
  tripwire is already cataloged.)
- **LIVE-FIRE SAFETY:** nothing in the walk needs a live effect. The
  recommendation is dry-run-with-the-log-as-the-show for the demo trigger;
  if theater demands a live fire, the witness-marker class (benign,
  §6-guarded, is_live toggled ON for the walk and OFF after) is the
  template — decided at G-1's build, not improvised on stage.
- **WHERE the demo runs:** staging (real deploy pipeline, both services,
  the seeds self-maintain) — with the freeze; a local fallback laptop with
  the same seeds as the contingency.

---

## 6. Sizing the fill

| Work | Kind | Size |
|---|---|---|
| G-1 emitter + trigger | dispatch | 1 short session |
| G-6 manufacturer choreography + demo_reset | dispatch (rehearsal-shaped) | 1 session |
| G-3 Sunnycrest-on-staging decision (+ creation if (a)) | operator decision; creation ≈ hours | hours |
| G-4 enrichment · G-5a variation | operator content | hours · minutes |
| G-2 / G-5 believability seeds | rider on G-6 or G-1 | hours |
| G-7 cemetery stamp | optional dispatch | 1 short session |
| First full rehearsal (both trees, timed) | operator + assistant | half a day, AFTER G-1+G-6 |

The honest total between here and a rehearsable walk: **two dispatches, one
decision, and an afternoon of operator content** — then rehearsal iterations,
which is exactly where a demo three months out should be.
