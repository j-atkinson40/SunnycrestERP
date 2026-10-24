"""A migration may not drop or rename a column or table without a reviewed marker.

James's dispatch of 2026-10-24, item 2: "Since migrations now run while the old version
serves, add a CI check that fails on a migration that drops or renames a column or
table unless it carries an explicit, reviewed marker."

⚠️ THE HAZARD IS NEW AS OF 2026-10-23 AND WAS NOT STATED WHEN IT ARRIVED. The healthcheck
landed that day, so Railway holds traffic on the PREVIOUS deployment while the new one
migrates; 2026-10-24 moved the whole phase into `preDeployCommand`, which does the same
thing more deliberately. Either way there is now a window — measured at 396-552 seconds —
in which the OLD code runs against the NEW schema.

    expand-only   the old deploy keeps working for the whole window
    destructive   `SELECT a_column_that_is_gone` for up to nine minutes

⚠️ AND THE WINDOW IS THE LEAST OF IT. A rollback to the previous image after a
destructive migration has no schema to roll back to, because `downgrade()` is not run on
a rollback. So the marker is not paperwork: it is the record that somebody checked the
PREVIOUS release's code against the new schema before the door closed.

── WHAT THE MARKER IS ────────────────────────────────────────────────────────

A module-level assignment in the migration:

    DESTRUCTIVE_REVIEWED = (
        "2026-10-24 — `legacy_note` is read by nothing: grepped app/, scripts/ and "
        "alembic/. The previous release does not select it."
    )

⚠️ A CONSTANT, NOT A COMMENT, AND THAT IS TODAY'S LESSON APPLIED. Four times in two days
I wrote a ratchet that matched a file's own prose — including one that failed on the
comment explaining the bug it was guarding. A comment is unparseable, greppable by
accident, and satisfied by the word appearing in a docstring. `ast` reads an assignment.

⚠️ AND IT MUST SAY SOMETHING. An empty string, `None`, or `"TODO"` is refused — a marker
whose content is unchecked is a checkbox, and a checkbox is how `skipped-multi` read like
a decision for three deploys.
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

VERSIONS = pathlib.Path(__file__).resolve().parent.parent / "alembic" / "versions"

#: The marker's name. One spelling, read by `ast`.
MARKER = "DESTRUCTIVE_REVIEWED"

#: ⚠️ SCOPED TO WHAT JAMES NAMED: "drops or renames a column or table". `drop_constraint`
#: is deliberately NOT here — dropping a unique index or a check does not make the
#: previous release's SELECTs fail, which is the hazard this guards. Six shipped
#: migrations drop a constraint and none of them is a risk to a running deploy.
DESTRUCTIVE_OPS = frozenset({"drop_column", "drop_table", "rename_table"})

#: `op.alter_column(..., new_column_name=...)` is a rename and reads like a tweak.
RENAME_KWARG = "new_column_name"

#: Raw SQL, because `op.execute("ALTER TABLE … DROP COLUMN …")` bypasses every op above.
RAW_DESTRUCTIVE = re.compile(
    r"\b(?:DROP\s+COLUMN|DROP\s+TABLE|RENAME\s+TO|RENAME\s+COLUMN)\b", re.IGNORECASE,
)

#: ⚠️ SHIPPED BEFORE THE RULE AND NOT REVIEWED UNDER IT — a RATCHET, and the direction is
#: the only thing that matters. Measured 2026-10-24: 12 of 398 migrations' `upgrade()`
#: drops or renames a column or table. They are already applied everywhere, so marking
#: them now would be a false claim: nobody checked the then-previous release's code
#: against them, and this list says so rather than pretending otherwise.
#:
#: ⚠️ IT MAY ONLY SHRINK. A new migration cannot be added here — `test_the_grandfather_
#: list_only_shrinks` pins the count, and the whole point is that the next destructive
#: migration carries a marker instead.
GRANDFATHERED: frozenset[str] = frozenset({
    "b3c4d5e6f7a8_add_granular_permissions.py",
    "c3d4e5f6a7b8_add_departments.py",
    "r134_qbo_credential_purge.py",
    "r199_service_time_and_eta.py",
    "r20_documents_backbone.py",
    "r29_notification_safety_merge.py",
    "r32_production_mold_config.py",
    "r56_ancillary_and_helper_assignment.py",
    "r70_platform_action_tokens.py",
    "r90_drop_legacy_composition_columns.py",
    "r96_focus_template_inheritance.py",
    "r99_chrome_vocabulary_v2.py",
})


def _upgrade(tree: ast.Module) -> ast.FunctionDef | None:
    """⚠️ `upgrade()` ONLY. `downgrade()` drops things BY DESIGN — it is the reverse of an
    expansion — so scanning the module would flag almost every migration in the tree and
    the check would be worthless. A downgrade also does not run on a rollback, which is
    half the reason the hazard exists.
    """
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "upgrade":
            return node
    return None


def destructive_ops(source: str) -> list[str]:
    """What this migration's `upgrade()` drops or renames. Empty means expand-only."""
    tree = ast.parse(source)
    up = _upgrade(tree)
    if up is None:
        return []
    found: set[str] = set()
    # ⚠️ DOCUMENTATION IS NOT SQL, AND MY OWN CONTROL CAUGHT ME GETTING THIS WRONG — the
    # FIFTH time in two days, in the check I wrote because of the other four. A string
    # used as a STATEMENT (a docstring, or a bare string in the body) cannot reach the
    # database: nothing receives it. A string passed as an ARGUMENT can. So the test is
    # structural — the node's position, not its content — and `"""This does NOT drop
    # column legacy_note."""` stops being a finding.
    #
    # ⚠️ A FALSE POSITIVE HERE IS NOT HARMLESS. It would demand a "reviewed" marker on an
    # expand-only migration, and a marker people add for nothing is a marker nobody
    # reads — which is how `skipped-multi` read like a decision for three deploys.
    documentation = {
        node.value
        for node in ast.walk(up)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }
    for node in ast.walk(up):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name in DESTRUCTIVE_OPS:
                found.add(name)
            if name == "alter_column":
                for kw in node.keywords:
                    if kw.arg == RENAME_KWARG:
                        found.add("rename_column")
        # ⚠️ EVERY STRING INSIDE `upgrade()`, not just `op.execute`'s first argument.
        # `op.execute(sa.text(...))`, a `textwrap.dedent`, an f-string's literal parts
        # and a module-level SQL constant referenced here all reach the database, and a
        # scanner that only understood one call shape would miss the others.
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node not in documentation
            and RAW_DESTRUCTIVE.search(node.value)
        ):
            found.add("raw_sql")
    return sorted(found)


