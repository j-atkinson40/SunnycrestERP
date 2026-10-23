"""The door's prompt seed must be able to ship a THIRD version. Local database.

⚠️ WHY THIS EXISTS, AND IT COST A LIVE REGRESSION. `seed_opas_order_list_prompt`
carried the platform's "Option A idempotent seed" state machine, whose last rule was:

    several versions (admin edits)    → SKIP with a warning, touch nothing

The seed creates versions itself. So from its own second update onward, "an admin
edited this" and "I have run twice" are the SAME OBSERVATION, and a count cannot tell
them apart. Measured on production 2026-10-23:

    the deploy of 0289edf6   upgraded the prompt v1 -> v2
    the deploy of f5474e4b   found two versions, logged "an admin has edited it.
                             Skipping.", and changed nothing

v3 is the version that stops the model computing dates. The validator that voids a
model-supplied date shipped in the same commit, so with v2 still active the model kept
returning `service_from` and the engine kept refusing it: **twenty runs of "anything
for hopkins next week" on production, twenty refusals.**

⚠️ IT WAS A ONE-SHOT SEED THAT REPORTED ITSELF AS IDEMPOTENT. `skipped-multi` reads
like a deliberate outcome. Every deploy after the first upgrade logged it and did
nothing, and nothing about that line says "this prompt can never be updated again".

⚠️ AND THE TEST THAT WOULD HAVE CAUGHT IT IS THE THIRD RUN, NOT THE SECOND. A seed
tested once from empty passes. Tested twice, it passes — the v1 -> v2 upgrade is the
path that works. Only the THIRD invocation with changed content reaches the frozen
branch. That is what `test_a_third_version_can_ship` is for, and why it is written as
three explicit rounds rather than a loop.
"""
from __future__ import annotations

import os

import pytest

if not os.environ.get("DATABASE_URL") or not os.environ.get("SECRET_KEY"):
    pytest.skip("DATABASE_URL is not set", allow_module_level=True)

from app.database import SessionLocal
from app.models.intelligence import IntelligencePrompt, IntelligencePromptVersion
from scripts import seed_opas_order_list_prompt as seed_mod

KEY = seed_mod.PROMPT_KEY


@pytest.fixture()
def db():
    session = SessionLocal()
    # ⚠️ A FUNCTION-SCOPED CLEAN SLATE, because this test asserts on version COUNTS and
    # the local database already holds whatever earlier runs left. Rolled back at the
    # end, so nothing persists either way.
    try:
        prompt = (
            session.query(IntelligencePrompt)
            .filter(IntelligencePrompt.company_id.is_(None),
                    IntelligencePrompt.prompt_key == KEY)
            .first()
        )
        if prompt is not None:
            session.query(IntelligencePromptVersion).filter(
                IntelligencePromptVersion.prompt_id == prompt.id).delete()
            session.delete(prompt)
            session.flush()
        yield session
    finally:
        session.rollback()
        session.close()


def _rows(db):
    """⚠️ SCOPED TO THIS PROMPT. My first version used a bare
    `db.query(IntelligencePromptVersion).one()`, which asks the whole table — and the
    local database holds 50+ prompts. `MultipleResultsFound`, immediately. A test that
    reaches past its own subject is not testing its subject.
    """
    prompt = (
        db.query(IntelligencePrompt)
        .filter(IntelligencePrompt.company_id.is_(None),
                IntelligencePrompt.prompt_key == KEY)
        .one()
    )
    return (
        db.query(IntelligencePromptVersion)
        .filter(IntelligencePromptVersion.prompt_id == prompt.id)
        .order_by(IntelligencePromptVersion.version_number)
        .all()
    )


def _versions(db):
    prompt = (
        db.query(IntelligencePrompt)
        .filter(IntelligencePrompt.company_id.is_(None),
                IntelligencePrompt.prompt_key == KEY)
        .one()
    )
    rows = (
        db.query(IntelligencePromptVersion)
        .filter(IntelligencePromptVersion.prompt_id == prompt.id)
        .order_by(IntelligencePromptVersion.version_number)
        .all()
    )
    return [(v.version_number, v.status) for v in rows]


