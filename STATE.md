# Bridgeable — Current State

Single source of truth for what is true RIGHT NOW. Updated by Sonnet at the end of every build session. Canon lives elsewhere — see read order in CLAUDE.md.

## Production

- Live tenant: Sunnycrest Precast at `sunnycrest.getbridgeable.com` (first tenant: James Atkinson)
- Go-live date: April 7, 2026
- Migration head: `r95_verticals_table`

## Build status

| Metric | Count |
|--------|-------|
| Database tables | ~258 |
| ORM model files | 165+ |
| ORM model exports (`__init__.py`) | 178+ |
| API route files | 105+ |
| API endpoints | 955+ |
| Route modules registered in v1.py | 95+ |
| Frontend routes | 150+ |
| Backend service files | 117+ |
| Migration files | 133 |
| Documents test suite (D-1 → D-9) | 224 passing |
| Agent jobs (scheduled) | 14 |
| Accounting agents (registered) | 12/12 (complete) |
| Accounting agent tests | 105 passing |
| Urn Sales E2E tests | 39/39 passing |
| Safety Program Generation E2E tests | 12/12 passing |
| Agent jobs (not yet built) | ~30 |
| TypeScript errors | 0 |
| Backend import errors | 0 |
| Migration chain | Single head, no broken links |

## Active arc

- Arc name: Studio shell precursors → Bridgeable Studio shell arc (consolidating 7 visual editors + runtime-aware editor under `/studio`)
- Current phase: Studio 1a-i.A1 next — Studio shell substrate (routing, rail, redirect, placeholder overview, smoke tests). Per DECISIONS.md 2026-05-13 (PM), 1a-i splits into A1 → A2 → B.
- Last shipped: Verticals-lite precursor (`c70050f` chain, 2026-05-13) — `verticals` table + service + admin page

## Active deferred items

- **Data Migration Tool** — waiting on Sage CSV exports from Sunnycrest accountant (invoice history, customer list, cash receipts)
- **Studio 1a-i.A2** — Live mode wrap + impersonation handshake (next after A1). **Studio 1a-i.B** — editor adaptation pass (after A2). **Studio 1a-ii** — overview surface implementation with inventory service (after 1a-i complete). **Spaces substrate arc** — locked as immediate post-Studio-shell priority per DECISIONS.md 2026-05-13.
- **Arc 4a.2b** — vault cluster Path 1 wrap (9 widgets) + dashboard_layouts seed script; sibling of Arc 4a.2a (committed `8affc8f`); estimated ~1,300-1,800 LOC
- **revenue_summary + ar_summary** — declared in backend WIDGET_DEFINITIONS but no frontend React component; documented in widget-renderer-parity.test.ts `KNOWN_DEFERRED_VAULT`; hygiene arc TBD
- **13 simpler agent jobs** — `STALE_DRAFT_MONITOR`, `REVERSAL_RUNNER`, `PO_DELIVERY_MONITOR`, `RECONCILIATION_MONITOR`, `ABANDONED_RECONCILIATION_MONITOR`, `STATEMENT_RUN_MONITOR`, `FINANCE_CHARGE_REMINDER`, `EXEMPTION_EXPIRY_MONITOR`, `1099_MONITOR`, `DELIVERY_WEEKLY_REVIEW`, `FINANCE_CHARGE_INSIGHT_JOB`, `DISCOUNT_UPTAKE_JOB`, `OUTCOME_CLOSURE_JOB`
- **NPCA Audit Prep feature** — placeholder UI at `/npca`; full feature not yet built (compliance score engine, gap analysis, audit package ZIP)
- **Performance optimization** for report generation
- **FastAPI `@app.on_event` → lifespan migration** — deprecated pattern; mechanical migration deferred to FastAPI version-bump arc
- **R-9 workflow node registry promotion** — ~900 LOC + BLOCKING parity test
- **R-classify customer classification refactor** — ~600 LOC + BLOCKING parity test
- **R-8.x cleanup arcs** — 5 bounded items (EmailChannel exception classes, Triage vertical_default scope, TriageQueueConfig discriminated union, AGENT_REGISTRY side-effect-import, ApprovalFlow enum)
- **R-8.y+1** — per-tenant configuration browser extending R-8.y.d
- **Bounded sub-arcs (trigger-driven)**: Arc-3.x-page-context-substrate, Arc-3.x-hybrid-filter, Arc-3.x-mount-gate, Arc-4a.x-IconPicker-rollout, Arc-4b.x-nesting-ui, Arc-4b.x-mention-hover-preview, Arc-4.x-approval-gate

