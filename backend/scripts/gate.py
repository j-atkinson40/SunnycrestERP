#!/usr/bin/env python
"""Run the gate against a FRESH database, so no run inherits another's state.

⚠️ WHY THIS EXISTS (ruling 2026-11-03, sweep item 4). The suite used to run
against the long-lived local dev database. On 2026-11-03 thirteen files were
red locally on a commit CI was green on, and the difference was never the code
— it was accumulated local row state. A red count produced that way is not a
before/after comparison of anything, so the ruling is that each local gate run
starts from a fresh database.

⚠️ AND THE POINT IS NOT CLEANLINESS, IT IS COMPARABILITY — which is why this
SEEDS BY DEFAULT.

⚠️ CORRECTED 2026-11-04, and the first full run is what corrected it. This
docstring said "CI builds a bare Postgres ... and runs the ci_gate.txt manifest
with no seed", and defaulted to no seed to match. That is FALSE. `ci.yml` has a
"Seed the canonical set" step that runs `scripts/seed_dev.sh` between the
migrations and pytest. Run bare, 40% of the manifest errored out; CI is green on
the same commit. So the flag was backwards: seeding is what makes a local run
comparable to CI, and `--no-seed` is the non-comparable option.

That is the same mistake this script exists to prevent, one level up — a
confident claim about what the reference does, never checked against it.

HOW IT IS FAST. 410 migrations take minutes, so they run ONCE into a template
database keyed by a fingerprint of alembic/versions/. Each run then does
`CREATE DATABASE <run> TEMPLATE <tpl>`, a file-level copy that takes seconds.
Edit or add a migration and the fingerprint changes, so the next run rebuilds
the template rather than testing a stale shape.

⚠️ THE CREDENTIAL NEVER LEAVES THIS PROCESS. The admin connection and the run
URL are built here and handed to alembic/pytest through a subprocess env. They
are never printed, never passed as argv, and never written to a file. Do not
add a debug print of the URL.

Usage:
    .venv/bin/python scripts/gate.py                 # the CI manifest, as CI runs it
    .venv/bin/python scripts/gate.py --all           # the whole tree
    .venv/bin/python scripts/gate.py tests/test_x.py # named files
    .venv/bin/python scripts/gate.py --keep          # leave the run DB for inspection
    .venv/bin/python scripts/gate.py --no-seed       # bare, deliberately unlike CI
"""
from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit

BACKEND = pathlib.Path(__file__).resolve().parent.parent
VERSIONS = BACKEND / "alembic" / "versions"
MANIFEST = BACKEND / "tests" / "ci_gate.txt"

#: Only these hosts may be created on and dropped. CLAUDE.md: never point a
#: local DATABASE_URL at Railway production. This script issues DROP DATABASE,
#: so the guard is not advisory — absence of a match refuses.
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", ""}


def _base_url() -> str:
    sys.path.insert(0, str(BACKEND))
    from dotenv import load_dotenv

    load_dotenv(BACKEND / ".env")
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        sys.exit("✗ DATABASE_URL is not set (checked the environment and backend/.env).")
    host = (urlsplit(url).hostname or "").lower()
    if host not in LOCAL_HOSTS:
        sys.exit(
            f"✗ REFUSING: DATABASE_URL points at host '{host}', which is not local.\n"
            "  This script creates and DROPS databases. It runs against localhost only."
        )
    return url


def _swap_db(url: str, name: str) -> str:
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, f"/{name}", p.query, p.fragment))


def _shape_files() -> list[pathlib.Path]:
    """Everything whose content determines the template's shape AND contents.

    ⚠️ The migrations are not sufficient. The template is migrated AND seeded, so
    a seed-script edit changes what the template holds while leaving every
    migration untouched. Keyed on migrations alone, the next run would reuse a
    template seeded by the OLD script and the edit would appear to do nothing.
    """
    out = sorted(VERSIONS.glob("*.py"))
    out += sorted((BACKEND / "scripts").glob("seed_*.py"))
    out += sorted((BACKEND / "scripts").glob("seed_*.sh"))
    for extra in ("scripts/run_canonical_seeds.sh",):
        f = BACKEND / extra
        if f.exists():
            out.append(f)
    return out


