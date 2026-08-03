"""Tenant data wipe — dynamic, preserve-list inversion, dry-run by default.

WHY DYNAMIC: the delete-set is derived from the LIVE schema on every run
(every tenant-scoped table, minus an explicit preserve-list, plus FK
descendants). A hardcoded delete-list would rot the way tests/_cleanup.py
did — a table added next month would be silently missed. The preserve-list
is the small, reviewable, stable surface; everything else is wiped, which is
the correct failure direction: stale transactional data left behind means
wrong books (unrecoverable), while a wrongly-deleted config table is a
re-seed (recoverable).

THREE GUARDS (all hard failures, per the cutover-arc decisions):
  1. PRESERVE-LIST ASSERTION — every name in PRESERVE must exist in the live
     schema. A typo/rename that silently drops a table into the delete-set is
     the exact failure this inversion could otherwise cause.
  2. FK DESCENT — the delete-set includes child tables with no tenant column
     (invoice_lines, journal_entry_lines, …); any such descendant pulled in
     is NAMED in the dry-run, never implicit.
  3. BLOCKER CHECK — any PRESERVED table holding a NOT NULL FK (NO ACTION/
     RESTRICT) into the delete-set would break the wipe; reported + hard fail.

SAFETY MODEL (deliberate):
  * DRY-RUN IS THE DEFAULT. --execute is required to delete.
  * Typed-slug confirmation before executing.
  * NO environment guard — ENVIRONMENT is unreliable on this deployment
    (resolves to "dev" on production), so an env-based rail would fire on the
    real DB and block on nothing. The dry-run default + typed confirmation
    are the real rails.
  * CHUNKED + RESUMABLE, NOT ATOMIC (W-1c). Deletion runs as many small
    committed batches (per table, chunked within tables), NOT one transaction.
    Rationale — the 2026-07-29/30 incident: a single-transaction delete of
    ~112k rows pinned all its rollback WAL until commit, exhausted the Postgres
    volume (PANIC: No space left on device) twice, and left the DB unable to
    complete crash recovery for ~25 hours. A complete wipe's end state is
    "everything gone," so partial progress is MONOTONIC toward the goal — a
    half-finished wipe is incomplete, not corrupt. What the tool needs is
    IDEMPOTENCE + RESUMABILITY, not atomicity: re-running continues from
    wherever the data actually is (deleting already-deleted rows is a no-op; FK
    order is re-derived each pass; no checkpoint file, no state table). Per-batch
    commits let Postgres checkpoint and recycle WAL between batches, so WAL never
    accumulates toward the volume size.
  * DISK GUARD. Free space is read (superuser `COPY FROM PROGRAM 'df'`) before
    starting and re-checked between tables; the wipe refuses to start, and aborts
    cleanly mid-run, below a configurable floor (--disk-floor-gb). A clean abort
    mid-wipe is a SAFE state (resume by re-running). If free space cannot be read
    at all, the tool REFUSES — a disk guard that can't see the disk is not a guard.
  * TELEMETRY-FIRST. The high-volume execution-log tables (agent_run_steps,
    workflow_run_steps + their FK-descendant closure) are deleted first, after a
    guard that the closure reaches nothing books-critical (period_locks
    especially). Shedding the bulk first means the rest runs against a smaller job.
  * The dry-run output IS the review artifact: because behavior tracks the live
    schema, each run must be re-reviewed. It echoes the preserve-list, per-table
    delete counts, the child-only descendants, the telemetry closure, and disk.

DELETE ORDER: topological over NO ACTION / RESTRICT FK edges only (children
first). SET NULL and CASCADE edges impose no ordering (the DB resolves them),
which collapses the apparent FK "cycle" (verified nominal on this schema).
Within that order, telemetry-closure tables delete first — FK-safe because the
closure is closed under inbound FKs (nothing outside it references it).

Reads DATABASE_URL from the environment (no app import — pure DB tool).
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from collections import defaultdict, deque

from sqlalchemy import create_engine, text


# ── Preserve-list — THE reviewable artifact. Verified against live schema. ──
# Identity/access, workflow config, MoC substrate, focus config, user prefs,
# tenant config, tax config, and financial-account/bank/Plaid setup.
PRESERVE = {
    # identity & access
    "companies", "users", "roles", "custom_permissions", "role_permissions",
    # workflow config + templates (runs/reviews/classifications are NOT here — they delete)
    "workflow_templates", "tenant_workflow_forks", "workflows",
    "workflow_enrollments", "workflow_step_params", "workflow_schedules",
    # MoC automation substrate (the born-native scheduling lives here)
    "moc_job", "moc_task_catalog", "moc_task_trigger", "moc_composition",
    "moc_pages", "moc_task_vocabulary", "moc_trigger_event_catalog",
    "moc_planning_item", "moc_job_ref", "moc_task_catalog_focuses",
    "moc_witness_marker", "moc_domain_event",
    # focus configuration (authored layer)
    "focus_compositions", "focus_layout_defaults", "focus_templates",
    "focus_cores", "focus_template_verticals",
    # spaces / per-user preferences (NOT user_track_progress — that's training
    # PROGRESS data (status/module_completions/started_at), transactional, and
    # it holds a NOT NULL FK into training_curriculum_tracks (delete-set), so
    # preserving it would be a GUARD-3 blocker. It deletes.)
    "user_space_affinity", "user_ai_preferences", "user_learning_profiles",
    "user_widget_layouts", "user_location_access",
    # tenant config
    "company_modules", "tenant_extensions", "dashboard_layouts",
    "document_templates",
    # tax config
    "tax_rates", "tax_jurisdictions",
    # financial-account setup + bank/Plaid links (kept; tied to preserved Plaid items)
    "financial_accounts", "bank_accounts", "plaid_items", "plaid_category_mappings",
}

# CoA: preserved BY DEFAULT (rebuilding 224 accounts is real work); deleted only with --include-coa.
COA_TABLES = {"tenant_gl_mappings"}

# Document DATA tables: deleted BY DEFAULT; preserved only with --preserve-documents.
# (document_templates is config and is ALWAYS preserved, above — not in this set.)
DOCUMENT_TABLES = {
    "documents", "documents_legacy", "fh_documents", "vault_documents",
    "kb_documents", "document_deliveries", "document_shares", "document_versions",
    "document_share_events", "document_share_reads", "document_search_index",
    "purchase_order_documents",
    "signature_envelopes", "signature_parties", "signature_fields", "signature_events",
}

NON_ORDERING_RULES = {"SET NULL", "CASCADE", "SET DEFAULT"}

# TELEMETRY-FIRST (W-1c): the high-volume execution-log tables. Their FK-descendant
# closure (things that reference them) is deleted FIRST — pure logs, the bulk of the
# volume (~55% on sunnycrest). Roots are the two big leaf-ish step tables; the closure
# is computed dynamically. GUARD: the closure must reach nothing books-critical (see
# BOOKS_CRITICAL) — period_locks in particular hangs off agent_jobs, NOT off these
# roots, and must never be swept into the fast log-deletion phase.
TELEMETRY_ROOTS = ("agent_run_steps", "workflow_run_steps")

# Books/financial/master tables that must NEVER appear in the telemetry closure. Not a
# preserve-list (most of these still delete — in the MAIN phase, visible and counted);
# this is the tripwire that the telemetry-first optimization never silently sweeps a
# books table into the log phase. Fail loud if the closure intersects this set.
BOOKS_CRITICAL = {
    "period_locks", "journal_entries", "journal_entry_lines",
    "invoices", "invoice_lines", "customer_payments", "customer_payment_applications",
    "vendor_bills", "vendor_bill_lines", "vendor_payments", "vendor_payment_applications",
    "sales_orders", "sales_order_lines", "quotes", "quote_lines",
    "customers", "vendors", "company_entities",
    "statements", "statement_run_items", "finance_charges",
    "reconciliation_runs", "reconciliation_transactions", "reconciliation_adjustments",
    "tenant_gl_mappings", "financial_accounts", "bank_accounts", "purchase_orders",
}

# Cross-tenant transfer records — TWO-PARTY, no single owner. A licensee_transfer
# names a HOME (originating) licensee and an AREA (receiving) licensee; wiping one
# party's rows silently deletes a record the other party still legitimately sees.
# So the tool never guesses: --transfer-records is required whenever the tenant is
# involved in any of these, and has no default (same shape as flag-needs-a-
# destination + the preserve-list assertion — when the tool can't know, it stops).
TRANSFER_TABLES = ("licensee_transfers", "transfer_notifications", "transfer_price_requests")


def transfer_predicates(mode):
    """Predicates for the two-party transfer tables per --transfer-records mode.
    None / 'skip' → None (not deleted). 'delete-as-home' scopes to rows where
    this tenant is the HOME (originating) licensee; 'delete-as-recipient' to rows
    where it is the AREA (receiving) licensee. Child tables follow their parent
    transfer's side (scoped via transfer_id), so a transfer and everything
    hanging off it move together — never a half-deleted transfer."""
    if mode in (None, "skip"):
        return {t: None for t in TRANSFER_TABLES}
    side = "home_tenant_id" if mode == "delete-as-home" else "area_tenant_id"
    parent = f'SELECT "id" FROM "licensee_transfers" WHERE "{side}" = :tid'
    return {
        "licensee_transfers": f'"{side}" = :tid',
        "transfer_notifications": f'"transfer_id" IN ({parent})',
        "transfer_price_requests": f'"transfer_id" IN ({parent})',
    }


def transfer_involvement(conn, tid):
    """Direct involvement of this tenant in the two-party transfer tables, by any
    side. Decides whether --transfer-records is required. Returns {table: count}
    for nonzero tables only. (A child row implies a parent transfer; if the tenant
    is named only on the child, the child's own tenant column catches it, and if
    only on the parent, licensee_transfers catches it — so the per-table direct
    checks together cover every involvement.)"""
    checks = {
        "licensee_transfers": '"home_tenant_id" = :tid OR "area_tenant_id" = :tid',
        "transfer_notifications": '"recipient_tenant_id" = :tid',
        "transfer_price_requests": '"requesting_tenant_id" = :tid OR "area_tenant_id" = :tid',
    }
    out = {}
    for t, where in checks.items():
        n = conn.execute(text(f'SELECT count(*) FROM "{t}" WHERE {where}'), {"tid": tid}).scalar()
        if n:
            out[t] = n
    return out


def die(msg: str) -> None:
    print(f"\n❌ {msg}", file=sys.stderr)
    sys.exit(1)


def load_schema(conn):
    scoped = dict(conn.execute(text("""
        SELECT table_name, column_name FROM information_schema.columns
        WHERE table_schema='public' AND column_name IN ('tenant_id','company_id')
    """)).fetchall())
    all_tables = {r[0] for r in conn.execute(text(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
    )).fetchall()}
    # PK column per table (single-col PKs; the schema convention is `id`)
    pk = {}
    for t, col in conn.execute(text("""
        SELECT tc.table_name, k.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage k
          ON tc.constraint_name=k.constraint_name AND tc.table_schema=k.table_schema
        WHERE tc.constraint_type='PRIMARY KEY' AND tc.table_schema='public'
    """)).fetchall():
        pk.setdefault(t, col)
    # FK edges: child.col -> parent, delete_rule, nullable
    nullable = {(t, c): (yn == 'YES') for t, c, yn in conn.execute(text("""
        SELECT table_name, column_name, is_nullable FROM information_schema.columns
        WHERE table_schema='public'
    """)).fetchall()}
    edges = []
    for child, ccol, parent, rule in conn.execute(text("""
        SELECT tc.table_name, kcu.column_name, ccu.table_name, rc.delete_rule
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name=kcu.constraint_name AND tc.table_schema=kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name=ccu.constraint_name AND tc.table_schema=ccu.table_schema
        JOIN information_schema.referential_constraints rc
          ON tc.constraint_name=rc.constraint_name AND tc.table_schema=rc.constraint_schema
        WHERE tc.constraint_type='FOREIGN KEY' AND tc.table_schema='public'
    """)).fetchall():
        if child == parent:
            continue  # self-FK — never a delete-order constraint
        edges.append((child, ccol, parent, rule, nullable.get((child, ccol), True)))
    return scoped, all_tables, pk, edges


def derive_delete_set(scoped, preserve, edges):
    """(scoped − preserve) ∪ FK-descendants (excluding preserve)."""
    children = defaultdict(list)  # parent -> [(child, ccol, rule, nullable)]
    for child, ccol, parent, rule, nn in edges:
        children[parent].append((child, ccol, rule, nn))
    roots = set(scoped) - preserve
    delete_set = set()
    q = deque(roots)
    while q:
        t = q.popleft()
        if t in delete_set or t in preserve:
            continue
        delete_set.add(t)
        for child, ccol, rule, nn in children.get(t, []):
            if child not in delete_set and child not in preserve:
                q.append(child)
    return delete_set


def _topo(delete_set, ordering_pairs):
    """Children-first topological sort over (child, parent) ordering pairs.
    Returns (order, residual) — residual is the set stuck in a cycle."""
    hard_children = defaultdict(set)
    parents = defaultdict(set)
    for child, parent in ordering_pairs:
        hard_children[parent].add(child)
        parents[child].add(parent)
    indeg = {t: len(hard_children.get(t, ())) for t in delete_set}
    ready = deque(sorted(t for t in delete_set if indeg[t] == 0))
    order, seen = [], set()
    while ready:
        t = ready.popleft()
        if t in seen:
            continue
        seen.add(t)
        order.append(t)
        for p in parents.get(t, ()):
            indeg[p] -= 1
            if indeg[p] == 0:
                ready.append(p)
    return order, delete_set - seen


def resolve_order(delete_set, edges):
    """Children-first delete order over NO ACTION/RESTRICT edges. Hard-edge
    cycles are broken GENERICALLY by nulling a NULLABLE edge that lies inside
    the cycle — never any other nullable FK. Returns
    (order, break_edges, unbreakable):
      break_edges  = [(child, col, parent)] whose FK will be set NULL (only
                     nullable edges, only ones inside a detected cycle).
      unbreakable  = set of tables in a hard cycle with NO nullable edge to
                     break (the caller must fail loudly — a schema problem for
                     a human, NOT a fallback to session_replication_role).
    """
    hard = [(ch, col, pa, nn) for ch, col, pa, rule, nn in edges
            if ch in delete_set and pa in delete_set and rule not in NON_ORDERING_RULES]
    active = list(hard)
    break_edges = []
    while True:
        order, residual = _topo(delete_set, [(ch, pa) for ch, col, pa, nn in active])
        if not residual:
            return order, break_edges, set()
        # a nullable edge that lies INSIDE the remaining cycle
        cand = sorted((ch, col, pa) for ch, col, pa, nn in active
                      if ch in residual and pa in residual and nn)
        if not cand:
            return order, break_edges, residual  # unbreakable — caller dies
        ch, col, pa = cand[0]
        break_edges.append((ch, col, pa))
        active = [e for e in active if not (e[0] == ch and e[1] == col and e[2] == pa)]


def check_blockers(preserve, delete_set, edges):
    """Preserved table with a NOT NULL, NO ACTION/RESTRICT FK into the delete-set."""
    blockers = []
    for child, ccol, parent, rule, nn in edges:
        if child in preserve and parent in delete_set and rule not in NON_ORDERING_RULES and not nn:
            blockers.append((child, ccol, parent, rule))
    return blockers


def build_predicate(table, scoped, pk, edges, delete_set, _memo, _stack):
    """WHERE clause identifying the tenant's rows in `table` (params use :tid).
    Scoped table → scope_col = :tid. Child-only → fk IN (SELECT pk FROM parent
    WHERE <parent predicate>), preferring a NOT NULL in-set parent FK. Returns
    (sql, confident:bool)."""
    if table in _memo:
        return _memo[table]
    if table in scoped:
        res = (f'"{scoped[table]}" = :tid', True)
        _memo[table] = res
        return res
    if table in _stack:  # predicate cycle — cannot build confidently
        return (None, False)
    _stack.add(table)
    # Parent FK edges usable for SCOPING. Scoping is a read question, not a
    # deletion question: follow a NOT NULL FK to ANY parent that carries the
    # tenant column, regardless of which side of the split it's on. A preserved
    # parent (e.g. users) is fine to descend into for a read-only subquery —
    # we scope through it, we never delete it. (Pre-fix this was `parent in
    # delete_set` only, which left employee_profiles — tenant-linked solely via
    # NOT NULL user_id -> users, a preserved table — unscopable.)
    cand = [(ccol, parent) for child, ccol, parent, rule, nn in edges
            if child == table and (parent in delete_set or parent in scoped)]
    nn_map = {(child, ccol): nn for child, ccol, parent, rule, nn in edges}
    # prefer a single NOT NULL edge (covers all rows); else OR all edges
    not_null = [(ccol, parent) for ccol, parent in cand if not nn_map.get((table, ccol), True)]
    chosen = not_null[:1] if not_null else cand
    clauses, confident = [], bool(chosen) and bool(not_null)
    for ccol, parent in chosen:
        psql, pconf = build_predicate(parent, scoped, pk, edges, delete_set, _memo, _stack)
        if psql is None:
            confident = False
            continue
        ppk = pk.get(parent, "id")
        clauses.append(f'"{ccol}" IN (SELECT "{ppk}" FROM "{parent}" WHERE {psql})')
        confident = confident and pconf
    _stack.discard(table)
    if not clauses:
        res = (None, False)
    else:
        res = ("(" + " OR ".join(clauses) + ")", confident)
    _memo[table] = res
    return res


def main():
    ap = argparse.ArgumentParser(description="Wipe a tenant's transactional data (dry-run by default).")
    ap.add_argument("slug", help="Tenant slug to wipe (REQUIRED — no all-tenants mode).")
    ap.add_argument("--execute", action="store_true", help="Actually delete (default is dry-run).")
    ap.add_argument("--include-coa", action="store_true", help="Also delete tenant_gl_mappings (chart of accounts).")
    ap.add_argument("--preserve-documents", action="store_true", help="Keep documents/signatures (deleted by default).")
    ap.add_argument("--transfer-records", choices=["skip", "delete-as-home", "delete-as-recipient"],
                    default=None,
                    help="Two-party cross-tenant transfer records (no default). REQUIRED if the "
                         "tenant is involved in any: skip=leave them; delete-as-home=delete "
                         "transfers this tenant originated; delete-as-recipient=those it received.")
    ap.add_argument("--verify", action="store_true",
                    help="Read-only: report the tenant's current delete-set state + preserved/"
                         "identity, using the tool's OWN predicates. Post-wipe the delete-set should "
                         "be empty; the same code is the standing pre/post-wipe check.")
    ap.add_argument("--batch-size", type=int, default=5000,
                    help="Rows per committed delete batch (default 5000). Each batch is its own "
                         "transaction so WAL recycles between batches — never accumulates toward the "
                         "volume size. Derived from the S-1 baseline, not intuition (see W-1c).")
    ap.add_argument("--disk-floor-gb", type=float, default=2.0,
                    help="Refuse to start, and abort cleanly between tables, if free space on the "
                         "Postgres volume drops below this many GB (default 2.0). A clean mid-wipe "
                         "abort is a safe state — re-run to resume.")
    args = ap.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        die("DATABASE_URL not set.")
    # keepalives — belt-and-braces against a proxied SSL connection being reaped
    # mid-transaction (the real fix is running on the internal host; this is cheap
    # insurance, no new semantics).
    eng = create_engine(db_url, connect_args={
        "keepalives": 1, "keepalives_idle": 10, "keepalives_interval": 5, "keepalives_count": 5,
    })

    with eng.connect() as conn:
        scoped, all_tables, pk, edges = load_schema(conn)

        # GUARD 1 — preserve-list assertion
        missing = sorted(PRESERVE - all_tables)
        if missing:
            die(f"PRESERVE-LIST ASSERTION FAILED — these names are not in the live schema "
                f"(rename/typo? refusing to run so they aren't silently wiped): {missing}")

        # effective preserve set per flags
        preserve = set(PRESERVE)
        if not args.include_coa:
            preserve |= COA_TABLES
        if args.preserve_documents:
            preserve |= DOCUMENT_TABLES

        # resolve tenant
        row = conn.execute(text("SELECT id, name, slug FROM companies WHERE slug=:s"),
                           {"s": args.slug}).fetchone()
        if not row:
            die(f"No tenant with slug '{args.slug}'.")
        tid, name, slug = row

        # --verify: read-only state check (the standing post-wipe verification).
        # No involvement refuse here — verify never writes; it just reports.
        if args.verify:
            r = verify_state(conn, tid, preserve, transfer_mode=args.transfer_records)
            print("=" * 72)
            print(f"WIPE VERIFY (read-only) — slug={slug!r}  name={name!r}  id={tid}")
            print("=" * 72)
            tot = r["delete_set_remaining_total"]
            print(f"\nDELETE-SET rows remaining: {tot}")
            for t, n in sorted(r["delete_set_remaining"].items(), key=lambda x: -x[1])[:12]:
                print(f"    {t:<42} {n}")
            print("\ncycle null-break back-edges (non-null; expect 0):")
            for (ch, col), n in r["cycle_backedges_nonnull"].items():
                print(f"    {ch}.{col}: {n}")
            print("\npreserved / identity:")
            print(f"    company row present: {r['company_present']}")
            for t, n in r["preserved"].items():
                print(f"    {t:<22} {n}")
            print(f"\ntransfer involvement: {r['transfer_involvement'] or 'none'}")
            print(f"\nVERDICT: " + ("DELETE-SET EMPTY — wipe verified" if tot == 0
                  else f"DELETE-SET NOT EMPTY — {tot} rows remain (wipe incomplete or not yet run)"))
            return

        # Two-party transfer records: refuse to guess ownership. If this tenant is
        # involved on any side and no mode was chosen, stop — a two-party record
        # deleted from one side is cross-tenant data loss dressed as a cleanup.
        involvement = transfer_involvement(conn, tid)
        if involvement and args.transfer_records is None:
            detail = ", ".join(f"{t}={n}" for t, n in involvement.items())
            die(f"TENANT INVOLVED IN CROSS-TENANT TRANSFER RECORDS ({detail}). These are "
                f"TWO-PARTY records with no single owner — refusing to guess. Re-run with "
                f"--transfer-records=skip (leave them), =delete-as-home (delete transfers this "
                f"tenant originated), or =delete-as-recipient (delete transfers it received). "
                f"The other party may still have a legitimate view of these rows.")

        (delete_set, order, break_edges, unbreakable, blockers,
         preds, child_only, unconfident) = plan_wipe(conn, preserve, transfer_mode=args.transfer_records)

        # telemetry-first closure + its books-critical guard (W-1c)
        tel_closure = telemetry_closure(TELEMETRY_ROOTS, edges, delete_set)
        tel_conflict = telemetry_books_conflict(tel_closure)

        # cycle null-break counts (rows whose FK would be nulled, this tenant)
        breaks_report = []
        for ch, col, pa in break_edges:
            pr = preds.get(ch)
            n = (conn.execute(text(f'SELECT count(*) FROM "{ch}" WHERE {pr} AND "{col}" IS NOT NULL'),
                              {"tid": tid}).scalar() if pr else None)
            breaks_report.append((ch, col, pa, n))

        print("=" * 72)
        print(f"TENANT WIPE — slug={slug!r}  name={name!r}  id={tid}")
        print(f"mode: {'EXECUTE' if args.execute else 'DRY-RUN (default)'}   "
              f"include_coa={args.include_coa}  preserve_documents={args.preserve_documents}")
        print(f"transfer_records: {args.transfer_records or 'n/a (tenant not involved)'}"
              + (f"   involvement: {', '.join(f'{t}={n}' for t, n in involvement.items())}"
                 if involvement else ""))
        print("=" * 72)
        print(f"\nPRESERVE-LIST ({len(preserve)} tables) — kept:")
        for t in sorted(preserve):
            print(f"    · {t}")
        print(f"\nDELETE-SET: {len(delete_set)} tables")
        print(f"child-only descendants pulled in (no tenant column — GUARD 2): {len(child_only)}")
        for t in child_only:
            print(f"    ~ {t}")

        print(f"\nTELEMETRY-FIRST closure (deleted first — roots {list(TELEMETRY_ROOTS)}): "
              f"{len(tel_closure)} tables")
        for t in sorted(tel_closure):
            print(f"    » {t}")
        if tel_conflict:
            print("\n❌ TELEMETRY GUARD — books-critical tables in the telemetry closure:")
            for t in tel_conflict:
                print(f"    !! {t} — a log-first phase would sweep a books table")
            die("Telemetry closure reaches books-critical table(s) — refusing to run. "
                "A telemetry root now has a books table as a descendant (schema change?); "
                "resolve before wiping.")

        print(f"\nCYCLE NULL-BREAKS (nullable in-cycle FK → NULL, in-txn, before delete): {len(break_edges)}")
        if not break_edges:
            print("    (none — no hard-edge cycles)")
        for ch, col, pa, n in breaks_report:
            flag = "   ⚠️  POPULATED — REAL DATA MUTATION, review before --execute" if n else ""
            print(f"    {ch}.{col} -> {pa}   rows to null (this tenant): {n}{flag}")

        if unbreakable:
            die(f"HARD-EDGE FK CYCLE WITH NO NULLABLE EDGE: {sorted(unbreakable)} — "
                f"a schema problem for a human. Refusing to run (will NOT escalate to "
                f"session_replication_role or any FK-disabling shortcut).")
        if blockers:
            print("\n❌ GUARD 3 — PRESERVE→DELETE BLOCKERS (NOT NULL FK into delete-set):")
            for child, ccol, parent, rule in blockers:
                print(f"    {child}.{ccol} -> {parent} ({rule}) — preserved table would break the wipe")
            die("Blocker(s) present — refusing to run. Resolve the preserve/delete split.")
        if unconfident:
            print("\n⚠️  child-only tables with no confident tenant-scoping predicate "
                  "(review — rows may be missed):")
            for t in unconfident:
                print(f"    ? {t}")

        # per-table delete counts
        print("\nPER-TABLE ROW COUNTS (rows that would be deleted for this tenant):")
        total = 0
        for t in order:
            sql = preds[t]
            if sql is None:
                print(f"    {t:<44} SKIPPED (no predicate)")
                continue
            n = conn.execute(text(f'SELECT count(*) FROM "{t}" WHERE {sql}'), {"tid": tid}).scalar()
            total += n
            if n:
                print(f"    {t:<44} {n}")
        print(f"\nTOTAL rows to delete: {total}")

        # disk status — informative in dry-run; --execute ENFORCES the floor.
        floor_bytes = int(args.disk_floor_gb * 1024 ** 3)
        try:
            data_dir = conn.execute(text("SELECT current_setting('data_directory')")).scalar()
            free = read_free_bytes(conn, data_dir)
            conn.commit()
            print(f"\ndisk: free {free / 1024**3:.2f} GB   floor {args.disk_floor_gb:.2f} GB   "
                  f"batch-size {args.batch_size}   (data_directory={data_dir})")
            if free < floor_bytes:
                print("    ⚠️  free space is BELOW the floor — --execute would REFUSE to start.")
        except Exception as ex:
            print(f"\ndisk: could not read free space ({ex}). --execute would REFUSE "
                  "(a disk guard that can't see the disk is not a guard).")

        if not args.execute:
            print(f"\nDRY-RUN complete. Re-run with --execute to delete — chunked in committed "
                  f"batches of {args.batch_size}, telemetry-first, resumable, disk-guarded. "
                  "A typed slug confirmation will be required.")
            return

    # ---- EXECUTE (chunked, resumable, disk-guarded — NOT atomic; see docstring) ----
    with eng.connect() as conn:  # commit-as-you-go: each batch commits on its own
        data_dir = conn.execute(text("SELECT current_setting('data_directory')")).scalar()
        try:
            free = assert_disk_floor(conn, data_dir, floor_bytes)
        except DiskFloorError as ex:
            die(f"DISK GUARD — {ex}. Refusing to run.")
        conn.commit()
        print(f"\ndisk pre-flight: free {free / 1024**3:.2f} GB   floor {args.disk_floor_gb:.2f} GB   "
              f"(data_directory={data_dir})")

        print(f"\n⚠️  About to PERMANENTLY DELETE ~{total} rows from tenant '{slug}' (id={tid}) "
              f"in committed batches of {args.batch_size} — telemetry-first, resumable. "
              f"(Nulls {len(break_edges)} in-cycle FK(s) first.)")
        typed = input(f"Type the tenant slug ({slug}) to confirm: ").strip()
        if typed != slug:
            die("Confirmation did not match the slug. Aborted — nothing deleted.")

        print("\n── executing (chunked, per-batch commits) ──", flush=True)
        nulled, deleted, aborted = chunked_wipe(
            conn, tid, order, preds, break_edges, first_set=tel_closure,
            batch_size=args.batch_size, data_dir=data_dir, floor_bytes=floor_bytes, progress=True)

    if nulled:
        print("\n✅ Nulled (in-cycle FK breaks):")
        for (ch, col), n in nulled.items():
            print(f"    {ch}.{col}   {n}")
    deleted_total = sum(deleted.values())
    print(f"\nDeleted {deleted_total} rows across {sum(1 for v in deleted.values() if v)} table(s).")

    if aborted:
        print("\n⚠️  ABORTED mid-wipe on the disk floor. The tenant is PARTIALLY wiped — a safe, "
              "resumable state. Re-run the same command to continue.")
        sys.exit(2)

    # Final state check — the transaction boundary no longer proves completion, so
    # --verify's own predicates are now the completion signal.
    with eng.connect() as conn:
        r = verify_state(conn, tid, preserve, transfer_mode=args.transfer_records)
    rem = r["delete_set_remaining_total"]
    if rem == 0:
        p = r["preserved"]
        print(f"\n✅ WIPE COMPLETE. Verified 0 rows remain in the delete-set. "
              f"Preserved: tenant_gl_mappings={p.get('tenant_gl_mappings')}, users={p.get('users')}, "
              f"roles={p.get('roles')}, company_present={r['company_present']}.")
    else:
        top = dict(sorted(r["delete_set_remaining"].items(), key=lambda x: -x[1])[:5])
        print(f"\n⚠️  {rem} rows still remain in the delete-set after this pass (top: {top}). "
              "Re-run to finish — the wipe is idempotent + resumable.")
        sys.exit(2)


# ── S-3: disk guard ─────────────────────────────────────────────────────────
class DiskFloorError(RuntimeError):
    """Free space below the floor, or unreadable. Either way the wipe must not run."""


def read_free_bytes(conn, data_dir) -> int:
    """True filesystem free bytes on the Postgres data volume, via superuser
    `COPY FROM PROGRAM 'df'`. The app connects over the proxy and has no
    filesystem view of the volume, so df must run ON the server — COPY FROM
    PROGRAM is the only path, and it works solely because the app role is
    superuser (finding #6; a dedicated role would need pg_read_server_files /
    pg_execute_server_program or an out-of-band metric). Uses portable `df -Pk`
    (GNU + BSD) and parses column 4 in Python (no in-shell awk quoting). Raises
    if it can't produce a number — the caller must treat that as "refuse."""
    conn.execute(text("DROP TABLE IF EXISTS _wipe_df"))
    conn.execute(text("CREATE TEMP TABLE _wipe_df (line text)"))
    conn.execute(text(f"COPY _wipe_df FROM PROGRAM 'df -Pk \"{data_dir}\" | tail -1'"))
    line = conn.execute(text("SELECT line FROM _wipe_df")).scalar()
    conn.execute(text("DROP TABLE IF EXISTS _wipe_df"))
    if not line:
        raise RuntimeError("df returned no output")
    parts = line.split()
    if len(parts) < 4 or not parts[3].isdigit():
        raise RuntimeError(f"could not parse df output: {line!r}")
    return int(parts[3]) * 1024  # column 4 = available 1K-blocks


