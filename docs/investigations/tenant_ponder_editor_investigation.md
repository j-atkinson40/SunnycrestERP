# TENANT-SIDE MoC + PONDER-AS-EDITOR — Investigation / Scoping (read-only)

**Date:** 2026-07-16 · **HEAD:** `60303c92` · **Read-only** — no code, no build. The plan is the deliverable.
**Direction:** the MoC + ponder come to the tenant side for learning, tweaking, monitoring — and the ponder becomes the configuration surface. Banked: view/ponder = all tenant users; edit = tenant admins; prompted fork on first edit of a shared task; confirm-with-evidence on live-task edits.
**Method:** every claim below checked against source/dev-DB at HEAD.

---

## THE HEADLINE — fork-vs-overlay: the overlay WINS, and most of it already exists — but the engine needs ONE seam

**The verdict is (b) PARAMETER OVERLAY, and it is not a new architecture — it is Phase 8a's dual-customization design finally getting its execution half.**

What exists TODAY (verified):
- **`WorkflowStepParam`** — platform defaults (`company_id NULL`) + tenant overrides (`company_id` set), keyed `(workflow_id, step_key, param_key)`, with `param_type / validation / is_configurable`. The **merged read already exists**: `routes/workflows.py::_load_step_params` computes `effective_value = override ?? default` — exactly the resolution the ponder-editor needs, currently UI-display-only.
- **`WorkflowEnrollment`** — tenant enrollment rows; **consumed at fire time** by `workflow_scheduler` (tier-3 gating) and by the engine's listing path. The enrollment IS the "tenant's relationship to a shared workflow" record — the natural anchor for the prompted fork.
- **`workflow_fork.py`** (Option A) — the full-fork path for STRUCTURAL divergence, already built, already lineage-stamped (`forked_from_workflow_id`).
- **The MoC side**: `moc_task_catalog` already has `scope="tenant_override"` + `tenant_id` + the merged tenant view (MoC Tenant View shipped) — the tenant's task row costs nothing new.

**The gap (the sizing headline):** the ENGINE never consumes `WorkflowStepParam` at fire time. `resolve_variables` supports 11 prefixes — none is `param.*` — and `_execute_step` resolves config verbatim; grep confirms zero `WorkflowStepParam` references in `workflow_engine.py`. The 8b seed comment ("tenants override dry_run via param enrollment if desired") described the intent, not the plumbing.

**The seam is contained, not surgery:** one merge point in `_execute_step` — load the step's effective params (the `_load_step_params` logic moved into a service fn, cached per-run) and either (i) resolve a new `{param.<key>}` prefix in configs, or (ii) shallow-merge effective params into `resolved_config` for declared keys. Option (ii) is safer (declared-params-only; a config key is overridable iff a platform param row DECLARES it — the honesty boundary below). Estimated: **one session including pins** (merge + `{param.*}` support + a parity test proving an un-overridden workflow executes byte-identically — the D-1 discipline).

