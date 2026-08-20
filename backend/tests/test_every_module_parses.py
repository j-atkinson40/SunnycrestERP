"""Every shipped Python file parses. The cheapest guard in the codebase.

⚠️ A MOUNTED ROUTER'S SERVICE WAS UNPARSEABLE AND NOTHING NOTICED.
`app/services/onboarding/unified_import_service.py` carried a SyntaxError from
commit `948acb4f` until TAX-5 found it by accident, while walking the AST for an
unrelated ratchet. In that window:

  - the module could not be imported AT ALL
  - `app/api/routes/unified_import.py` imported it in TWENTY places
  - that router was MOUNTED (`app/api/v1.py:838`)

Every one of those endpoints raised on call. The app booted cleanly because the
imports are lazy — inside the request handlers — so nothing evaluated the module
until someone hit the endpoint, and nobody did. **A syntax error survived in a
shipped, routed path for the life of a commit.**

⚠️ THE GAP IS UNPARSEABLE FILES, NOT UNIMPORTABLE ONES, AND CONFLATING THEM
WOULD MAKE THIS GUARD WORSE THAN NOTHING. The obvious version — walk `app/` and
`importlib.import_module` everything — would execute import-time side effects in
modules that are perfectly fine: registry population, singleton construction,
`lru_cache` warm-up, and anything else a module does at import. It would fail on
healthy code and turn a guard into a bug generator.

`ast.parse` reads the file and builds a tree. It runs nothing. It catches
exactly the class of defect that got through — a file Python cannot read — and
nothing else. That narrowness is the feature.

What this does NOT catch, stated so nobody mistakes it for more than it is:
a module that parses and fails at import (bad import, missing dependency,
exception at module scope). That is a real gap and it wants a different
mechanism than this one.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

BACKEND = pathlib.Path(__file__).resolve().parent.parent

#: Shipped trees, worst-consequence first. `app/` is served; `scripts/` runs on
#: every deploy through the canonical seed runner; `alembic/versions/` runs
#: before the server starts, so a broken migration is a failed deploy.
TREES = ("app", "scripts", "alembic/versions")


def _python_files(tree: str) -> list[pathlib.Path]:
    root = BACKEND / tree
    if not root.exists():
        return []
    return sorted(
        p for p in root.rglob("*.py")
        if "__pycache__" not in p.parts
    )


@pytest.mark.parametrize("tree", TREES)
def test_every_file_parses(tree):
    """⚠️ PARAMETRISED PER TREE so a failure names WHERE, and so one broken
    tree does not mask another behind a single assertion."""
    broken = []
    for path in _python_files(tree):
        try:
            ast.parse(path.read_text(), filename=str(path))
        except SyntaxError as exc:
            broken.append(f"{path.relative_to(BACKEND)}:{exc.lineno}  {exc.msg}")
        except UnicodeDecodeError as exc:
            broken.append(f"{path.relative_to(BACKEND)}  undecodable: {exc}")
    assert not broken, (
        f"{len(broken)} file(s) under {tree}/ cannot be parsed by Python — "
        "each one raises on import, and a lazy import means that surfaces only "
        "when someone calls the code:\n  " + "\n  ".join(broken)
    )


def test_the_guard_is_actually_looking_at_files():
    """⚠️ A GUARD THAT SCANS NOTHING PASSES. `rglob` over a mistyped or moved
    directory returns an empty list and the assertion above holds vacuously —
    the same shape as a ratchet satisfied by an empty set. Pin a floor so the
    guard cannot quietly stop guarding."""
    counts = {tree: len(_python_files(tree)) for tree in TREES}
    assert counts["app"] > 400, counts
    assert counts["scripts"] > 20, counts
    assert counts["alembic/versions"] > 100, counts


def test_the_file_this_guard_was_written_for_parses():
    """The worked example, held by name. It carried a SyntaxError across an
    unknown number of deploys behind twenty lazy imports on a mounted router."""
    path = BACKEND / "app" / "services" / "onboarding" / "unified_import_service.py"
    ast.parse(path.read_text(), filename=str(path))
