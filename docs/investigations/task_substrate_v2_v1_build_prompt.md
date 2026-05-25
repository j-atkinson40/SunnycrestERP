# Task Substrate v2 — v1 Build Prompt (v1.0 substrate + v1.5 integration)

> **Document purpose.** Dispatch-ready build prompt for the task substrate v1 arc. Closes Phase 5 of the v2 investigation. Drafts against `task_substrate_v2_state.md` (locked architecture) + `task_substrate_v2_phasing.md` (locked phasing + operator-resolved §8 questions) + current code state. Phase 3's lost implementable specifics are re-derived here against current code rather than reconstructed from the lost design document.
>
> **Authority basis.** Every locked-input citation references state doc §X.Y or phasing doc §X.Y verbatim. Implementable specifics (column inventory, file:line citations, plugin contract signatures) re-derive against HEAD ca88f50; build agent re-verifies at v1 dispatch.
>
> **Discipline.** Single arc, two internal phases (v1.0 substrate + v1.5 integration), single commit at v1.5 close (per phasing §8.1). No canon edits. No STATE.md edits until v1 close note. Material-divergence triggers (§9 below) STOP + surface, do not auto-proceed.
>
> **Date:** May 25, 2026. **HEAD at draft:** ca88f50 (Phase 4 commit). **Migration head:** r106. **v1 target migration head:** r107.

---

## §1. Header — scope, lineage, bounded decision

### 1.1 Predecessor lineage

The task substrate arc spans seven distinct deliverables across roughly five days:

1. **May 21–22, 2026 — primary source conversation** (state doc §1; §2.1). Operator surfaces task substrate insight; Claude responds with 19 architectural claims. No code dispatched.
2. **May ~23, 2026 — task substrate v1 investigation** (state doc §2.2; commit `57d8210`). Five-phase investigation. Partial H2 verdict with H1-shaped projection-view warranted. Audit incomplete (missed existing `Task` model + `task_service.py` + `task_triage` queue + `_build_tasks_item` stub + `task_assigned` notification category) — see state doc §3 retrospective.
3. **May ~23, 2026 — (c) investigation arc** (state doc §2.3; commit `dfd876c`). Locked notification-shared-discipline scope; 9 §19 categories; helper substrate; producer-site cohort.
4. **May 24, 2026 — (c) build arc** (state doc §2.4; commit `868fec3`). Shipped `notify_users_with_permission` helper at `notification_service.py:155`, 9 §19 categories appended to `category_types.py`, `fh_cases.aftercare` permission slug, 8 producer-site dispatches at canonical state-transition points, backfill script. Total ~1,535 LOC.
5. **May 24, 2026 — task substrate v2 investigation Phases 0–3** (state doc §2.5). Capability-demand map (22 rows) + gap analysis (substrate is MORE PRESENT than v1 surfaced) + substrate design (13 sections; ~8,980 LOC v1 surface). All five `/tmp/task_substrate_v2_*.md` deliverables lost at 20:12 `/tmp/` rotation.
6. **May 24, 2026 — Option E recovery** (state doc — this consolidated state document; commit `bc7c4ba`). Persistent storage discipline established.
7. **May 25, 2026 — Phase 4 phasing recommendation** (phasing doc; commit `ca88f50`). v1.0/v1.5/v2/v3 sequenced; operator-resolved 9 open questions at Phase 4 → Phase 5 gate (per dispatch).

This build prompt dispatches against [6] + [7] + current code state.

### 1.2 Bounded decision the v1 build arc closes

*"Ship the task substrate v1 — v1.0 substrate phase per phasing §1 + v1.5 integration phase per phasing §2 — as a single arc with two internal phases, validated against staging at the v1.0 → v1.5 operator-confirm gate, committed once at v1.5 close, narrated in a STATE.md entry at v1 close."*

### 1.3 Framing relationship to v1's internal phases

Per phasing §1.3 + §2.6 + operator §8.1 resolution: **v1 is a single arc.** v1.0 and v1.5 are internal phases of the same arc. The v1.0 → v1.5 operator-confirm gate is conversational (per phasing §8.8 recommendation). No git commit lands at v1.0 close; single commit lands at v1.5 close covering both phases.

If material divergence surfaces at the gate, the arc stops, build agent surfaces findings to operator, no half-committed substrate.

---

## §2. Read order

### 2.1 At v1 build arc dispatch (before v1.0 work begins)

**Locked-input documents (read in full):**

1. `docs/investigations/task_substrate_v2_state.md` (605 lines) — architectural trajectory §5; sequence shape §6; operator locks §4.
2. `docs/investigations/task_substrate_v2_phasing.md` (691 lines) — v1.0 final-lock §1; v1.5 final-lock §2; cross-version concerns §6; 9 open questions §8 (all resolved by operator at Phase 4 → Phase 5 dispatch).
3. This build prompt (`task_substrate_v2_v1_build_prompt.md`).

**Canon documents (read sections relevant to substrate):**

4. `CLAUDE.md` — build-arc discipline; single-commit-at-arc-close pattern (§ "Recent Changes" + §12 spec-override); Option A idempotent seed canon (Phase 6 + 8b + 8d.1 + R-6.1a precedent).
5. `BRIDGEABLE_MASTER.md` §3.24 — VaultItem unified model canon.
6. `PLUGIN_CONTRACTS.md` — Tier R1 plugin pattern (Intake adapters precedent at §"Intake adapters"; v1.0 registers three new categories against this pattern).

**Production code anchors (read for current-state grounding):**

7. `backend/app/models/task.py` (118 LOC; 5-state lifecycle at line 104-110; produced fields enumerated at lines 41-95).
8. `backend/app/models/vault_item.py` (lines 1-140; `item_type` enum currently 11 values at line 28-30; `metadata_json` JSONB at line 119-122).
9. `backend/app/services/task_service.py` (298 LOC; transition rules at lines 50-58; `create_task` at lines 129-194; `task_assigned` dispatch at lines 164-192).
10. `backend/app/services/pulse/personal_layer_service.py:87-168` (`_build_tasks_item` stub returning None at line 111; scaffolded query preserved at lines 116-168).
11. `backend/app/services/notification_service.py:155-237` (`notify_users_with_permission` helper from (c)).
12. `backend/app/services/notifications/category_types.py` (28 §19 categories at lines 43-143; `task_assigned` at line 152; frozen module constant).
13. `backend/app/api/routes/tasks.py` (existing `/api/v1/tasks/*` routes).
14. `backend/app/services/triage/platform_defaults.py:34-45` (`task_triage` queue config + `source_direct_query_key="task_triage"`).
15. `backend/app/services/peek/builders.py` (Peek task builder; one of 8 existing Task consumers).
16. `backend/app/models/focus_session.py` (FocusSession model at line 37; columns at lines 40-78; **no `task_id` column** — v1.5 §7.5 adds it).
17. Recent r-migrations: `backend/alembic/versions/r100_*.py` through `r106_*.py` for naming + structural conventions.

**(c) build arc precedent files (read for refactor-pattern grounding):**

18. `backend/app/services/social_service_certificate_service.py:160` — (c) producer #2.
19. `backend/app/services/agents/base_agent.py:103` — (c) producer #3 (canonical convergence for 4 AgentAnomaly producers).
20. `backend/app/services/workflows/aftercare_adapter.py:204` — (c) producer #4.
21. `backend/app/services/workflows/catalog_fetch_adapter.py:256` — (c) producer #5.
22. `backend/app/services/safety_program_generation_service.py:177` — (c) producer #6.
23. `backend/app/services/workflows/workflow_engine.py:812` — (c) producer #7.
24. `backend/app/services/classification/dispatch.py:377` — (c) producer #8.
25. `backend/scripts/seed_pending_attention_backfill.py` — (c) backfill script (Option A idempotent precedent for r107 backfill).

### 2.2 Before v1.5 phase dispatches (after operator-confirm gate)

Re-read v1.0 work-in-progress files for context continuity. Specifically: the new `backend/app/services/tasks/` package created in v1.0 (substrate / lifecycle / subscribers / plugins) — v1.5 wires consumers into it; reading the substrate's public API surface before wiring prevents shape drift.

---

## §3. Locked scope

### 3.1 v1.0 ships (per phasing §1.1)

