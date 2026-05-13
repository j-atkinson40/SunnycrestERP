# Bridgeable — Current State

Single source of truth for what is true RIGHT NOW. Updated by Sonnet at the end of every build session. Canon lives elsewhere — see read order in CLAUDE.md.

## Production

- Live tenant: Sunnycrest Precast at `sunnycrest.getbridgeable.com` (first tenant: James Atkinson)
- Go-live date: April 7, 2026
- Migration head: `r91_compositions_kind_and_pages`

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

- Arc name: Visual authoring substrate (Arc 4 sequence) — pre-September Wilbert demo prep
- Current phase: Arc 4d — uncommitted in working tree (scope cascade visualization + SourceBadge tenth canonical shared authoring primitive + ScopeDiffPopover eleventh candidate co-located)
- Last shipped: Arc 4c (commit `efeed99`) — Focus compositions canvas polish (alignment guides + keyboard nudge + inspector inline ops)

## Active deferred items

- **Data Migration Tool** — waiting on Sage CSV exports from Sunnycrest accountant (invoice history, customer list, cash receipts)
- **Arc 4a.2** — dashboard-componentMap substrate coverage; post-September; estimated 1,500-3,500 LOC (likely warrants 4a.2a/4a.2b split per sub-agent execution ceiling canon)
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

1. **Arc 4c** (`efeed99`, 2026-05-12) — Focus compositions canvas polish: AlignmentGuideOverlay + shift-marquee cumulative-select + drop-shadow drag lift + inspector Move-left/Move-right + Alt+Arrow keyboard reorder + ColumnCountPopover. ~1,747 LOC.
2. **Arc 4b.2b** (`7ff864a`, 2026-05-12) — Mention consumer UX: `@` trigger + SuggestionDropdown integration + getCaretCoordinates companion utility + 4 Jinja-aware field sites (header.title/subtitle + body_section.heading/body). ~1,400 LOC.
3. **Arc 4b.2a** (`66ec8c5`, 2026-05-12) — Mention substrate: Jinja `ref` filter + dedicated `/api/v1/documents-v2/admin/mentions/resolve` endpoint + per-render MentionResolutionCache. ~640 LOC.
4. **Arc 4b.1b** (`a534adb`, 2026-05-12) — SuggestionDropdown (9th shared primitive) + slash command insertion + drag-drop block reorder via @dnd-kit/sortable + Alt+ArrowUp/Down keyboard. ~1,860 LOC.
5. **Arc 4b.1a** (`3008ca2`, 2026-05-12) — PropControlDispatcher vocabulary extension: 4 new ConfigPropType discriminators (tableOfColumns, tableOfRows, listOfParties, conditionalRule) + per-block-kind canonical dispatch. ~1,900 LOC.
6. **Arc 4a.1** (`63fc1c2`, 2026-05-12) — Focus action bar substrate via class-level buttonSlugs (R-2.1 canon reuse) + IconPicker as 6th shared authoring primitive (45 curated lucide icons). ~810 LOC.
7. **Arc-3.x-deep-link-retrofit** (`7c56f44`, 2026-05-12) — Workflows + Documents bidirectional deep-link retrofit; extracted deep-link-state shared utility. ~635 LOC.
8. **Arc 3a** (`f0c8daf`, 2026-05-12) — Focus compositions tab on inspector with read-mostly canvas embed + bidirectional deep-link to standalone Focus editor. ~2,202 LOC.
9. **Arc 3b** (`e054e3a`, 2026-05-12) — Documents tab on inspector with 3-level mode-stack + per-block immediate writes (third save-semantics pattern). ~2,315 LOC.
10. **Phase R-8.y.d** (2026-05-11) — Plugin Registry browser at `/visual-editor/plugin-registry`; 24 plugin categories surfaced from PLUGIN_CONTRACTS.md.

## Open questions / blockers

- **Sage CSV exports** — blocked on Sunnycrest accountant providing invoice history, customer list, cash receipts files. Once received, Data Migration Tool can complete.
- **Arc 4d commit** — uncommitted in working tree; ready for user review per spec instruction "Do NOT push".
- **Pre-existing bugs** catalogued in `backend/docs/BUGS.md` (separate file) — `quote_service` calls `audit_service.log` but function is `log_action` (BUGS.md entry #7), unrelated to active arc.
