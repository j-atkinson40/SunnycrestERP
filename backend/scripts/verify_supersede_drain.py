"""READ-ONLY verification of the first production exercise of the 5b listeners.

Run AFTER an agent that writes anomalies has run — `ar_collections` fires nightly
at ~23:07 UTC. Until then this reports "not yet exercised", which is the honest
answer and is NOT the same as a pass.

    railway run --project <id> --environment production --service SunnycrestERP \
        python -m scripts.verify_supersede_drain

⚠️ WHY THIS EXISTS RATHER THAN A GLANCE AT THE TABLE. Both `before_insert`
listeners had never run in production when 5b shipped, and the schema is
permissive enough that a misfire is SILENT: `tenant_id` is nullable until 5c, so
a row filed under the wrong tenant — or none — inserts cleanly and shows up as
somebody else's open work with nothing raised anywhere. This check is the only
thing between that and nobody noticing.

Writes nothing. Uses a connection-level read-only guard.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from sqlalchemy import create_engine, text


def main() -> int:
    url = os.environ["DATABASE_URL"]
    u = urlparse(url)
    print(f"target: host={u.hostname} port={u.port} db={(u.path or '/')[1:]}")
    eng = create_engine(url, connect_args={"options": "-c default_transaction_read_only=on"})
    problems: list[str] = []

    with eng.connect() as c:
        print("server now():", c.execute(text("SELECT now()")).scalar())

        exercised = c.execute(text("""
            SELECT count(*) FROM agent_anomalies
            WHERE created_at > now() - interval '26 hours'""")).scalar()
        print(f"\nanomalies written in the last 26h: {exercised}")
        if not exercised:
            print("⚠️ LISTENERS NOT YET EXERCISED — no anomaly written in 26h.")
            print("   Absence of evidence, not a pass. Re-run after ~23:07 UTC.")
            print("   Checks 1-3 and 5 are SKIPPED; 4a/4b still run below —")
            print("   the dedup is a manual script run and does not depend on")
            print("   an agent having fired.")

        # 1. Tenant listener — every new row must carry its job's tenant.
        bad = 0 if not exercised else c.execute(text("""
            SELECT count(*) FROM agent_anomalies a JOIN agent_jobs j ON j.id = a.agent_job_id
            WHERE a.created_at > now() - interval '26 hours'
              AND (a.tenant_id IS NULL OR a.tenant_id IS DISTINCT FROM j.tenant_id)""")).scalar()
        print(f"\n1. new rows with a missing or WRONG tenant_id: "
              f"{bad if exercised else 'skipped — no new rows'}")
        if bad:
            problems.append(f"{bad} new anomalies are filed under the wrong tenant or none")

        # 2. Supersede — at most one open row per key, tenant-wide.
        print("\n2. keys holding MORE THAN ONE open row (supersede's whole job):")
        dupes = c.execute(text("""
            SELECT tenant_id, anomaly_type, entity_type, entity_id, count(*) AS n
            FROM agent_anomalies
            WHERE resolved = false AND superseded_at IS NULL
            GROUP BY 1,2,3,4 HAVING count(*) > 1 ORDER BY n DESC""")).fetchall()
        if not dupes:
            print("   none — exactly one open row per key")
        for d in dupes:
            print(f"   {d[1]:<32} {str(d[2]):<18} {str(d[3])[:20]:<22} n={d[4]}")
        residual = sum(d[4] - 1 for d in dupes)
        print(f"   residual duplicate rows: {residual}")
        print("   (rows for an agent that has not re-run yet are EXPECTED here —")
        print("    the drain is per-agent, on that agent's own next run)")

        # 3. The drain, per type.
        print("\n3. supersede activity by anomaly_type:")
        for r in c.execute(text("""
            SELECT anomaly_type,
                   count(*) FILTER (WHERE superseded_at IS NOT NULL) AS superseded,
                   count(*) FILTER (WHERE resolved = false AND superseded_at IS NULL) AS still_open
            FROM agent_anomalies GROUP BY 1 HAVING count(*) FILTER (WHERE superseded_at IS NOT NULL) > 0
            ORDER BY 2 DESC""")):
            print(f"   {r[0]:<32} superseded={r[1]:<6} open={r[2]}")

        # 4. THE DEDUP'S OWN TWO CONFIRMATIONS.
        #
        # Named as the things to check before 5c is authored. They are checks
        # rather than notes because the second one is the FIRST REAL EXERCISE OF
        # TENANT SCOPING ON A WRITE NOBODY IS WATCHING -- the audit rows are
        # written per tenant by a script run once at a terminal, and if the
        # scoping is wrong the only symptom is one tenant reading another
        # tenant's maintenance record.
        print("\n4a. one open row per key across the WHOLE table")
        print("    (listener grouping: NULLs MATCH, which is what 5c's index must use)")
        still = c.execute(text("""
            SELECT count(*) FROM (
              SELECT 1 FROM agent_anomalies
              WHERE resolved = false AND superseded_at IS NULL
              GROUP BY tenant_id, anomaly_type, entity_type, entity_id
              HAVING count(*) > 1) z""")).scalar()
        print(f"    keys still holding more than one open row: {still}")
        if still:
            problems.append(
                f"{still} key(s) still hold >1 open row -- 5c's unique index "
                "would refuse to build")

        print("\n4b. the dedup's audit rows, present and correctly scoped")
        arows = c.execute(text("""
            SELECT company_id, count(*), max(created_at)
            FROM audit_logs
            WHERE action = 'platform_maintenance.anomalies_deduplicated'
            GROUP BY 1 ORDER BY 1""")).fetchall()
        if not arows:
            print("    none -- the dedup has not run yet (or wrote no audit row)")
        for r in arows:
            print(f"    tenant {r[0]}  rows={r[1]}  at={r[2]}")
        if arows:
            # Exactly one row per tenant, and every tenant named must be one
            # whose anomalies were actually touched.
            dupe_tenants = [r[0] for r in arows if r[1] != 1]
            if dupe_tenants:
                problems.append(
                    f"{len(dupe_tenants)} tenant(s) have more than one dedup "
                    "audit row -- the script ran twice, or scoping is wrong")
            orphan = c.execute(text("""
                SELECT count(*) FROM audit_logs al
                WHERE al.action = 'platform_maintenance.anomalies_deduplicated'
                  AND NOT EXISTS (
                    SELECT 1 FROM agent_anomalies a
                    WHERE a.tenant_id = al.company_id
                      AND a.superseded_at IS NOT NULL)""")).scalar()
            print(f"    audit rows naming a tenant with no superseded anomaly: {orphan}")
            if orphan:
                problems.append(
                    f"{orphan} dedup audit row(s) are filed against a tenant "
                    "whose anomalies were never touched -- WRONG TENANT")

        # 5. Did the writing job survive the listeners?
        print("\n5. failed agent jobs in the last 26h (a listener raise lands here):")
        for r in c.execute(text("""
            SELECT job_type, count(*) FROM agent_jobs
            WHERE created_at > now() - interval '26 hours' AND status IN ('failed','error')
            GROUP BY 1 ORDER BY 2 DESC""")):
            print(f"   ⚠️ {r[0]}: {r[1]}")
            problems.append(f"{r[1]} {r[0]} job(s) failed")
        print("   (nothing above = no failures)")

    print("\n" + "=" * 60)
    if problems:
        print("⚠️ PROBLEMS FOUND:")
        for p in problems:
            print(f"   - {p}")
        return 1
    print("No problems found in what was checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
