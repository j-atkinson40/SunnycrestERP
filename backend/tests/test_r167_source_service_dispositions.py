"""IOD r167 — `source_service` as the index, and the r164 correction it forced.

Static, no DB.

`source_service` is a CONVENTION (17 of 36 workflows declare it) and it names the
service the definition was meant to call. Checking those declarations against the
filesystem falsified one of r164's eight markings.

Three things are pinned:

  1. Document Review Reminder gets BOTH flags. `is_coming_soon` labels it;
     `is_active=False` is what actually stops its Monday cron.
  2. Legacy Print — Proof is UNMARKED. Its capabilities exist, so
     `is_coming_soon` ("declared, never built") was false about it.
  3. It is unmarked but NOT wired, because the two capabilities do not compose —
     and that reason is recorded, so the next reader does not re-derive it or
     assume the wiring was simply forgotten.
"""
from __future__ import annotations

import importlib.util
import pathlib
import re

import pytest

_MIGRATION = (
    pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"
    / "r167_drr_placeholder_unmark_legacy_proof.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("r167", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


r167 = _load()


class TestSourceServiceIsTheIndex:
    def test_it_is_a_convention_not_a_one_off(self):
        """The premise of this whole pass. If declarations stopped being kept,
        the shortcut stops being reliable and future passes should know."""
        from app.data.default_workflows import ALL_DEFAULT_WORKFLOWS

        declared = [w for w in ALL_DEFAULT_WORKFLOWS if w.get("source_service")]
        assert len(declared) >= 15, (
            f"only {len(declared)} workflows declare source_service — the "
            f"convention is eroding and the check is no longer a reliable index"
        )

    def test_drrs_declared_service_is_genuinely_absent(self):
        """The single check that settled DRR. If someone later ADDS
        document_review_service.py, this fails and the disposition should be
        revisited — which is the point."""
        from app.data.default_workflows import ALL_DEFAULT_WORKFLOWS

        drr = next(w for w in ALL_DEFAULT_WORKFLOWS if w["id"] == r167._DRR)
        assert drr["source_service"] == "document_review_service.py"
        path = pathlib.Path("app/services") / drr["source_service"]
        assert not path.exists(), (
            "document_review_service.py now exists — DRR may be unwired rather "
            "than unbuilt, and its is_coming_soon marking is then wrong"
        )

    def test_filename_existence_is_not_capability_existence(self):
        """The caveat that kept six of r164's eight correct. cemetery_service.py
        EXISTS and contains no plot/reservation/deed capability at all — so a
        file-exists check alone would have unmarked Plot Reservation wrongly."""
        src = pathlib.Path("app/services/cemetery_service.py")
        assert src.exists()
        assert not re.search(r"def [a-z_]*(plot|reserv|deed)[a-z_]*\(", src.read_text(), re.I)


class TestDRRGetsBothFlags:
    def test_marked_and_deactivated(self):
        """is_coming_soon governs the tenant catalog; the scheduler sweep filters
        is_active. DRR is scheduled (Monday 08:00), so marking alone would label
        it and leave it failing weekly."""
        src = _MIGRATION.read_text()
        stmt = src.split("SET is_coming_soon = true")[1].split(")")[0]
        assert "is_active = false" in stmt

    def test_the_reason_is_in_the_human_readable_field(self):
        desc = r167._DRR_NEW_DESC
        assert "NOT BUILT" in desc
        assert "document_review_service.py" in desc
        assert "does not exist" in desc

    def test_the_original_description_is_the_real_one(self):
        """Read off the definition rather than reconstructed — the first draft of
        this migration invented a plausible description and it was wrong.

        ⚠️ ASSERTION CHANGED WHEN r167's INTENT WAS PORTED INTO
        `default_workflows.py`. It originally required exact equality with the
        definition, which held until the port rewrote that description. It now
        requires CONTAINMENT, which is the durable property: the ported text
        embeds the original verbatim ("… Original: <text>"), so the pre-r167
        wording survives in both places and the downgrade still restores the real
        value rather than an invented one.

        This is a deliberate behaviour change, not a test bent to pass — the
        migration's stored original is unchanged; what moved is the definition.
        """
        from app.data.default_workflows import ALL_DEFAULT_WORKFLOWS

        drr = next(w for w in ALL_DEFAULT_WORKFLOWS if w["id"] == r167._DRR)
        assert r167._DRR_WAS_DESC in drr["description"], (
            "the ported description no longer embeds the pre-r167 original — the "
            "downgrade would restore text that appears nowhere in the definition"
        )
        assert r167._DRR_WAS_DESC in r167._DRR_NEW_DESC


class TestTheR164Correction:
    def test_legacy_proof_is_unmarked(self):
        src = _MIGRATION.read_text()
        assert "is_coming_soon = false" in src

    def test_both_of_its_capabilities_actually_exist(self):
        """The evidence for the correction. If either disappears, the workflow
        IS unbuilt again and the marking should return."""
        from app.services.generation_focus.headless_dispatch import HEADLESS_DISPATCH
        from app.services.legacy_email_service import send_proof_email

        assert "legacy_proof_generation" in HEADLESS_DISPATCH
        assert "generate_proof" in HEADLESS_DISPATCH["legacy_proof_generation"]
        assert callable(send_proof_email)

    def test_it_is_not_deactivated_only_unmarked(self):
        """"Unwired" means declared and visible. Deactivating would say
        something different and stronger than the evidence supports."""
        src = _MIGRATION.read_text()
        legacy_stmt = src.split("is_coming_soon = false")[1].split("upgrade")[0]
        assert "is_active" not in legacy_stmt.split("def ")[0]

    @pytest.mark.parametrize("fragment", [
        "persists no LegacyProof", "loads one by id", "no event system",
    ])
    def test_the_reason_it_is_not_wired_is_recorded_on_the_row(self, fragment):
        """Three independent blockers. Without them on the row, the next pass
        reads an unmarked broken workflow as an oversight and wires it — and the
        email step fails on an id the generation step never creates."""
        assert fragment in r167._LEGACY_NEW_DESC

    def test_legacy_print_final_is_untouched(self):
        """finalize_artwork has no verified capability. Claiming either way
        without checking is the error this migration corrects."""
        assert "wf_sys_legacy_print_final" not in _MIGRATION.read_text()


class TestReversibility:
    def test_downgrade_restores_both_flags_and_both_descriptions(self):
        down = _MIGRATION.read_text().split("def downgrade")[1]
        assert "is_coming_soon = true" in down and "is_coming_soon = false" in down
        assert "is_active = true" in down
        assert "Generate print proof" in down
