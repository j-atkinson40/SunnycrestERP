"""r201's frozen availability map must agree with the live seed script.

⚠️ THE DUPLICATION IS DELIBERATE AND THIS TEST IS WHAT MAKES IT SAFE. r201 carries
its own copy of the SKU map because a migration's data has to be fixed at the
revision — one that imported `scripts/seed_personalization_availability.py` would
replay differently every time the script changed, so running the chain on a fresh
database in six months would write whatever the script says then rather than what
this revision wrote.

The cost of freezing is drift. This test is the detector: while both are live they
must agree, so a change to one without the other fails here rather than producing two
databases that disagree about what a licensee offers.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _load(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, _ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_r201_matches_the_seed_map():
    mig = _load("alembic/versions/r201_personalization_availability_data.py", "_r201")
    seed = _load("scripts/seed_personalization_availability.py", "_seed_avail")

    assert set(mig.AVAILABILITY_BY_SKU) == set(seed.AVAILABILITY_BY_SKU), (
        "the SKU sets differ — migration-only: "
        f"{sorted(set(mig.AVAILABILITY_BY_SKU) - set(seed.AVAILABILITY_BY_SKU))}, "
        "script-only: "
        f"{sorted(set(seed.AVAILABILITY_BY_SKU) - set(mig.AVAILABILITY_BY_SKU))}"
    )
    for sku in sorted(mig.AVAILABILITY_BY_SKU):
        assert sorted(mig.AVAILABILITY_BY_SKU[sku]) == sorted(
            seed.AVAILABILITY_BY_SKU[sku]
        ), f"{sku} differs between the migration and the seed script"


def test_the_map_is_not_empty_and_covers_every_form_group():
    """⚠️ POSITIVE CONTROL on the test above. Two empty dicts are equal, so the
    agreement assertion alone would pass against a map that had been emptied."""
    mig = _load("alembic/versions/r201_personalization_availability_data.py", "_r201b")

    assert len(mig.AVAILABILITY_BY_SKU) == 40, len(mig.AVAILABILITY_BY_SKU)
    for prefix in ("BV-", "UV-", "GL-", "LC-", "CE-"):
        assert any(k.startswith(prefix) for k in mig.AVAILABILITY_BY_SKU), prefix
    # ⚠️ The P-series urns must be ABSENT — pending James, by ruling.
    assert not [k for k in mig.AVAILABILITY_BY_SKU if k.startswith("P")], (
        "the P-series urns are in the map; the ruling leaves them NOT_CONFIGURED"
    )


def test_no_permitted_set_contains_none():
    """`none` is granted wherever the question is asked at all, and must never be
    stored — `Availability.permits` would then be deciding it twice."""
    mig = _load("alembic/versions/r201_personalization_availability_data.py", "_r201c")
    for sku, answers in mig.AVAILABILITY_BY_SKU.items():
        assert "none" not in answers, sku
