"""Workflow authoring — platform-realm route (Builder AI Assistant Phase 1b).

The 1b consumer (Studio Workflow editor) runs in the platform-admin realm. The
1a service is realm-agnostic (company_id: str | None); this route is the thin
platform mount over it. These tests pin the realm-agnostic contract:

  - the route passes company_id=None (platform authoring of vertical-default
    workflows has no single tenant), and
  - the route's GenerateResponse serializes the service's graceful failure
    shape (ai_execution_id=None) instead of 500ing — parity with the 1a
    tenant-route hotfix #2.

The route is a plain function; FastAPI deps are defaults, so we can call it
directly with a fake actor + monkeypatched service (no HTTP / auth round-trip).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.routes.admin import visual_editor_workflow_authoring as route_mod


_VALID_CANVAS = {
    "version": 1,
    "nodes": [
        {"id": "n_start", "type": "start", "position": {"x": 0, "y": 0}, "config": {}},
        {"id": "n_end", "type": "end", "position": {"x": 0, "y": 120}, "config": {}},
    ],
    "edges": [{"id": "e1", "source": "n_start", "target": "n_end"}],
}


def test_platform_route_passes_company_id_none(monkeypatch):
    """Platform authoring → company_id=None into the realm-agnostic service."""
    captured: dict = {}

    def _capture(db, **kwargs):
        captured.update(kwargs)
        return {
            "ai_status": "success",
            "ai_execution_id": "exec-1",
            "ai_latency_ms": 10,
            "model_used": "claude-sonnet-4-6",
            "canvas_state": _VALID_CANVAS,
            "valid": True,
            "validation_error": None,
        }

    monkeypatch.setattr(
        route_mod.workflow_authoring, "generate_workflow_canvas", _capture
    )

    body = route_mod.GenerateRequest(
        nl="when a case is committed, generate the case file then notify the family",
        vertical="funeral_home",
        workflow_type="funeral_cascade_generated",
    )
    resp = route_mod.generate(body=body, current_user=SimpleNamespace(id="pu-1"), db=None)

    assert captured["company_id"] is None  # the realm-agnostic contract
    assert captured["vertical"] == "funeral_home"
    assert captured["workflow_type"] == "funeral_cascade_generated"
    assert resp.valid is True
    assert resp.canvas_state == _VALID_CANVAS
    assert resp.model_used == "claude-sonnet-4-6"


def test_platform_route_serializes_guard_failure_shape(monkeypatch):
    """The graceful failure shape (ai_execution_id=None) must serialize — NOT
    500 — exactly like the 1a tenant route after hotfix #2."""

    def _guard_error(db, **kwargs):
        return {
            "ai_status": "error",
            "ai_execution_id": None,
            "ai_latency_ms": None,
            "model_used": None,
            "canvas_state": None,
            "valid": False,
            "validation_error": "generation could not run (PromptNotFoundError: ...)",
        }

    monkeypatch.setattr(
        route_mod.workflow_authoring, "generate_workflow_canvas", _guard_error
    )

    body = route_mod.GenerateRequest(nl="x", vertical="manufacturing", workflow_type="t")
    resp = route_mod.generate(body=body, current_user=SimpleNamespace(id="pu-1"), db=None)

    assert resp.valid is False
    assert resp.ai_status == "error"
    assert resp.ai_execution_id is None  # must not trip response-model validation
    assert "generation could not run" in (resp.validation_error or "")


def test_platform_route_uses_platform_auth_dep():
    """The route's auth dependency is get_current_platform_user (platform realm),
    NOT the tenant get_current_user — the 1b consumer's realm."""
    from app.api.deps import get_current_platform_user

    # The generate route's signature carries the platform dependency as the
    # default for current_user.
    import inspect

    sig = inspect.signature(route_mod.generate)
    dep = sig.parameters["current_user"].default
    # FastAPI Depends wraps the callable; assert it points at the platform dep.
    assert getattr(dep, "dependency", None) is get_current_platform_user
