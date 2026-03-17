"""Lightweight hooks that other services call after relevant platform actions.

Each hook wraps a ``check_completion`` call so that the onboarding checklist
progresses automatically as the tenant uses the system.  All hooks are
fire-and-forget -- they catch and log every exception so that a failure in
onboarding tracking never disrupts the actual business operation.
"""

import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def on_product_created(db: Session, tenant_id: str) -> None:
    """Call after a product is created."""
    try:
        from app.services.onboarding_service import check_completion

        check_completion(db, tenant_id, "add_products")
    except Exception:
        logger.exception("Onboarding hook failed: on_product_created")


def on_customer_created(db: Session, tenant_id: str) -> None:
    """Call after a customer is created."""
    try:
        from app.services.onboarding_service import check_completion

        check_completion(db, tenant_id, "add_first_customer")
    except Exception:
        logger.exception("Onboarding hook failed: on_customer_created")


def on_employee_created(db: Session, tenant_id: str) -> None:
    """Call after an employee / user is created."""
    try:
        from app.services.onboarding_service import check_completion

        check_completion(db, tenant_id, "add_employees")
    except Exception:
        logger.exception("Onboarding hook failed: on_employee_created")


def on_integration_connected(db: Session, tenant_id: str) -> None:
    """Call after an accounting integration is connected."""
    try:
        from app.services.onboarding_service import check_completion

        check_completion(db, tenant_id, "connect_accounting")
    except Exception:
        logger.exception("Onboarding hook failed: on_integration_connected")


def on_scenario_completed(db: Session, tenant_id: str, scenario_key: str) -> None:
    """Maps scenario keys to checklist item keys and marks them complete."""
    SCENARIO_TO_ITEM = {
        "vault_order_walkthrough": "run_vault_scenario",
        "work_order_walkthrough": "run_work_order_scenario",
        "month_end_walkthrough": "run_month_end_scenario",
        "case_walkthrough": "run_case_scenario",
        "fh_vault_order_walkthrough": "run_vault_order_scenario",
    }
    item_key = SCENARIO_TO_ITEM.get(scenario_key)
    if item_key:
        try:
            from app.services.onboarding_service import check_completion

            check_completion(db, tenant_id, item_key)
        except Exception:
            logger.exception("Onboarding hook failed: on_scenario_completed")


def on_price_list_updated(db: Session, tenant_id: str) -> None:
    """Call after a funeral-home price list is updated."""
    try:
        from app.services.onboarding_service import check_completion

        check_completion(db, tenant_id, "add_price_list")
    except Exception:
        logger.exception("Onboarding hook failed: on_price_list_updated")


def on_manufacturer_linked(db: Session, tenant_id: str) -> None:
    """Call after a vault manufacturer is linked to a funeral home."""
    try:
        from app.services.onboarding_service import check_completion

        check_completion(db, tenant_id, "link_vault_supplier")
    except Exception:
        logger.exception("Onboarding hook failed: on_manufacturer_linked")
