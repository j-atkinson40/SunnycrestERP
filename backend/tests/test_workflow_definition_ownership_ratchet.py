"""RATCHET — a migration may not edit `workflow_steps.config`. The definition owns it.

⚠️ THE FAILURE THIS EXISTS TO PREVENT, WHICH ALREADY HAPPENED FOUR TIMES IN ONE DAY.

`seed_default_workflows` runs on EVERY BOOT (`app/main.py`) and, for every step
declared in `app/data/default_workflows.py`, does an unconditional
`setattr(existing_step, k, v)` over all declared columns — **including `config`**
(`app/data/seed_workflows.py`). There is no preserve rule: the file is ~109 lines,
the function takes only `db`, and there is no `preserve` / `force` /
`user_modified` branch anywhere in it.

So a migration that UPDATEs `workflow_steps.config` is writing to a row the
seeder rewrites on the next deploy. r162, r165 and r166 each did exactly that and
each was silently undone in production:

    r166 compliance scan_inspections  → producer wiring        REVERTED
    r165 MSR generate_statements      → producer wiring        REVERTED
    r162 AR approval_gate             → park_when predicate    REVERTED

The r166 revert is the sharp one: Compliance Sync went on firing live daily
against a real tenant and doing nothing, because all four steps returned
`unknown_action_type` again.

**The durable home for step config is `default_workflows.py`.** Once the
definition is right, the seeder stops being the eraser and becomes the repair
mechanism — every reverted row heals itself on the next boot with no migration at
all.

⚠️ SURVIVAL IS DECIDED BY DECLAREDNESS, NOT BY TABLE. The tempting summary —
"`workflows` rows survive, `workflow_steps` configs don't" — is wrong in both
directions:

    workflows.description     declared by 36/36  → OVERWRITTEN every boot
    workflows.is_active       declared by  0/36  → never written, survives
    workflows.is_coming_soon  declared by  3/36  → overwritten for those 3 only
    a step declared in the definition            → config overwritten
    an ORPHAN step (absent from the definition)  → untouched, survives

⚠️ AND SOME MIGRATIONS SURVIVE ONLY BY COINCIDENCE. r160's `categorize` and
r161's `ar_snapshot` / `fetch_catalog` are inert today ONLY because their
step_keys are absent from `default_workflows.py`. **Adding any of those keys back
to the definition would silently revert those migrations too.** They are not
protected; they are merely unreached.
"""
from __future__ import annotations

import pathlib
import re

import pytest

_VERSIONS = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"

#: Migrations that predate this ratchet and DID write step config. Grandfathered
#: because they are already applied; their intent has been ported into
#: `default_workflows.py`, which is what actually holds. NOTHING MAY BE ADDED
#: HERE — a new entry means someone reached for a migration again.
_GRANDFATHERED = {
    "r160_neutralise_orphan_categorize_step.py",
    "r161_neutralise_orphan_producer_twins.py",
    "r162_finish_the_migrated_four.py",
    "r165_wire_monthly_statement_run.py",
    "r166_wire_compliance_sync_retire_training_expiry.py",
}

#: An UPDATE that sets `config` on workflow_steps. Deliberately narrow: deleting
#: a step row is legitimate (r162/r163 did, and the seeder does not resurrect
#: undeclared keys), and reading config is fine.
#:
#: ⚠️ MATCHED AGAINST NORMALISED TEXT, NOT RAW SOURCE. Migrations build SQL from
#: ADJACENT PYTHON STRING LITERALS — `"UPDATE workflow_steps "` on one line and
#: `"SET config = ..."` on the next — so the quote and newline between them
#: defeat a naive `\s+`. The first draft of this ratchet missed r160 for exactly
#: that reason and would have missed any future migration written in the same
#: (normal) style. `_normalise` strips quote characters and collapses runs of
#: whitespace so the SQL reads as one line regardless of how it was assembled.
_WRITES_STEP_CONFIG = re.compile(
    r"UPDATE\s+workflow_steps\s+SET\b[^;]{0,400}?\bconfig\b", re.IGNORECASE
)


