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
        "production_log_walkthrough": "run_production_log_scenario",
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


def on_team_intelligence_configured(db: Session, tenant_id: str) -> None:
    """Call after team intelligence (briefings + announcements) is configured."""
    try:
        from app.services.onboarding_service import check_completion

        check_completion(db, tenant_id, "setup_team_intelligence")
    except Exception:
        logger.exception("Onboarding hook failed: on_team_intelligence_configured")


def on_safety_training_configured(db: Session, tenant_id: str) -> None:
    """Call after safety training program is set up."""
    try:
        from app.services.onboarding_service import check_completion

        check_completion(db, tenant_id, "setup_safety_training")
    except Exception:
        logger.exception("Onboarding hook failed: on_safety_training_configured")


def on_charge_account_configured(db: Session, tenant_id: str, customer) -> None:
    """Auto-complete setup_charge_accounts when any funeral home customer has
    credit_limit > 0 or invoice_delivery_preference set."""
    try:
        from decimal import Decimal

        is_funeral_home = getattr(customer, "customer_type", None) == "funeral_home"
        has_credit_limit = (
            getattr(customer, "credit_limit", None) is not None
            and customer.credit_limit > Decimal("0")
        )
        has_delivery_pref = bool(getattr(customer, "invoice_delivery_preference", None))

        if is_funeral_home and (has_credit_limit or has_delivery_pref):
            from app.services.onboarding_service import check_completion

            check_completion(db, tenant_id, "setup_charge_accounts")
    except Exception:
        logger.exception("Onboarding hook failed: on_charge_account_configured")


def on_vault_mold_config_setup(db: Session, tenant_id: str) -> None:
    """Auto-complete setup_vault_molds when at least one mold config exists."""
    try:
        from app.models.production_mold_config import ProductionMoldConfig
        from app.services.onboarding_service import check_completion

        count = (
            db.query(ProductionMoldConfig)
            .filter(
                ProductionMoldConfig.company_id == tenant_id,
                ProductionMoldConfig.is_active.is_(True),
            )
            .count()
        )
        if count > 0:
            check_completion(db, tenant_id, "setup_vault_molds")
    except Exception:
        logger.exception("Onboarding hook failed: on_vault_mold_config_setup")
