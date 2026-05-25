"""Task substrate v1 — task surfaces plugin contract tests."""

from __future__ import annotations

import pytest

from app.services.tasks.plugins import surfaces


def teardown_function(_):
    for k in ("test_surface_a", "test_surface_b"):
        surfaces.unregister_task_surface(k)


def test_surface_kinds_canonical():
    assert set(surfaces.SURFACE_KINDS) == {
        "list", "detail", "creation_form", "card", "row",
    }


def test_register_and_lookup_surface():
    class TestSurface:
        surface_key = "test_surface_a"
        surface_kind = "list"
        accepted_task_types = ("generic_task",)
        def render_context(self, db, **kwargs): return {}

    s = TestSurface()
    surfaces.register_task_surface(s)
    assert surfaces.get_task_surface("test_surface_a") is s


def test_register_rejects_empty_key():
    class Bad:
        surface_key = ""
        surface_kind = "list"
        accepted_task_types = ()
        def render_context(self, db, **kwargs): return {}

    with pytest.raises(ValueError):
        surfaces.register_task_surface(Bad())


def test_register_rejects_unknown_kind():
    class Bad:
        surface_key = "x"
        surface_kind = "bogus"
        accepted_task_types = ()
        def render_context(self, db, **kwargs): return {}

    with pytest.raises(ValueError):
        surfaces.register_task_surface(Bad())


def test_get_surfaces_filtered_by_kind():
    class S1:
        surface_key = "test_surface_a"
        surface_kind = "list"
        accepted_task_types = ("generic_task",)
        def render_context(self, db, **kwargs): return {}

    class S2:
        surface_key = "test_surface_b"
        surface_kind = "detail"
        accepted_task_types = ("generic_task",)
        def render_context(self, db, **kwargs): return {}

    surfaces.register_task_surface(S1())
    surfaces.register_task_surface(S2())

    list_surfaces = surfaces.get_task_surfaces(kind="list")
    keys = {x.surface_key for x in list_surfaces}
    assert "test_surface_a" in keys
    assert "test_surface_b" not in keys


def test_get_surfaces_filtered_by_task_type():
    class S1:
        surface_key = "test_surface_a"
        surface_kind = "list"
        accepted_task_types = ("review_approval_task",)
        def render_context(self, db, **kwargs): return {}

    surfaces.register_task_surface(S1())
    filtered = surfaces.get_task_surfaces(task_type="generic_task")
    keys = {x.surface_key for x in filtered}
    assert "test_surface_a" not in keys


def test_list_and_unregister():
    class S1:
        surface_key = "test_surface_a"
        surface_kind = "list"
        accepted_task_types = ()
        def render_context(self, db, **kwargs): return {}

    surfaces.register_task_surface(S1())
    assert "test_surface_a" in surfaces.list_task_surfaces()
    assert surfaces.unregister_task_surface("test_surface_a") is True
    assert surfaces.unregister_task_surface("test_surface_a") is False
    assert "test_surface_a" not in surfaces.list_task_surfaces()
