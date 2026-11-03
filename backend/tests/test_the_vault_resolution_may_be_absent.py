"""Every reader of `evaluate_typed`'s resolution must handle it being absent.

Follow-up 2 (James, 2026-11-03): *"Every path that reads a resolution after the linked-
product path must handle it being absent. Grep for the same assumption."*

⚠️ THE GREP, DONE ONCE AND THEN MADE STRUCTURAL. A grep answers today and nothing
else — the defect it found was two lines old in human terms and four months old in the
repo, and the next caller to bind that value will not re-run it. So this file is a
RATCHET rather than a one-time audit.

⚠️ THE ONE PRODUCER OF AN ABSENT RESOLUTION IS `evaluate_typed`, measured rather than
assumed. `product_name_resolver.resolve` is annotated `-> Resolution` and returns one on
every path, so every OTHER module that holds a resolution got it from there and cannot
see a `None`. The exposure is exactly "callers of `evaluate_typed` that keep the first
value", which is four call sites, of which three discard it.
"""
import ast
import pathlib

import pytest

APP = pathlib.Path(__file__).resolve().parents[1] / "app"

#: Call sites allowed to BIND `evaluate_typed`'s resolution under a real name.
#:
#: ⚠️ EACH ONE IS A PROMISE THAT THE SITE HANDLES `None`, and the list may only shrink.
#: Adding a name here is a deliberate act with a reviewer; the default — binding it to
#: `_` or `_resolution` — needs no entry because a discarded value cannot be
#: dereferenced.
ALLOWED = {
    # read_state serves `vault_resolution` and falls back to the linked path's answer.
    # This is the site that produced the 2026-11-03 500.
    ("app/services/capture/session_service.py", "resolution"),
}


def _bindings() -> list[tuple[str, str, int]]:
    """Every `… = evaluate_typed(...)` binding of the FIRST tuple element.

    ⚠️ PARSED, NOT GREPPED, AND THE DIFFERENCE IS LOAD-BEARING. A regex over
    `evaluate_typed` would match the import, the definition, the docstrings that quote
    it, and this file — and would miss a binding split across lines. `ast` sees
    assignments.
    """
    out: list[tuple[str, str, int]] = []
    for path in sorted(APP.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:  # pragma: no cover - a file that does not parse is a
            continue          # different test's problem, not this one's
        rel = str(path.relative_to(APP.parent))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            call = node.value
            if not isinstance(call, ast.Call):
                continue
            fn = call.func
            name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
            if name != "evaluate_typed":
                continue
            for target in node.targets:
                if isinstance(target, ast.Tuple) and target.elts:
                    first = target.elts[0]
                    if isinstance(first, ast.Name):
                        out.append((rel, first.id, node.lineno))
                elif isinstance(target, ast.Name):
                    out.append((rel, target.id, node.lineno))
    return out


def test_the_scanner_can_SEE_the_call_sites():
    """⚠️ POSITIVE CONTROL ONE. A scanner that matches nothing satisfies every
    "no violations" assertion trivially, and an absence looks identical whether the
    instrument works or not."""
    found = _bindings()
    assert len(found) >= 4, f"expected at least 4 evaluate_typed bindings, saw {found}"
    files = {f for f, _, _ in found}
    assert "app/services/capture/session_service.py" in files


def test_the_allowlist_is_TIGHT():
    """⚠️ POSITIVE CONTROL TWO. An allowlist larger than the real population has stopped
    ratcheting and rejects nothing. Every entry must correspond to a live binding."""
    live = {(f, n) for f, n, _ in _bindings()}
    stale = ALLOWED - live
    assert stale == set(), (
        "these allowlist entries no longer exist, so the list is looser than the code "
        f"needs: {sorted(stale)}"
    )


def test_no_UNDECLARED_site_keeps_the_resolution():
    """The claim. A new caller that keeps the value fails here until someone decides.

    ⚠️ DISCARDING IS THE DEFAULT AND NEEDS NO ENTRY. `_`, `_resolution` and any other
    underscore-prefixed name are ignored, because a value nobody reads cannot be
    dereferenced — which is what three of the four live call sites already do.
    """
    undeclared = sorted(
        (f, n, line)
        for f, n, line in _bindings()
        if not n.startswith("_") and (f, n) not in ALLOWED
    )
    assert undeclared == [], (
        "these sites bind evaluate_typed's resolution, which is None whenever the vault "
        "resolved through its tenant link. Handle the absence, or discard the value by "
        "naming it `_`:\n  "
        + "\n  ".join(f"{f}:{line} binds {n!r}" for f, n, line in undeclared)
    )


def test_the_only_producer_of_an_absent_resolution_is_evaluate_typed():
    """⚠️ THE PREMISE THE WHOLE RATCHET RESTS ON, pinned so it cannot drift silently.

    `product_name_resolver.resolve` is what every other module calls, and it is
    annotated to return a `Resolution`. If that ever becomes optional, this file's scope
    is wrong — it watches the wrong function — and this test is where that is noticed.
    """
    src = (APP / "services" / "product_name_resolver.py").read_text()
    tree = ast.parse(src)
    fn = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "resolve"
    )
    assert fn.returns is not None, "resolve() lost its return annotation"
    rendered = ast.unparse(fn.returns)
    assert rendered == "Resolution", (
        f"resolve() now returns {rendered!r}; if it can return None, the absent-"
        "resolution ratchet must widen beyond evaluate_typed"
    )


@pytest.mark.parametrize("field", ["variant_template_id", "candidates", "discriminators"])
def test_read_state_guards_every_attribute_it_reads(field):
    """⚠️ THE SITE THAT CRASHED, ASSERTED AT THE SOURCE LEVEL.

    `test_a_linked_vault_does_not_500_the_pane.py` proves the behaviour; this proves the
    GUARD is what produces it, so a future edit that happens to avoid the crash by some
    other route does not quietly remove the thing the comment says is load-bearing.
    """
    src = (APP / "services" / "capture" / "session_service.py").read_text()
    i = src.index('"vault_resolution"')
    block = src[i : i + 1200]
    assert f"resolution.{field}" in block
    assert "if resolution is not None" in block
