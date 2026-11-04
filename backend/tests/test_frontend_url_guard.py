"""One rule for outward links: nobody reads FRONTEND_URL raw except four OAuth sites.

James's ruling of 2026-11-04, after an invite email went to a real address with
`localhost:5173` in the link: *"calendar: route through the helper too; its own
app.getbridgeable.com fallback goes. One rule."*

`app/core/links.py::tenant_link_base` is that one rule. This guard is what keeps
a new email link from quietly reintroducing the twelfth version of it.

⚠️ **IT PARSES CODE, IT DOES NOT GREP TEXT, AND THAT IS NOT A STYLE
PREFERENCE.** The first draft of this guard was a grep, and it reported a false
positive on its OWN explanatory comment — the string `settings.FRONTEND_URL`
inside a sentence about not writing `settings.FRONTEND_URL`. A text scan cannot
tell a read from a mention, so it fires on documentation, on this docstring, and
on the allowlist below, and the natural fix for that noise is to loosen the
pattern until it stops seeing things. An AST walk sees reads only.

⚠️ **AND THE ALLOWLIST IS KEYED BY FUNCTION NAME, NOT BY A MARKER COMMENT.**
A comment-keyed exemption (`# allow-raw-frontend-url`) is self-granting: any
future site exempts itself by describing itself, which is exactly the move this
guard exists to catch. Adding a site here is an edit to this file, in a diff,
with a reviewer.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

APP = pathlib.Path(__file__).resolve().parent.parent / "app"

#: Every site permitted to read FRONTEND_URL raw, as (module path, function).
#:
#: The four OAuth sites are here because a `redirect_uri` is NOT a link sent to
#: a person — it is a string the provider matches character-for-character
#: against its registered-app config, so a per-tenant host would be rejected for
#: every tenant not separately registered. `tenant_link_base` itself is here
#: because it is the one rule; reading the setting is its job.
ALLOWED: frozenset[tuple[str, str]] = frozenset({
    ("app/core/links.py", "tenant_link_base"),
    ("app/api/routes/ringcentral.py", "oauth_callback"),
    ("app/api/routes/legacy_delivery.py", "dropbox_callback"),
    ("app/api/routes/legacy_delivery.py", "gdrive_callback"),
})


def _enclosing_function(tree: ast.AST, lineno: int) -> str:
    """Name of the innermost function containing `lineno`, or '<module>'."""
    best: tuple[int, str] | None = None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        start = node.lineno
        end = max(getattr(d, "lineno", start) for d in ast.walk(node))
        if start <= lineno <= end:
            span = end - start
            if best is None or span < best[0]:
                best = (span, node.name)
    return best[1] if best else "<module>"


def _reads_in(path: pathlib.Path) -> list[tuple[str, int, str]]:
    """Every raw FRONTEND_URL read in one file, as (relpath, lineno, function)."""
    source = path.read_text()
    # ⚠️ A SyntaxError must FAIL, not be skipped. A file this guard cannot parse
    # is a file whose reads it cannot see, which is indistinguishable from a
    # file that has none.
    tree = ast.parse(source, filename=str(path))
    rel = str(path.relative_to(APP.parent))
    found = []
    for node in ast.walk(tree):
        hit = (
            # settings.FRONTEND_URL, app_settings.FRONTEND_URL, _settings.FRONTEND_URL
            (isinstance(node, ast.Attribute) and node.attr == "FRONTEND_URL")
            # getattr(settings, "FRONTEND_URL", "http://localhost:5173")
            or (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "FRONTEND_URL"
            )
        )
        if hit:
            found.append((rel, node.lineno, _enclosing_function(tree, node.lineno)))
    return found


def _all_reads() -> list[tuple[str, int, str]]:
    return sorted(r for p in APP.rglob("*.py") for r in _reads_in(p))


def test_no_new_raw_frontend_url_reads():
    """Any read outside the four OAuth sites and the helper itself is a defect."""
    offenders = [r for r in _all_reads() if (r[0], r[2]) not in ALLOWED]
    assert not offenders, (
        "These sites read FRONTEND_URL raw instead of going through "
        "app.core.links.tenant_link_base:\n"
        + "\n".join(f"  {f}:{line} in {func}()" for f, line, func in offenders)
        + "\n\nAn outward link built from FRONTEND_URL points at localhost on "
          "production, where the variable is deliberately unset. If this site "
          "genuinely is not a link sent to a person, add it to ALLOWED with the "
          "reason."
    )


# ───────────────────────────────── positive controls
#
# ⚠️ THE ASSERTION ABOVE IS AN ABSENCE, AND AN ABSENCE READS THE SAME WHETHER THE
# SCANNER WORKS OR NOT. A walk that matched nothing at all — wrong directory,
# wrong attribute name, a parse that silently failed — would satisfy it
# trivially. These two prove the instrument can see, and that the ceiling is
# tight rather than merely above the real count.


def test_the_scanner_can_see():
    """It finds every allowlisted site. A scanner finding none proves nothing."""
    located = {(f, func) for f, _, func in _all_reads()}
    missing = ALLOWED - located
    assert not missing, (
        f"The scanner did not find {sorted(missing)}. Either those sites were "
        "converted to the helper (remove them from ALLOWED) or this guard has "
        "stopped seeing reads at all."
    )


def test_the_allowlist_is_tight():
    """Exactly five reads exist. An allowlist with room in it rejects nothing."""
    reads = _all_reads()
    assert len(reads) == 5, (
        f"Expected 5 raw reads (2 in ringcentral's oauth_callback, 1 each in "
        f"dropbox_callback and gdrive_callback, 1 in tenant_link_base); found "
        f"{len(reads)}:\n" + "\n".join(f"  {f}:{n} in {fn}()" for f, n, fn in reads)
    )


def test_a_mention_in_prose_is_not_a_read():
    """The failure that made this an AST walk: a comment is not a read.

    ⚠️ This is not a hypothetical. The grep version of this guard fired on its
    own docstring. Both strings below would match any text scan; neither is a
    read of the setting.
    """
    source = '''
# Never write settings.FRONTEND_URL in an email link.
"""Use tenant_link_base, not getattr(settings, "FRONTEND_URL", ...)."""
NOT_A_READ = "FRONTEND_URL"
'''
    tmp = pathlib.Path(__file__).parent / "_frontend_url_prose_fixture.py"
    tmp.write_text(source)
    try:
        assert _reads_in(tmp) == []
    finally:
        tmp.unlink()


def test_a_real_read_in_a_fixture_is_caught():
    """The control for the control: a genuine read in the same place IS found."""
    source = 'from app.config import settings\n\ndef send():\n    return settings.FRONTEND_URL\n'
    tmp = pathlib.Path(__file__).parent / "_frontend_url_read_fixture.py"
    tmp.write_text(source)
    try:
        found = _reads_in(tmp)
        assert len(found) == 1, found
        assert found[0][2] == "send"
    finally:
        tmp.unlink()


def test_an_unparseable_file_fails_rather_than_being_skipped():
    """A file this guard cannot read is not a file with no reads."""
    tmp = pathlib.Path(__file__).parent / "_frontend_url_broken_fixture.py"
    tmp.write_text("def broken(:\n    pass\n")
    try:
        with pytest.raises(SyntaxError):
            _reads_in(tmp)
    finally:
        tmp.unlink()