def _fingerprint() -> str:
    """Hash of every shape file — content and name, order-independent."""
    h = hashlib.sha256()
    for f in _shape_files():
        h.update(f.name.encode())
        h.update(hashlib.sha256(f.read_bytes()).digest())
    return h.hexdigest()[:12]


def _admin(url: str):
    """Autocommit connection on the maintenance database (CREATE/DROP need it)."""
    import psycopg2

    conn = psycopg2.connect(_swap_db(url, "postgres"))
    conn.autocommit = True
    return conn


def _exists(cur, name: str) -> bool:
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
    return cur.fetchone() is not None


def _kill_sessions(cur, name: str) -> None:
    cur.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = %s AND pid <> pg_backend_pid()",
        (name,),
    )


def _table_count(url: str, name: str) -> int:
    import psycopg2

    conn = psycopg2.connect(_swap_db(url, name))
    try:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
        return cur.fetchone()[0]
    finally:
        conn.close()


def _row_count(url: str, name: str, table: str) -> int:
    import psycopg2

    conn = psycopg2.connect(_swap_db(url, name))
    try:
        cur = conn.cursor()
        cur.execute(f'SELECT count(*) FROM "{table}"')
        return cur.fetchone()[0]
    finally:
        conn.close()


def _drop(url: str, name: str) -> None:
    conn = _admin(url)
    cur = conn.cursor()
    try:
        _kill_sessions(cur, name)
        cur.execute(f'DROP DATABASE IF EXISTS "{name}"')
    finally:
        cur.close()
        conn.close()