## Recently shipped (rolling, last 10)

1. **Verticals-lite precursor** (this commit, 2026-05-13) — `verticals` table + service + 3 admin endpoints + `/admin/verticals` page; precursor to Studio shell. Migration `r95_verticals_table` (spec named `r92` but r92-r94 already existed; renumbered per CLAUDE.md §12 Spec-Override). ~720 LOC.
2. **Arc 4a.2a** (`8affc8f`, 2026-05-13) — Ops-board cluster Path 1 wrap + 28 supported_surfaces backfills + dashboard-grid parity test branch. 17 ops-board widgets wrapped via registerComponent HOC; componentMap consumers updated; revenue_summary + ar_summary deferred (no frontend React component). ~1,624 LOC.
3. **Arc 4d** (`9fbcab5`, 2026-05-13) — Scope cascade visualization + tenth canonical shared authoring primitive (SourceBadge with letter/chip variant) + eleventh candidate co-located (ScopeDiffPopover). Documents Class C → Class B transition via `_resolve_version` extension. Sixth audit-count recalibration shape (audit-frames-as-uniform-where-substrate-architecturally-distinct). PRE-SEPTEMBER ARC 4 SEQUENCE CLOSES. ~1,565 LOC.
4. **Canon/state separation** (`c655771`, 2026-05-13) — CLAUDE.md cleanup (2537 → 1631 lines) + STATE.md + DECISIONS.md. Documentation discipline: Sonnet writes STATE.md only; canon stays canon (Opus-only, batched).
5. **Arc 4c** (`efeed99`, 2026-05-12) — Focus compositions canvas polish: AlignmentGuideOverlay + shift-marquee cumulative-select + drop-shadow drag lift + inspector Move-left/Move-right + Alt+Arrow keyboard reorder + ColumnCountPopover. ~1,747 LOC.
6. **Arc 4b.2b** (`7ff864a`, 2026-05-12) — Mention consumer UX: `@` trigger + SuggestionDropdown integration + getCaretCoordinates companion utility + 4 Jinja-aware field sites. ~1,400 LOC.
7. **Arc 4b.2a** (`66ec8c5`, 2026-05-12) — Mention substrate: Jinja `ref` filter + dedicated `/api/v1/documents-v2/admin/mentions/resolve` endpoint + per-render MentionResolutionCache. ~640 LOC.
8. **Arc 4b.1b** (`a534adb`, 2026-05-12) — SuggestionDropdown (9th shared primitive) + slash command insertion + drag-drop block reorder via @dnd-kit/sortable + Alt+ArrowUp/Down keyboard. ~1,860 LOC.
9. **Arc 4b.1a** (`3008ca2`, 2026-05-12) — PropControlDispatcher vocabulary extension: 4 new ConfigPropType discriminators + per-block-kind canonical dispatch. ~1,900 LOC.
10. **Arc 4a.1** (`63fc1c2`, 2026-05-12) — Focus action bar substrate via class-level buttonSlugs (R-2.1 canon reuse) + IconPicker as 6th shared authoring primitive. ~810 LOC.

## Open questions / blockers

- **Sage CSV exports** — blocked on Sunnycrest accountant providing invoice history, customer list, cash receipts files. Once received, Data Migration Tool can complete.
- **Pre-existing bugs** catalogued in `backend/docs/BUGS.md` (separate file) — `quote_service` calls `audit_service.log` but function is `log_action` (BUGS.md entry #7), unrelated to active arc.
