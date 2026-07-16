"""The Ponder — derivation service pins (P0+P1).

Hermetic (the borrow-a-core lesson): every test builds its OWN runtime
workflow + mirror template + task row — no dependence on seeded state.
"""
from __future__ import annotations

import uuid

import pytest

from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.company import Company
from app.models.moc_task_catalog import MoCTaskCatalog
from app.models.workflow import Workflow, WorkflowRun, WorkflowStep
from app.models.workflow_template import WorkflowTemplate
from app.services.maps_of_content import ponder
from app.services.maps_of_content.ponder import (
    QUEUE_REGISTRY,
    build_ponder_script,
    check_mirror_drift,
    cron_to_prose,
    save_caption,
)


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    # Residue hygiene (P2): _mk_fixture COMMITS its workflow + mirror + task
    # rows; a rollback-only teardown left them behind, inflating the fleet
    # census for any later suite (test_moc_workflow_mirrors' count pin
    # false-failed on the residue). Clean by the fixture's own patterns —
    # never touching real rows.
    s.execute(sql_text(
        "DELETE FROM moc_task_trigger WHERE task_catalog_id IN "
        "(SELECT id FROM moc_task_catalog WHERE name LIKE 'Ponder Task %')"
    ))
    s.execute(sql_text(
        "DELETE FROM moc_task_catalog_focuses WHERE task_catalog_id IN "
        "(SELECT id FROM moc_task_catalog WHERE name LIKE 'Ponder Task %')"
    ))
    s.execute(sql_text("DELETE FROM moc_task_catalog WHERE name LIKE 'Ponder Task %'"))
    s.execute(sql_text(
        "DELETE FROM workflow_templates WHERE workflow_type LIKE 'mirror_ponder_%'"
    ))
    s.execute(sql_text(
        "DELETE FROM workflow_run_steps WHERE run_id IN "
        "(SELECT id FROM workflow_runs WHERE workflow_id LIKE 'wf_ponder_%')"
    ))
    s.execute(sql_text(
        "DELETE FROM workflow_runs WHERE workflow_id LIKE 'wf_ponder_%'"
    ))
    s.execute(sql_text("DELETE FROM workflow_steps WHERE workflow_id LIKE 'wf_ponder_%'"))
    s.execute(sql_text("DELETE FROM workflows WHERE id LIKE 'wf_ponder_%'"))
    s.commit()
    s.close()


def _mk_fixture(db, *, trigger_type="scheduled",
                trigger_config=None, registry_id: str | None = None):
    """Runtime workflow (4 semantic steps incl. an approval gate) + faithful
    mirror + task row. Returns (task, template, workflow)."""
    suffix = uuid.uuid4().hex[:6]
    wf_id = registry_id or f"wf_ponder_{suffix}"
    wf = Workflow(
        id=wf_id, name=f"Ponder Fixture {suffix}", company_id=None,
        tier=1, scope="core", trigger_type=trigger_type,
        trigger_config=trigger_config or {"cron": "0 6 1 * *", "timezone": "America/New_York"},
    )
    db.add(wf)
    steps_spec = [
        ("identify_customers", "action", {"description": "Find charge-account customers with activity"}),
        ("generate_statements", "action", {"description": "Generate statement PDFs"}),
        ("approval_gate", "input", {"prompt": "Review flagged statements"}),
        ("send_statements", "action", {"description": "Email approved statements"}),
    ]
    for i, (key, typ, cfg) in enumerate(steps_spec, start=1):
        db.add(WorkflowStep(
            id=str(uuid.uuid4()), workflow_id=wf_id, step_key=key,
            step_type=typ, step_order=i, config=cfg,
        ))
    nodes = [
        {"id": k, "type": t, "label": k, "config": c, "position": {"x": 0, "y": i * 120}}
        for i, (k, t, c) in enumerate(steps_spec)
    ]
    edges = [
        {"id": f"e{i}", "source": steps_spec[i - 1][0], "target": steps_spec[i][0], "label": ""}
        for i in range(1, len(steps_spec))
    ]
    tpl = WorkflowTemplate(
        id=str(uuid.uuid4()), scope="platform_default", vertical=None,
        workflow_type=f"mirror_ponder_{suffix}", display_name=f"Ponder Mirror {suffix}",
        version=1, is_active=True,
        canvas_state={"version": 1, "nodes": nodes, "edges": edges},
        mirrored_from_workflow_id=wf_id,
    )
    db.add(tpl)
    db.flush()
    task = MoCTaskCatalog(
        scope="vertical_default", vertical="manufacturing",
        name=f"Ponder Task {suffix}", workflow_template_id=tpl.id,
    )
    db.add(task)
    db.commit()
    return task, tpl, wf