1. **Schema extension:** VaultItem `item_type` enum gains 12th value `'task'` + new `task_details` join table (1:1 with VaultItem rows of `item_type='task'`).
2. **Alembic migration r107 + backfill script** (same commit at arc close).
3. **Dual lifecycle state machine** (action shape + reminder shape per state doc §5.2).
4. **Subscriber registry substrate** (7 event types; 6 subscribers; sync execution in v1; idempotency per subscriber).
5. **Three plugin category contracts** (task creators / task surfaces / task type behaviors) per phasing §1.1.5.
6. **Five task type behavior plugins** (`generic_task`, `review_approval_task`, `scheduled_recurring_task`, `customer_communication_task`, `anomaly_resolution_task`) per state doc §4.7.
7. **Task service layer extension + Task façade** for backward-compat with 8 existing Task consumers.
8. **v1.0 internal test cohort** (~150-200 tests per phasing §1.1.8).

### 3.2 v1.5 ships (per phasing §2.1)

1. **Pulse `_build_tasks_item` wire** at `pulse/personal_layer_service.py:87-168`.
2. **Briefings task-substrate consumption** (3 new helpers per phasing §2.1.2).
3. **(c) refactor of 8 producer sites** (notification path now flows producer → task creation → subscriber → `notify_users_with_permission`; same downstream function; different upstream invocation path).
4. **3 workflow node types** (`create_task` / `wait_for_task_completion` / `route_on_task_outcome`).
5. **Focus extension column** (`focus_sessions.task_id` nullable FK to `vault_items.id`).
6. **Intelligence task-creation refactor** (Intelligence observations produce tasks rather than ephemeral notifications).
7. **Communications cascade task-creation** (inbound communications produce tasks).
8. **Two routing modes** (`direct_user` + `round_robin`) + **visibility enforcement** (operator-only at query-filter layer; portal-shape schema present but query layer does not surface).

### 3.3 Commit shape (per phasing §6.4 + operator §8.1 resolution)

**Single commit at v1.5 close** covering both v1.0 + v1.5 work. Commit message reflects full v1 arc shape (substrate + integration). Push to main after commit. STATE.md close note added in same commit.

### 3.4 Explicit deferrals (NOT v1)

- 10 non-task triage queue adapter folding → **v2a** (state doc §5.8; phasing §3.1).
- Family portal task surfaces → **v2b** (state doc §5.9; phasing §3.2).
- Contractor portal task surfaces → **v3a** (phasing §4.1).
- Escalation routing mode + persistent subscriber log + task templates → **v2c** (phasing §3.3).
- Workshop UI / coaching / shelf parking deeper integration → **v3b–v3d** (phasing §4.2–4.4).
- Canon edits (CLAUDE.md task-centric statement; PLUGIN_CONTRACTS.md three new categories; BRIDGEABLE_MASTER.md §3.24 12th item_type ratification; DECISIONS.md hybrid-schema entry) → **canon-update arc post-v1, pre-v2** (phasing §6.2 + operator §8.2 resolution).

---

## §4. Phase A.0 inline scoping (single round-trip at v1 build arc opening)

Following (c) build arc canon (state doc §2.4: "Phase A.0 absorbed inline — single round-trip at build arc opening turn, not separate document round-trip"), Phase A.0 surfaces build-time scoping questions that depend on then-current code state at v1 dispatch. Build agent surfaces these in opening message; operator resolves; v1.0 proceeds.

### 4.1 Anticipated scoping questions (build agent confirms or refines)

**Q-A0-1 — `task_details` table name vs absorbing `tasks` rename.** Phase 4 phasing §1.7 reads "extend [Task model] for façade — does not remove existing public API." Two implementable shapes:

  - **Shape A:** Keep `tasks` table as-is; add new `task_details` table with `vault_item_id` FK CASCADE + UNIQUE constraint enforcing 1:1; backfill creates VaultItem row per existing Task + populates `task_details` columns from existing Task columns. Task façade reads through join.
  - **Shape B:** Rename `tasks` → `task_details`, add `vault_item_id` FK column to renamed table, backfill creates VaultItem rows + populates `vault_item_id`.

  **Phase 5 recommendation:** Shape A. Reasoning: existing `tasks` table has 8 consumers + an actively-used route surface (`/api/v1/tasks/*`); renaming the table introduces avoidable risk for the façade contract. Shape A's "Task façade reads vault_items LEFT JOIN tasks" satisfies the state doc §5.1 closing paragraph contract ("consumers query through service-layer + Task façade pattern that abstracts table layout"). At v1.0 close, `tasks` rows still exist; future consolidation arc (v2 or later) can rename. Build agent re-verifies against current code at v1 dispatch and confirms with operator.

**Q-A0-2 — FK direction on task_details.vault_item_id.** State doc §5.1 specifies "FK CASCADE on company_id; SET NULL on user FKs." Verify VaultItem cascade conventions at v1 dispatch (e.g., does VaultItem itself CASCADE when its parent Vault deletes? — relevant for orphan-row semantics on task_details).

  **Phase 5 recommendation:** `task_details.vault_item_id` FK → `vault_items.id` ON DELETE CASCADE. Reasoning: task_details has no independent business existence; if VaultItem row deletes, task_details row should follow.

**Q-A0-3 — Subscriber registry as net-new module vs piggybacking on workflow_engine subscriber substrate.** State doc §5.7 + §13 specifies "subscriber registry; 7 event types; sync execution v1." Verify at v1 dispatch whether `workflow_engine.py` carries a similar subscriber pattern that the task substrate could reuse (avoid two-substrates drift) OR ship net-new.

  **Phase 5 recommendation:** **net-new module** at `backend/app/services/tasks/subscribers/`. Reasoning: state doc §13 specifies task-substrate-specific event types (task_created, task_assigned, task_status_changed, etc.); reusing workflow_engine subscribers would force generic-event abstraction at substrate layer where task-specific event semantics matter. Future arc may consolidate; v1 ships narrow + canonical.

**Q-A0-4 — Test cohort organization.** v1.0 produces ~150-200 tests; v1.5 produces ~100-150 tests (phasing §1.5 + §2.5). Two implementable patterns:

  - **Pattern A:** Extend existing `backend/tests/test_task_service.py` + add new substrate test files under `backend/tests/tasks/`.
  - **Pattern B:** Consolidate under `backend/tests/tasks/` subdirectory; relocate existing task tests.

  **Phase 5 recommendation:** Pattern A. Reasoning: relocating existing tests at v1 dispatch introduces churn beyond v1's scope. Net-new test files at `backend/tests/tasks/test_substrate_*.py` + `test_lifecycle.py` + `test_subscribers.py` + `test_plugins.py` + `test_facade.py`; existing `test_task_service.py` (if it exists; build agent verifies at v1 dispatch) stays where it is.

### 4.2 Phase A.0 protocol

Build agent opens v1 arc with a single message:

1. Confirms read order completed (state doc + phasing + this build prompt + canon docs + 17 production code anchors + (c) precedent files all read).
2. Surfaces Q-A0-1 through Q-A0-4 with Phase 5 recommendations + any newly-surfaced scoping questions discovered during current-code re-verification.
3. Waits for operator confirmation.

Operator confirms / refines in same response thread. Build agent proceeds to v1.0 code work immediately after confirmation.

If Phase A.0 surfaces more than ~3 net-new scoping questions beyond the four anticipated above, **STOP + surface to operator** — that's a material-divergence trigger per §9.

---

## §5. Phase A (v1.0) — substrate

v1.0 ships net-new additive substrate per phasing §1.8 ("zero existing-surface behavior changes"). The five task type plugins register substrate but don't activate against producer sites; activation is v1.5. The subscriber registry fires correctly but (c)'s notification dispatch path remains unchanged; the v1.5 phase flips the call sites.

### 5.1 Schema migration r107 + backfill

**File path:** `backend/alembic/versions/r107_task_substrate.py`

**Migration content:**

1. **Extend VaultItem.item_type to permit `'task'`.** Currently the column is `String(30)` without a DB CHECK constraint (verify at v1 dispatch against `vault_item.py:28-30`). Add `'task'` to the documented enum comment + verify no application-level enum is enforced anywhere that would reject the new value.

