"""Task substrate v1 — task creators plugin contract tests."""

from __future__ import annotations

import pytest

from app.services.tasks.plugins import creators


def teardown_function(_):
    # Clean any test-registered creators
    for k in ("test_create_prov_a", "test_create_prov_b"):
        creators.unregister_task_creator(k)


def test_task_creator_protocol_has_required_attrs():
    """The Protocol declares the contract surface."""
    assert hasattr(creators.TaskCreatorProtocol, "create")


def test_register_and_lookup_creator():
    class TestCreator:
        provenance_kind = "test_create_prov_a"
        task_type_default = "generic_task"

        def create(self, db, **kwargs):
            return "fake_td_id"

    c = TestCreator()
    creators.register_task_creator(c)
    assert creators.get_task_creator("test_create_prov_a") is c


def test_register_rejects_empty_provenance_kind():
    class BadCreator:
        provenance_kind = ""
        task_type_default = "generic_task"

        def create(self, db, **kwargs):
            return None

    with pytest.raises(ValueError):
        creators.register_task_creator(BadCreator())


def test_register_replaces_existing():
    class C1:
        provenance_kind = "test_create_prov_a"
        task_type_default = "generic_task"
        def create(self, db, **kwargs): return "c1"

    class C2:
        provenance_kind = "test_create_prov_a"
        task_type_default = "generic_task"
        def create(self, db, **kwargs): return "c2"

    creators.register_task_creator(C1())
    creators.register_task_creator(C2())
    found = creators.get_task_creator("test_create_prov_a")
    assert found.create(None) == "c2"


def test_list_task_creators_includes_registered():
    class TestCreator:
        provenance_kind = "test_create_prov_a"
        task_type_default = "generic_task"
        def create(self, db, **kwargs): return None

    creators.register_task_creator(TestCreator())
    assert "test_create_prov_a" in creators.list_task_creators()


def test_get_returns_none_for_unknown():
    assert creators.get_task_creator("never_registered") is None


def test_unregister_creator():
    class TestCreator:
        provenance_kind = "test_create_prov_a"
        task_type_default = "generic_task"
        def create(self, db, **kwargs): return None

    creators.register_task_creator(TestCreator())
    assert creators.unregister_task_creator("test_create_prov_a") is True
    assert creators.get_task_creator("test_create_prov_a") is None


def test_unregister_returns_false_for_unknown():
    assert (
        creators.unregister_task_creator("never_registered") is False
    )


def test_dispatch_creator_invokes_create():
    captured = {}

    class TestCreator:
        provenance_kind = "test_create_prov_a"
        task_type_default = "generic_task"

        def create(self, db, **kwargs):
            captured.update(kwargs)
            return "dispatched-td-id"

    creators.register_task_creator(TestCreator())
    result = creators.dispatch_creator(
        None,
        provenance_kind="test_create_prov_a",
        company_id="co",
        provenance_ref_type="x",
        provenance_ref_id="r",
        event_kind="e",
        title="t",
    )
    assert result == "dispatched-td-id"
    assert captured["company_id"] == "co"


def test_dispatch_creator_returns_none_for_unknown_kind():
    result = creators.dispatch_creator(
        None,
        provenance_kind="never_registered",
        company_id="co",
        provenance_ref_type="x",
        provenance_ref_id="r",
        event_kind="e",
        title="t",
    )
    assert result is None
