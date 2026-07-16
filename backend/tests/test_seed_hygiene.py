"""Seed-cleanup / perf pass pins (2026-07).

  * THE MANIFEST — tiers are declared with justifications; a local-only
    seed is provably absent from a staging-shaped run (the Railway marker,
    not ENVIRONMENT — staging deliberately runs ENVIRONMENT=dev) and
    provably present locally; manual seeds never run anywhere.
  * THE RUNNER — skips manifest seeds WITH the reason in the log; a seed's
    own declared skip (exit 3) counts as skipped, never as a failure;
    every executed seed gets a [seed-timing] line (the permanent per-seed
    profile in every boot log).
  * THE PURGE — the keep-list protects real content through a live
    --apply run; the purge is idempotent; production refuses.
"""
from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
RUNNER = BACKEND / "scripts" / "run_canonical_seeds.sh"


class TestManifest:
    def test_every_entry_declares_a_tier_and_a_justification(self):
        from scripts.seed_manifest import TIERS, _VALID_TIERS

        for name, (tier, why) in TIERS.items():
            assert tier in _VALID_TIERS, name
            assert len(why) > 20, f"{name}: the justification is the contract"

    def test_local_only_absent_from_staging_shaped_run(self, monkeypatch):
        monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "deadbeef")
        from scripts.seed_manifest import skips

        names = {n for n, _, _ in skips()}
        assert "seed_full_year_e2e" in names
        assert "seed_intelligence_dev_executions" in names

    def test_local_only_present_locally(self, monkeypatch):
        monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
        from scripts.seed_manifest import skips

        names = {n for n, _, _ in skips()}
        assert "seed_full_year_e2e" not in names
        assert "seed_intelligence_dev_executions" not in names

    def test_manual_skipped_everywhere(self, monkeypatch):
        from scripts.seed_manifest import TIERS, skips

        manual = {n for n, (t, _) in TIERS.items() if t == "manual"}
        for env in (None, "deadbeef"):
            if env is None:
                monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
            else:
                monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", env)
            assert manual <= {n for n, _, _ in skips()}


@pytest.fixture
def synthetic_seeds(tmp_path):
    """A temp scripts/ package the runner can sweep (SEEDS_DIR/BACKEND_DIR
    overrides exist for exactly this)."""
    pkg = tmp_path / "scripts"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "seed_manifest.py").write_text(textwrap.dedent("""
        import os, sys
        TIERS = {"seed_devish": ("local-only", "a synthetic dev-scale fixture for the runner pin")}
        def skips():
            deployed = bool(os.environ.get("RAILWAY_GIT_COMMIT_SHA"))
            out = []
            for name, (tier, why) in TIERS.items():
                if tier == "manual" or (tier == "local-only" and deployed):
                    out.append((name, tier, why))
            return out
        if __name__ == "__main__":
            if "--skips" in sys.argv:
                for n, t, w in skips():
                    print(f"{n}\\t{t}\\t{w}")
    """))
    (pkg / "seed_devish.py").write_text("print('devish ran')\n")
    (pkg / "seed_normal.py").write_text("print('normal ran')\n")
    (pkg / "seed_declared_skip.py").write_text(
        "import sys\nprint('prereq absent — SKIPPED (declared)')\nsys.exit(3)\n"
    )
    return tmp_path


def _run_runner(root: Path, extra_env: dict | None = None) -> str:
    env = {**os.environ, "SEEDS_DIR": str(root / "scripts"),
           "BACKEND_DIR": str(root)}
    env.update(extra_env or {})
    out = subprocess.run(
        ["bash", str(RUNNER)], capture_output=True, text=True, env=env,
        timeout=120,
    )
    return out.stdout + out.stderr


class TestRunner:
    def test_staging_shaped_run_skips_local_only_with_reason(self, synthetic_seeds):
        log = _run_runner(synthetic_seeds, {"RAILWAY_GIT_COMMIT_SHA": "deadbeef"})
        assert "Skip: seed_devish (tier local-only — a synthetic dev-scale fixture" in log
        assert "devish ran" not in log
        assert "normal ran" in log  # untiered seeds still run

    def test_local_run_executes_local_only(self, synthetic_seeds):
        env = {k: v for k, v in os.environ.items() if k != "RAILWAY_GIT_COMMIT_SHA"}
        out = subprocess.run(
            ["bash", str(RUNNER)], capture_output=True, text=True,
            env={**env, "SEEDS_DIR": str(synthetic_seeds / "scripts"),
                 "BACKEND_DIR": str(synthetic_seeds)},
            timeout=120,
        )
        log = out.stdout + out.stderr
        assert "devish ran" in log

    def test_exit_3_counts_as_declared_skip_not_failure(self, synthetic_seeds):
        log = _run_runner(synthetic_seeds)
        assert "Skipped by seed: seed_declared_skip (declared skip, exit 3)" in log
        assert "0 failed" in log.splitlines()[-1] or "0 failed" in log

    def test_every_executed_seed_gets_a_timing_line(self, synthetic_seeds):
        log = _run_runner(synthetic_seeds)
        assert "[seed-timing] seed_normal:" in log
        assert "(ok)" in log


class TestPurge:
    def test_production_refuses(self):
        out = subprocess.run(
            ["python", "-m", "scripts.purge_fixture_residue", "--apply"],
            capture_output=True, text=True, cwd=str(BACKEND),
            env={**os.environ, "ENVIRONMENT": "production"},
            timeout=60,
        )
        assert out.returncode == 1
        assert "refusing" in out.stdout

    def test_keep_list_survives_a_live_apply(self):
        """THE PIN: a real --apply run on the dev DB leaves every keep-list
        tenant (and its users) standing. Residue created here dies."""
        import uuid

        from sqlalchemy import text

        from app.database import SessionLocal

        db = SessionLocal()
        marker = f"residue-{uuid.uuid4().hex[:8]}"
        db.execute(text(
            "INSERT INTO companies (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (:i, :n, :s, true, now(), now())"
        ), {"i": str(uuid.uuid4()), "n": marker, "s": marker})
        db.commit()

        out = subprocess.run(
            ["python", "-m", "scripts.purge_fixture_residue", "--apply"],
            capture_output=True, text=True, cwd=str(BACKEND),
            env=dict(os.environ), timeout=600,
        )
        assert out.returncode == 0, out.stdout[-2000:]

        survivors = {r[0] for r in db.execute(text(
            "SELECT slug FROM companies"
        ))}
        db.close()
        assert "testco" in survivors
        assert "hopkins-fh" in survivors
        assert "st-marys" in survivors
        assert marker not in survivors  # residue died

        db = SessionLocal()
        n = db.execute(text(
            "SELECT count(*) FROM users u JOIN companies c ON c.id = u.company_id "
            "WHERE c.slug = 'testco' AND u.is_active"
        )).scalar()
        db.close()
        assert n >= 5  # testco's seeded roster intact