def assert_disk_floor(conn, data_dir, floor_bytes) -> int:
    """Return free bytes if at/above the floor; raise DiskFloorError if below OR
    unreadable. 'Unreadable → refuse' is deliberate: a disk guard that can't see
    the disk is not a guard."""
    try:
        free = read_free_bytes(conn, data_dir)
    except Exception as ex:
        raise DiskFloorError(f"disk guard blind — cannot read free space ({ex})")
    if free < floor_bytes:
        raise DiskFloorError(
            f"free {free / 1024**3:.2f} GB below floor {floor_bytes / 1024**3:.2f} GB")
    return free


# ── S-2: telemetry-first + chunked, resumable deletion ───────────────────────
def telemetry_closure(roots, edges, delete_set) -> set:
    """FK-descendant closure of `roots` within the delete-set (roots + everything
    that transitively references them). Deleted first. FK-safe to delete first:
    the closure is closed under inbound FKs by construction (any table referencing
    a member is itself a descendant → a member), so nothing outside references it."""
    children = defaultdict(list)
    for ch, ccol, pa, rule, nn in edges:
        children[pa].append(ch)
    closure, q = set(), deque(r for r in roots if r in delete_set)
    while q:
        t = q.popleft()
        if t in closure:
            continue
        closure.add(t)
        for ch in children.get(t, []):
            if ch in delete_set and ch not in closure:
                q.append(ch)
    return closure


