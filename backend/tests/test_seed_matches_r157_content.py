"""THE SEED AND THE MIGRATION SAY THE SAME THING, OR THIS FAILS.

r157 corrects the accounting Map's content on rows that ALREADY EXIST. The
seeds mint rows that do NOT exist. Both produce the same state and r157 shipped
without touching the seeds — so on a fresh database the migration ran first
against zero jobs, correctly skipped everything, and the seed then wrote the
pre-r157 text. **Every new tenant got exactly the content r157 exists to
delete**, permanently, with no error signal.

That is the same shape as the void handling `journal_entry_id` and missing
`discount_journal_entry_id`: A CORRECTION APPLIED AT ONE OF TWO SITES THAT
PRODUCE THE SAME STATE.

WHY THIS IS A TEST RATHER THAN ONE DEFINITION. The obvious fix — have r157
import the seed's text — is WRONG. A migration is history: it must keep a
frozen copy, because if it read live code then editing the seed next year would
retroactively change what a migration written today does. So the duplication is
correct and deliberate, and what it needs is a mechanism binding the copies.
This is that mechanism. The two files have no other reason to be opened
together, which is precisely why the drift went unnoticed.

NO DATABASE. Pure text comparison over both modules' constants, so it runs on
CI's fresh Postgres like any other gate entry — the whole point being that the
gate is what catches this next time.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from scripts.seed_accounting_jobs import SKELETON
from scripts.seed_suite_jobs import DESCRIPTION_REWRITES, JOBS

_R157 = (
    Path(__file__).resolve().parents[1]
    / "alembic" / "versions" / "r157_map_accounting_content.py"
)


def _load_r157():
    """Load the migration as a module. Importable despite living outside a
    package because it has no relative imports — only alembic + sqlalchemy."""
    spec = importlib.util.spec_from_file_location("r157_under_test", _R157)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def r157():
    return _load_r157()


def _seed_descriptions() -> dict[str, str]:
    """Every job description the seeds MINT, from both producing files."""
    out = {name: desc for name, desc, _refs in SKELETON}
    for entry in JOBS:
        out[entry[0]] = entry[1]
    return out


class TestEveryCorrectionReachedTheSeed:
    """The defect itself: r157 corrected three descriptions and the seeds kept
    minting the old ones."""

    def test_every_corrected_description_is_what_the_seed_writes(self, r157):
        minted = _seed_descriptions()
        for name, _expected, corrected in r157._DESCRIPTIONS:
            assert name in minted, (
                f"r157 corrects {name!r} but no seed mints it — either the job "
                f"moved producers or the migration names a job that no longer "
                f"ships."
            )
            assert minted[name] == corrected, (
                f"DRIFT on {name!r}.\n"
                f"  the seed mints: {minted[name]!r}\n"
                f"  r157 corrects to: {corrected!r}\n"
                f"A new tenant would get the seed's text and the migration "
                f"would never reach them — it only corrects rows that already "
                f"exist."
            )

    def test_no_seed_still_mints_a_superseded_description(self, r157):
        """The inverse, stated separately because it fails differently: a seed
        carrying r157's `expected` value is carrying the text r157 was written
        to REMOVE."""
        minted = _seed_descriptions()
        for name, expected, _corrected in r157._DESCRIPTIONS:
            assert minted.get(name) != expected, (
                f"{name!r} is still minted with the PRE-r157 text. This is the "
                f"exact wording the migration exists to delete."
            )


class TestTheJobR157Creates:
    """r157 doesn't only correct — it births `Cash receipts matching`, which
    had been borrowing Bank reconciliation's name."""

    def test_the_new_job_is_seeded_too(self, r157):
        new_name, new_desc, new_type = r157._NEW_JOB
        minted = _seed_descriptions()
        assert new_name in minted, (
            f"r157 creates {new_name!r} on existing databases and no seed "
            f"creates it on new ones."
        )
        assert minted[new_name] == new_desc
        assert new_type == "Accounting"

    def test_the_new_job_carries_the_refs_r157_moves_to_it(self, r157):
        """A job with the right name and no refs teaches nothing."""
        dest = {name: refs for name, _d, refs in SKELETON}[r157._NEW_JOB[0]]
        keys = {(r[0], r[1]) for r in dest}
        for _src, to_job, kind, key in r157._MOVES:
            assert to_job == r157._NEW_JOB[0]
            assert (kind, key) in keys, (
                f"r157 moves ({kind}, {key}) onto {to_job!r}; the seed does "
                f"not give it that ref, so a new tenant's card is empty where "
                f"an existing tenant's is not."
            )

    def test_the_source_job_no_longer_mints_the_moved_refs(self, r157):
        """A move is a move. Leaving them on the source makes the seed produce
        the pre-split shape with the post-split names."""
        src = {name: refs for name, _d, refs in SKELETON}["Bank reconciliation"]
        keys = {(r[0], r[1]) for r in src}
        for _from, _to, kind, key in r157._MOVES:
            assert (kind, key) not in keys


class TestTheRefR157Adds:
    def test_books_review_is_seeded_with_its_label(self, r157):
        src = {name: refs for name, _d, refs in SKELETON}["Bank reconciliation"]
        for job, kind, key, label in r157._ADDS:
            assert job == "Bank reconciliation"
            match = [r for r in src if r[0] == kind and r[1] == key]
            assert match, f"seed does not add the {key!r} ref r157 adds"
            assert len(match[0]) > 3 and match[0][3] == label, (
                f"the ref is seeded without its label {label!r} — the card "
                f"would render the raw queue id where r157 renders a name."
            )


class TestTheRewriteLadderEndsAtTheTruth:
    """`seed_suite_jobs` carries its own match-before-update ladder, which made
    THREE producers of one string. A rung whose target is a superseded value
    strands any database that reaches it: r157 has already run, alembic will
    not run it again, and nothing else would ever correct the row."""

    def test_every_rewrite_target_is_the_current_text(self):
        minted = _seed_descriptions()
        for name, _old, new in DESCRIPTION_REWRITES:
            if name not in minted:
                continue
            assert new == minted[name], (
                f"the rewrite ladder for {name!r} lands on text the seed no "
                f"longer mints. A database rewritten to it is stranded there."
            )

    def test_no_rewrite_rung_targets_a_pre_r157_value(self, r157):
        for name, _expected, corrected in r157._DESCRIPTIONS:
            for rw_name, _old, new in DESCRIPTION_REWRITES:
                if rw_name == name:
                    assert new == corrected


class TestTheOtherContentMigration:
    """r158 is the only other content migration. Confirmed rather than assumed:
    it writes CAPTIONS onto a composition row it creates when absent, and no
    seed mints captions — so it has one producer and cannot drift the way r157
    did. If a seed ever starts writing captions, this fails and says why."""

    def test_r158_captions_have_no_competing_seed_producer(self):
        import scripts.seed_accounting_jobs as a
        import scripts.seed_suite_jobs as s

        for mod in (a, s):
            src = Path(mod.__file__).read_text()
            assert "captions" not in src, (
                f"{Path(mod.__file__).name} now writes captions, which r158 "
                f"also writes — the r157 drift shape, one migration later. "
                f"Bind them the way this file binds r157."
            )