**The overlayable/structural boundary (what the model itself says):**
| Edit | Mechanism | Notes |
|---|---|---|
| From-address/reply-to, template variant, thresholds, quantities, copy | **Param overlay** — requires a DECLARED param row on the step (platform authors what's tweakable; `is_configurable` already exists as the gate) | The seed's `params` lists are sparse today (17 rows) — P1 includes a declaration pass over the accounting/FH steps |
| Recipients/audience of a notify step | **Param overlay** (`roles` is step config the derivation already reads — declare it as a param) | Write-what-you-read symmetry holds |
| Trigger (when it fires) | **Per-task, not per-workflow** — MoC triggers hang on the task row; the tenant's task row owns its own triggers. NO overlay needed; the T-1b editors write it directly | The cleanest case |
| Adding/removing/reordering steps, changing action types | **STRUCTURAL → Option A full fork** (exists) | The fork prompt's "advanced" path; rare |
| Captions/ponder narrative | The r127 `ponder` JSONB on the TENANT's task row | Already per-row |

**Update-offer implications (why overlay wins):** with overlays, a vertical-default workflow improvement propagates FREE to every tenant (their overlays sit on top, field-granular — the focus-chrome-cascade semantics exactly). V-2's offers machinery (`target_tenant_id` schema-ready) is only needed for the RARE full forks. Full-fork-everything would instead make every one-field tweak a divergent copy needing whole-workflow merges — strictly worse on every axis. **The prompted fork therefore creates: a tenant task row (+ its triggers, copied) + an enrollment — NOT a workflow copy.** "Create your own version" means "own your task's schedule, captions, and declared knobs," with the workflow staying shared.

## THE EDITING GRAMMAR PER BEAT (read paths reversed into writes)

- **TRIGGER BEAT** → writes `moc_task_trigger` rows (the T-1b editors' machinery, remounted in-ponder). **Recurrence:** the sweep evaluates `spec_kind ∈ {time_of_day (days+time, tenant-local), cron}` — custom Python, so **ordinal-weekday is a new `spec_kind: "ordinal_weekday"`** (`{ordinal: 1..4|last, weekday, time}`), evaluated tenant-local in `_due_intended_fire` (~40 lines; NO migration — config is JSONB). Standard cron cannot express it (dom/dow OR-semantics), so don't contort cron. **The friendly builder**: presets (daily / weekly-on / monthly-on-date / monthly-on-ordinal-weekday / cron-advanced) + the WHEN grammar running in REVERSE as live readback — `cron_to_prose` extended with the ordinal branch renders "the first Monday of every month at 4:00 PM" as you compose it. Event triggers: the catalog picker (`moc_trigger_event_catalog` + `filterable_fields` condition editor — the T-1b event editor exists admin-side).
- **EMAIL STEP BEAT** — the split, precisely: **per-step layer** (overlayable params: `reply_to`, recipients, template variant — the delivery abstraction already accepts `reply_to` per send; steps pass it from config) vs **tenant layer** (the sending identity/domain: today `legacy_email_settings` (r42 — sender_tier/custom_from/domain_verified) is the only tenant sending-identity table and it is Legacy-module-scoped; a general tenant sending identity is a KNOWN GAP — the beat links "Sending identity → tenant email settings" and that page generalizes `legacy_email_settings` when the arc needs it, flagged not built). The beat exposes the step's declared params and LINKS the tenant layer — never duplicates it into step config.
- **AUDIENCE BEAT** → the enrichment's derivation reversed: notify steps get a picker over `roles` (writing the same config key `_audience_for_step` reads — symmetry closes the loop, the audience line immediately shows the pick); queue-permission audiences are READ-ONLY here (they belong to queue governance, not the task). Named-user selection = a new config shape (`user_ids`) — declare it only if a step type honestly consumes it; otherwise roles-only in P1.
- **FORK PROMPT** — first edit of a `vertical_default` task: "This is the standard version for {vertical}. Create {tenant}'s own?" → creates the tenant task row (name/desc/icon/captions copied, triggers copied, `ponder` copied) + enrollment; lineage: the tenant row records its seed template identity so V-2-style offers can reach it later (schema-ready via the existing offers tables' `target_tenant_id`). **LIVE CONFIRM** — editing a task whose triggers are `is_live`: the confirm shows the field diff + "this task is live — the next fire uses these settings" (the Live-toggle evidence pattern); dry-run tasks edit free.

## THE TENANT SURFACE

- **Mount:** a top-level **"Automations"** nav item in the tenant app (peer of Operations Board — recommended over burying in `/settings/workflows`, which stays as the builder power-surface; Automations is the comprehension surface). One page: the task table (tabs, hold-P, ponder — the admin components are tenant-clean already: they render from props + a service module) over THEIR merged view (vertical defaults + their overrides).
- **APIs — the realm map:** tenant-side workflows APIs EXIST (`/api/v1/workflows` — three tabs, enrollments, forks, params). The MoC reads (task catalog, ponder derivation, document preview, fires) are PLATFORM-realm only → **P2 mounts a tenant router over the same realm-agnostic services** (the canon pattern: `ponder.build_ponder_script` takes db+task_id already; the tenant router adds company-scoping — tasks filtered to `vertical_default(company.vertical) + tenant_override(company)`, garnish/fires company-scoped, audience counts company-scoped (which also fixes the cross-tenant count ambiguity — the tenant surface counts THEIR users)). Document preview: tenant-visible templates only (the D-6 visibility rules exist).
- **Roles:** view = `get_current_user` (all tenant users), edit = `require_admin` (exists); per-role configurability later = a permission key (`automations.edit`) through the existing role-permission machinery — cheap when wanted.
- **Monitoring:** company-scoped fires exist (`workflow_runs` + `list_recent_runs` tenant-side). The tenant ponder's garnish becomes THEIR numbers for free once company-scoped. A per-task recent-fires strip in-ponder = one filtered read.
- **Comes along:** task table + tabs + hold-P + the full ponder (view + edit-mode per role). **Stays admin:** Planning, vocabulary editing, core/vertical governance, the mirror pass, Studio links (tenant sees "using: Professional v1" without the Studio link, or links to their template viewer).

## THE PHASED PLAN (honest sizing — this is the biggest direction since the hierarchy)

| Phase | Content | Size |
|---|---|---|
| **P1 — the execution seam + editing grammar, ADMIN-side first** | The engine param seam (+parity pins) · param declaration pass over accounting/FH steps · in-ponder edit surfaces: trigger editor (incl. `ordinal_weekday` + reverse-grammar readback), declared-param fields on email/notify beats, audience picker (roles) · write-what-you-read pins | **2–3 sessions** |
| **P2 — the tenant surface** | Tenant "Automations" mount · tenant MoC/ponder routers over the realm-agnostic services (company-scoped reads, counts, garnish) · roles wiring (view-all / edit-admin) · the fork prompt (tenant task row + enrollment + lineage) · live-edit confirm-with-evidence | **2–3 sessions** |
| **P3 — monitoring + polish** | Per-task fires strip in-ponder · offers wiring for forked tenant rows (V-2 reach) · the tenant sending-identity generalization IF email edits demand it · reduced-motion/perf passes | **1–2 sessions** |

**Total: ~5–8 sessions**, each independently shippable; P1 proves configuration-through-comprehension where the rails already run (the admin map), so the tenant surface arrives with the grammar already trusted.

**Migrations flagged:** likely **NONE for the overlay** (WorkflowStepParam/Enrollment exist; trigger config is JSONB; tenant task rows exist). Candidates if P2 wants them: a lineage column on tenant task rows for offer-reach (or ride a JSONB key), and the generalized tenant email-identity table in P3 (deferred until demanded).

## STOP-CONDITION LEDGER

- **(a) engine can't resolve overlays without surgery** — PARTIALLY TRUE, downgraded: the engine ignores params today, but the fix is one contained merge seam (a session), not an architecture flip. The overlay verdict stands.
- **(b) no tenant mount / admin-coupled APIs** — CLEAR: the tenant app has natural nav space + the workflows APIs as precedent; MoC services are realm-agnostic at the service layer; only routers are net-new.
- **(c) ordinal-weekday recurrence** — TRUE that the model can't express it TODAY, but the sweep is custom Python: a new `spec_kind` (no migration) + ~40 lines + the reverse-grammar readback. A rider inside P1, not a preceding arc.

**STOP.** Read-only; nothing built. The three decisions already banked (visibility, prompted fork, live confirm) all map cleanly onto existing machinery — the fork prompt in particular becomes CHEAPER than designed (a task row + enrollment, not a workflow copy). The one true unlock is the engine seam, and it is small.
