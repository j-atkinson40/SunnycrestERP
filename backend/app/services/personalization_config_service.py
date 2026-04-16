"""Personalization Configuration Service — manages per-program personalization options.

Handles pricing modes, option enablement, approval workflows, and price calculation
for vault/casket/monument personalization programs.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import ConfigurableItemRegistry, WilbertProgramEnrollment

logger = logging.getLogger(__name__)


class PersonalizationConfigService:
    """Manages personalization configuration for program enrollments."""

    @staticmethod
    def get_config(db: Session, company_id: str, program_code: str) -> dict:
        """Get personalization config for a program enrollment.

        Returns the personalization_config JSON from the enrollment, merged with
        master registry defaults for any missing options.
        """
        enrollment = _get_active_enrollment(db, company_id, program_code)
        if not enrollment:
            return {"error": "No active enrollment found", "options": []}

        config = dict(enrollment.personalization_config or {})

        # Merge with master registry defaults
        master_options = _get_master_options(db)
        config_options = config.get("options", {})

        merged_options = []
        for opt in master_options:
            key = opt.item_key
            tenant_override = config_options.get(key, {})
            merged_options.append({
                "option_key": key,
                "display_name": opt.display_name,
                "description": opt.description,
                "tier": opt.tier,
                "tags": opt.tags or [],
                "is_enabled": tenant_override.get("is_enabled", opt.tier <= 2),
                "applicable_product_ids": tenant_override.get(
                    "applicable_product_ids",
                    opt.default_config.get("applicable", "all") if opt.default_config else "all",
                ),
                "price_addition": tenant_override.get("price_addition"),
                "price_overrides_by_product": tenant_override.get("price_overrides_by_product"),
                "is_custom": False,
            })

        # Add custom options (tier 4)
        for key, opt_data in config_options.items():
            if opt_data.get("is_custom"):
                merged_options.append({
                    "option_key": key,
                    "display_name": opt_data.get("display_name", key),
                    "description": opt_data.get("description"),
                    "tier": 4,
                    "tags": opt_data.get("tags", ["custom"]),
                    "is_enabled": opt_data.get("is_enabled", True),
                    "applicable_product_ids": opt_data.get("applicable_product_ids", "all"),
                    "price_addition": opt_data.get("price_addition"),
                    "price_overrides_by_product": opt_data.get("price_overrides_by_product"),
                    "is_custom": True,
                    "notes_for_director": opt_data.get("notes_for_director"),
                })

        return {
            "program_code": program_code,
            "pricing_mode": config.get("pricing_mode", "included"),
            "flat_fee_amount": config.get("flat_fee_amount"),
            "approval_workflow": config.get("approval_workflow", {
                "workflow": "none",
                "approver_user_id": None,
                "family_proof_required": False,
                "family_proof_timeout_hours": 72,
                "family_proof_timeout_action": "proceed",
            }),
            "options": merged_options,
        }

    @staticmethod
    def update_pricing_mode(
        db: Session,
        company_id: str,
        program_code: str,
        pricing_mode: str,
        flat_fee_amount: float | None = None,
    ) -> dict:
        """Update the pricing mode for personalization.

        pricing_mode: 'included' | 'flat_fee' | 'per_option'
        """
        if pricing_mode not in ("included", "flat_fee", "per_option"):
            raise ValueError(f"Invalid pricing_mode: {pricing_mode}")

        enrollment = _get_active_enrollment(db, company_id, program_code)
        if not enrollment:
            raise ValueError("No active enrollment found")

        config = dict(enrollment.personalization_config or {})
        config["pricing_mode"] = pricing_mode
        if pricing_mode == "flat_fee":
            config["flat_fee_amount"] = flat_fee_amount
        else:
            config.pop("flat_fee_amount", None)

        enrollment.personalization_config = config
        enrollment.updated_at = datetime.now(timezone.utc)
        db.flush()
        logger.info(
            "Updated pricing mode for company=%s program=%s: %s",
            company_id, program_code, pricing_mode,
        )
        return {"pricing_mode": pricing_mode, "flat_fee_amount": config.get("flat_fee_amount")}

    @staticmethod
    def update_option(
        db: Session,
        company_id: str,
        program_code: str,
        option_key: str,
        is_enabled: bool | None = None,
        applicable_product_ids: list[str] | str | None = None,
        price_addition: float | None = None,
        price_overrides_by_product: dict | None = None,
    ) -> dict:
        """Update a single personalization option's config."""
        enrollment = _get_active_enrollment(db, company_id, program_code)
        if not enrollment:
            raise ValueError("No active enrollment found")

        config = dict(enrollment.personalization_config or {})
        options = dict(config.get("options", {}))
        opt = dict(options.get(option_key, {}))

        if is_enabled is not None:
            opt["is_enabled"] = is_enabled
        if applicable_product_ids is not None:
            opt["applicable_product_ids"] = applicable_product_ids
        if price_addition is not None:
            opt["price_addition"] = price_addition
        if price_overrides_by_product is not None:
            opt["price_overrides_by_product"] = price_overrides_by_product

        options[option_key] = opt
        config["options"] = options
        enrollment.personalization_config = config
        enrollment.updated_at = datetime.now(timezone.utc)
        db.flush()
        logger.info(
            "Updated option %s for company=%s program=%s",
            option_key, company_id, program_code,
        )
        return opt

    @staticmethod
    def create_custom_option(
        db: Session,
        company_id: str,
        program_code: str,
        display_name: str,
        description: str | None = None,
        applicable_product_ids: list[str] | str | None = None,
        price_addition: float | None = None,
        notes_for_director: str | None = None,
    ) -> dict:
        """Create a custom personalization option (tier 4)."""
        enrollment = _get_active_enrollment(db, company_id, program_code)
        if not enrollment:
            raise ValueError("No active enrollment found")

        option_key = f"custom.{str(uuid.uuid4())[:8]}"

        config = dict(enrollment.personalization_config or {})
        options = dict(config.get("options", {}))
        options[option_key] = {
            "is_custom": True,
            "display_name": display_name,
            "description": description,
            "is_enabled": True,
            "applicable_product_ids": applicable_product_ids or "all",
            "price_addition": price_addition,
            "notes_for_director": notes_for_director,
            "tags": ["custom"],
        }
        config["options"] = options
        enrollment.personalization_config = config
        enrollment.updated_at = datetime.now(timezone.utc)
        db.flush()
        logger.info(
            "Created custom option %s for company=%s program=%s",
            option_key, company_id, program_code,
        )
        return {"option_key": option_key, **options[option_key]}

    @staticmethod
    def delete_custom_option(
        db: Session,
        company_id: str,
        program_code: str,
        option_key: str,
    ) -> bool:
        """Delete a custom option. Only works on tier 4 (custom) items."""
        enrollment = _get_active_enrollment(db, company_id, program_code)
        if not enrollment:
            return False

        config = dict(enrollment.personalization_config or {})
        options = dict(config.get("options", {}))
        opt = options.get(option_key)
        if not opt or not opt.get("is_custom"):
            return False

        del options[option_key]
        config["options"] = options
        enrollment.personalization_config = config
        enrollment.updated_at = datetime.now(timezone.utc)
        db.flush()
        logger.info(
            "Deleted custom option %s for company=%s program=%s",
            option_key, company_id, program_code,
        )
        return True

    @staticmethod
    def update_approval_workflow(
        db: Session,
        company_id: str,
        program_code: str,
        workflow: str,
        approver_user_id: str | None = None,
        family_proof_required: bool | None = None,
        family_proof_timeout_hours: int | None = None,
        family_proof_timeout_action: str | None = None,
    ) -> dict:
        """Update approval workflow settings."""
        if workflow not in ("none", "staff_approval", "family_proof"):
            raise ValueError(f"Invalid workflow: {workflow}")

        enrollment = _get_active_enrollment(db, company_id, program_code)
        if not enrollment:
            raise ValueError("No active enrollment found")

        config = dict(enrollment.personalization_config or {})
        approval = dict(config.get("approval_workflow", {}))
        approval["workflow"] = workflow
        if approver_user_id is not None:
            approval["approver_user_id"] = approver_user_id
        if family_proof_required is not None:
            approval["family_proof_required"] = family_proof_required
        if family_proof_timeout_hours is not None:
            approval["family_proof_timeout_hours"] = family_proof_timeout_hours
        if family_proof_timeout_action is not None:
            approval["family_proof_timeout_action"] = family_proof_timeout_action

        config["approval_workflow"] = approval
        enrollment.personalization_config = config
        enrollment.updated_at = datetime.now(timezone.utc)
        db.flush()
        logger.info(
            "Updated approval workflow for company=%s program=%s: %s",
            company_id, program_code, workflow,
        )
        return approval

    @staticmethod
    def get_applicable_options_for_product(
        db: Session,
        company_id: str,
        program_code: str,
        product_id: str,
    ) -> list[dict]:
        """Get all enabled options applicable to a specific product. Used by Composer."""
        full_config = PersonalizationConfigService.get_config(db, company_id, program_code)
        if "error" in full_config:
            return []

        applicable = []
        for opt in full_config["options"]:
            if not opt.get("is_enabled"):
                continue
            product_scope = opt.get("applicable_product_ids", "all")
            if product_scope == "all" or (isinstance(product_scope, list) and product_id in product_scope):
                applicable.append(opt)

        return applicable

    @staticmethod
    def calculate_personalization_price(
        db: Session,
        company_id: str,
        program_code: str,
        product_id: str,
        selected_option_keys: list[str],
    ) -> dict:
        """Calculate total personalization price for selected options on a product.

        Returns: {total, breakdown: [{option_key, display_name, price}], pricing_mode}
        """
        full_config = PersonalizationConfigService.get_config(db, company_id, program_code)
        if "error" in full_config:
            return {"total": 0, "breakdown": [], "pricing_mode": "included"}

        pricing_mode = full_config.get("pricing_mode", "included")

        if pricing_mode == "included":
            return {"total": 0, "breakdown": [], "pricing_mode": "included"}

        if pricing_mode == "flat_fee":
            fee = full_config.get("flat_fee_amount", 0) or 0
            return {
                "total": fee,
                "breakdown": [{"option_key": "_flat_fee", "display_name": "Personalization Fee", "price": fee}],
                "pricing_mode": "flat_fee",
            }

        # per_option pricing
        options_map = {opt["option_key"]: opt for opt in full_config["options"]}
        breakdown = []
        total = 0.0
        for key in selected_option_keys:
            opt = options_map.get(key)
            if not opt or not opt.get("is_enabled"):
                continue
            # Check for product-specific override
            overrides = opt.get("price_overrides_by_product") or {}
            price = overrides.get(product_id, opt.get("price_addition") or 0)
            price = float(price) if price else 0.0
            breakdown.append({
                "option_key": key,
                "display_name": opt.get("display_name", key),
                "price": price,
            })
            total += price

        return {"total": total, "breakdown": breakdown, "pricing_mode": "per_option"}

    @staticmethod
    def initialize_defaults(
        db: Session,
        company_id: str,
        program_code: str,
    ) -> dict:
        """Set up default personalization config for a new program enrollment.

        Creates config with: pricing_mode='included', all tier 1+2 options enabled,
        tier 1 locked, tier 2 applicable to 'all', tier 3 disabled.
        """
        master_options = _get_master_options(db)
        options = {}
        for opt in master_options:
            key = opt.item_key
            if opt.tier <= 2:
                options[key] = {
                    "is_enabled": True,
                    "applicable_product_ids": opt.default_config.get("applicable", "all") if opt.default_config else "all",
                }
            else:
                options[key] = {
                    "is_enabled": False,
                }

        config = {
            "pricing_mode": "included",
            "options": options,
            "approval_workflow": {
                "workflow": "none",
                "approver_user_id": None,
                "family_proof_required": False,
                "family_proof_timeout_hours": 72,
                "family_proof_timeout_action": "proceed",
            },
        }

        enrollment = _get_active_enrollment(db, company_id, program_code)
        if enrollment:
            enrollment.personalization_config = config
            enrollment.updated_at = datetime.now(timezone.utc)
            db.flush()

        logger.info(
            "Initialized default personalization config for company=%s program=%s",
            company_id, program_code,
        )
        return config


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _get_active_enrollment(
    db: Session, company_id: str, program_code: str
) -> WilbertProgramEnrollment | None:
    """Fetch the active enrollment for a company + program."""
    return (
        db.query(WilbertProgramEnrollment)
        .filter(
            WilbertProgramEnrollment.company_id == company_id,
            WilbertProgramEnrollment.program_code == program_code,
            WilbertProgramEnrollment.is_active == True,  # noqa: E712
        )
        .first()
    )


def _get_master_options(db: Session) -> list[ConfigurableItemRegistry]:
    """Fetch all active personalization_option registry items for manufacturing."""
    return (
        db.query(ConfigurableItemRegistry)
        .filter(
            ConfigurableItemRegistry.registry_type == "personalization_option",
            ConfigurableItemRegistry.vertical == "manufacturing",
            ConfigurableItemRegistry.is_active == True,  # noqa: E712
        )
        .order_by(ConfigurableItemRegistry.sort_order)
        .all()
    )