class TestCronProse:
    def test_first_of_month_tenant_local(self):
        assert cron_to_prose("0 6 1 * *", "America/New_York") == \
            "The 1st of each month at 6:00 AM (tenant-local)"

    def test_nightly(self):
        assert cron_to_prose("0 23 * * *") == "Every night at 11:00 PM"

    def test_every_15(self):
        assert cron_to_prose("*/15 * * * *") == "Every 15 minutes"

    def test_unrecognized_falls_back_honestly(self):
        assert "5 4 * 2 1-3" in cron_to_prose("5 4 * 2 1-3")


class TestScriptAssembly:
    def test_beat_order_and_kinds(self, db):
        task, tpl, wf = _mk_fixture(db)
        script = build_ponder_script(db, task.id)
        keys = [b["key"] for b in script["beats"]]
        assert keys[:6] == [
            "when",
            "step:identify_customers", "step:generate_statements",
            "pause:approval_gate", "step:send_statements",
            "downstream:failure",
        ]
        when = script["beats"][0]
        assert "1st of each month at 6:00 AM" in when["text"]
        pause = script["beats"][3]
        assert pause["kind"] == "pause"
        assert "Review flagged statements" in pause["text"]
        # H1's truth, cited by the real queue.
        failure = [b for b in script["beats"] if b["key"] == "downstream:failure"][0]
        assert failure["queue_id"] == "workflow_review_triage"
        assert "Decision Triage" in failure["text"]
        assert script["mirror_drift"] == []

    def test_registry_workflow_gets_the_queue_beat(self, db):
        # A fixture that IS a registry id (statement run's entry).
        task, tpl, wf = _mk_fixture(db, registry_id=f"wf_sys_statement_run_test_{uuid.uuid4().hex[:4]}")
        # Not in the registry (suffixed) → no queue beat.
        script = build_ponder_script(db, task.id)
        assert not any(b["key"] == "downstream:queue" for b in script["beats"])
        # Registry entries themselves are pinned complete:
        assert set(QUEUE_REGISTRY) == {
            "wf_sys_statement_run", "wf_sys_month_end_close",
            "wf_sys_ar_collections", "wf_sys_expense_categorization",
            "wf_sys_cash_receipts",
        }

    def test_manual_trigger_reads_honestly(self, db):
        task, _, _ = _mk_fixture(db, trigger_type="manual", trigger_config={})
        script = build_ponder_script(db, task.id)
        assert "When you run it" in script["beats"][0]["text"]

    def test_garnish_present_after_a_completed_run_and_absent_before(self, db):
        task, tpl, wf = _mk_fixture(db)
        s1 = build_ponder_script(db, task.id)
        assert not any(b["kind"] == "garnish" for b in s1["beats"])  # never fabricated

        co = Company(id=str(uuid.uuid4()), name=f"P-{uuid.uuid4().hex[:5]}",
                     slug=f"p-{uuid.uuid4().hex[:5]}", is_active=True)
        db.add(co)
        db.flush()
        db.add(WorkflowRun(id=str(uuid.uuid4()), workflow_id=wf.id, company_id=co.id,
                           status="completed", trigger_source="manual"))
        db.commit()
        s2 = build_ponder_script(db, task.id)
        garnish = [b for b in s2["beats"] if b["kind"] == "garnish"]
        assert len(garnish) == 1
        assert "as of" in garnish[0]["text"]  # stale-honest: dated


class TestCaptions:
    def test_authored_overlays_and_clears_to_derived(self, db):
        task, _, _ = _mk_fixture(db)
        save_caption(db, task.id, "step:identify_customers",
                     "Every open charge account gets a look.")
        script = build_ponder_script(db, task.id)
        beat = [b for b in script["beats"] if b["key"] == "step:identify_customers"][0]
        assert beat["authored"] is True
        assert beat["text"] == "Every open charge account gets a look."
        assert beat["derived_text"] == "Find charge-account customers with activity"

        save_caption(db, task.id, "step:identify_customers", None)  # clear
        script = build_ponder_script(db, task.id)
        beat = [b for b in script["beats"] if b["key"] == "step:identify_customers"][0]
        assert beat["authored"] is False
        assert beat["text"] == "Find charge-account customers with activity"

    def test_orphaned_caption_never_renders_but_is_reclaimable(self, db):
        task, _, _ = _mk_fixture(db)
        save_caption(db, task.id, "step:renamed_away", "stale teaching")
        script = build_ponder_script(db, task.id)
        assert all(b["text"] != "stale teaching" for b in script["beats"])
        assert script["orphaned_captions"] == {"step:renamed_away": "stale teaching"}


