"""The deploy's own shape: seeds out of the serving path, demo seeds out of production.

James's dispatch of 2026-10-24: "the seeds shouldn't sit in the startup path at all",
and fix the demo-seed risk.

⚠️ WHY A TEST AND NOT JUST THE CONFIG. `railway.toml` is read by Railway, not by this
repo, so nothing here fails if a key is renamed, the dashboard overrides it, or the
config-file path is changed in the UI. "The deploy worked" is satisfied by a service
that never migrated — the schema was already current — so a green deploy is not
evidence the file applied. These tests pin the two halves that CAN be checked locally
(the files say what they must) and the one that can only be checked live (Railway
echoes back what it read).
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import tomllib

import pytest

BACKEND = pathlib.Path(__file__).resolve().parent.parent
TOML = BACKEND / "railway.toml"
START = BACKEND / "railway-start.sh"
PREP = BACKEND / "railway-prep.sh"


def _toml() -> dict:
    with TOML.open("rb") as fh:
        return tomllib.load(fh)


def _code(path: pathlib.Path) -> str:
    """The script's CODE, with comments and blank lines removed.

    ⚠️ THIS EXISTS BECAUSE I WROTE THE SAME BUG THREE TIMES IN TWO DAYS. Every
    "this string must be absent" assertion over a shell script in this repo fails on
    the script's own documentation, because these files explain their defects by
    QUOTING them. `railway-prep.sh` quotes the guard that failed open
    (`"${ENVIRONMENT:-dev}" != "production"`) in the comment recording that it created
    `hopkins-fh` on production, and quotes `exec uvicorn` in the comment saying it must
    not appear. Yesterday's version of this mistake was a seed ratchet grepping for
    "an admin has edited it", which the seed now quotes for the same reason.

    CLAUDE.md §11 states the rule and I kept reaching for grep anyway: a file that
    records a correction by quoting it returns hits for the superseded string
    permanently, so the count cannot reach zero and must not be read as if it could.
    The remedy is to scan STRUCTURE, not prose. For shell that means dropping comment
    lines; for Python it meant `ast` (see `test_seed_prompt_is_not_one_shot.py`).
    """
    return "\n".join(
        line for line in path.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


# ── the files say what they must ──────────────────────────────────────────────


def test_prep_is_the_pre_deploy_command():
    deploy = _toml()["deploy"]
    assert deploy["preDeployCommand"] == "bash railway-prep.sh"
    assert PREP.exists(), "preDeployCommand names a script that must ship in the image"
    # Railway's ceiling for this field is 3600. Prep measured 537-552 s on 2026-10-23.
    assert 600 <= deploy["preDeployTimeoutSeconds"] <= 3600


def test_the_start_script_only_starts_the_server():
    """⚠️ THE WHOLE POINT, AND THE THING THAT WILL REGRESS. The next person who needs
    "just one thing before the server starts" is how the old file reached 195 lines,
    every one of them delaying the first request. Boot work belongs in prep.
    """
    body = [
        line.strip() for line in START.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert any(line.startswith("exec uvicorn") for line in body), body
    # Nothing that migrates, seeds, or reaches the database.
    forbidden = ("alembic", "scripts.seed", "seed_", "run_canonical_seeds", "with_boot_lock")
    for line in body:
        for word in forbidden:
            assert word not in line, f"{word!r} is back in railway-start.sh: {line!r}"
    # ⚠️ THE POSITIVE CONTROL. An empty `body` would satisfy every assertion above for
    # free, which is the shape of a scan that cannot see.
    assert len(body) >= 2, body


def test_prep_still_carries_the_whole_phase():
    """The move must not have dropped a step. These are the five things prep does."""
    src = _code(PREP)
    # ⚠️ THE INVOCATIONS, NOT THE MESSAGES, AND A BREAK TEST FORCED THAT. My first
    # version asserted `"alembic upgrade head" in src`; replacing the command with
    # `if false` left the string in prep's own failure echo ("✗ alembic upgrade head
    # FAILED") and the test stayed green. It was checking that the script still TALKS
    # about migrating. CLAUDE.md §11 shape 6: a check that passes for a reason
    # unrelated to what it claims.
    for needed in ("if ! alembic upgrade head",
                   "python -m scripts.seed_staging",
                   "python -m scripts.seed_fh_demo",
                   "bash \"$(dirname \"$0\")/scripts/run_canonical_seeds.sh\"",
                   "scripts/require_known_environment.sh"):
        assert needed in src, needed
    # ⚠️ AND IT MUST NOT START A SERVER. A pre-deploy container that serves holds the
    # phase open until its timeout and then fails the deploy. Checked against CODE —
    # the file's comments mention `exec uvicorn` twice, deliberately.
    assert "exec uvicorn" not in src
    # The positive control: an empty read would satisfy the line above for free.
    assert len(src.splitlines()) > 20


def test_prep_keeps_its_fail_loud_discipline():
    """R-1.6.3 and R-3.1.3: a migration or seed failure fails the deploy. Moving the
    phase to `preDeployCommand` is what preserves that — Railway fails the deploy on a
    non-zero exit — so the `exit 1`s must still be there to produce one.
    """
    src = _code(PREP)
    # ⚠️ EACH ABORT NAMED, NOT COUNTED, AND A BREAK TEST FORCED THAT TOO. My first
    # version asserted `src.count("exit 1") >= 5`; deleting seed_staging's abort left
    # five others and the test stayed green. A count is satisfied by the paths that
    # remain, which is the denominator problem in miniature — it cannot see WHICH
    # failure stopped being loud.
    # ⚠️ AND MY STRICT VERSION WAS WRONG ABOUT THE SHAPE, which the run said
    # immediately: alembic's abort message carries a suffix ("(R-3.1.3 fail-loud
    # discipline)") and is followed by three explanatory echoes before its `exit 1`.
    # Requiring `exit 1` on the very next line asserted a formatting habit, not the
    # discipline. The window is what matters — an abort followed by nothing is the
    # failure mode.
    lines = src.splitlines()
    for step in ("alembic upgrade head", "seed_staging.py", "seed_fh_demo.py",
                 "seed_dispatch_demo.py", "seed_edge_panel_inheritance.py"):
        at = [i for i, line in enumerate(lines) if f"✗ {step} FAILED" in line]
        assert at, f"no abort message for {step}"
        i = at[0]
        window = [line.strip() for line in lines[i + 1:i + 7]]
        assert "exit 1" in window, (step, window)


def test_the_dockerfile_ships_both_scripts_executable():
    src = (BACKEND / "Dockerfile").read_text()
    assert "chmod +x railway-start.sh railway-prep.sh" in src
    assert 'CMD ["bash", "railway-start.sh"]' in src


def test_the_healthcheck_budget_matches_a_server_that_only_binds_a_port():
    """⚠️ 900 s WAS RIGHT YESTERDAY AND IS WRONG NOW, which is the whole trade. It was
    ~1.7x a measured nine-minute boot; with seeding gone this container imports the app
    and binds, so a budget in minutes would be a place for a real hang to hide.
    """
    deploy = _toml()["deploy"]
    assert deploy["healthcheckPath"] == "/api/health"
    assert deploy["healthcheckTimeout"] <= 300, (
        "a tight budget is only honest while railway-start.sh does nothing but serve"
    )


# ── the demo seeds are out of production ─────────────────────────────────────

#: The five that had no `ENVIRONMENT` guard and ran on every production deploy.
UNGUARDED_DEMO_SEEDS = (
    "seed_quotes",
    "seed_saved_orders",
    "seed_nl_demo_data",
    "seed_demo_artifact_focuses",
    "seed_demo_artifact_workflows",
)


@pytest.mark.parametrize("name", UNGUARDED_DEMO_SEEDS)
def test_a_demo_seed_without_a_production_guard_is_manual(name):
    """⚠️ EITHER A GUARD OR A TIER, AND THE TIER IS THE ONE A READER CAN SEE. A seed
    that writes demo data on a production deploy is the hazard; `seed_quotes` and
    `seed_saved_orders` share a `pick_tenant` that falls back to the first active
    company with the sales module, which on production is `sunnycrest`.
    """
    from scripts.seed_manifest import TIERS

    src = (BACKEND / "scripts" / f"{name}.py").read_text()
    guarded = "ENVIRONMENT" in src
    tier = TIERS.get(name, (None,))[0]
    assert guarded or tier == "manual", (
        f"{name} writes demo data, has no ENVIRONMENT guard, and is not manual"
    )


@pytest.mark.parametrize("name", UNGUARDED_DEMO_SEEDS)
def test_local_dev_and_ci_still_get_them(name):
    """⚠️ THE HALF THAT IS EASY TO MISS. A `manual` tier is skipped EVERYWHERE, so
    declaring these manual removes them from local dev and CI as well as production.
    `seed_dev.sh` must invoke them explicitly or a dev database quietly loses data and
    the first symptom is a test failing for want of rows nobody removed on purpose.
    """
    # ⚠️ AGAINST CODE, AND THE FOURTH TIME I MADE THIS MISTAKE IN TWO DAYS — in the
    # same file as the `_code` helper written to prevent it. My first version fell back
    # to `name in read_text()`, and the comment block I had just added to `seed_dev.sh`
    # NAMES `seed_quotes` and `seed_saved_orders` while explaining why they are manual.
    # So emptying the loop entirely left those two green and reddened only the three the
    # comment does not mention. Knowing the rule is plainly not the operative variable;
    # using the helper is.
    assert name in _code(BACKEND / "scripts" / "seed_dev.sh"), name


def test_the_guard_that_failed_open_is_still_closed():
    """⚠️ NOT A NEW RULE — A REGRESSION TEST ON prep's OWN RECORDED INCIDENT. Its
    comment: `!= "production"` inferred "dev" from a MISSING variable, so absence
    permitted demo seeding, and `hopkins-fh` was created on production 73 seconds
    after that guard was committed. Absence must refuse.
    """
    src = _code(PREP)
    assert "require_known_environment.sh" in src
    assert '"${ENVIRONMENT:-dev}" != "production"' not in src


# ── and the half that can only be checked live ───────────────────────────────


@pytest.mark.skipif(
    shutil.which("railway") is None or not os.environ.get("BRIDGEABLE_CHECK_LIVE_DEPLOY"),
    reason="needs the railway CLI and BRIDGEABLE_CHECK_LIVE_DEPLOY=1 (opt-in; hits the API)",
)
def test_railway_echoes_back_the_keys_it_read_from_the_file():
    """⚠️ THE ONLY AVAILABLE PROOF THAT THE FILE APPLIED, and it is opt-in because it
    calls Railway. A working deploy is not evidence: the schema is already current, so
    a service that never ran prep serves perfectly well. Railway reports both the path
    it read and which keys came from the file, which is checkable without deploy logs.
    """
    out = subprocess.run(
        ["railway", "deployment", "list", "--service", "SunnycrestERP",
         "--environment", "production", "--json"],
        capture_output=True, text=True, timeout=120,
    )
    assert out.returncode == 0, out.stderr[:400]
    rows = json.loads(out.stdout)
    rows = rows if isinstance(rows, list) else rows.get("deployments", rows)
    meta = rows[0]["meta"]
    assert meta.get("configFile", "").endswith("railway.toml"), meta.get("configFile")
    mapping = json.dumps(meta.get("propertyFileMapping", {}))
    assert "preDeployCommand" in mapping, (
        "Railway did not take preDeployCommand from the file — prep may not be running"
    )
    # ⚠️ RAILWAY NORMALISES IT TO A SINGLE-ITEM LIST, AND MY FIRST ASSERTION DID NOT
    # KNOW THAT. The schema says `preDeployCommand` accepts "string or single-item array
    # of strings"; the config file carries a string and the deployment object echoed
    # `['bash railway-prep.sh']`. An `== "bash railway-prep.sh"` would have failed the
    # live check against a deploy that was working perfectly — the test being wrong
    # about the shape of the evidence, which is its own failure mode.
    echoed = meta["serviceManifest"]["deploy"]["preDeployCommand"]
    if isinstance(echoed, list):
        assert len(echoed) == 1, echoed
        echoed = echoed[0]
    assert echoed == "bash railway-prep.sh", echoed
