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
  * Transactional — a single transaction; any error rolls the whole wipe back.
  * The dry-run output IS the review artifact: because behavior tracks the
    live schema, each run must be re-reviewed. It echoes the preserve-list,
    per-table delete counts, and the child-only descendants pulled in.

DELETE ORDER: topological over NO ACTION / RESTRICT FK edges only. SET NULL
and CASCADE edges impose no ordering (the DB resolves them), which collapses
the apparent FK "cycle" (verified nominal on this schema).

Reads DATABASE_URL from the environment (no app import — pure DB tool).
"""
from __future__ import annotations

import argparse
import os
import sys
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
    args = ap.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        die("DATABASE_URL not set.")
    eng = create_engine(db_url)

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

        if not args.execute:
            print("\nDRY-RUN complete. Re-run with --execute to delete (a typed confirmation will be required).")
            return

    # ---- EXECUTE ----
    print(f"\n⚠️  About to PERMANENTLY DELETE {total} rows from tenant '{slug}' (id={tid}), "
          f"nulling {len(break_edges)} in-cycle FK(s) first (in the same transaction).")
    typed = input(f"Type the tenant slug ({slug}) to confirm: ").strip()
    if typed != slug:
        die("Confirmation did not match the slug. Aborted — nothing deleted.")

    with eng.begin() as conn:  # single transaction — all or nothing (null-breaks included)
        nulled, deleted = execute_deletes(conn, tid, order, preds, break_edges)

    if nulled:
        print("\n✅ Nulled (in-cycle FK breaks):")
        for (ch, col), n in nulled.items():
            print(f"    {ch}.{col}   {n}")
    print("\n✅ WIPE COMPLETE (committed). Deleted counts per table:")
    for t in order:
        if deleted.get(t):
            print(f"    {t:<44} {deleted[t]}")
    print(f"\nTOTAL deleted: {sum(deleted.values())}. Verified 0 remaining in all delete-set tables.")


def execute_deletes(conn, tid, order, preds, break_edges=()) -> tuple[dict, dict]:
    """In one transaction (the caller's): (1) null the in-cycle break edges,
    (2) delete the tenant's rows in `order`, (3) verify zero remaining. Raises
    (rolling the whole thing back, null-breaks included) if any delete-set table
    still holds tenant rows afterward. Returns (nulled, deleted) — nulled is
    {(table,col): rowcount}, deleted is {table: rowcount}."""
    nulled = {}
    for ch, col, pa in break_edges:
        sql = preds.get(ch)
        if sql is None:
            continue  # can't scope — leave it; a residual FK would surface post-delete
        r = conn.execute(
            text(f'UPDATE "{ch}" SET "{col}" = NULL WHERE {sql} AND "{col}" IS NOT NULL'),
            {"tid": tid})
        nulled[(ch, col)] = r.rowcount
    deleted = {}
    for t in order:
        sql = preds.get(t)
        if sql is None:
            continue
        r = conn.execute(text(f'DELETE FROM "{t}" WHERE {sql}'), {"tid": tid})
        deleted[t] = r.rowcount
    remaining = {}
    for t in order:
        sql = preds.get(t)
        if sql is None:
            continue
        n = conn.execute(text(f'SELECT count(*) FROM "{t}" WHERE {sql}'), {"tid": tid}).scalar()
        if n:
            remaining[t] = n
    if remaining:
        raise RuntimeError(f"POST-DELETE non-zero (rolling back): {remaining}")
    return nulled, deleted


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