def telemetry_books_conflict(closure) -> list:
    """Books-critical tables that landed in the telemetry closure — must be empty.
    Non-empty means the log-first phase would sweep a books table (e.g. a schema
    change hangs period_locks off a telemetry root); the caller fails loud."""
    return sorted(closure & BOOKS_CRITICAL)


def delete_table_chunked(conn, tid, table, pred, batch_size, progress=True) -> int:
    """Delete this tenant's rows from `table` in committed batches (ctid-based).
    `conn` is commit-as-you-go: each batch is its own transaction, so a committed
    batch's WAL becomes recyclable at once — no single transaction pins more than
    ~batch_size rows of WAL. Idempotent + resumable: re-running deletes whatever
    remains; 0 matches → returns 0 without a write. Returns rows deleted.

    ctid batching (not PK-range): `ctid IN (SELECT ctid ... WHERE <pred> LIMIT n)`
    handles scoped tables AND child-only tables (whose <pred> is an `fk IN
    (SELECT ...)` subquery) uniformly, and needs no single-column PK or position
    tracking — each pass re-selects the first n remaining matches."""
    if pred is None:
        return 0
    total, batches = 0, 0
    t0 = time.monotonic()
    while True:
        r = conn.execute(text(
            f'DELETE FROM "{table}" WHERE ctid IN '
            f'(SELECT ctid FROM "{table}" WHERE {pred} LIMIT :__lim)'),
            {"tid": tid, "__lim": batch_size})
        conn.commit()
        n = r.rowcount
        if n == 0:
            break
        total += n
        batches += 1
        if progress and batches == 1:
            print(f"    → {table} ...", flush=True)
        if progress and batches % 10 == 0:
            print(f"      {table}: {total} rows so far ({batches} batches)", flush=True)
    if progress and total:
        print(f"    ✓ {table}: {total} rows in {batches} batch(es), "
              f"{time.monotonic() - t0:.1f}s", flush=True)
    return total


