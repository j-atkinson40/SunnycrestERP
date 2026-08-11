"""IOD r163 — one of the eight is deleted; the other seven are declarations and stay.

Static, no DB.

The load-bearing claim is the SCOPE OF THE DELETE. Seven never-run unbuilt
workflows are deliberately left in place because they are declared roadmap — tier
1–3, visible in the builder's Vertical tab, and the definition is the only record
that the capability was intended. A later pass holding a list of "workflows with
broken steps and zero runs" would reasonably delete all eight.

The distinction is narrow enough to be worth stating mechanically: Social Service
Certificate is the only one that duplicates a WORKING capability
(`social_service_certificate_service.py` + the `ss_cert_triage` queue) rather than
declaring an absent one.

Also pinned: the code edit and the migration are ONE change. `seed_default_workflows`
never deletes, so a migration without the definition removal is undone on the next
boot.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

_MIGRATION = (
    pathlib.Path(__file__).resolve().parents[1]
    / "alembic" / "versions" / "r163_delete_ss_certificate_workflow.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("r163", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


r163 = _load()

#: The eight never-run unbuilt workflows found by the IOD derivation.
_THE_EIGHT = [
    "wf_sys_ss_certificate",
    "wf_sys_scribe_processing",
    "wf_tpl_fh_preneed_flag",
    "wf_sys_legacy_print_final",
    "wf_sys_legacy_print_proof",
    "wf_sys_plot_reservation",
    "wf_tpl_fh_send_info_form",
    "wf_sys_vault_order_fulfillment",
]


class TestScopeOfTheDelete:
    def test_exactly_one_workflow_is_deleted(self):
        assert r163._WORKFLOW_ID == "wf_sys_ss_certificate"

    @pytest.mark.parametrize("workflow_id", [w for w in _THE_EIGHT if w != "wf_sys_ss_certificate"])
    def test_the_other_seven_are_not_touched(self, workflow_id):
        """They declare capabilities that are absent and wanted. Deleting the
        declaration erases the intent — there is no other record that Legacy
        Print or Arrangement Scribe were planned."""
        src = _MIGRATION.read_text()
        deleting = [
            ln for ln in src.splitlines()
            if workflow_id in ln and ("DELETE" in ln.upper() or "_WORKFLOW_ID =" in ln)
        ]
        assert not deleting, f"{workflow_id} appears in a delete path"

    def test_the_seven_survivors_are_named_with_their_reason(self):
        """If the exclusion is not written down it reads as an oversight, and
        the next pass closes the gap."""
        doc = r163.__doc__ or ""
        assert "NOT ORPHANS" in doc and "DECLARATIONS" in doc
        assert "roadmap" in doc.lower()

    def test_the_kept_ones_are_distinguished_from_residue(self):
        """r160–r162 removed residue: rows with no definition behind them. These
        have definitions. Conflating the two categories is how the roadmap gets
        deleted as cleanup."""
        doc = r163.__doc__ or ""
        assert "default_workflows.py" in doc
        assert "r160" in doc and "r162" in doc


class TestCodeAndMigrationAreOneChange:
    def test_the_definition_is_gone_from_the_seeder(self):
        """THE HALF THAT MAKES IT STICK. `seed_default_workflows` inserts-or-
        updates and never deletes, so the migration alone would be undone by the
        next boot. Asserted against the real module rather than the docstring."""
        from app.data.default_workflows import ALL_DEFAULT_WORKFLOWS

        ids = {w["id"] for w in ALL_DEFAULT_WORKFLOWS}
        assert "wf_sys_ss_certificate" not in ids, (
            "the definition is still seeded — the deleted row returns on next boot"
        )

    def test_the_seeder_still_defines_everything_else(self):
        """Guards the edit itself: a 33-line deletion in a 1,800-line literal is
        easy to over-cut, and the failure would be silent until a tenant noticed
        a missing workflow."""
        from app.data.default_workflows import ALL_DEFAULT_WORKFLOWS

        ids = {w["id"] for w in ALL_DEFAULT_WORKFLOWS}
        assert len(ALL_DEFAULT_WORKFLOWS) == len(ids), "duplicate ids after the edit"
        for survivor in _THE_EIGHT:
            if survivor == "wf_sys_ss_certificate":
                continue
            assert survivor in ids, f"{survivor} was removed — only one deletion was ruled"
        assert "wf_sys_expense_categorization" in ids


class TestDeletionSafety:
    def test_the_blocking_tables_are_checked_at_apply_time(self):
        """Counts were true when taken; the migration runs later. All four
        NO ACTION referents are re-checked before anything is destroyed."""
        src = _MIGRATION.read_text()
        for table in ("workflow_runs", "workflow_enrollments", "workflow_schedules", "saved_orders"):
            assert table in src, f"{table} is a NO ACTION referent and is not checked"

    def test_a_late_reference_skips_rather_than_fails_or_destroys(self):
        """If someone invoked it since, that is new information about the
        disposition — not a reason to destroy history, and not a reason to abort
        an otherwise-fine upgrade."""
        src = _MIGRATION.read_text()
        assert "SKIPPED" in src and "re-triage" in src

    def test_downgrade_restores_the_workflow_and_its_steps(self):
        assert r163._WORKFLOW["name"] == "Social Service Certificate"
        assert len(r163._STEPS) == 3
        assert {s[1] for s in r163._STEPS} == {"generate_cert", "store_cert", "email_cert"}

    def test_downgrade_says_it_only_restores_half(self):
        """Restoring rows without restoring the definition recreates the exact
        orphan condition r160–r162 spent three migrations cleaning up. The
        downgrade has to say the commit revert is the other half."""
        assert "revert" in (r163.downgrade.__doc__ or "") or "revert" in _MIGRATION.read_text()
