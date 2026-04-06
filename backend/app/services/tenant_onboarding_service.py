"""Alias module — re-exports tenant onboarding functions from onboarding_service.

The route layer imports ``app.services.tenant_onboarding_service`` while the
actual implementation lives in ``app.services.onboarding_service`` (which also
contains legacy employee-onboarding helpers).  This shim bridges the two.
"""

from app.services.onboarding_service import (  # noqa: F401
    initialize_checklist,
    check_completion,
    recalculate_progress,
    get_checklist,
    skip_item,
    get_scenarios as list_scenarios,
    start_scenario,
    advance_scenario,
    get_product_templates as get_product_library,
    import_product_templates,
    create_data_import,
    update_data_import,
    dismiss_help,
    get_dismissed_help,
    schedule_check_in_call,
    request_white_glove_import,
    get_onboarding_analytics,
)


def update_item_status(db, tenant_id: str, item_key: str, status: str):
    """Update a checklist item's status (e.g. to in_progress)."""
    from app.models.onboarding_checklist_item import OnboardingChecklistItem

    item = (
        db.query(OnboardingChecklistItem)
        .filter(
            OnboardingChecklistItem.tenant_id == tenant_id,
            OnboardingChecklistItem.item_key == item_key,
        )
        .first()
    )
    if not item:
        return None
    item.status = status
    if status == "not_started":
        item.completed_at = None
        item.completed_by = None
    db.commit()

    # Recalculate checklist progress after status change
    from app.services.onboarding_service import recalculate_progress
    recalculate_progress(db, tenant_id)
    db.commit()

    db.refresh(item)
    return item


def get_scenario(db, tenant_id: str, scenario_key: str):
    """Get a single scenario by key."""
    from app.models.onboarding_scenario import OnboardingScenario
    from sqlalchemy.orm import joinedload

    return (
        db.query(OnboardingScenario)
        .options(joinedload(OnboardingScenario.steps))
        .filter(
            OnboardingScenario.tenant_id == tenant_id,
            OnboardingScenario.scenario_key == scenario_key,
        )
        .first()
    )


def list_integrations(db, tenant_id: str):
    """List integration setups for a tenant."""
    from app.models.onboarding_integration_setup import OnboardingIntegrationSetup

    return (
        db.query(OnboardingIntegrationSetup)
        .filter(OnboardingIntegrationSetup.tenant_id == tenant_id)
        .all()
    )


def create_integration(db, tenant_id: str, integration_type: str):
    """Create an integration setup record."""
    from app.models.onboarding_integration_setup import OnboardingIntegrationSetup

    setup = OnboardingIntegrationSetup(
        tenant_id=tenant_id,
        integration_type=integration_type,
    )
    db.add(setup)
    db.commit()
    db.refresh(setup)
    return setup


def update_integration(db, integration_id: str, tenant_id: str, **kwargs):
    """Update an integration setup."""
    from datetime import datetime, timezone
    from app.models.onboarding_integration_setup import OnboardingIntegrationSetup

    setup = (
        db.query(OnboardingIntegrationSetup)
        .filter(
            OnboardingIntegrationSetup.id == integration_id,
            OnboardingIntegrationSetup.tenant_id == tenant_id,
        )
        .first()
    )
    if not setup:
        return None

    if kwargs.get("briefing_acknowledged"):
        setup.briefing_acknowledged_at = datetime.now(timezone.utc)
        setup.status = "briefing_acknowledged"
    if kwargs.get("sandbox_approved"):
        setup.sandbox_test_approved_at = datetime.now(timezone.utc)
        setup.status = "live"
        setup.went_live_at = datetime.now(timezone.utc)
    if "status" in kwargs and kwargs["status"]:
        setup.status = kwargs["status"]

    db.commit()
    db.refresh(setup)
    return setup


def list_data_imports(db, tenant_id: str):
    """List data imports for a tenant."""
    from app.models.onboarding_data_import import OnboardingDataImport

    return (
        db.query(OnboardingDataImport)
        .filter(OnboardingDataImport.tenant_id == tenant_id)
        .order_by(OnboardingDataImport.created_at.desc())
        .all()
    )


def get_data_import(db, import_id: str, tenant_id: str):
    """Get a single data import."""
    from app.models.onboarding_data_import import OnboardingDataImport

    return (
        db.query(OnboardingDataImport)
        .filter(
            OnboardingDataImport.id == import_id,
            OnboardingDataImport.tenant_id == tenant_id,
        )
        .first()
    )


def preview_data_import(db, import_id: str, tenant_id: str):
    """Generate preview for a data import."""
    import json
    from app.models.onboarding_data_import import OnboardingDataImport

    imp = (
        db.query(OnboardingDataImport)
        .filter(
            OnboardingDataImport.id == import_id,
            OnboardingDataImport.tenant_id == tenant_id,
        )
        .first()
    )
    if not imp:
        return None
    preview = json.loads(imp.preview_data) if imp.preview_data else []
    mapping = json.loads(imp.field_mapping) if imp.field_mapping else {}
    return {
        "preview_rows": preview[:5] if preview else [],
        "total_records": imp.total_records,
        "mapped_fields": [
            {"source_column": k, "target_field": v} for k, v in mapping.items()
        ],
    }


def execute_data_import(db, import_id: str, tenant_id: str):
    """Execute a data import."""
    from datetime import datetime, timezone
    from app.models.onboarding_data_import import OnboardingDataImport

    imp = (
        db.query(OnboardingDataImport)
        .filter(
            OnboardingDataImport.id == import_id,
            OnboardingDataImport.tenant_id == tenant_id,
        )
        .first()
    )
    if not imp:
        return None
    imp.status = "complete"
    imp.imported_records = imp.total_records
    imp.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(imp)
    return imp


def list_all_white_glove_imports(db, status=None, limit=50, offset=0):
    """Admin: list all white-glove imports across tenants."""
    from app.models.onboarding_data_import import OnboardingDataImport

    q = db.query(OnboardingDataImport).filter(
        OnboardingDataImport.source_format == "white_glove"
    )
    if status:
        q = q.filter(OnboardingDataImport.status == status)
    return q.order_by(OnboardingDataImport.created_at.desc()).offset(offset).limit(limit).all()


def get_white_glove_import(db, import_id: str):
    """Admin: get a single white-glove import."""
    from app.models.onboarding_data_import import OnboardingDataImport

    return (
        db.query(OnboardingDataImport)
        .filter(
            OnboardingDataImport.id == import_id,
            OnboardingDataImport.source_format == "white_glove",
        )
        .first()
    )


def update_white_glove_import(db, import_id: str, status: str, notes: str | None = None):
    """Admin: update a white-glove import status."""
    from datetime import datetime, timezone
    from app.models.onboarding_data_import import OnboardingDataImport

    imp = (
        db.query(OnboardingDataImport)
        .filter(
            OnboardingDataImport.id == import_id,
            OnboardingDataImport.source_format == "white_glove",
        )
        .first()
    )
    if not imp:
        return None
    imp.status = status
    if status == "complete":
        imp.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(imp)
    return imp


def list_all_checklists(db, preset=None, limit=50, offset=0):
    """Admin: list onboarding checklists across all tenants."""
    from app.models.onboarding_checklist import TenantOnboardingChecklist

    q = db.query(TenantOnboardingChecklist)
    if preset:
        q = q.filter(TenantOnboardingChecklist.preset == preset)
    return q.order_by(TenantOnboardingChecklist.created_at.desc()).offset(offset).limit(limit).all()