2. **Create `task_details` table.** Columns derived from state doc §5.1 + Phase 3 §1 conclusions, re-derived against current Task model:

   ```
   id                          UUID PRIMARY KEY
   vault_item_id               String(36) NOT NULL UNIQUE
                               FOREIGN KEY → vault_items(id) ON DELETE CASCADE
   assignee_realm              String(20) NOT NULL DEFAULT 'user'
                               CHECK IN ('user', 'portal_user')
   assignee_user_id            String(36) NULL
                               FOREIGN KEY → users(id) ON DELETE SET NULL
   assignee_portal_user_id     String(36) NULL
                               (forward-compat; v1 does not write this; v2/v3 portal arcs do)
   lifecycle_shape             String(16) NOT NULL
                               CHECK IN ('action', 'reminder')
   current_state               String(32) NOT NULL
                               (per-shape state machine; values validated at service layer)
   provenance_kind             String(32) NOT NULL
                               CHECK IN (12 values; see §5.3 below)
   provenance_ref_type         String(64) NULL
   provenance_ref_id           String(36) NULL
   event_kind                  String(64) NOT NULL DEFAULT 'manual'
   visibility                  String(24) NOT NULL DEFAULT 'operator_internal'
                               CHECK IN (5 values; see §5.5 below)
   priority                    String(16) NOT NULL DEFAULT 'normal'
                               CHECK IN ('low', 'normal', 'high', 'urgent')
   due_date                    Date NULL
   due_datetime                DateTime(timezone=True) NULL
   assigned_at                 DateTime(timezone=True) NULL
   completed_at                DateTime(timezone=True) NULL
   resolution_outcome          String(64) NULL
   suppression_key             String(128) NULL
   created_at                  DateTime(timezone=True) NOT NULL DEFAULT now()
   updated_at                  DateTime(timezone=True) NOT NULL DEFAULT now()
   ```

3. **Six indexes** per state doc §5.1:

   - `ix_task_details_vault_item_id` on `(vault_item_id)` (UNIQUE supports this; explicit index unnecessary if UNIQUE constraint creates one — verify at v1 dispatch against PG behavior).
   - `ix_task_details_assignee_state` on `(assignee_user_id, current_state)` (Pulse + briefings query path).
   - `ix_task_details_due_date` on `(due_date)` (time-based queries; partial WHERE `due_date IS NOT NULL`).
   - `ix_task_details_provenance` on `(provenance_kind, provenance_ref_type, provenance_ref_id)` (source-lookup query path; partial WHERE `provenance_ref_id IS NOT NULL`).
   - `ix_task_details_lifecycle_state` on `(lifecycle_shape, current_state)` (state-distribution query path).
   - **`uq_task_details_idempotency` PARTIAL UNIQUE** on `(provenance_kind, provenance_ref_type, provenance_ref_id, event_kind) WHERE provenance_ref_id IS NOT NULL` (load-bearing idempotency per state doc §5.3 — prevents duplicate task creation on producer retry).

4. **Downgrade direction:** drop indexes, drop table, leave VaultItem.item_type unchanged (enum was a comment-level update; no constraint to remove).

**Backfill script path:** `backend/scripts/seed_task_substrate_backfill.py` (~150-250 LOC; Option A idempotent — see (c) precedent at `seed_pending_attention_backfill.py`).

**Backfill contract:**

- ENVIRONMENT=production refusal guard (mirrors (c) backfill canon at state doc §2.4).
- Walks all rows in existing `tasks` table.
- For each Task row:
  - Idempotency check: does a VaultItem with `item_type='task'` + a join through `task_details.vault_item_id` pointing to this `tasks.id` already exist? (lookup via `task_details.provenance_ref_type='legacy_task' AND provenance_ref_id=task.id`). If yes, skip.
  - Create VaultItem row with `item_type='task'`, `company_id=task.company_id`, `title=task.title`, `description=task.description`, `created_by=task.created_by_user_id`, `created_at=task.created_at`, `updated_at=task.updated_at`, `is_active=task.is_active`, `visibility='internal'` (VaultItem-level, not task_details-level), `status='active'`, `source='migrated'`.
  - Create task_details row with:
    - `vault_item_id` = new VaultItem.id
    - `assignee_realm='user'`, `assignee_user_id=task.assignee_user_id`
    - `lifecycle_shape='action'` (existing 5-state machine maps to action shape per state doc §5.2)
    - `current_state` = direct map from `task.status` (open / in_progress / blocked / done / cancelled — state machine validates per §5.2)
    - `provenance_kind='manual_creation'` (backfill assumes legacy tasks were manually created; this is honest — existing system has no provenance tracking)
    - `provenance_ref_type='legacy_task'`, `provenance_ref_id=task.id` (preserves audit chain back to original Task row)
    - `event_kind='backfill'`
    - `visibility='operator_internal'`
    - `priority=task.priority`, `due_date=task.due_date`, `due_datetime=task.due_datetime`
    - `assigned_at=task.created_at IF task.assignee_user_id ELSE NULL`
    - `completed_at=task.completed_at`
    - `created_at=task.created_at`, `updated_at=task.updated_at`
  - Log progress every 100 rows.
- Idempotent re-run: zero new VaultItem or task_details rows on second run.
- Honest scope reporting: print summary at end ("Backfilled N tasks → N VaultItem + N task_details rows; skipped M already-backfilled").

**Single-commit ship:** r107 migration + backfill script land in the v1.5-close commit, NOT a separate v1.0-close commit. Per phasing §1.4 + §6.4: "single commit at arc close means r107 + backfill ship in v1.5's commit."

This means at the v1.0 → v1.5 operator-confirm gate, the r107 migration has been applied to staging (Railway auto-deploy from local branch push to a v1-work branch — OR operator runs `alembic upgrade head` against staging manually); the backfill has been run against staging; validation confirms substrate cleanliness; then v1.5 dispatches. The git commit lands at v1.5 close.

### 5.2 Dual lifecycle state machine

**Module path:** `backend/app/services/tasks/lifecycle.py` (~200-250 LOC including state validators, transition handlers, event emission to subscriber registry).

**Public API:**

```python
# Lifecycle shape values (frozen module constant).
LIFECYCLE_SHAPES: tuple[str, ...] = ("action", "reminder")

# State machines per shape.
ACTION_STATES: tuple[str, ...] = (
    "created", "assigned", "in_progress", "blocked", "done", "cancelled",
)
REMINDER_STATES: tuple[str, ...] = ("informational", "acknowledged", "dismissed")

ACTION_TRANSITIONS: dict[str, set[str]] = {
    "created":     {"assigned", "in_progress", "cancelled"},
    "assigned":    {"in_progress", "blocked", "done", "cancelled"},
    "in_progress": {"blocked", "done", "cancelled"},
    "blocked":     {"in_progress", "cancelled"},
    "done":        set(),
    "cancelled":   set(),
}

REMINDER_TRANSITIONS: dict[str, set[str]] = {
    "informational": {"acknowledged", "dismissed"},
    "acknowledged":  set(),
    "dismissed":     set(),
}

# Legacy 5-state backward-compat map (existing tasks.status → action-shape state).
LEGACY_STATUS_MAP: dict[str, str] = {
    "open":        "assigned",     # has assignee — semantically "assigned and waiting to start"
    "in_progress": "in_progress",
    "blocked":     "blocked",
    "done":        "done",
    "cancelled":   "cancelled",
}
# NOTE: "open" with NULL assignee maps to "created" instead of "assigned" — backfill applies this.

def validate_transition(
    *,
    lifecycle_shape: str,
    from_state: str,
    to_state: str,
) -> None:
    """Raises InvalidTransition if illegal."""

def apply_transition(
    db: Session,
    *,
    task_details_id: str,
    to_state: str,
    actor_user_id: str | None,
    resolution_outcome: str | None = None,
) -> None:
    """Transition the task; emit subscriber registry events; write audit row."""
```

**Subscriber registry event emission:** every transition fires `task_status_changed`; `created → assigned` additionally fires `task_assigned`; `* → done` additionally fires `task_completed`; `* → blocked` fires `task_blocked`; `blocked → *` fires `task_unblocked`; `* → cancelled` fires `task_cancelled`. See §5.3 for event-shape contract.

**Audit trail:** writes to existing audit_log table (verify table exists + write pattern at v1 dispatch — likely via existing `app/services/audit_service.py`). Actor + before/after state + resolution_outcome.

**Suppression-key check:** `apply_transition` checks if any task with the same `suppression_key` AND `current_state='done'` AND `completed_at > now() - SUPPRESSION_WINDOW` (e.g. 24h) exists; if yes, the new transition warns + proceeds (suppression at task-creation time, not transition time). The suppression-key field is set at task creation via the task creators plugin contract (see §5.4).