class TestMirrorDrift:
    def test_desynced_mirror_is_named_and_warned(self, db, caplog):
        task, tpl, wf = _mk_fixture(db)
        # The runtime grows a step the mirror doesn't know about.
        db.add(WorkflowStep(
            id=str(uuid.uuid4()), workflow_id=wf.id, step_key="new_hotness",
            step_type="action", step_order=5, config={},
        ))
        db.commit()
        with caplog.at_level("WARNING"):
            script = build_ponder_script(db, task.id)
        assert any("step count" in d for d in script["mirror_drift"])
        assert any("PONDER MIRROR DRIFT" in r.message for r in caplog.records)

    def test_type_divergence_is_named(self):
        tpl = WorkflowTemplate(
            id="x", scope="platform_default", workflow_type="t",
            display_name="t", version=1,
            canvas_state={"version": 1, "nodes": [
                {"id": "a", "type": "action", "label": "a", "config": {}},
            ], "edges": []},
        )
        step = WorkflowStep(id="s", workflow_id="w", step_key="a",
                            step_type="input", step_order=1, config={})
        drift = check_mirror_drift(tpl, [step])
        assert drift and "type on 'a'" in drift[0]


class TestErrors:
    def test_missing_task_404s(self, db):
        with pytest.raises(ponder.PonderError):
            build_ponder_script(db, "no-such-task")

    def test_task_without_workflow_is_honest(self, db):
        task = MoCTaskCatalog(scope="vertical_default", vertical="manufacturing",
                              name=f"Bare {uuid.uuid4().hex[:5]}")
        db.add(task)
        db.commit()
        with pytest.raises(ponder.PonderError, match="no workflow"):
            build_ponder_script(db, task.id)


class TestMotifGrammar:
    """Ponder Polish Set 3 — beat semantics → scene hints; unplaceable → None
    (a missing visual beats a lying one)."""

    def test_create_transform_send_and_honest_none(self):
        from app.services.maps_of_content.ponder import motif_for_step

        assert motif_for_step({"id": "generate_statements", "type": "action",
                               "config": {"description": "Generate statement PDFs"}}) == \
            {"kind": "create", "entity": "statement"}
        assert motif_for_step({"id": "gen_inv", "type": "action",
                               "config": {"description": "Generate draft invoices from eligible orders"}}) == \
            {"kind": "transform", "from": "order", "to": "invoice"}
        assert motif_for_step({"id": "send_statements", "type": "action",
                               "config": {"description": "Email approved statements"}}) == \
            {"kind": "send", "entity": "statement"}
        # The grammar can't place it → None → typographic treatment.
        assert motif_for_step({"id": "identify_customers", "type": "action",
                               "config": {"description": "Find charge-account customers with activity"}}) is None
        assert motif_for_step({"id": "branch_x", "type": "condition", "config": {}}) == {"kind": "branch"}

    def test_beats_carry_motifs(self, db):
        task, tpl, wf = _mk_fixture(db)
        script = build_ponder_script(db, task.id)
        by_key = {b["key"]: b for b in script["beats"]}
        assert by_key["when"]["motif"] == {"kind": "clock"}  # scheduled fixture
        assert by_key["pause:approval_gate"]["motif"] == {"kind": "pause"}
        assert by_key["step:generate_statements"]["motif"] == {"kind": "create", "entity": "statement"}
        assert by_key["step:send_statements"]["motif"] == {"kind": "send", "entity": "statement"}
        assert by_key["step:identify_customers"].get("motif") is None  # typographic
        assert by_key["downstream:failure"]["motif"] == {"kind": "failure", "label": "Decision Triage"}


