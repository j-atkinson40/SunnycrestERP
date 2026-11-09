"""`ChSup1` and `Garn` never leave the payroll area.

James's ruling, 2026-11-09: *"Child support (`ChSup1`) and garnishments
(`Garn`) are sensitive. They stay visible to payroll users only, and Opas never
mentions them in a home note or summary... line-level only, payroll area only,
never summarised in a note, report, or Opas text outside the payroll area."*

⚠️ **SENSITIVE MEANS RESTRICTED AT THE SURFACE, NOT ABSENT FROM THE DATA.**
These are real deductions on real checks. The register must import them or a
check's deduction total will not add up, and a check that does not add up is
how the parser detects its own faults. So the rule cannot be "do not store
them" — it has to be "only the payroll area can read them".

⚠️ **WHICH MAKES THE RULE STRUCTURAL, AND THAT IS WHY THIS TEST IS A SCAN
RATHER THAN A REQUEST.** Asserting that today's endpoints do not return these
codes would be true and nearly worthless: the risk is a surface added LATER —
a home note, an Opas summary, a dashboard total — by someone who never read
this ruling. So the scan enumerates every module that can reach a check line
AT ALL and requires each one to be named here with a reason. A new reader of
`payroll_check_lines` fails this test until a person decides it belongs.

⚠️ **TWO POSITIVE CONTROLS, because an allowlist ratchet needs them:** one
proves the scanner can SEE (it finds the modules we know reach these rows), and
one proves the allowlist is TIGHT (every entry really does reach them). A
scanner matching nothing satisfies the rule trivially.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.services.payroll.register_parser import (
    KNOWN_DEDUCTION_CODES,
    SENSITIVE_DEDUCTION_CODES,
)

APP = Path(__file__).resolve().parent.parent / "app"

#: The names that reach a check line, in any spelling a module could use.
REACHES_CHECK_LINES = ("PayrollCheckLine", "payroll_check_lines")

#: ⚠️ **TWO LISTS, BECAUSE THERE ARE TWO DIFFERENT PERMISSIONS**, and I had
#: them as one until `test_the_allowlist_is_tight` said so. Reaching the TABLE
#: and naming the CODE STRINGS are different powers held by different modules:
#: `register_parser.py` names `ChSup1` (it is a code it must recognise) and
#: never touches the table, while `register_import.py` writes the table and
#: never names a sensitive code. One combined list allowlisted each module for
#: both, which would have pre-exempted the parser if it ever started reading
#: check rows — the stale-entry failure the control exists to catch.
#:
#: Every module in either list must be inside the payroll area —
#: `app/api/v1.py` mounts the payroll router with `area:payroll`, which
#: `test_the_payroll_router_is_area_tagged` holds.

#: May reach `payroll_check_lines` / `PayrollCheckLine`.
ALLOWED_TABLE_READERS: dict[str, str] = {
    "app/models/payroll_report.py":
        "defines the tables. Storing them is required: a check's deduction "
        "total will not add up without them.",
    "app/services/payroll/register_import.py":
        "writes the rows. Behind the payroll data switch and admin-only.",
}

#: May name `ChSup1` or `Garn` as string literals.
ALLOWED_CODE_NAMERS: dict[str, str] = {
    "app/services/payroll/register_parser.py":
        "names every code the register uses, including these two, so the "
        "parse can recognise them. Reads a PDF; returns no response, writes "
        "no row and reaches no surface.",
}

#: Surfaces that compose text for a person outside the payroll area. None of
#: them may reach a check line, by name or by table.
#:
#: ⚠️ Listed EXPLICITLY as well as covered by the allowlist above, because
#: these are the specific surfaces the ruling names, and a reader of this file
#: should be able to see that they were checked rather than infer it.
NEVER_REACHES = (
    "app/services/opas",
    "app/services/notes",
    "app/api/routes/opas.py",
    "app/api/routes/notes.py",
    "app/api/routes/dashboard.py",
    "app/api/routes/home.py",
)


def _modules_reaching_check_lines() -> dict[str, list[str]]:
    """Every module under `app/` that names a check line, and how.

    Walks the AST rather than grepping, so a name in a comment or docstring
    does not count and a name in code cannot be missed by a pattern.
    """
    found: dict[str, list[str]] = {}
    for path in sorted(APP.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:                                   # pragma: no cover
            continue
        hits: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in REACHES_CHECK_LINES:
                hits.append(node.id)
            elif isinstance(node, ast.Attribute) and node.attr in REACHES_CHECK_LINES:
                hits.append(node.attr)
            elif isinstance(node, ast.alias) and node.name in REACHES_CHECK_LINES:
                hits.append(node.name)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                # A table name in a raw SQL string or a `__tablename__`.
                if any(n in node.value for n in REACHES_CHECK_LINES):
                    hits.append(node.value[:60])
        if hits:
            found[str(path.relative_to(APP.parent))] = sorted(set(hits))
    return found


# ── the rule ─────────────────────────────────────────────────────────────────

def test_only_named_modules_can_reach_a_check_line():
    """A new reader of these rows fails until a person decides it belongs."""
    found = _modules_reaching_check_lines()
    unnamed = sorted(set(found) - set(ALLOWED_TABLE_READERS))
    assert not unnamed, (
        "these modules reach a payroll check line and are not named in "
        f"ALLOWED_TABLE_READERS: {unnamed}. If one of them should, add it "
        "WITH A REASON — and check it is inside the payroll area first."
    )


def test_no_surface_outside_payroll_reaches_a_check_line():
    """The surfaces the ruling names, checked by name."""
    found = _modules_reaching_check_lines()
    offenders = [m for m in found if any(m.startswith(p) for p in NEVER_REACHES)]
    assert not offenders, (
        f"a non-payroll surface reaches a check line: {offenders}. "
        "ChSup1 and Garn are line-level, payroll area only."
    )


def test_the_sensitive_codes_are_never_hard_coded_outside_the_allowlist():
    """The code strings themselves, wherever they appear in code.

    Catches the shape that the table scan would miss: a module that does not
    read `payroll_check_lines` but mentions `ChSup1` in a label, a summary
    template or an Opas prompt.
    """
    offenders: dict[str, list[str]] = {}
    for path in sorted(APP.rglob("*.py")):
        rel = str(path.relative_to(APP.parent))
        if rel in ALLOWED_CODE_NAMERS:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:                                   # pragma: no cover
            continue
        hits = sorted({
            node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and node.value in SENSITIVE_DEDUCTION_CODES
        })
        if hits:
            offenders[rel] = hits
    assert not offenders, f"sensitive codes named outside the payroll area: {offenders}"


def test_the_payroll_router_is_area_tagged():
    """⚠️ The allowlist's reasons rest on this.

    Every allowed module is allowed *because it is inside the payroll area*. If
    the payroll router lost its `area:payroll` tag, every one of those reasons
    would be false and this file would still be green.
    """
    from app.api.v1 import v1_router

    payroll_routes = [r for r in v1_router.routes
                      if getattr(r, "path", "").startswith("/payroll-reports")]
    assert payroll_routes, "no /payroll-reports routes found — the scan target moved"
    for route in payroll_routes:
        assert "area:payroll" in getattr(route, "tags", []), (
            f"{route.path} is not tagged area:payroll"
        )


# ── positive controls ────────────────────────────────────────────────────────

def test_the_scanner_can_see():
    """⚠️ Control one: an AST walk that matches nothing proves nothing.

    If the scan found no module at all, every assertion above would pass while
    the rule went unenforced. These three modules definitely reach check lines.
    """
    found = _modules_reaching_check_lines()
    for expected in ("app/models/payroll_report.py",
                     "app/services/payroll/register_import.py"):
        assert expected in found, (
            f"the scanner did not find {expected}, which certainly reaches "
            f"check lines. It found: {sorted(found)}"
        )


def test_the_allowlist_is_tight():
    """⚠️ Control two: a stale entry pre-exempts a module that stops qualifying.

    An allowlist that keeps names which no longer reach these rows is an
    allowlist that will silently permit the next thing to appear at that path.
    """
    found = _modules_reaching_check_lines()
    stale = sorted(set(ALLOWED_TABLE_READERS) - set(found))
    assert not stale, (
        f"these are allowlisted to read check lines but no longer do: {stale}. "
        "Remove them — a stale entry pre-exempts whatever lands there next."
    )


def test_the_code_namer_allowlist_is_tight():
    """The same control on the other list."""
    namers = set()
    for path in sorted(APP.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:                                   # pragma: no cover
            continue
        if any(isinstance(n, ast.Constant) and isinstance(n.value, str)
               and n.value in SENSITIVE_DEDUCTION_CODES for n in ast.walk(tree)):
            namers.add(str(path.relative_to(APP.parent)))
    stale = sorted(set(ALLOWED_CODE_NAMERS) - namers)
    assert not stale, (
        f"these are allowlisted to name the sensitive codes but no longer do: "
        f"{stale}. Remove them."
    )


@pytest.mark.parametrize("allowlist, name", [
    (ALLOWED_TABLE_READERS, "ALLOWED_TABLE_READERS"),
    (ALLOWED_CODE_NAMERS, "ALLOWED_CODE_NAMERS"),
])
def test_every_allowlist_entry_has_a_reason_and_exists(allowlist, name):
    for module, reason in allowlist.items():
        assert (APP.parent / module).exists(), f"{name}: {module} does not exist"
        assert len(reason) > 30, f"{name}: {module} needs a real reason, got {reason!r}"


def test_the_sensitive_codes_are_real_codes():
    """⚠️ A restriction on a code that does not exist restricts nothing.

    If these were misspelled the whole file would be green and the real lines
    would be unguarded. They must be codes the register actually uses.
    """
    assert SENSITIVE_DEDUCTION_CODES
    assert SENSITIVE_DEDUCTION_CODES <= KNOWN_DEDUCTION_CODES, (
        f"not real deduction codes: {SENSITIVE_DEDUCTION_CODES - KNOWN_DEDUCTION_CODES}"
    )


@pytest.mark.parametrize("code", sorted(SENSITIVE_DEDUCTION_CODES))
def test_each_sensitive_code_is_named_once_and_deliberately(code):
    assert code in ("ChSup1", "Garn"), (
        f"{code} was added to SENSITIVE_DEDUCTION_CODES without a ruling. "
        "The ruling of 2026-11-09 names child support and garnishments."
    )
