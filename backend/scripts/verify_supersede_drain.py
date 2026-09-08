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
            print("⚠️ NOT YET EXERCISED — neither listener has run. This is an")
            print("   absence of evidence, not a pass. Re-run after ~23:07 UTC.")
            return 0

        # 1. Tenant listener — every new row must carry its job's tenant.
        bad = c.execute(text("""
            SELECT count(*) FROM agent_anomalies a JOIN agent_jobs j ON j.id = a.agent_job_id
            WHERE a.created_at > now() - interval '26 hours'
              AND (a.tenant_id IS NULL OR a.tenant_id IS DISTINCT FROM j.tenant_id)""")).scalar()
        print(f"\n1. new rows with a missing or WRONG tenant_id: {bad}")
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

        # 4. Did the writing job survive the listeners?
        print("\n4. failed agent jobs in the last 26h (a listener raise lands here):")
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