def test_a_third_version_can_ship(db, monkeypatch):
    """Three rounds, each with different content. The third is the one that froze."""
    assert seed_mod.seed(db) == "created"
    db.flush()
    assert _versions(db) == [(1, "active")]

    # Round 2: the content changes, as it did when `going_out` was redefined.
    monkeypatch.setattr(seed_mod, "SYSTEM_PROMPT", seed_mod.SYSTEM_PROMPT + "\n# v2")
    assert seed_mod.seed(db) == "upgraded"
    db.flush()
    assert _versions(db) == [(1, "retired"), (2, "active")]

    # ⚠️ ROUND 3 IS THE WHOLE TEST. Before the fix this returned "skipped-multi" and
    # left v2 live, which is exactly what production did.
    monkeypatch.setattr(seed_mod, "SYSTEM_PROMPT", seed_mod.SYSTEM_PROMPT + "\n# v3")
    assert seed_mod.seed(db) == "upgraded"
    db.flush()
    assert _versions(db) == [(1, "retired"), (2, "retired"), (3, "active")]

    # And a fourth, so "three" is not itself a new ceiling.
    monkeypatch.setattr(seed_mod, "SYSTEM_PROMPT", seed_mod.SYSTEM_PROMPT + "\n# v4")
    assert seed_mod.seed(db) == "upgraded"
    db.flush()
    assert _versions(db) == [(1, "retired"), (2, "retired"), (3, "retired"), (4, "active")]


def test_an_unchanged_prompt_is_a_noop_at_every_depth(db, monkeypatch):
    """The control. If every run upgraded, each deploy would add a version forever."""
    assert seed_mod.seed(db) == "created"
    db.flush()
    assert seed_mod.seed(db) == "noop"
    db.flush()
    assert _versions(db) == [(1, "active")]

    monkeypatch.setattr(seed_mod, "SYSTEM_PROMPT", seed_mod.SYSTEM_PROMPT + "\n# v2")
    assert seed_mod.seed(db) == "upgraded"
    db.flush()
    # Three more runs at the same content must all be no-ops, not v3, v4, v5.
    for _ in range(3):
        assert seed_mod.seed(db) == "noop"
        db.flush()
    assert _versions(db) == [(1, "retired"), (2, "active")]


def test_the_superseded_version_is_retained_not_deleted(db, monkeypatch):
    """⚠️ THE OLD GUARD'S PREMISE, CHECKED RATHER THAN ASSUMED. It said a seed that
    updated a prompt "would silently throw away a person's work". Nothing is thrown
    away — the row survives as `retired`, readable and reactivatable. What a new version
    does take is which one is LIVE, which is why that is logged by version number.
    """
    assert seed_mod.seed(db) == "created"
    db.flush()
    first_text = _rows(db)[0].system_prompt

    monkeypatch.setattr(seed_mod, "SYSTEM_PROMPT", "a completely different prompt body")
    assert seed_mod.seed(db) == "upgraded"
    db.flush()

    rows = _rows(db)
    assert len(rows) == 2
    assert rows[0].status == "retired"
    assert rows[0].system_prompt == first_text, "the superseded body must survive intact"
    assert rows[1].status == "active"
    assert rows[1].system_prompt == "a completely different prompt body"


def test_a_prompt_whose_newest_version_matches_but_is_not_live_is_reactivated(db):
    """A hand-retired-everything state resolves to live rather than staying dark."""
    assert seed_mod.seed(db) == "created"
    db.flush()
    _rows(db)[0].status = "retired"
    db.flush()
    assert seed_mod.seed(db) == "reactivated"
    db.flush()
    assert _versions(db) == [(1, "active")]


def test_the_count_based_guard_cannot_come_back():
    """⚠️ A RATCHET ON THE CODE, READ WITH `ast` RATHER THAN GREPPED, AND MY FIRST
    VERSION WAS GREPPED AND WRONG.

    It asserted the string "an admin has edited it" was absent from the file. The file
    now QUOTES that old log line inside the comment explaining the bug — so the ratchet
    failed on its own documentation. CLAUDE.md §11 names this exactly: a file that
    records a correction by quoting what was wrong returns hits for the superseded
    string permanently, and the count cannot reach zero.

    So the check is structural: no `return` in this module may yield the dead sentinel,
    and no branch may compare a version COUNT against a literal. Prose is free to
    discuss both.
    """
    import ast
    import pathlib

    tree = ast.parse(pathlib.Path(seed_mod.__file__).read_text())

    returns = [
        node.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Return)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ]
    assert "skipped-multi" not in returns
    # ⚠️ THE POSITIVE CONTROL. An empty `returns` would satisfy the line above for free,
    # which is the shape of a scanner that cannot see. These are the live outcomes.
    assert set(returns) >= {"created", "noop", "upgraded", "reactivated"}, returns

    compares = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Compare)
        and isinstance(node.left, ast.Call)
        and isinstance(node.left.func, ast.Name)
        and node.left.func.id == "len"
    ]
    assert compares == [], "a version COUNT is not evidence of who authored a version"