def _ensure_template(url: str, tpl: str, seed: bool) -> None:
    conn = _admin(url)
    cur = conn.cursor()
    try:
        if _exists(cur, tpl):
            # ⚠️ EXISTENCE IS NOT CURRENCY, AND THIS CHECK IS NOT BELT-AND-BRACES.
            # The first real run of this script crashed between CREATE DATABASE
            # and `alembic upgrade`, leaving a template with the right name, the
            # right fingerprint, and ZERO TABLES. Name-only reuse accepted it as
            # current, which would have run the whole gate against an empty
            # database and blamed the code. A template must be shown to have a
            # schema, not merely to exist.
            n = _table_count(url, tpl)
            # A seeded template must also still HOLD its seed. Same reasoning as
            # the table check: the right name proves nothing about the contents.
            ok = n > 0 and (not seed or _row_count(url, tpl, "companies") > 0)
            if ok:
                print(f"  template {tpl} is current ({n} tables) — reusing it", flush=True)
                return
            print(f"  template {tpl} is half-built ({n} tables, seed missing or empty) — rebuilding", flush=True)
            _kill_sessions(cur, tpl)
            cur.execute(f'DROP DATABASE IF EXISTS "{tpl}"')
        # Any template whose fingerprint no longer matches is stale. Drop them,
        # or every migration edit leaves another copy behind.
        # Keep any template at the CURRENT fingerprint (the seeded and bare
        # variants share it); drop only genuinely stale shapes.
        cur.execute(
            "SELECT datname FROM pg_database WHERE datname LIKE 'bridgeable_gate_tpl%%' "
            "AND datname NOT LIKE %s",
            (f"%_{_fingerprint()}",),
        )
        for (stale,) in cur.fetchall():
            _kill_sessions(cur, stale)
            cur.execute(f'DROP DATABASE IF EXISTS "{stale}"')
            print(f"  dropped stale template {stale}", flush=True)
        print(f"  building template {tpl} ({len(list(VERSIONS.glob('*.py')))} migrations, one time)", flush=True)
        cur.execute(f'CREATE DATABASE "{tpl}"')
    finally:
        cur.close()
        conn.close()

    # ⚠️ ANY failure past this point must drop the template, not just a non-zero
    # exit. The crash that proved this was FileNotFoundError on a bare `alembic`
    # (not on PATH — hence sys.executable -m), which raised straight past an
    # exit-code-only cleanup and left the empty template above.
    env = {**os.environ, "DATABASE_URL": _swap_db(url, tpl), "PYTHONPATH": str(BACKEND)}
    try:
        r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env)
        if r.returncode != 0:
            raise RuntimeError(f"alembic upgrade head exited {r.returncode}")
        n = _table_count(url, tpl)
        if n == 0:
            raise RuntimeError("alembic reported success but the template has no tables")
        print(f"  migrated: {n} tables", flush=True)

        if seed:
            # ⚠️ THE SEED LOG IS NEVER PRINTED AND NEVER READ HERE.
            # `seed_sunnycrest.py` generates and prints a temporary admin
            # password. CLAUDE.md: that value must not transit a session, in
            # either direction. seed_dev.sh honours SEED_DEV_LOG, so the output
            # goes to a file this script does not open. On failure it reports the
            # PATH and the exit code — never the contents.
            log = pathlib.Path(os.environ.get("TMPDIR", "/tmp")) / f"gate-seed-{tpl}.log"
            print(f"  seeding the canonical set (~222s in CI; log: {log})", flush=True)
            senv = {**env, "SEED_DEV_LOG": str(log), "ENVIRONMENT": "dev"}
            # ⚠️ DO NOT SEND THIS TO DEVNULL. It was, and the first worktree run
            # failed BEFORE seed_dev.sh opened its own log — so the log did not
            # exist, the subprocess output had been discarded, and the failure
            # had left no evidence anywhere. Capture it to a sibling file: the
            # script's own log still holds the credential and is never read
            # here, but a pre-log failure now has somewhere to land.
            shell_log = log.with_suffix(".shell.log")
            r = subprocess.run(["bash", "scripts/seed_dev.sh"], cwd=BACKEND, env=senv,
                               capture_output=True, text=True)
            shell_log.write_text(
                f"$ bash scripts/seed_dev.sh  -> exit {r.returncode}\n"
                f"--- stdout ---\n{r.stdout}\n--- stderr ---\n{r.stderr}\n"
            )
            if r.returncode != 0:
                tail = (r.stderr or r.stdout or "").strip().splitlines()[-3:]
                raise RuntimeError(
                    f"seed_dev.sh exited {r.returncode}. Its own log is at {log} "
                    f"(contains a generated password — read it yourself, this script "
                    f"will not surface it). Shell output: {shell_log}. Last lines: {tail}")
            # ⚠️ EXIT 0 IS NOT EVIDENCE THE SEED LANDED. run_canonical_seeds.sh
            # exits 0 even when individual seeds fail — a locked decision, noted
            # in seed_dev.sh. So assert the rows exist.
            c = _row_count(url, tpl, "companies")
            if c == 0:
                raise RuntimeError(
                    f"seed_dev.sh exited 0 but companies is empty; log at {log}")
            print(f"  seeded: {c} companies", flush=True)
    except BaseException as exc:
        _drop(url, tpl)
        sys.exit(f"✗ template build failed ({exc}); template dropped, not left half-built.")