def reviewed_marker(source: str) -> str | None:
    """The marker's text, or None. Read structurally — never grepped."""
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(t, ast.Name) and t.id == MARKER for t in targets):
            continue
        value = node.value
        # A joined literal (parenthesised multi-line string) folds to one Constant.
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
        return ""  # present but not a plain string — refused below
    return None


def _migrations() -> list[pathlib.Path]:
    return sorted(p for p in VERSIONS.glob("*.py") if p.name != "__init__.py")


# ── the rule ──────────────────────────────────────────────────────────────────


def test_no_unmarked_destructive_migration():
    """The check itself. A new drop or rename must carry a reviewed marker."""
    offenders: list[str] = []
    for path in _migrations():
        if path.name in GRANDFATHERED:
            continue
        ops = destructive_ops(path.read_text())
        if not ops:
            continue
        marker = reviewed_marker(path.read_text())
        if marker is None or len(marker.strip()) < 20 or "TODO" in marker.upper():
            offenders.append(f"{path.name}: {ops} — marker={marker!r}")
    assert offenders == [], (
        "These migrations drop or rename a column or table in upgrade() with no "
        f"reviewed {MARKER} marker. Migrations now run while the PREVIOUS deploy is "
        "still serving (396-552 s measured), so a dropped column breaks production for "
        "that window and a rollback has no schema to return to.\n\nAdd, with the "
        "check you actually did:\n\n    " + MARKER + ' = (\n        "<date> — <which '
        'code reads it, and why the previous release is safe>"\n    )\n\n'
        + "\n".join(offenders)
    )


# ── the two positive controls ─────────────────────────────────────────────────


DESTRUCTIVE_SAMPLES = {
    "drop_column": 'def upgrade():\n    op.drop_column("orders", "legacy_note")\n',
    "drop_table": 'def upgrade():\n    op.drop_table("old_notes")\n',
    "rename_table": 'def upgrade():\n    op.rename_table("a", "b")\n',
    "rename_column": 'def upgrade():\n    op.alter_column("t", "a", new_column_name="b")\n',
    "raw_sql": 'def upgrade():\n    op.execute("ALTER TABLE orders DROP COLUMN legacy_note")\n',
    "raw_sql_nested": 'def upgrade():\n    op.execute(sa.text("""\n        DROP TABLE old_notes\n    """))\n',
    "raw_sql_rename": 'def upgrade():\n    conn.execute("ALTER TABLE a RENAME TO b")\n',
}


