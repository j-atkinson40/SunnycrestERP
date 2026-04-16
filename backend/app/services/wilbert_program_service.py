"""Wilbert Program Service — manages Wilbert program enrollments for licensees.

EXTENDED: works alongside existing onboarding_service.py
NEW: no existing equivalent for Wilbert program management
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Company, WilbertProgramEnrollment

logger = logging.getLogger(__name__)


WILBERT_PROGRAMS = {
    "vault": {
        "code": "vault",
        "name": "Burial Vault Program",
        "tier": 2,
        "default_enabled": True,
        "description": "Wilbert burial vault manufacturing and distribution",
    },
    "urn": {
        "code": "urn",
        "name": "Urn Program",
        "tier": 2,
        "default_enabled": True,
        "description": "Wilbert urn catalog sales to funeral homes",
    },
    "casket": {
        "code": "casket",
        "name": "Casket Program",
        "tier": 3,
        "default_enabled": False,
        "description": "Wilbert casket sales through funeral homes",
    },
    "monument": {
        "code": "monument",
        "name": "Monument Program",
        "tier": 3,
        "default_enabled": False,
        "description": "Memorial Monuments products through Wilbert",
    },
    "chemical": {
        "code": "chemical",
        "name": "Embalming Chemical Program",
        "tier": 3,
        "default_enabled": False,
        "description": "Champion, Pierce, Dodge and other embalming chemical brands",
    },
    "stationery": {
        "code": "stationery",
        "name": "Memorial Stationery",
        "tier": 2,
        "default_enabled": True,
        "can_disable": True,
        "program_type": "platform_native",
        "description": "Memorial stationery for families — programs, cards, bookmarks. Territory revenue on every order. No handling required by default.",
        "catalog_key": "stationery_catalog",
        "composer": "stationery_composer",
        "fulfillment_options": [
            {"key": "bridgeable_partner", "label": "Through Bridgeable (recommended)", "description": "We handle print, QC, and shipping. You earn territory revenue.", "is_default": True, "requires_config": False},
            {"key": "self_fulfill", "label": "I handle fulfillment", "description": "You manage print vendor and delivery. We handle ordering and payment.", "is_default": False, "requires_config": True},
            {"key": "funeral_home_vendor", "label": "Route to funeral home's vendor", "description": "Order recorded, revenue tracked, funeral home manages production.", "is_default": False, "requires_config": False},
        ],
        "settings_tabs": ["general", "fulfillment", "design_approvals", "notifications", "permissions"],
    },
    "digital_products": {
        "code": "digital_products",
        "name": "Digital Products and Memorial Experiences",
        "tier": 1,
        "default_enabled": True,
        "can_disable": False,
        "program_type": "platform_native",
        "description": "Memory books, tribute videos, digital memorials, legacy portraits. Territory revenue generated automatically. No handling required.",
        "catalog_key": "digital_products_catalog",
        "composer": "digital_composer",
        "settings_tabs": ["general", "revenue_visibility", "payout_settings", "notifications", "permissions"],
    },
}


class WilbertProgramService:
    """Manages Wilbert program enrollments for licensee companies."""

    @staticmethod
    def get_catalog(db: Session = None, company_id: str = None) -> dict:
        """Return the full WILBERT_PROGRAMS catalog dict with enrollment status.

        If db and company_id are provided, each program entry includes
        'enrolled' (bool) and 'enrollment' (dict or None) fields.
        """
        import copy

        catalog = copy.deepcopy(WILBERT_PROGRAMS)

        if db and company_id:
            enrollments = (
                db.query(WilbertProgramEnrollment)
                .filter(WilbertProgramEnrollment.company_id == company_id)
                .all()
            )
            enrollment_map = {e.program_code: e for e in enrollments}

            for code, program in catalog.items():
                enrollment = enrollment_map.get(code)
                if enrollment and enrollment.is_active:
                    program["enrolled"] = True
                    program["enrollment"] = {
                        "id": enrollment.id,
                        "is_active": enrollment.is_active,
                        "program_type": enrollment.program_type,
                        "fulfillment_path": enrollment.fulfillment_path,
                        "territory_ids": enrollment.territory_ids,
                        "uses_vault_territory": enrollment.uses_vault_territory,
                    }
                else:
                    program["enrolled"] = False
                    program["enrollment"] = None

        return catalog

    @staticmethod
    def get_company_programs(db: Session, company_id: str) -> list[WilbertProgramEnrollment]:
        """Query all active program enrollments for a company."""
        return (
            db.query(WilbertProgramEnrollment)
            .filter(
                WilbertProgramEnrollment.company_id == company_id,
                WilbertProgramEnrollment.is_active == True,  # noqa: E712
            )
            .order_by(WilbertProgramEnrollment.program_code)
            .all()
        )

    @staticmethod
    def enroll_in_program(
        db: Session,
        company_id: str,
        program_code: str,
        territory_ids: list[str] | None = None,
        uses_vault_territory: bool = True,
        enabled_product_ids: list[str] | None = None,
        program_type: str | None = None,
        fulfillment_path: str | None = None,
        personalization_config: dict | None = None,
        permissions_config: dict | None = None,
        notifications_config: dict | None = None,
        fulfillment_config: dict | None = None,
        payout_config: dict | None = None,
    ) -> WilbertProgramEnrollment:
        """Create a new program enrollment record.

        If an inactive enrollment exists for this program, reactivate it
        instead of creating a duplicate.
        """
        program_def = WILBERT_PROGRAMS.get(program_code)
        if not program_def:
            raise ValueError(f"Unknown program code: {program_code}")

        # Check for existing (possibly inactive) enrollment
        existing = (
            db.query(WilbertProgramEnrollment)
            .filter(
                WilbertProgramEnrollment.company_id == company_id,
                WilbertProgramEnrollment.program_code == program_code,
            )
            .first()
        )

        if existing:
            existing.is_active = True
            existing.territory_ids = territory_ids
            existing.uses_vault_territory = uses_vault_territory
            existing.enabled_product_ids = enabled_product_ids
            if program_type is not None:
                existing.program_type = program_type
            if fulfillment_path is not None:
                existing.fulfillment_path = fulfillment_path
            if personalization_config is not None:
                existing.personalization_config = personalization_config
            if permissions_config is not None:
                existing.permissions_config = permissions_config
            if notifications_config is not None:
                existing.notifications_config = notifications_config
            if fulfillment_config is not None:
                existing.fulfillment_config = fulfillment_config
            if payout_config is not None:
                existing.payout_config = payout_config
            existing.updated_at = datetime.now(timezone.utc)
            db.flush()
            logger.info(
                "Reactivated program enrollment: company=%s program=%s",
                company_id,
                program_code,
            )
            return existing

        enrollment = WilbertProgramEnrollment(
            id=str(uuid.uuid4()),
            company_id=company_id,
            program_code=program_code,
            program_name=program_def["name"],
            is_active=True,
            territory_ids=territory_ids,
            uses_vault_territory=uses_vault_territory,
            enabled_product_ids=enabled_product_ids,
            program_type=program_type or program_def.get("program_type", "wilbert"),
            fulfillment_path=fulfillment_path,
            personalization_config=personalization_config,
            permissions_config=permissions_config,
            notifications_config=notifications_config,
            fulfillment_config=fulfillment_config,
            payout_config=payout_config,
        )
        db.add(enrollment)
        db.flush()
        logger.info(
            "Enrolled company=%s in program=%s",
            company_id,
            program_code,
        )
        return enrollment

    @staticmethod
    def unenroll_from_program(
        db: Session, company_id: str, program_code: str
    ) -> bool:
        """Soft-delete a program enrollment. Returns True if found and deactivated."""
        enrollment = (
            db.query(WilbertProgramEnrollment)
            .filter(
                WilbertProgramEnrollment.company_id == company_id,
                WilbertProgramEnrollment.program_code == program_code,
                WilbertProgramEnrollment.is_active == True,  # noqa: E712
            )
            .first()
        )
        if not enrollment:
            return False

        enrollment.is_active = False
        enrollment.updated_at = datetime.now(timezone.utc)
        db.flush()
        logger.info(
            "Unenrolled company=%s from program=%s",
            company_id,
            program_code,
        )
        return True

    @staticmethod
    def configure_program_products(
        db: Session,
        company_id: str,
        program_code: str,
        enabled_product_ids: list[str],
    ) -> WilbertProgramEnrollment | None:
        """Update the enabled product IDs for a program enrollment."""
        enrollment = (
            db.query(WilbertProgramEnrollment)
            .filter(
                WilbertProgramEnrollment.company_id == company_id,
                WilbertProgramEnrollment.program_code == program_code,
                WilbertProgramEnrollment.is_active == True,  # noqa: E712
            )
            .first()
        )
        if not enrollment:
            logger.warning(
                "configure_program_products: no active enrollment for company=%s program=%s",
                company_id,
                program_code,
            )
            return None

        enrollment.enabled_product_ids = enabled_product_ids
        enrollment.updated_at = datetime.now(timezone.utc)
        db.flush()
        return enrollment

    @staticmethod
    def configure_program_territory(
        db: Session,
        company_id: str,
        program_code: str,
        territory_ids: list[str],
        uses_vault_territory: bool,
    ) -> WilbertProgramEnrollment | None:
        """Update the territory configuration for a program enrollment."""
        enrollment = (
            db.query(WilbertProgramEnrollment)
            .filter(
                WilbertProgramEnrollment.company_id == company_id,
                WilbertProgramEnrollment.program_code == program_code,
                WilbertProgramEnrollment.is_active == True,  # noqa: E712
            )
            .first()
        )
        if not enrollment:
            logger.warning(
                "configure_program_territory: no active enrollment for company=%s program=%s",
                company_id,
                program_code,
            )
            return None

        enrollment.territory_ids = territory_ids
        enrollment.uses_vault_territory = uses_vault_territory
        enrollment.updated_at = datetime.now(timezone.utc)
        db.flush()
        return enrollment

    @staticmethod
    def get_effective_territory(
        db: Session, company_id: str, program_code: str
    ) -> dict:
        """Return the effective territory for a program.

        Falls back to the vault program territory if uses_vault_territory is True,
        then to the company's settings for wilbert_vault_territory.
        """
        enrollment = (
            db.query(WilbertProgramEnrollment)
            .filter(
                WilbertProgramEnrollment.company_id == company_id,
                WilbertProgramEnrollment.program_code == program_code,
                WilbertProgramEnrollment.is_active == True,  # noqa: E712
            )
            .first()
        )

        if enrollment and enrollment.territory_ids and not enrollment.uses_vault_territory:
            return {
                "source": "program",
                "program_code": program_code,
                "territory_ids": enrollment.territory_ids,
            }

        # Fall back to vault program territory
        if program_code != "vault":
            vault_enrollment = (
                db.query(WilbertProgramEnrollment)
                .filter(
                    WilbertProgramEnrollment.company_id == company_id,
                    WilbertProgramEnrollment.program_code == "vault",
                    WilbertProgramEnrollment.is_active == True,  # noqa: E712
                )
                .first()
            )
            if vault_enrollment and vault_enrollment.territory_ids:
                return {
                    "source": "vault_program",
                    "program_code": "vault",
                    "territory_ids": vault_enrollment.territory_ids,
                }

        # Fall back to company settings
        company = db.query(Company).filter(Company.id == company_id).first()
        if company:
            settings = company.settings if hasattr(company, "settings") else {}
            if settings and isinstance(settings, dict):
                territory = settings.get("wilbert_vault_territory")
                if territory:
                    return {
                        "source": "company_settings",
                        "territory_code": territory,
                        "territory_ids": [],
                    }

        return {"source": "none", "territory_ids": []}

    @staticmethod
    def setup_defaults(db: Session, company_id: str) -> list[WilbertProgramEnrollment]:
        """Enroll in default programs (vault, urn, stationery, digital_products).

        Called during onboarding. Idempotent — skips already-enrolled programs.
        Tier 1 and 2 programs with default_enabled=True are enrolled.
        """
        enrolled = []
        for code, program_def in WILBERT_PROGRAMS.items():
            if not program_def.get("default_enabled"):
                continue
            if program_def.get("tier", 99) > 2:
                continue

            # Build extra kwargs for platform-native programs
            extra_kwargs: dict = {}
            if code == "stationery":
                extra_kwargs["fulfillment_path"] = "bridgeable_partner"
                extra_kwargs["program_type"] = "platform_native"
            elif code == "digital_products":
                extra_kwargs["permissions_config"] = {"view_revenue": ["admin"]}
                extra_kwargs["program_type"] = "platform_native"

            enrollment = WilbertProgramService.enroll_in_program(
                db, company_id, code, **extra_kwargs
            )
            enrolled.append(enrollment)
        db.commit()
        logger.info(
            "Setup default programs for company=%s: %s",
            company_id,
            [e.program_code for e in enrolled],
        )
        return enrolled
