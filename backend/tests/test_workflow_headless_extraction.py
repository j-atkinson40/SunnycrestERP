"""Phase R-6.0a — headless Generation Focus invocation tests.

Coverage:
  * generation_focus.headless_dispatch registry shape (BVPS entries
    registered for 3 canonical ops).
  * dispatch() raises typed errors for unknown focus_id / op_id.
  * dispatch() routes BVPS ops to the canonical ai_extraction_review
    functions (via monkeypatch — no Claude calls in tests).
  * workflow_engine._handle_invoke_generation_focus error envelopes
    + canonical success shape with status="applied".
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.services.generation_focus import (
    HEADLESS_DISPATCH,
    HeadlessDispatchError,
    UnknownGenerationFocus,
    UnknownGenerationFocusOp,
    dispatch,
    list_dispatch_keys,
)


# ── Registry shape ──────────────────────────────────────────────────


class TestRegistryShape:
    """BVPS dispatch entries registered at module load."""

    def test_burial_vault_focus_registered(self):
        assert "burial_vault_personalization_studio" in HEADLESS_DISPATCH

    def test_three_canonical_ops_registered(self):
        ops = HEADLESS_DISPATCH["burial_vault_personalization_studio"]
        assert "extract_decedent_info" in ops
        assert "suggest_layout" in ops
        assert "suggest_text_style" in ops

    def test_list_dispatch_keys_includes_bvps(self):
        keys = list_dispatch_keys()
        assert ("burial_vault_personalization_studio", "extract_decedent_info") in keys
        assert ("burial_vault_personalization_studio", "suggest_layout") in keys
        assert ("burial_vault_personalization_studio", "suggest_text_style") in keys


# ── dispatch() error paths ──────────────────────────────────────────


class TestDispatchErrors:
    """Typed errors for unknown focus_id / op_id."""

    def test_unknown_focus_raises(self):
        with pytest.raises(UnknownGenerationFocus) as exc_info:
            dispatch("nonexistent_focus", "extract_decedent_info", db=None, company_id="x")
        assert "nonexistent_focus" in str(exc_info.value)

    def test_unknown_op_raises(self):
        with pytest.raises(UnknownGenerationFocusOp) as exc_info:
            dispatch(
                "burial_vault_personalization_studio",
                "nonexistent_op",
                db=None,
                company_id="x",
                instance_id="i",
            )
        assert "nonexistent_op" in str(exc_info.value)

    def test_both_errors_inherit_from_base(self):
        assert issubclass(UnknownGenerationFocus, HeadlessDispatchError)
        assert issubclass(UnknownGenerationFocusOp, HeadlessDispatchError)


# ── dispatch() routing ──────────────────────────────────────────────


class TestDispatchRouting:
    """dispatch() routes BVPS ops to ai_extraction_review functions.
    Monkeypatched — no Claude calls in tests."""

    def test_extract_decedent_info_routes(self, monkeypatch):
        captured: dict[str, Any] = {}

        def _fake_extract(db, *, instance_id, company_id, content_blocks, context_summary=None):
            captured["instance_id"] = instance_id
            captured["company_id"] = company_id
            captured["content_blocks"] = content_blocks
            captured["context_summary"] = context_summary
            return {"line_items": [{"field_key": "deceased_name", "value": "JS"}]}

        monkeypatch.setattr(
            "app.services.personalization_studio.ai_extraction_review.extract_decedent_info",
            _fake_extract,
        )
        out = dispatch(
            "burial_vault_personalization_studio",
            "extract_decedent_info",
            db=None,
            company_id="co-1",
            instance_id="inst-1",
            content_blocks=[{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "AAA"}}],
            context_summary="death cert",
        )
        assert out == {"line_items": [{"field_key": "deceased_name", "value": "JS"}]}
        assert captured["instance_id"] == "inst-1"
        assert captured["company_id"] == "co-1"
        assert captured["context_summary"] == "death cert"

    def test_suggest_layout_routes(self, monkeypatch):
        captured: dict[str, Any] = {}

        def _fake_suggest(db, *, instance_id, company_id):
            captured["instance_id"] = instance_id
            captured["company_id"] = company_id
            return {"line_items": [{"field_key": "layout", "value": "centered"}]}

        monkeypatch.setattr(
            "app.services.personalization_studio.ai_extraction_review.suggest_layout",
            _fake_suggest,
        )
        out = dispatch(
            "burial_vault_personalization_studio",
            "suggest_layout",
            db=None,
            company_id="co-1",
            instance_id="inst-9",
        )
        assert out["line_items"][0]["field_key"] == "layout"

    def test_suggest_text_style_routes(self, monkeypatch):
        called = {}

        def _fake_text_style(db, *, instance_id, company_id, family_preferences=None):
            called["family_preferences"] = family_preferences
            return {"line_items": []}

        monkeypatch.setattr(
            "app.services.personalization_studio.ai_extraction_review.suggest_text_style",
            _fake_text_style,
        )
        dispatch(
            "burial_vault_personalization_studio",
            "suggest_text_style",
            db=None,
            company_id="co-1",
            instance_id="inst-1",
            family_preferences="bold serif",
        )
        assert called["family_preferences"] == "bold serif"


# ── _handle_invoke_generation_focus shape ───────────────────────────


class TestInvokeGenerationFocusHandler:
    """Engine handler envelope: success + error shapes."""

    def test_missing_focus_id_returns_error(self):
        from app.services.workflow_engine import _handle_invoke_generation_focus

        run = SimpleNamespace(company_id="co-1", id="run-1")
        out = _handle_invoke_generation_focus(None, {"action_type": "invoke_generation_focus"}, run)
        assert out["status"] == "errored"
        assert out["error_code"] == "missing_dispatch_key"

    def test_missing_op_id_returns_error(self):
        from app.services.workflow_engine import _handle_invoke_generation_focus

        run = SimpleNamespace(company_id="co-1", id="run-1")
        out = _handle_invoke_generation_focus(
            None,
            {"action_type": "invoke_generation_focus", "focus_id": "x"},
            run,
        )
        assert out["status"] == "errored"
        assert out["error_code"] == "missing_dispatch_key"

    def test_unknown_focus_routes_to_dispatch_error(self):
        from app.services.workflow_engine import _handle_invoke_generation_focus

        run = SimpleNamespace(company_id="co-1", id="run-1")
        out = _handle_invoke_generation_focus(
            None,
            {
                "action_type": "invoke_generation_focus",
                "focus_id": "nonexistent",
                "op_id": "x",
            },
            run,
        )
        assert out["status"] == "errored"
        assert out["error_code"] == "headless_dispatch_error"

    def test_invalid_kwargs_type(self):
        from app.services.workflow_engine import _handle_invoke_generation_focus

        run = SimpleNamespace(company_id="co-1", id="run-1")
        out = _handle_invoke_generation_focus(
            None,
            {
                "action_type": "invoke_generation_focus",
                "focus_id": "burial_vault_personalization_studio",
                "op_id": "suggest_layout",
                "kwargs": "not-a-dict",
            },
            run,
        )
        assert out["status"] == "errored"
        assert out["error_code"] == "invalid_kwargs"

    def test_success_envelope_includes_status_applied(self, monkeypatch):
        from app.services.workflow_engine import _handle_invoke_generation_focus

        monkeypatch.setattr(
            "app.services.personalization_studio.ai_extraction_review.suggest_layout",
            lambda db, *, instance_id, company_id: {"line_items": [{"x": 1}]},
        )
        run = SimpleNamespace(company_id="co-1", id="run-1")
        out = _handle_invoke_generation_focus(
            None,
            {
                "action_type": "invoke_generation_focus",
                "focus_id": "burial_vault_personalization_studio",
                "op_id": "suggest_layout",
                "kwargs": {"instance_id": "inst-1"},
            },
            run,
        )
        assert out["status"] == "applied"
        assert out["focus_id"] == "burial_vault_personalization_studio"
        assert out["op_id"] == "suggest_layout"
        assert out["line_items"] == [{"x": 1}]