def _warn_if_not_like_ci() -> None:
    """Name uncommitted migrations and test files, because CI cannot see them.

    ⚠️ THE GATE IS FAITHFUL TO THE FILESYSTEM; THE FILESYSTEM MAY NOT BE FAITHFUL
    TO main. pytest imports app/ from the working tree and `alembic upgrade head`
    resolves the head by reading alembic/versions/ — so uncommitted code and
    uncommitted migrations both enter the run, and CI has neither.

    Measured 2026-11-04 in this shared checkout: 17 reds against a green CI, all
    from a concurrent session's uncommitted work — 16 on `two_step_required` and
    one on the ci_membership partition.

    ⚠️ AND APP SOURCE, NOT THE MIGRATION, WAS THE CAUSE — this function watched
    only migrations and tests at first, which is exactly how I misattributed it.
    Three untracked migrations (r225 two-step sign-in, r226, r227) were the
    obvious suspect and I called them definitive. Testing it falsified it: on a
    database migrated to r224 — main's head, with no `user_two_step` table at all
    — the same 16 still failed. `app/core/two_step.py` is UNTRACKED and absent
    from main, and main's `area_guard.py` contains zero occurrences of
    `two_step_required`. The schema was never the variable; the imported code
    was. So all three trees are reported, and app/ first.

    This is the r228 class of problem (a migration chained off an uncommitted
    revision) seen from the other end, and it is why a red here is only
    comparable to CI once this says nothing.
    """
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--", "app", "alembic/versions", "tests"],
            cwd=BACKEND, capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return
    if out.returncode != 0:
        return
    rows = [ln for ln in out.stdout.splitlines() if ln.strip()]
    mig = [r for r in rows if "alembic/versions/" in r]
    src = [r for r in rows if "/app/" in r]
    tst = [r for r in rows if r not in mig and r not in src]
    if not rows:
        return
    print("", flush=True)
    print("  ⚠️  THIS RUN IS NOT COMPARABLE TO CI — uncommitted files CI cannot see:", flush=True)
    # app/ first: it is imported by every test, and it is what actually caused
    # the 17 reds this notice was written for.
    if src:
        shown = ", ".join(r.split("/")[-1] for r in src[:4])
        more = f" (+{len(src) - 4} more)" if len(src) > 4 else ""
        print(f"       app        {len(src)} modified/untracked: {shown}{more}", flush=True)
        print("                  ⚠️ imported by every test — a red here can be entirely this", flush=True)
    for r in mig:
        print(f"       migration  {r.strip()}   <-- APPLIED to the template; CI has no such schema", flush=True)
    # Migrations are listed in full — each one changes the schema under test.
    # Modified test files are only counted: a shared checkout routinely carries
    # dozens, and listing them buries the migrations that actually matter.
    other = [r for r in tst if r not in mig]
    if other:
        shown = ", ".join(r.split("/")[-1] for r in other[:4])
        more = f" (+{len(other) - 4} more)" if len(other) > 4 else ""
        print(f"       tests      {len(other)} modified/untracked: {shown}{more}", flush=True)
    if mig:
        print("       An untracked migration changes `alembic heads`, so the template"
              " is built\n       to a head that does not exist on main. Reds here may"
              " be entirely explained\n       by that. Commit or stash before trusting"
              " a red against CI.", flush=True)
    print("", flush=True)


def _reap_orphan_runs(url: str) -> None:
    """Drop run databases whose owning process is gone.

    ⚠️ A KILLED RUN LEAKS ITS DATABASE, and the `finally` block does not save
    you: SIGTERM terminates without unwinding, so a Ctrl-C'd or killed gate run
    leaves `bridgeable_gate_run_<pid>` behind — a full clone of the template
    (36 MB migrated, measured 2026-11-04; more once seeded). The stale-template sweep never touched these because it only
    matches the `tpl` prefix. Proven by killing a run mid-pytest, which is
    exactly how it happens in practice.

    The pid is in the name, so liveness is checkable: signal 0 tests existence
    without delivering anything.
    """
    conn = _admin(url)
    cur = conn.cursor()
    try:
        cur.execute("SELECT datname FROM pg_database WHERE datname LIKE 'bridgeable_gate_run_%%'")
        for (name,) in cur.fetchall():
            tail = name.rsplit("_", 1)[-1]
            if not tail.isdigit():
                continue
            pid = int(tail)
            if pid == os.getpid():
                continue
            try:
                os.kill(pid, 0)
                continue  # still running — someone else's live gate, leave it
            except ProcessLookupError:
                pass
            except PermissionError:
                continue  # exists but owned by another user — not ours to drop
            _kill_sessions(cur, name)
            cur.execute(f'DROP DATABASE IF EXISTS "{name}"')
            print(f"  reaped orphaned run database {name} (pid {pid} is gone)", flush=True)
    finally:
        cur.close()
        conn.close()


