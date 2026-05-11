"""R-8.y.d — CI snapshot-drift gate.

PRs that modify PLUGIN_CONTRACTS.md MUST regenerate + commit the
snapshot at frontend/src/lib/plugin-registry/plugin-contracts-snapshot.json
or this test fails with a clear message pointing at the regen command.

The codegen pipeline lives at scripts/generate_plugin_contracts_snapshot.py.
Idempotent — same source produces byte-identical JSON.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
CODEGEN_PATH = REPO_ROOT / "scripts" / "generate_plugin_contracts_snapshot.py"
SNAPSHOT_PATH = (
    REPO_ROOT
    / "frontend"
    / "src"
    / "lib"
    / "plugin-registry"
    / "plugin-contracts-snapshot.json"
)


def _run_codegen_fresh() -> dict:
    """Run the codegen script in a subprocess + capture its JSON.

    Uses a temp output path so the test never mutates the
    committed snapshot. Subprocess invocation avoids dataclass
    module-resolution edge cases when loading the script via
    importlib.util.spec_from_file_location.
    """
    # Add a small driver that calls codegen.generate(write=False)
    # and prints the result. We do this by injecting `generate`
    # from the script via -c invocation.
    cmd = [
        sys.executable,
        "-c",
        (
            "import sys, runpy, json; "
            "sys.path.insert(0, "
            f"{str(REPO_ROOT / 'scripts')!r}); "
            "mod = runpy.run_path("
            f"{str(CODEGEN_PATH)!r}, run_name='_load_only'); "
            "print(json.dumps(mod['generate'](write=False)))"
        ),
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)


def test_snapshot_matches_codegen_output():
    """Snapshot on disk equals codegen output (byte-identical).

    Failure means PLUGIN_CONTRACTS.md was modified without
    regenerating the snapshot. Fix:

        python scripts/generate_plugin_contracts_snapshot.py
    """
    fresh = _run_codegen_fresh()
    committed = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

    # Compare structured payloads — equality is JSON-deep.
    assert fresh == committed, (
        "PLUGIN_CONTRACTS.md modified without regenerating the snapshot. "
        "Run: python scripts/generate_plugin_contracts_snapshot.py "
        "and commit the updated "
        "frontend/src/lib/plugin-registry/plugin-contracts-snapshot.json."
    )


def test_snapshot_has_canonical_24_categories():
    """Sanity check on the document-version + count invariants."""
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    assert snapshot["total_count"] == 24
    assert snapshot["canonical_count"] + snapshot["partial_count"] + snapshot[
        "implicit_count"
    ] == 24
    assert len(snapshot["categories"]) == 24


def test_snapshot_every_category_fully_populated():
    """Every category should have all 9 canonical subsections present.

    Documents drift — if a section is added to PLUGIN_CONTRACTS.md
    without all 8 canonical subsections, the parser would surface
    empty fields and the browser would render empty panels.
    """
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    required = [
        "purpose",
        "input_contract",
        "output_contract",
        "guarantees",
        "failure_modes",
        "configuration_shape",
        "registration_mechanism",
        "current_implementations",
        "cross_references",
    ]
    for category in snapshot["categories"]:
        for field in required:
            assert category.get(field), (
                f"§{category['section_number']} "
                f"{category['title']} missing field '{field}'. "
                f"Run codegen + verify PLUGIN_CONTRACTS.md structure."
            )
