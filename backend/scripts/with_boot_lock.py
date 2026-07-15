"""Serialize the boot-prep phase (migrations + seeds) across overlapping
container boots — the C-10 postmortem's second bug (2026-07-09).

WHY: Railway's restart policy can overlap boots — attempt N+1's
railway-start begins while attempt N is still inside its seed phase.
seed_staging's clean+re-seed then races the previous boot's
seed_dispatch_demo: witnessed on staging as a SELF-SUSTAINING crash loop —
boot N queried testco's cemeteries, boot N+1's seed_staging deleted and
re-created them (new UUIDs) before N's order INSERT flushed, N died on
sales_orders_cemetery_id_fkey, Railway started N+2, which killed N+1 the
same way, for over an hour. Each boot was correct in isolation; the overlap
was the bug.

HOW: hold a session-scoped Postgres advisory lock for the duration of the
wrapped command (the boot-prep phase only — NOT the server; railway-start
re-execs uvicorn after this wrapper exits, so the lock never outlives prep).
Overlapping boots serialize instead of interleaving. If a holder dies, its
session dies and Postgres releases the lock automatically — no wedge.

Usage (from railway-start.sh):
    python -m scripts.with_boot_lock bash railway-start.sh   # re-exec form
"""
from __future__ import annotations

import os
import subprocess
import sys

import psycopg2

# Arbitrary constant, platform-unique: the boot-prep phase lock.
BOOT_PREP_LOCK_KEY = 815_001


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m scripts.with_boot_lock <command> [args...]")
        return 2
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("[boot-lock] DATABASE_URL not set — refusing to run unserialized.")
        return 1

    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    print("[boot-lock] acquiring boot-prep advisory lock "
          f"(key={BOOT_PREP_LOCK_KEY}) — waits if another boot is in prep...",
          flush=True)
    cur.execute("SELECT pg_advisory_lock(%s)", (BOOT_PREP_LOCK_KEY,))
    print("[boot-lock] acquired.", flush=True)
    try:
        return subprocess.call(sys.argv[1:])
    finally:
        try:
            cur.execute("SELECT pg_advisory_unlock(%s)", (BOOT_PREP_LOCK_KEY,))
            conn.close()
            print("[boot-lock] released.", flush=True)
        except Exception:
            pass  # session teardown releases it regardless


if __name__ == "__main__":
    sys.exit(main())