def _targets(args) -> list[str]:
    if args.files:
        return args.files
    if args.all:
        return ["tests"]
    lines = [
        ln.strip()
        for ln in MANIFEST.read_text().splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    if not lines:
        sys.exit(f"✗ {MANIFEST} yielded no entries.")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="test paths (default: the ci_gate.txt manifest)")
    ap.add_argument("--all", action="store_true", help="run the whole tests/ tree")
    ap.add_argument("--keep", action="store_true", help="do not drop the run database")
    ap.add_argument("--no-seed", dest="seed", action="store_false", default=True,
                    help="skip the canonical seed (NOT comparable to CI — CI seeds)")
    ap.add_argument("-q", "--quiet", action="store_true", help="pass -q to pytest")
    args, extra = ap.parse_known_args()

    url = _base_url()
    if args.seed and not (BACKEND / ".venv" / "bin" / "python").exists():
        # ⚠️ seed_dev.sh DEGRADES SILENTLY HERE, it does not fail loudly. It
        # prefers ${BACKEND_DIR}/.venv/bin/python and otherwise falls back to
        # whatever `python` is on PATH — a documented hazard in that script
        # (measured 2026-09-23). In a fresh worktree there is no .venv, so the
        # fallback interpreter has none of the dependencies and the seed dies
        # with no useful message. Refuse with the remedy instead.
        sys.exit(
            f"✗ {BACKEND / '.venv/bin/python'} does not exist, and scripts/seed_dev.sh\n"
            "  silently falls back to PATH `python`, which will not have the deps.\n"
            "  In a worktree, link the venv from the primary checkout:\n"
            f"    ln -sfn <primary>/backend/.venv {BACKEND}/.venv\n"
            "  and add `backend/.venv` to .git/info/exclude so the tree stays clean.\n"
            "  Or run with --no-seed (NOT comparable to CI)."
        )
    kind = "tpl" if args.seed else "tplbare"
    tpl = f"bridgeable_gate_{kind}_{_fingerprint()}"
    run = f"bridgeable_gate_run_{os.getpid()}"

    print(f"▸ fresh-database gate   template={tpl}   run={run}"
          + ("" if args.seed else "   ⚠️ --no-seed: NOT comparable to CI"), flush=True)
    _warn_if_not_like_ci()
    _reap_orphan_runs(url)
    _ensure_template(url, tpl, args.seed)

    conn = _admin(url)
    cur = conn.cursor()
    _kill_sessions(cur, tpl)  # CREATE ... TEMPLATE requires the source idle
    cur.execute(f'DROP DATABASE IF EXISTS "{run}"')
    cur.execute(f'CREATE DATABASE "{run}" TEMPLATE "{tpl}"')
    cur.close()
    conn.close()
    print(f"  created {run} from template", flush=True)

    env = {**os.environ, "DATABASE_URL": _swap_db(url, run), "PYTHONPATH": str(BACKEND)}
    try:
        cmd = [sys.executable, "-m", "pytest", *_targets(args), *extra]
        if args.quiet:
            cmd.append("-q")
        print(f"  pytest over {len(_targets(args))} target(s)\n", flush=True)
        status = subprocess.run(cmd, cwd=BACKEND, env=env).returncode
    finally:
        if args.keep:
            print(f"\n  --keep: {run} left in place. Drop it with:", flush=True)
            print(f"    psql -d postgres -c 'DROP DATABASE \"{run}\"'", flush=True)
        else:
            _drop(url, run)
            print(f"\n  dropped {run}", flush=True)

    print(f"▸ gate exit {status}" + ("  (green)" if status == 0 else "  (RED)"), flush=True)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