def _strip_prose(text: str) -> str:
    """Remove docstrings and `#` comments BEFORE matching.

    ⚠️ WITHOUT THIS THE RATCHET FALSE-POSITIVES ON ITS OWN SUBJECT MATTER. Every
    migration in this line documents what it does to step config, so a future
    one whose docstring says "this deliberately does NOT update
    workflow_steps.config" would be flagged as an offender by the guard
    describing it — blocking exactly the careful author it exists to help.

    Verified in the other direction too: all five known offenders still match
    after stripping, so the detector fires on CODE and never depended on prose.
    That check matters because a ratchet satisfied by its own docstring is a
    ratchet that cannot fail — the same class the detector self-test caught from
    a different angle.

    Docstrings first (they can contain `#`), then comments.
    """
    without_docstrings = re.sub(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'', " ", text)
    return "\n".join(line.split("#")[0] for line in without_docstrings.splitlines())


def _normalise(text: str) -> str:
    """Source → the SQL as the database would see it, near enough to match.

    Prose is stripped first; the quote-and-whitespace collapse then joins SQL
    that migrations assemble from adjacent string literals.
    """
    stripped = _strip_prose(text)
    return re.sub(r"\s+", " ", re.sub(r"[\"']", " ", stripped))


def _migration_files():
    return sorted(p for p in _VERSIONS.glob("*.py") if p.name != "__init__.py")


class TestNoNewMigrationWritesStepConfig:
    def test_the_ratchet(self):
        """A migration that edits step config loses to the next boot.

        If this fails on a migration you just wrote: put the change in
        `app/data/default_workflows.py` instead. The seeder will apply it to
        every existing row on the next deploy — which is precisely the mechanism
        that would otherwise have erased your migration.
        """
        offenders = [
            p.name for p in _migration_files()
            if p.name not in _GRANDFATHERED
            and _WRITES_STEP_CONFIG.search(_normalise(p.read_text()))
        ]
        assert not offenders, (
            f"{offenders} UPDATE workflow_steps.config. That row is owned by "
            f"app/data/default_workflows.py and seed_default_workflows rewrites "
            f"it on every boot, so the migration will be silently reverted on "
            f"the next deploy — this happened to r162, r165 and r166 in one day. "
            f"Make the change in default_workflows.py instead."
        )

    def test_the_grandfathered_set_only_shrinks(self):
        """A ratchet that can be widened is a convention, and conventions are
        what failed here. Adding an entry means someone reached for a migration
        again rather than the definition."""
        assert len(_GRANDFATHERED) == 5

    def test_the_detector_actually_fires_on_every_known_offender(self):
        """A GUARD THAT NEVER MATCHES IS INDISTINGUISHABLE FROM A CLEAN REPO.

        The five grandfathered migrations are known-positive samples: each really
        does UPDATE workflow_steps.config. If the detector stops matching them it
        has rotted, and the ratchet above would keep passing while catching
        nothing. The first draft matched only 4 of 5 — r160 assembles its SQL
        from adjacent string literals — which is why this exists.
        """
        missed = [
            n for n in sorted(_GRANDFATHERED)
            if not _WRITES_STEP_CONFIG.search(_normalise((_VERSIONS / n).read_text()))
        ]
        assert not missed, (
            f"the detector no longer matches {missed}, which are known to write "
            f"step config — the ratchet is now vacuous"
        )

    def test_prose_alone_does_not_trip_the_ratchet(self):
        """⚠️ THE FALSE-POSITIVE DIRECTION, and it was real before this test.

        Every migration in this line DOCUMENTS what it does to step config, so
        the guard was matching its own subject matter: a migration whose
        docstring said "this deliberately does NOT update workflow_steps SET
        config" was flagged as an offender. The ratchet would have blocked
        precisely the careful author it exists to help, and the failure message
        would have pointed them at a file they had already read.

        A guard that fires on descriptions of the thing, rather than the thing,
        is the mirror of a guard satisfied by its own docstring.
        """
        prose_only = (
            '"""A migration that deliberately does NOT touch step config.\n'
            "This is NOT an UPDATE workflow_steps SET config statement.\n"
            '"""\n'
            "# also not: UPDATE workflow_steps SET config = ...\n"
            "def upgrade():\n    pass\n"
        )
        assert not _WRITES_STEP_CONFIG.search(_normalise(prose_only)), (
            "the ratchet fires on a migration that merely MENTIONS step config "
            "in prose — it would block an author documenting that they avoided it"
        )

    def test_stripping_prose_did_not_blind_the_detector(self):
        """The other direction, kept adjacent so the two are read together: all
        five known offenders must still match AFTER prose is stripped, proving
        the detector reads code and never leaned on documentation."""
        missed = [
            n for n in sorted(_GRANDFATHERED)
            if not _WRITES_STEP_CONFIG.search(_normalise((_VERSIONS / n).read_text()))
        ]
        assert not missed, f"stripping prose blinded the detector on {missed}"

    @pytest.mark.parametrize("name", [
        "r163_delete_ss_certificate_workflow.py",   # deletes steps, legitimate
        "r164_mark_declared_but_unbuilt.py",        # UPDATEs workflows, not steps
        "r167_drr_placeholder_unmark_legacy_proof.py",
    ])
    def test_the_detector_does_not_fire_on_legitimate_migrations(self, name):
        """Known-negatives. Deleting an undeclared step row is fine (the seeder
        does not resurrect it) and workflow-level flags are fine (`is_active` is
        declared by no definition). A ratchet that forbids those would push the
        next person back toward the thing it exists to prevent."""
        assert not _WRITES_STEP_CONFIG.search(_normalise((_VERSIONS / name).read_text()))

    def test_every_grandfathered_migration_still_exists(self):
        """If one is deleted, remove it from the set in the same commit — a
        stale exemption silently un-ratchets whatever name gets reused."""
        names = {p.name for p in _migration_files()}
        assert _GRANDFATHERED <= names, f"stale exemptions: {_GRANDFATHERED - names}"