def chunked_wipe(conn, tid, order, preds, break_edges, first_set=frozenset(),
                 batch_size=5000, data_dir=None, floor_bytes=0, progress=True):
    """Execute the wipe as committed batches. `conn` is commit-as-you-go.
      1. Null the in-cycle break edges (chunked, idempotent) — committed.
      2. Delete `first_set` (telemetry closure) tables first, then the rest, each
         in the child-first `order`, each chunked into `batch_size` committed batches.
      3. If data_dir + floor_bytes are set, re-check free space between tables and
         ABORT CLEANLY below the floor (a safe state — resume by re-running).
    Returns (nulled, deleted, aborted). Not atomic by design — see module docstring."""
    nulled = {}
    for ch, col, pa in break_edges:
        pred = preds.get(ch)
        if pred is None:
            continue
        n = 0
        while True:
            r = conn.execute(text(
                f'UPDATE "{ch}" SET "{col}" = NULL WHERE ctid IN '
                f'(SELECT ctid FROM "{ch}" WHERE {pred} AND "{col}" IS NOT NULL LIMIT :__lim)'),
                {"tid": tid, "__lim": batch_size})
            conn.commit()
            if r.rowcount == 0:
                break
            n += r.rowcount
        if n:
            nulled[(ch, col)] = n

    # telemetry-closure tables first, then the rest — child-first within each (a
    # subset of `order` preserves its ordering).
    phased = [t for t in order if t in first_set] + [t for t in order if t not in first_set]
    deleted, aborted = {}, False
    for t in phased:
        deleted[t] = delete_table_chunked(conn, tid, t, preds.get(t), batch_size, progress)
        if data_dir and floor_bytes:
            try:
                free = read_free_bytes(conn, data_dir)
                conn.commit()
            except Exception as ex:
                free = -1
                if progress:
                    print(f"\n⚠️  disk read failed between tables ({ex}) — CLEAN ABORT after {t}. "
                          f"Re-run to resume.", flush=True)
            if free < floor_bytes:
                if free >= 0 and progress:
                    print(f"\n⚠️  free {free / 1024**3:.2f} GB dropped below floor — CLEAN ABORT "
                          f"after {t}. Re-run to resume (idempotent).", flush=True)
                aborted = True
                break
    return nulled, deleted, aborted