### 5.3 Subscriber registry

**Module path:** `backend/app/services/tasks/subscribers/__init__.py` + `registry.py` + per-subscriber modules (~200-300 LOC across files).

**7 event types:**

```python
EVENT_TYPES: tuple[str, ...] = (
    "task_created",
    "task_assigned",
    "task_status_changed",
    "task_completed",
    "task_blocked",
    "task_unblocked",
    "task_cancelled",
)
```

**6 v1 subscribers** (ship in v1.0; some are no-ops in v1.0 + activate in v1.5):

| Subscriber | v1.0 behavior | v1.5 behavior |
|------------|---------------|---------------|
| `notification_dispatcher` | Registered; observes events; **does NOT dispatch** (v1.0 keeps (c) direct path) | Dispatches via `notify_users_with_permission` + replaces (c) producer-site direct calls |
| `audit_writer` | Writes audit_log row per event | Same |
| `idempotency_recorder` | Checks composite key on `task_created`; raises if duplicate (per state doc §5.3 partial-unique enforcement at subscriber layer in addition to DB constraint) | Same |
| `suppression_checker` | Checks suppression_key on `task_created`; warns + proceeds if recent done-task with same key exists | Same |
| `briefings_invalidator` | Registered; no-op (v1.0 briefings don't read task substrate) | Invalidates briefings cache on `task_created` / `task_completed` |
| `pulse_invalidator` | Registered; no-op (v1.0 `_build_tasks_item` still returns None) | Invalidates Pulse cache on `task_created` / `task_completed` / `task_assigned` |

**Sync execution semantics** (per phasing §1.1.4):

- All subscribers fire synchronously within the task lifecycle transaction.
- Each subscriber wraps its body in try/except — a failed subscriber logs the exception + continues to next subscriber; the task transaction commits regardless.
- Subscriber order is deterministic (registration order; documented in `registry.py`).
- Persistent log defers to v2c per phasing §3.3.

**Idempotency per subscriber:**

- `notification_dispatcher` checks `(provenance_kind, provenance_ref_type, provenance_ref_id, event_kind, "notification_dispatched")` before firing (via a new `subscriber_idempotency` table OR via existing notification dedup — verify at v1 dispatch; likely net-new lightweight table at r107).
- `audit_writer` is naturally idempotent (each transition creates new audit row; no dedup required).
- Others as appropriate.

**Public API:**

```python
def emit_event(
    db: Session,
    *,
    event_type: str,
    task_details_id: str,
    actor_user_id: str | None,
    payload: dict[str, Any],
) -> None:
    """Dispatches event to all registered subscribers synchronously."""

def register_subscriber(
    name: str,
    handler: Callable[[Session, dict[str, Any]], None],
    *,
    event_types: tuple[str, ...] = EVENT_TYPES,
) -> None:
    """Registration mechanism. Called at module import time from each subscriber file."""
```

### 5.4 Three plugin category contracts

**Module path:** `backend/app/services/tasks/plugins/` + `contracts.py` (~100-150 LOC per contract; ~400-450 LOC total).

Follows existing Bridgeable Tier R1 in-memory plugin pattern (`PLUGIN_CONTRACTS.md` §"Intake adapters" precedent — typed Protocols + module-import-time registration + introspection helpers).

**Contract 1 — Task creators.** Input: caller-specific kwargs; output: created task_details_id. Guarantees: idempotency via composite key; emits `task_created` event; honors suppression_key.

```python
class TaskCreatorProtocol(Protocol):
    """Plugin shape for creating tasks from producer sites.

    Concrete creators per provenance_kind in §5.5 plugin set.
    """
    provenance_kind: str  # one of 12 values per §5.5
    task_type_default: str  # default task type plugin to invoke

    def create(
        self,
        db: Session,
        *,
        company_id: str,
        provenance_ref_type: str,
        provenance_ref_id: str,
        event_kind: str,
        title: str,
        description: str | None = None,
        assignee_user_id: str | None = None,
        priority: str = "normal",
        due_date: date | None = None,
        suppression_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Returns task_details_id of created task; raises if duplicate per idempotency."""
        ...

def register_task_creator(creator: TaskCreatorProtocol) -> None: ...
def get_task_creator(provenance_kind: str) -> TaskCreatorProtocol: ...
```

**Contract 2 — Task surfaces.** Surface registrations consumed by Visual Editor + Studio per Phase 3 §7 (which is canon-deferred; for v1 ships the contract surface only; concrete surface implementations are visual-editor-side work).

```python
class TaskSurfaceProtocol(Protocol):
    """Plugin shape for surface registrations.

    Visual editor authors surfaces; this Protocol declares the shape
    a registered surface honors so Workshop / Studio can introspect.
    """
    surface_key: str  # e.g. "task_list_default", "task_detail_default"
    surface_kind: str  # "list" | "detail" | "creation_form" | "card" | "row"
    accepted_task_types: tuple[str, ...]  # which task types this surface renders

    def render_context(
        self,
        db: Session,
        *,
        task_details_id: str,
        viewing_user_id: str,
    ) -> dict[str, Any]:
        """Returns render-context dict for the surface."""
        ...

def register_task_surface(surface: TaskSurfaceProtocol) -> None: ...
def get_task_surfaces(*, kind: str | None = None) -> list[TaskSurfaceProtocol]: ...
```

**Contract 3 — Task type behaviors.** Lifecycle behavior overrides, routing defaults, surface defaults per task type.

```python
class TaskTypeBehaviorProtocol(Protocol):
    """Plugin shape for task-type-specific behaviors.

    5 v1 plugins per §5.5 below.
    """
    task_type_key: str  # one of 5 v1 values
    default_lifecycle_shape: str  # 'action' or 'reminder'
    default_routing_mode: str  # 'direct_user' or 'round_robin'
    default_priority: str  # one of TASK_PRIORITIES
    default_visibility: str  # one of 5 visibility values

    def on_status_change(
        self,
        db: Session,
        *,
        task_details_id: str,
        from_state: str,
        to_state: str,
        actor_user_id: str | None,
    ) -> None:
        """Hook fired post-transition. Default: no-op."""
        ...

    def render_default_payload(
        self,
        db: Session,
        *,
        task_details_id: str,
    ) -> dict[str, Any]:
        """Per-task-type Pulse / briefing payload shape."""
        ...

def register_task_type_behavior(behavior: TaskTypeBehaviorProtocol) -> None: ...
def get_task_type_behavior(task_type_key: str) -> TaskTypeBehaviorProtocol: ...
```

### 5.5 Five task type behavior plugins (v1)

**Module path:** `backend/app/services/tasks/plugins/types/` (~100-150 LOC per plugin; ~600-750 LOC total).

**Twelve provenance_kind values** (frozen at v1; consumed by task creators):

```python
PROVENANCE_KINDS: tuple[str, ...] = (
    "workflow_step",           # workflow_engine creates task
    "intelligence_observation", # Intelligence observation produces task
    "manual_creation",          # user-driven creation
    "communication_inbound",    # inbound email/SMS produces task
    "integration_event",        # external integration produces task
    "shelf_parking",            # v3 — shelf parking; column present in v1
    "coaching_observation",     # v3 — coaching; column present in v1
    "scheduled_recurring",      # cron / scheduler / time-based producers
    "triage_event",             # triage queue action produces task
    "focus_completion",         # Focus session completion produces followup task
    "anomaly_detection",        # AgentAnomaly → task
    "system_internal",          # platform-internal admin task
)
```

**Five v1 task type plugins:**

1. **`generic_task`** — catch-all; default behaviors throughout. Default lifecycle_shape=`action`; routing_mode=`direct_user`; priority=`normal`; visibility=`operator_internal`. No hooks beyond defaults.

2. **`review_approval_task`** — covers approval-gate cohort. Same defaults but priority=`high` for items with explicit due_date < 48 hours. Hook on `done` writes resolution_outcome="approved" if metadata.outcome="approved"; "rejected" if metadata.outcome="rejected"; else "completed". Used by 5 of 8 (c) producer sites (social_service_certificate, base_agent month_end_close, catalog_fetch, safety_program, workflow_engine).

3. **`scheduled_recurring_task`** — accounting recurring + aftercare. lifecycle_shape=`action`; routing_mode=`round_robin` (load-distributes recurring work across role members). Hook on `created` populates default due_date based on metadata.recurrence_offset_days (e.g. month-end-close created on the 1st has due_date set 5 days later). Used by aftercare_adapter.

4. **`customer_communication_task`** — communications cascade. lifecycle_shape=`action`; routing_mode=`direct_user`; default_visibility=`operator_internal` (v2 family-portal extension uses different visibility). Hook on `done` writes outbound communication if metadata.outbound_response is set. Used by classification/dispatch + future communications cascade work.

5. **`anomaly_resolution_task`** — AgentAnomaly producer sites (3 of base_agent's 4 producers — cash_receipts, ar_collections, expense_categorization). lifecycle_shape=`action`; routing_mode=`direct_user`; priority=`high`. Hook on `done` updates AgentAnomaly.is_resolved=True via existing service path.

### 5.6 Task service layer extension + Task façade

**Existing file extension:** `backend/app/services/task_service.py` (currently 298 LOC; extends to ~500-600 LOC) — new functions added alongside existing surface; existing public API preserved.

**Façade pattern:** the existing `Task` ORM model (`backend/app/models/task.py`) keeps its public attribute surface. v1.0 adds a class method or service-level façade function that, given a Task row, reads through to find the matching VaultItem + task_details row + returns a "rich Task" view object (or extends `Task` with properties that lazy-load task_details fields). Build agent picks implementation at v1 dispatch — both shapes preserve the 8 consumer contract.

**8 existing Task consumers preserved unchanged in v1.0** (per phasing §1.1.7 + state doc §2.5):

1. `_dq_task_triage` direct query at `triage/platform_defaults.py:45` (`source_direct_query_key="task_triage"` — verify the actual direct-query function at v1 dispatch).
2. NL creation extractor (verify path at `nl_creation/entity_registry.py` per grep result above).
3. Peek builder at `peek/builders.py`.
4. Route handlers at `api/routes/tasks.py`.
5. `task_service.create_task` itself (currently fires `task_assigned` at line 174; (c) refactor at v1.5 changes this).
6. `_build_tasks_item` stub at `pulse/personal_layer_service.py:87-168` (still returns None at v1.0; wires at v1.5).
7. Triage action handlers at `triage/action_handlers.py`.
8. Command bar resolver at `command_bar/resolver.py`.

**New service-layer functions added in v1.0:**

```python
def create_task_with_provenance(
    db: Session,
    *,
    company_id: str,
    provenance_kind: str,
    provenance_ref_type: str,
    provenance_ref_id: str,
    event_kind: str,
    task_type_key: str,
    title: str,
    description: str | None = None,
    assignee_user_id: str | None = None,
    priority: str | None = None,  # None → task type default
    due_date: date | None = None,
    suppression_key: str | None = None,
    visibility: str | None = None,  # None → task type default
    metadata: dict[str, Any] | None = None,
) -> str:
    """Creates VaultItem + task_details + emits task_created event.

    Honors composite idempotency key via DB partial unique +
    subscriber-layer check. Returns task_details_id.
    """

def get_task_details(db: Session, *, task_details_id: str) -> TaskDetails: ...
def transition_task(
    db: Session,
    *,
    task_details_id: str,
    to_state: str,
    actor_user_id: str | None,
    resolution_outcome: str | None = None,
) -> None: ...

# Façade preserves existing 8 consumers' contract:
def list_tasks_via_facade(db: Session, *, company_id: str, ...) -> list[Task]:
    """Equivalent to existing list_tasks but reads through new substrate.
    Returns Task façade objects with .task_details lazy-loaded.
    """
```

**Backward-compat verification (per phasing §1.2 acceptance criteria):**

- All 8 consumers exercised against staging at v1.0 → v1.5 gate.
- Specifically: `task_service.create_task` (existing function) keeps writing to `tasks` table AND additionally creates corresponding VaultItem + task_details (dual-write at v1.0; clean-cutover at v1.5 when (c) refactor activates the new path).

OR — alternative shape — at v1.0 close, `task_service.create_task` writes ONLY through new substrate (creating VaultItem + task_details + a synthetic `tasks` row for façade compatibility). Build agent picks at v1 dispatch; either works for v1.0 → v1.5 backward-compat.

### 5.7 v1.0 tests (~150-200 tests per phasing §1.5)

**Test files** (new under `backend/tests/tasks/`):

- `test_schema_migration.py` — r107 applies cleanly, downgrades cleanly, columns + indexes present per spec (~10 tests)
- `test_backfill.py` — backfill idempotent (run twice → no extra rows), legacy 5-state maps correctly to action shape, all existing Task rows acquire VaultItem + task_details, ENVIRONMENT=production refusal works (~15-20 tests)
- `test_lifecycle.py` — action shape transitions (all valid + invalid pairs), reminder shape transitions, legacy-status-map correctness, completed_at auto-set on `done` (~30-40 tests)
- `test_subscribers.py` — 7 event types fire correctly; 6 subscribers register; sync semantics (one failure doesn't block others); idempotency composite key prevents duplicates (~25-30 tests)
- `test_plugin_contracts.py` — 3 categories register + introspect cleanly; Protocol shape enforced; registration mechanism idempotent (~15-20 tests)
- `test_plugin_types.py` — 5 plugins × ~6 behaviors each ≈ ~30 plugin tests
- `test_service_facade.py` — `create_task_with_provenance` correctness; tenant isolation; idempotency via composite key; façade compat against 8 existing consumers (~25-30 tests)
- `test_backward_compat.py` — 8 existing consumers exercised against new substrate (each consumer ≥ 1 happy-path assertion + ≥ 1 façade-via-substrate assertion) (~10-15 tests)

**Coverage targets:**

- Schema migration tests cover r107 apply + downgrade + table shape.
- Backfill tests verify both empty-database (zero existing tasks) and pre-populated-database (synthetic 100-task fixture) paths.
- Lifecycle tests assert the legacy 5-state → action-shape mapping AT BACKFILL TIME, not at runtime (runtime uses the new shape canonically).
- Subscriber sync-failure isolation tested via monkey-patched subscriber that raises; verify other subscribers still fire + task transaction commits.

### 5.8 v1.0 internal close gate (per phasing §1.2 + §5.1)

v1.0 closes (internally — no git commit at v1.0) when ALL of:

1. r107 migration applies cleanly on staging.
2. Backfill catches every existing `tasks` row; spot-check verifies 1:1 VaultItem creation; pre/post backfill query results identical via façade.
3. All 8 existing Task consumers exercised against staging (manual + automated).
4. Synthetic scenario: create new task via service layer → VaultItem + task_details 1:1 → task_triage queue picks it up → existing `task_assigned` notification fires (unchanged path).
5. Real-data scenario: pre/post backfill query identity confirmed (sample 5 existing task rows; query through façade pre-backfill vs post-backfill identical).
6. Zero existing-surface behavior changes verified via full regression cohort.
7. Subscriber registry fires 7 event types correctly; idempotency composite key prevents duplicates under retry.
8. Five task type plugins register + resolve correctly; lifecycle transitions per plugin honored.

Build agent surfaces a "v1.0 acceptance criteria met; ready to dispatch v1.5?" message in a single conversation turn (per phasing §8.8 conversational gate). Operator confirms or surfaces concerns. **If material divergence surfaces, STOP arc + surface findings + decide whether to extend v1.0, alter v1.5 scope, or pause.**

---

## §6. v1.0 → v1.5 operator-confirm gate

Per phasing §1.3 + §5.1 + operator §8.8 resolution.

### 6.1 Gate format

Conversational. Build agent surfaces:

```
v1.0 substrate complete. Acceptance criteria status:
  [x] r107 applied cleanly on staging
  [x] Backfill caught N rows; spot-check 1:1 verified
  [x] 8 existing Task consumers exercised — list with status
  [x] Synthetic + real-data scenarios pass
  [x] Zero existing-surface behavior changes verified
  [x] Subscriber registry + 5 plugins active
  
Outstanding findings: [none] OR [list]

Ready to dispatch v1.5 integration phase?
```

Operator confirms in same response thread. v1.5 dispatches immediately.

### 6.2 Working-tree hygiene during gate

Per phasing §6.4 + operator §8.1 resolution: **no git commit at v1.0 close.** Work stays uncommitted in working tree.

Practical implication: if another arc needs to ship during the v1.0 → v1.5 gate window (uncommon but possible), build agent surfaces the conflict to operator immediately. Operator decides: stash work (git stash with explicit message), branch off (work continues on a v1-work branch), or pause v1 arc.

**The gate window should be short** (hours, not days) — substrate validates against staging quickly; operator confirms; v1.5 dispatches.

### 6.3 What gate failure looks like

If acceptance criteria don't meet:

- r107 migration fails: investigate root cause (FK conflict? backfill loop? missing column?); fix in-place; re-run; do not proceed to v1.5 until clean.
- Backfill drops or duplicates rows: investigate idempotency logic; fix; re-run backfill in dry-run mode against staging; verify counts match before proceeding.
- 8 existing Task consumers regress: investigate per-consumer; fix façade or service-layer extension; do not proceed to v1.5.
- Synthetic scenario fails: investigate task creation → triage queue surface → notification path; this is end-to-end smoke; failure here suggests substrate integration gap.

In all cases: STOP, surface to operator, decide next step. Do not silently extend v1.0 scope or compress v1.5 scope.

---

## §7. Phase B (v1.5) — integration

v1.5 ships 8 integration items per phasing §2.1. The substrate validated at v1.0 is now wired into Pulse / briefings / (c) refactor / workflows / Focus / Intelligence / communications. Single commit at v1.5 close covers both phases.

### 7.1 Pulse `_build_tasks_item` wire

**File touched:** `backend/app/services/pulse/personal_layer_service.py:87-168`

**Change:** remove `return None` at line 111; preserve scaffolded query at lines 116-168 (minor adjustment to read through new substrate via façade or `get_task_details`-shaped helper).

**Query shape (post-substrate):** query `task_details` JOIN `vault_items` filtered by `vault_items.company_id == user.company_id AND vault_items.item_type='task' AND task_details.assignee_user_id == user.id AND vault_items.is_active AND task_details.current_state IN ('created', 'assigned', 'in_progress', 'blocked')`. Order by `priority` (urgent → high → normal → low) then `due_date` ASC NULLS LAST. Limit 20.

**LOC envelope:** ~50-80 LOC of net change (mostly un-commenting + minor query adjustment per phasing §2.1.1).

**Composition engine matching:** v1.5 work also ensures composition_engine's IntelligenceStream registration on dispatch side has a matching entry for `tasks_assigned` component key (the W-4a Cleanup Session B.1 deferral note in the scaffolded code mentions this was the original blocker). Build agent verifies at v1.5 dispatch against `backend/app/services/pulse/composition_engine.py` or equivalent.

**Test:** Pulse Personal layer renders task list for viewing user with assigned tasks; renders nothing when zero tasks (no empty-state cards); priority ordering correct; tenant isolation enforced.

### 7.2 Briefings consumption

**File touched:** new helpers added to existing briefings substrate (verify path at v1.5 dispatch; likely `backend/app/services/briefings/data_sources.py` or similar — the briefings substrate landed mid-2026; current file location requires verification).

**Three new helpers** (per phasing §2.1.2):

```python
def pull_tasks_needing_attention_this_week(
    db: Session,
    *,
    company_id: str,
    user_id: str,
) -> list[dict]:
    """Returns assigned + active tasks for user with due_date ≤ today+7."""

def pull_tasks_resolved_recently(
    db: Session,
    *,
    company_id: str,
    user_id: str,
    since: datetime,
) -> list[dict]:
    """Returns user's tasks completed (current_state='done') since timestamp."""

def pull_tasks_upcoming_deadlines(
    db: Session,
    *,
    company_id: str,
    user_id: str,
    days_ahead: int = 14,
) -> list[dict]:
    """Returns user's active tasks with due_date in window."""
```

**LOC envelope:** ~150-200 LOC across 3 helpers + integration points (replaces ad-hoc per-domain "what needs attention" queries with task-substrate-canonical reads).

**Briefings prompt template additions deferred** to canon-update arc per phasing §2.1.2; v1.5 ships helpers + invocation from current briefings substrate; prompt-template wording stays current shape.

### 7.3 (c) refactor of 8 producer sites

**Pattern per site** (per phasing §2.1.3 table):

```
PRE-REFACTOR (current state):
  producer_code:
    ...
    notify_users_with_permission(
        db, company_id, permission_key, title, message, ...
    )

POST-REFACTOR (v1.5):
  producer_code:
    ...
    task_id = task_service.create_task_with_provenance(
        db,
        company_id=company_id,
        provenance_kind=<per-site>,
        provenance_ref_type=<per-site>,
        provenance_ref_id=<per-site>,
        event_kind=<per-site>,
        task_type_key=<per-site>,
        title=title,
        description=message,
        ...
    )
    # task_created event fires from lifecycle; notification_dispatcher
    # subscriber catches event + calls notify_users_with_permission
    # (same downstream function; different upstream path).
```

**Per-site map** (re-derived against current code at v1.5 dispatch; values per phasing §2.1.3):

| Site | task_type / provenance_kind / category |
|------|------------------------------------------|
| `task_service.py:164` | NO REFACTOR — already task creation; just ensure subscriber dispatches `task_assigned` (the existing inline notification dispatch at lines 172-192 is REMOVED in v1.5; subscriber takes over) |
| `social_service_certificate_service.py:160` | `review_approval_task` / `anomaly_detection` / `ss_cert_pending` |
| `base_agent.py:103` | `anomaly_resolution_task` / `anomaly_detection` / `agent_anomaly_pending` (3 anomaly producers); `review_approval_task` for month_end_close branch |
| `aftercare_adapter.py:204` | `customer_communication_task` / `scheduled_recurring` / `funeral_followup_pending` |
| `catalog_fetch_adapter.py:256` | `review_approval_task` / `integration_event` / `catalog_fetch_pending` |
| `safety_program_generation_service.py:177` | `review_approval_task` / `scheduled_recurring` / `safety_program_pending` |
| `workflow_engine.py:812` | `review_approval_task` / `workflow_step` / `workflow_review_pending` |
| `classification/dispatch.py:377` | `customer_communication_task` / `communication_inbound` / `intake_classification_pending` |

**LOC envelope:** ~250-300 LOC total per phasing §2.1.3.

**(c) parity regression:** new tests assert that for each site, the notification dispatch shape (recipient cohort, title, message, category, link) is IDENTICAL pre/post refactor. Test pattern: synthetic trigger of producer site → assert notification rows created match pre-refactor shape. (c)'s helper unchanged.

**(c) backfill alignment:** the v1.5 commit ALSO writes a one-time backfill (small; ~50 LOC) that creates task_details rows for any pre-existing pending-attention notification rows (created by (c) backfill at `seed_pending_attention_backfill.py`). This ensures that v1.5 ships not just net-new-pending tasks but a unified pending-task view across legacy + new substrate.

### 7.4 Three workflow node types

**File touched:** `backend/app/services/workflows/` — register 3 node types via existing workflow plugin pattern (verify at v1.5 dispatch against existing canonical node-type registrations like `send_email`, `generation_focus_invocation`).

**Three node types:**

1. **`create_task`** — workflow step creates a task and continues. Config: `task_type_key`, `title_template`, `description_template`, `assignee_resolution` (literal user_id or role-based), `priority`, `due_offset_days`.

2. **`wait_for_task_completion`** — workflow step pauses until task transitions to `done` or `cancelled`. Config: `task_details_id` (resolved from prior step output) + `timeout_days` (optional escalation). Subscriber registry fires `task_completed` → workflow_engine resumes.

3. **`route_on_task_outcome`** — workflow step branches based on task's `resolution_outcome`. Config: `outcome_branches: dict[outcome_value, next_step_id]`.

**LOC envelope:** ~200-300 LOC total per phasing §2.1.4.

**Tests:** round-trip test covers create_task → wait_for_task_completion → route_on_task_outcome; workflow correctly pauses + resumes + branches on outcome.

### 7.5 Focus extension column

**Migration:** an additional schema delta lands inside the v1.5 commit. Either bumps to **r108** (separate from r107) OR absorbs into r107 (atomic schema for v1).

**Phase 5 recommendation:** **separate migration r108** for `focus_sessions.task_id` column.

Reasoning: r107 is "task substrate" scope; r108 is "Focus integration" scope. Even though both ship in v1.5's single commit, keeping them as separate alembic files preserves clean rollback path + clearer history. Build agent re-verifies at v1.5 dispatch.

**Schema change:**

```
ALTER TABLE focus_sessions
  ADD COLUMN task_id String(36) NULL,
  ADD CONSTRAINT fk_focus_sessions_task
    FOREIGN KEY (task_id) REFERENCES vault_items(id) ON DELETE SET NULL;
CREATE INDEX ix_focus_sessions_task_id ON focus_sessions(task_id);
```

**Service-layer extension:** Focus open flow accepts optional `task_id` parameter; persists when supplied; subscriber on `task_completed` updates linked focus_sessions.is_active=False.

**LOC envelope:** ~100-150 LOC per phasing §2.1.5.

### 7.6 Intelligence task-creation refactor

**Files touched:** verify Intelligence producer sites at v1.5 dispatch (likely under `backend/app/services/intelligence/`); 3-5 sites typical.

**Refactor pattern:** producers currently fire notifications + ephemeral surfaces; post-refactor producers call `create_task_with_provenance(... provenance_kind='intelligence_observation', task_type_key='generic_task' ...)`. Task persists; user can return to it; Pulse + briefings surface it.

**LOC envelope:** ~150-200 LOC per phasing §2.1.6.

### 7.7 Communications cascade task-creation

**File touched:** `backend/app/services/classification/dispatch.py:377` (overlaps with §7.3 item #8; refactor pattern resolved at v1.5 dispatch).

**Behavior:** inbound communication (email / SMS / form submission per R-6.2a intake substrate) produces task with `provenance_kind='communication_inbound'`, `task_type_key='customer_communication_task'`. Existing `classification/dispatch.py:377` notification fires from task creation (per (c) refactor §7.3) AND task persists.

**LOC envelope:** ~150-200 LOC per phasing §2.1.7.

### 7.8 Two routing modes + visibility enforcement

**Migration r108 (or absorbed into r107 — see §7.5):** also adds `task_routing_rules` table.

```
task_routing_rules
  id                  UUID PRIMARY KEY
  scope               String(20) CHECK IN ('platform', 'vertical', 'tenant')
  vertical            String(32) NULL  -- when scope='vertical'
  tenant_id           String(36) NULL  -- when scope='tenant'
                       FOREIGN KEY → companies(id) ON DELETE CASCADE
  task_type_key       String(32) NOT NULL
  routing_mode        String(16) NOT NULL CHECK IN ('direct_user', 'round_robin')
  routing_config      JSONB NOT NULL DEFAULT '{}'::jsonb
  is_active           Boolean NOT NULL DEFAULT TRUE
  created_at          DateTime NOT NULL
  updated_at          DateTime NOT NULL
```

**Three-tier resolver** (per state doc §5.4 + Phase 3 §10):

```python
def resolve_routing_rule(
    db: Session,
    *,
    company_id: str,
    task_type_key: str,
) -> RoutingRule:
    """Looks up tenant → vertical → platform. First match wins."""
```

**`direct_user` mode:** fixed-recipient assignment; assignee_user_id resolved at task creation from caller-supplied value OR routing_config.default_user_id.

**`round_robin` mode:** load-distributes across role members matching routing_config.role_slug; round-robin index persisted in routing_config or tenant-level state.

**Visibility enforcement** (per state doc §5.5; operator-only in v1):

```python
VISIBILITY_VALUES: tuple[str, ...] = (
    "operator_internal",   # default; visible to operator users in tenant
    "operator_assigned",   # visible only to assignee
    "portal_family",       # forward-compat for v2b; v1 query filter rejects
    "portal_contractor",   # forward-compat for v3a; v1 query filter rejects
    "portal_partner",      # forward-compat; v1 query filter rejects
)
```

v1 query filter at service layer + API layer:

```python
def _apply_visibility_filter(query, *, viewing_user):
    if viewing_user.realm == "platform":
        return query  # platform admin sees all
    if viewing_user.realm == "tenant":
        return query.filter(
            TaskDetails.visibility.in_(("operator_internal", "operator_assigned"))
        )
    if viewing_user.realm == "portal":
        # v1 rejects entirely; v2/v3 implement portal filter
        return query.filter(False)
```

**LOC envelope:** ~250-350 LOC per phasing §2.1 routing + visibility lines combined.

### 7.9 v1.5 tests (~100-150 tests per phasing §2.5)

- Pulse render tests (mocked task state) — ~10
- Briefings consumption tests (3 helpers × ~5 cases) — ~15
- (c) parity regression — 8 producer sites × ~5 assertions = ~40
- Workflow node tests — 3 nodes × ~5 scenarios = ~15
- Focus integration tests — ~5
- Intelligence + communications refactor parity — ~10
- Routing mode tests — direct_user, round_robin distribution, three-tier resolver — ~10
- Visibility enforcement — operator-only, portal-rejection — ~10
- End-to-end task-creation-to-completion happy path — ~5

### 7.10 Single commit at v1.5 close

**Commit message structure** (single commit; covers v1.0 + v1.5):

```
feat(tasks): v1 task substrate — VaultItem 12th item_type + 
  dual-shape lifecycle + subscriber registry + (c) refactor + 
  Pulse/briefings/workflow/Focus integration

v1.0 substrate phase:
- r107: VaultItem item_type 'task' + task_details join table 
  + 6 indexes + composite partial-unique idempotency
- Backfill script: legacy tasks → VaultItem + task_details 1:1
- Dual lifecycle state machine (action + reminder shapes)
- Subscriber registry: 7 events, 6 subscribers, sync exec
- 3 plugin contracts (creators / surfaces / type behaviors)
- 5 task type behavior plugins
- Task façade preserves 8 existing consumer contract

v1.5 integration phase:
- Pulse _build_tasks_item wired (W-4b deferral closed)
- Briefings: 3 helpers (attention/resolved/upcoming)
- (c) refactor: 8 producer sites → task-event-driven dispatch
- r108: focus_sessions.task_id + task_routing_rules
- 3 workflow node types (create_task / wait_for_task / 
  route_on_outcome)
- Focus extension (task → focus_sessions linkage)
- Intelligence task-creation refactor
- Communications cascade task creation
- 2 routing modes (direct_user + round_robin) + 3-tier resolver
- Visibility enforcement (operator-only v1; portal forward-compat)

~9,000 LOC; ~250-350 tests; closes v2 investigation v1 phase.
Migration head: r106 → r107 → r108.

Subsumes (d) projection-view from v1 investigation lineage.
Canon edits deferred to canon-update arc (next).
```

Push to main after commit.

---

## §8. Operational coexistence

### 8.1 v1.0 — purely additive

Zero existing-surface behavior changes (per phasing §1.8). All deferrals honored:

- 28 existing §19 categories unchanged.
- 8 existing Task consumers preserved via service-layer + façade.
- 10 non-task triage queues continue working via existing (c) pattern.
- `task_triage` queue continues working (reads through façade because backfill creates VaultItem 1:1).
- VaultItem schema beyond enum extension: no changes (task-specific concerns live in task_details).
- All other tables unchanged.

### 8.2 v1.5 — (c) refactor preserves dispatch behavior

8 (c) producer sites: notification path now flows producer → task creation → subscriber → `notify_users_with_permission`. **Operationally equivalent** — same notifications fire to same cohorts at same triggering moments. Parity regression verifies. Difference: task is now persisted + surfaceable.

**What changes operator-visibly at v1.5 close:**

- Pulse Personal layer: users see assigned-task list (where they previously saw nothing — the stub returned None).
- Briefings: "what needs attention this week" / "what got resolved" / "what's coming up" pull from task substrate.
- Workflow authoring: 3 new node types available.
- Intelligence: observations persist as tasks.
- Inbound communications: a task is created per inbound communication.

**What stays unchanged at v1.5 close** (deferred to v2/v3):

- V-1d notification dispatch helpers (signatures unchanged; only call sites shift).
- 10 non-task triage queues continue working via existing (c) pattern.
- Customer-facing portals: no task surfaces visible to PortalUser identities in v1.
- Task templates / authored task creators: defer to v2.

### 8.3 Tenant-specific behavior

- **Sunnycrest (`staging-test-001`):** existing behavior unchanged operator-visibly except for Pulse + briefings + new workflow nodes. Existing accounting agents (cash_receipts, ar_collections, etc.) keep firing on schedule; (c)'s notification dispatch still happens (now via task substrate; operationally equivalent).
- **Hopkins FH (`hopkins-fh`):** existing behavior unchanged except for Pulse + briefings. Aftercare adapter now creates tasks per-case (provenance_kind='scheduled_recurring'); existing aftercare email behavior preserved.

---

## §9. Material-divergence triggers

Build agent surfaces immediately to operator if ANY of:

1. **v1.0 production LOC exceeds ~6,500** (15% above 5,500 mid-estimate; trigger threshold per phasing §1.4).
2. **v1.5 production LOC exceeds ~4,100** (15% above 3,500 mid-estimate; trigger threshold per phasing §2.4).
3. **r107 schema migration surfaces breaking changes to any of 8 existing Task consumers** that the façade pattern cannot absorb.
4. **Subscriber registry substrate exceeds ~1,000 LOC** at v1.0 close (suggests investigation-worthy sub-question about substrate shape).
5. **(c) refactor surfaces idempotency dependencies** not visible in state doc §5.7 — e.g. an existing producer site has notification dedup logic that interacts non-trivially with the new composite-key idempotency.
6. **Any pre-existing tests start failing** post-v1.0 or post-v1.5 work that aren't trivially fixable by updating the test expectation to match preserved behavior.
7. **Phase A.0 scoping requires more than ~3 net-new questions** beyond the four anticipated in §4.1.
8. **Task façade backward-compat verification fails for any of 8 existing consumers** at v1.0 → v1.5 gate.
9. **r107 + backfill apply on staging surface FK or constraint violations** not surfaced in fresh-database test runs.
10. **Pulse `_build_tasks_item` re-enabling surfaces an IntelligenceStream composition_engine gap** that requires net-new composition_engine work beyond ~50-80 LOC (per phasing §2.1.1).

Triggers fire → STOP arc → write up findings → surface to operator → operator decides (extend phase scope, alter v1.5 scope, pause, or accept overshoot).

---

## §10. Locked disciplines

### 10.1 Single commit at v1 close

Per phasing §6.4 + operator §8.1 resolution. No commits at:
- Phase A.0 close
- v1.0 substrate close (= v1.0 → v1.5 gate)
- Mid-v1.5 work

Single commit covers both v1.0 + v1.5 work. Push to main after commit.

### 10.2 No canon edits

CLAUDE.md, BRIDGEABLE_MASTER.md, PLATFORM_ARCHITECTURE.md, DESIGN_LANGUAGE.md, PLUGIN_CONTRACTS.md, DECISIONS.md: NO EDITS during v1 arc. Canon candidates surfaced during v1 build (subscriber registry pattern canon, plugin contract Tier R1 canon extension, façade pattern canon, etc.) file forward to canon-update arc per phasing §6.2 + operator §8.5 resolution.

By v1 close: ~64+ canon candidates accumulated across full Bridgeable lineage. Canon-update arc dispatches next after v1 close.

### 10.3 No STATE.md edits until v1 close

STATE.md gets ONE entry at v1.5 close (= v1 close), in the single commit. No interim STATE.md updates. Phase 4 → Phase 5 gate (this dispatch) DOES include a STATE.md close note for the v2 investigation arc itself, separately, at Phase 5 close after operator confirms this build prompt — that's the closing STATE.md update for the v2 investigation arc, NOT for the v1 build arc.

### 10.4 Backfill same-commit with r107 migration

Per phasing §1.1.2 + (c) build arc canon. r107 + `seed_task_substrate_backfill.py` ship in the same commit (the v1.5-close commit). At v1.0 internal close, the migration has been applied to staging + backfill has been run, but git commit lands at v1.5 close.

### 10.5 114 stale screenshot deletions untouched

The state-of-tree shows 114 deleted screenshot files at git status time. v1 build arc does NOT touch these. They're orthogonal cleanup; not v1 scope.

### 10.6 Build prompt is locked

If execution surfaces material the prompt is wrong about, STOP and surface to operator. Do not silently revise build prompt scope.

Specifically: if at v1 dispatch the production code state has changed materially since this prompt was drafted (HEAD ca88f50 → some later commit), build agent surfaces the delta to operator before proceeding.

### 10.7 Bounded-decision invariant

Build closes when v1.5 lands with single commit + push + STATE.md close note. The bounded decision (per §1.2 above) is closed at that point. v2 dispatch waits for operator-observable signals per phasing §5.

### 10.8 ENVIRONMENT=production refusal guard

Backfill script + any other seed-script-shaped helper carries ENVIRONMENT=production refusal guard per (c) precedent + general Bridgeable seed-script canon.

---

## §11. STATE.md close note

Build agent writes at v1 close (in the single v1.5-close commit):

```
Task substrate v1 build arc — shipped foundational task substrate per
locked architecture + phasing. v1.0 substrate (~5,500 LOC): VaultItem
12th item_type 'task' + task_details join table + r107 migration +
backfill + dual lifecycle state machine (action + reminder shapes) +
subscriber registry (7 events / 6 subscribers / sync exec) + 3 plugin
category contracts (task creators / task surfaces / task type
behaviors) + 5 task type behavior plugins + Task service layer
extension + Task façade preserving 8 existing consumer contract.
v1.5 integration (~3,500 LOC): Pulse _build_tasks_item wired
(W-4b deferral closed) + briefings consume task substrate as
canonical "what needs attention" source (3 new helpers) + (c)
refactor of 8 producer sites to task-event-driven dispatch +
r108 focus_sessions.task_id + task_routing_rules table + 3
workflow node types (create_task / wait_for_task_completion /
route_on_task_outcome) + Focus extension (task→focus linkage) +
Intelligence task-creation refactor + communications cascade
task-creation + 2 routing modes (direct_user + round_robin) +
visibility enforcement (operator-only v1; portal forward-compat
schema in place). Single commit covers v1.0 + v1.5. Migration
head r106 → r107 → r108. ~250-350 tests; all green.

Closes v2 investigation arc's locked v1 phase. (d)
projection-view from v1 investigation lineage subsumed into v1.5
Pulse + briefings work. Canon-update arc dispatches next against
~64+ accumulated candidates; v2 sub-arcs (v2a triage adapters /
v2b family portal / v2c substrate refinements) signal-dispatched
per phasing §5.2 operator-observable workflow signals. Zero canon
edits this arc. Zero existing-surface behavior regressions.
```

LOC + test counts adjust to actuals at close.

---

## §12. Dispatch acknowledgement

### 12.1 Opening message protocol

Build agent opens v1 arc with single message:

1. **Read-order confirmation:** "Completed full read order — state doc + phasing + this build prompt + canon docs + 17 production code anchors + 8 (c) precedent files."

2. **Current-state re-verification:** "HEAD at v1 dispatch is [SHA]. Material delta from build-prompt-draft HEAD ca88f50: [none / list]."

3. **Phase A.0 scoping resolution:** surface Q-A0-1 through Q-A0-4 + any newly-discovered scoping questions with Phase 5 recommendations.

4. **Acceptance criteria preview:** confirm v1.0 acceptance criteria per phasing §1.2 + §5.8 above are understood.

5. **Wait for operator confirmation.**

### 12.2 Operator confirms

Operator confirms / refines in same response thread:

- Phase A.0 question resolutions confirmed or refined.
- Any newly-surfaced scoping questions resolved.
- Any material-delta concerns addressed.

### 12.3 Build agent proceeds

Build agent proceeds to v1.0 substrate work immediately. Single-message dispatch protocol — no further round-trip until v1.0 → v1.5 gate.

### 12.4 If dispatch surfaces blocking material divergence at opening

STOP. Surface findings to operator. Do not proceed.

Examples of opening-blocker shapes:

- Existing code state shows `tasks` table was renamed since Phase 5 drafted (highly unlikely; flagged for completeness).
- VaultItem schema has gained material columns since draft that interact with task_details design.
- A canon doc was edited in a way that conflicts with the v1 scope above.
- 8 existing Task consumers grew to 9+ since draft, OR shrunk to ≤7 with one of the original 8 removed.

---

*Document captured May 25, 2026 by Opus in service of Phase 5 v1 build prompt against state doc + phasing doc + current code state at HEAD ca88f50. Closes the v2 investigation's Phase 5 bounded decision. Dispatches v1 build arc upon operator confirmation. v1 build arc closes the bounded decision: ship task substrate v1 (substrate + integration) as a single arc with internal phase gate, single commit at v1.5 close, STATE.md close note in the same commit.*