class TestTheSeederStillBehavesAsDocumented:
    """The ratchet's premise. If the seeder ever gains a preserve rule, this
    ratchet becomes unnecessary and should be reconsidered rather than left to
    forbid something that is no longer dangerous."""

    def test_the_seeder_has_no_preserve_rule(self):
        seeder = (
            pathlib.Path(__file__).resolve().parents[1]
            / "app" / "data" / "seed_workflows.py"
        ).read_text()
        assert "setattr(existing_step" in seeder, (
            "the step-update path changed shape — re-derive whether migrations "
            "editing step config are still reverted"
        )
        body = seeder.split("def seed_default_workflows")[1]
        assert not re.search(r"\bpreserve\b|\buser_modified\b", body), (
            "the seeder appears to have gained a preserve rule; if step config "
            "is now preserved, this ratchet may no longer be needed"
        )

    def test_is_active_is_declared_by_no_definition(self):
        """Why r164/r166/r167's flag changes survive while their description
        changes did not. If a definition ever declares `is_active`, those
        deactivations start reverting on boot."""
        from app.data.default_workflows import ALL_DEFAULT_WORKFLOWS

        declaring = [w["id"] for w in ALL_DEFAULT_WORKFLOWS if "is_active" in w]
        assert not declaring, (
            f"{declaring} now declare is_active — r164/r166/r167 deactivated "
            f"workflows via migration on the assumption the seeder never writes "
            f"it, and those would now be reverted on every boot"
        )


class TestCoincidentalSurvivorsAreNotProtected:
    """r160 and r161 survive because their targets are ORPHANS. Declaring any of
    these keys would revert those migrations without a word."""

    @pytest.mark.parametrize("workflow_id,step_key,migration", [
        ("wf_sys_expense_categorization", "categorize", "r160"),
        ("wf_sys_ar_collections", "ar_snapshot", "r161"),
        ("wf_sys_catalog_fetch", "fetch_catalog", "r161"),
        ("wf_sys_ar_collections", "tier_classification", "r162"),
        ("wf_sys_catalog_fetch", "notify_if_updated", "r162"),
    ])
    def test_orphan_steps_stay_undeclared(self, workflow_id, step_key, migration):
        from app.data.default_workflows import ALL_DEFAULT_WORKFLOWS

        wf = next(
            (w for w in ALL_DEFAULT_WORKFLOWS if w["id"] == workflow_id), None
        )
        if wf is None:
            pytest.skip(f"{workflow_id} is not a seeded definition")
        declared = {s["step_key"] for s in wf.get("steps", [])}
        assert step_key not in declared, (
            f"{workflow_id}.{step_key} is now declared in default_workflows.py, "
            f"so the seeder will overwrite it and silently revert {migration}, "
            f"which neutralised it. If the step is genuinely wanted, port "
            f"{migration}'s config into the definition rather than adding the "
            f"old shape back."
        )