def verify_state(conn, tid, preserve, transfer_mode=None):
    """Read-only state check for a tenant, using the tool's OWN predicates so the
    pre/post-wipe check is the same code every time (never a reconstructed
    script). Returns a dict; the caller renders it. After a successful wipe,
    `delete_set_remaining_total` is 0 and the cycle back-edges are 0 non-null;
    preserved/identity counts confirm the tenant is still usable/seedable."""
    (delete_set, order, break_edges, unbreakable, blockers,
     preds, child_only, unconfident) = plan_wipe(conn, preserve, transfer_mode=transfer_mode)

    remaining, total = {}, 0
    for t in order:
        sql = preds.get(t)
        if sql is None:
            continue
        n = conn.execute(text(f'SELECT count(*) FROM "{t}" WHERE {sql}'), {"tid": tid}).scalar()
        total += n
        if n:
            remaining[t] = n

    backedges = {}
    for ch, col, pa in break_edges:
        sql = preds.get(ch)
        if sql is None:
            continue
        backedges[(ch, col)] = conn.execute(
            text(f'SELECT count(*) FROM "{ch}" WHERE {sql} AND "{col}" IS NOT NULL'),
            {"tid": tid}).scalar()

    preserved = {}
    for t in ("tenant_gl_mappings", "financial_accounts", "users", "roles"):
        sc = conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_schema='public' "
            "AND table_name=:t AND column_name IN ('tenant_id','company_id')"), {"t": t}).fetchall()
        col = sc[0][0] if sc else None
        preserved[t] = (conn.execute(text(f'SELECT count(*) FROM "{t}" WHERE "{col}"=:t'),
                                     {"t": tid}).scalar() if col else None)

    return {
        "delete_set_remaining_total": total,
        "delete_set_remaining": remaining,
        "cycle_backedges_nonnull": backedges,
        "preserved": preserved,
        "company_present": bool(conn.execute(
            text("SELECT 1 FROM companies WHERE id=:t"), {"t": tid}).scalar()),
        "transfer_involvement": transfer_involvement(conn, tid),
    }