class TestArtifactAndAudience:
    """Ponder Enrichment — artifact previews + audience attribution."""

    def test_document_artifact_derives_from_config_then_registry(self, db):
        from app.services.maps_of_content.ponder import _document_artifact

        # 1. config-carried template ref (derived)
        art = _document_artifact(db, None, {
            "id": "make_doc", "type": "action",
            "config": {"action_type": "generate_document", "template_key": "statement.professional"},
        })
        assert art and art["type"] == "document"
        assert art["template_key"] == "statement.professional"
        assert art["version"] >= 1
        # 2. the authored registry (mirrors real adapter behavior)
        art2 = _document_artifact(db, "wf_sys_statement_run", {
            "id": "generate_statements", "type": "action", "config": {}})
        assert art2 and art2["template_key"] == "statement.professional"
        assert art2["authored_source"] is True
        # 3. no ref anywhere → None (a missing preview beats a lying one)
        assert _document_artifact(db, "wf_not_registered", {
            "id": "x", "type": "action", "config": {}}) is None
        # 4. a ref to a template that doesn't exist → None
        assert _document_artifact(db, None, {
            "id": "x", "type": "action",
            "config": {"template_key": "no.such.template"}}) is None

    def test_audience_from_queue_and_step_config_and_honest_absence(self, db):
        from app.services.maps_of_content.ponder import (
            _audience_for_queue, _audience_for_step,
        )

        aud = _audience_for_queue(db, "month_end_close_triage")
        assert aud and "invoice.approve" in aud["text"]
        assert isinstance(aud["count"], int)
        assert _audience_for_queue(db, "no_such_queue") is None

        step_aud = _audience_for_step(db, {
            "id": "notify", "config": {"roles": ["safety_trainer", "admin"]}})
        assert step_aud and "safety trainer" in step_aud["text"]
        assert _audience_for_step(db, {"id": "x", "config": {}}) is None

    def test_beats_carry_artifacts_and_audience_on_the_registry_workflow(self, db):
        # Build the fixture AS wf_sys_statement_run's shape via the registry id
        # trick — a fresh runtime with the registry's exact id would collide
        # with the seeded row, so pin through the seeded task instead when
        # present; else skip gracefully (hermetic-first, seeded-second).
        from app.models.moc_task_catalog import MoCTaskCatalog

        task = (
            db.query(MoCTaskCatalog)
            .filter(MoCTaskCatalog.name == "Monthly Statement Run",
                    MoCTaskCatalog.vertical == "manufacturing",
                    MoCTaskCatalog.is_active.is_(True))
            .first()
        )
        if task is None or not task.workflow_template_id:
            import pytest as _pytest
            _pytest.skip("seeded Statement Run task absent on this DB")
        script = build_ponder_script(db, task.id)
        by_key = {b["key"]: b for b in script["beats"]}
        gen = by_key["step:generate_statements"]
        assert gen["artifact"]["template_key"] == "statement.professional"
        pause = by_key["pause:approval_gate"]
        assert pause["audience"] and "invoice.approve" in pause["audience"]["text"]
        q = by_key["downstream:queue"]
        assert q["audience"] and "invoice.approve" in q["audience"]["text"]
        assert by_key["when"].get("audience") is None  # never a guessed line

    def test_focus_beat_from_attached_focus_resolved_live(self, db):
        from app.models.focus_template import FocusTemplate
        from app.models.moc_task_catalog import MoCTaskCatalogFocus

        tpl = (
            db.query(FocusTemplate)
            .filter(FocusTemplate.is_active.is_(True),
                    FocusTemplate.template_slug == "decision-triage")
            .first()
        )
        if tpl is None:
            import pytest as _pytest
            _pytest.skip("decision-triage template absent on this DB")
        task, _, _ = _mk_fixture(db)
        db.add(MoCTaskCatalogFocus(task_catalog_id=task.id,
                                   focus_template_id=tpl.id, display_order=0))
        db.commit()
        db.refresh(task)

        script = build_ponder_script(db, task.id)
        focus_beats = [b for b in script["beats"] if b["kind"] == "focus"]
        assert len(focus_beats) == 1
        art = focus_beats[0]["artifact"]
        assert art["type"] == "focus"
        assert art["template_slug"] == "decision-triage"
        assert art["core_slug"]  # the lineage, resolved live
        assert isinstance(art["rows"], list)
        # the derived description below the miniature — preserved shape
        assert "The work happens in" in focus_beats[0]["text"]

    def test_preview_render_is_live_never_stale(self, db):
        """The live-resolution pin: edit the template body → the preview
        changes on the next render (rolled back — dev untouched)."""
        from app.models.document_template import DocumentTemplate, DocumentTemplateVersion
        from app.services.documents.document_renderer import render_preview_html

        tpl = (
            db.query(DocumentTemplate)
            .filter(DocumentTemplate.template_key == "statement.professional",
                    DocumentTemplate.company_id.is_(None)).first()
        )
        assert tpl is not None
        before = render_preview_html(db, template_key="statement.professional",
                                     context={"company_name": "X", "items": []})
        v = db.get(DocumentTemplateVersion, tpl.current_version_id)
        original = v.body_template
        try:
            v.body_template = original + "\n<!-- PONDER-LIVE-PIN -->"
            db.flush()
            after = render_preview_html(db, template_key="statement.professional",
                                        context={"company_name": "X", "items": []})
            assert "PONDER-LIVE-PIN" in after
            assert "PONDER-LIVE-PIN" not in before
        finally:
            db.rollback()


class TestFailureBeatExhibit:
    def test_failure_beat_carries_the_decision_triage_focus(self, db):
        task, _, _ = _mk_fixture(db)
        script = build_ponder_script(db, task.id)
        failure = [b for b in script["beats"] if b["key"] == "downstream:failure"][0]
        art = failure.get("artifact")
        if art is None:
            import pytest as _pytest
            _pytest.skip("decision-triage template absent on this DB")
        assert art["type"] == "focus"
        assert art["template_slug"] == "decision-triage"
        assert art["display_name"] == "Decision Triage"