@pytest.mark.parametrize("name,source", sorted(DESTRUCTIVE_SAMPLES.items()))
def test_THE_SCANNER_CAN_SEE(name, source):
    """⚠️ CONTROL ONE. "No offenders" is satisfied by a scanner that matches nothing, and
    that is the shape CLAUDE.md §11 calls an absent signal. Each of these must be caught.
    """
    assert destructive_ops(source) != [], name


def test_the_scanner_ignores_a_downgrade_and_an_expansion():
    """The other half of control one: it must not flag what it should not."""
    assert destructive_ops(
        'def upgrade():\n    op.add_column("orders", sa.Column("x", sa.Text()))\n'
        'def downgrade():\n    op.drop_column("orders", "x")\n'
    ) == []
    # ⚠️ A CONSTRAINT IS NOT A COLUMN. Six shipped migrations drop one and none breaks a
    # running deploy's SELECTs, which is what this guard is about.
    assert destructive_ops('def upgrade():\n    op.drop_constraint("ck_x", "orders")\n') == []
    # A docstring that merely TALKS about dropping a column is prose, not SQL — and the
    # distinction is POSITIONAL. The same text passed as an argument is still caught,
    # which is the control that this exclusion did not just switch the scanner off.
    assert destructive_ops(
        'def upgrade():\n    """This does NOT drop column legacy_note."""\n    pass\n'
    ) == []
    assert destructive_ops(
        'def upgrade():\n    """Expand only."""\n    op.execute("DROP COLUMN legacy_note")\n'
    ) == ["raw_sql"]
    # A bare string statement mid-body is documentation too, and cannot reach the DB.
    assert destructive_ops(
        'def upgrade():\n    "DROP TABLE old_notes"\n    pass\n'
    ) == []


def test_the_grandfather_list_only_shrinks():
    """⚠️ CONTROL TWO: THE CEILING MUST BE TIGHT. A list longer than the real population
    has stopped ratcheting and permits a new offender to be filed under an old name.

    Measured 2026-10-24: 12 of 398 migrations. If a grandfathered migration is ever
    cleaned up, its entry must come OUT — which this makes mandatory rather than polite.
    """
    actual = {p.name for p in _migrations() if destructive_ops(p.read_text())}
    assert GRANDFATHERED <= actual, (
        "These are listed as grandfathered but are no longer destructive — remove them, "
        f"or the list is hiding a slot a new migration could take: {sorted(GRANDFATHERED - actual)}"
    )
    assert len(GRANDFATHERED) <= 12, "the list may only shrink"


def test_the_marker_is_read_structurally_and_must_say_something():
    """⚠️ A CONSTANT, NOT A COMMENT, AND NOT A CHECKBOX."""
    marked = (
        'DESTRUCTIVE_REVIEWED = (\n'
        '    "2026-10-24 — legacy_note is read by nothing; grepped app/, scripts/ and '
        'alembic/."\n)\n'
        'def upgrade():\n    op.drop_column("orders", "legacy_note")\n'
    )
    assert reviewed_marker(marked) is not None
    assert len(reviewed_marker(marked).strip()) >= 20

    # A comment is not a marker — it is unparseable and satisfied by prose.
    assert reviewed_marker('# DESTRUCTIVE_REVIEWED: yes\ndef upgrade():\n    pass\n') is None
    # Present but empty, or a placeholder, is refused by the rule above.
    assert reviewed_marker('DESTRUCTIVE_REVIEWED = ""\n') == ""
    assert reviewed_marker('DESTRUCTIVE_REVIEWED = "TODO"\n') == "TODO"
    assert reviewed_marker('DESTRUCTIVE_REVIEWED = None\n') == ""
    assert reviewed_marker('def upgrade():\n    pass\n') is None


def test_every_migration_parses():
    """The scanner's own precondition. An unparseable file would silently pass the rule
    above, since `ast.parse` raising inside the loop would abort rather than flag.
    """
    for path in _migrations():
        ast.parse(path.read_text())