def plan_wipe(conn, preserve, transfer_mode=None):
    """Build the full wipe plan against the live schema for the given effective
    preserve set. Returns (delete_set, order, break_edges, unbreakable,
    blockers, preds, child_only, unconfident). Pure/read-only — used by the CLI
    and by tests. `break_edges` = nullable in-cycle FKs to be set NULL;
    `unbreakable` = hard cycle with no nullable edge (caller must fail loudly).
    `transfer_mode` controls the two-party transfer tables — their predicates are
    NOT auto-derived (no single owner); they're set explicitly per the mode and
    excluded from `unconfident` because they're deliberately handled, not unknown."""
    scoped, all_tables, pk, edges = load_schema(conn)
    missing = sorted(preserve - all_tables)
    if missing:
        raise ValueError(f"preserve-list names not in schema: {missing}")
    delete_set = derive_delete_set(scoped, preserve, edges)
    order, break_edges, unbreakable = resolve_order(delete_set, edges)
    blockers = check_blockers(preserve, delete_set, edges)
    memo, preds, unconfident = {}, {}, []
    for t in order:
        sql, conf = build_predicate(t, scoped, pk, edges, delete_set, memo, set())
        preds[t] = sql
        if sql is None or not conf:
            unconfident.append(t)
    # Two-party transfer tables: mode-controlled, never auto-scoped. Override any
    # (unconfident) auto-derived predicate with the explicit mode predicate, and
    # drop them from `unconfident` — they're a deliberate decision, not a gap.
    tpreds = transfer_predicates(transfer_mode)
    for t in TRANSFER_TABLES:
        if t in preds:
            preds[t] = tpreds[t]
    unconfident = [t for t in unconfident if t not in TRANSFER_TABLES]
    child_only = sorted(t for t in delete_set if t not in scoped)
    return delete_set, order, break_edges, unbreakable, blockers, preds, child_only, unconfident


if __name__ == "__main__":
    main()
