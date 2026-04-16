"""Onboarding Summary Service — generates final onboarding summary and first briefing data.

NEW: no existing equivalent. Aggregates data from all onboarding steps to produce
a comprehensive summary and initial morning briefing content.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.models import (
    Company,
    CompanyEntity,
    ConfigurableItemRegistry,
    DataImportSession,
    EmployeeProfile,
    Location,
    Product,
    TenantItemConfig,
    WilbertProgramEnrollment,
)

logger = logging.getLogger(__name__)


class OnboardingSummaryService:
    """Generates onboarding completion summaries and first briefing data."""

    @staticmethod
    def generate_summary(db: Session, company_id: str) -> dict:
        """Count everything set up during onboarding and calculate value metrics.

        Returns: programs, products, locations, team, funeral_homes, cemeteries,
        compliance_items, historical_orders, years_of_history, pricing_configured,
        neighboring_licensees, time_savings, roi_estimate.
        """
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            return {"error": "Company not found"}

        # Programs enrolled
        programs = (
            db.query(WilbertProgramEnrollment)
            .filter(
                WilbertProgramEnrollment.company_id == company_id,
                WilbertProgramEnrollment.is_active == True,  # noqa: E712
            )
            .all()
        )
        program_summary = [
            {"code": p.program_code, "name": p.program_name}
            for p in programs
        ]

        # Products
        product_count = (
            db.query(sa_func.count(Product.id))
            .filter(
                Product.company_id == company_id,
                Product.is_active == True,  # noqa: E712
            )
            .scalar()
            or 0
        )
        products_with_price = (
            db.query(sa_func.count(Product.id))
            .filter(
                Product.company_id == company_id,
                Product.is_active == True,  # noqa: E712
                Product.price.isnot(None),
                Product.price > 0,
            )
            .scalar()
            or 0
        )

        # Locations
        location_count = (
            db.query(sa_func.count(Location.id))
            .filter(Location.company_id == company_id)
            .scalar()
            or 0
        )

        # Team members
        employee_count = (
            db.query(sa_func.count(EmployeeProfile.id))
            .filter(EmployeeProfile.company_id == company_id)
            .scalar()
            or 0
        )

        # Funeral homes
        fh_count = (
            db.query(sa_func.count(CompanyEntity.id))
            .filter(
                CompanyEntity.company_id == company_id,
                CompanyEntity.is_funeral_home == True,  # noqa: E712
            )
            .scalar()
            or 0
        )

        # Cemeteries
        cemetery_count = (
            db.query(sa_func.count(CompanyEntity.id))
            .filter(
                CompanyEntity.company_id == company_id,
                CompanyEntity.is_cemetery == True,  # noqa: E712
            )
            .scalar()
            or 0
        )

        # Compliance items enabled
        compliance_items = (
            db.query(sa_func.count(TenantItemConfig.id))
            .filter(
                TenantItemConfig.company_id == company_id,
                TenantItemConfig.registry_type == "compliance",
                TenantItemConfig.is_enabled == True,  # noqa: E712
            )
            .scalar()
            or 0
        )

        # Import history
        import_sessions = (
            db.query(DataImportSession)
            .filter(
                DataImportSession.company_id == company_id,
                DataImportSession.status == "completed",
            )
            .all()
        )
        total_imported = sum(s.imported_records or 0 for s in import_sessions)

        # Years of history
        years_of_history = 0.0
        if import_sessions:
            date_starts = [s.date_range_start for s in import_sessions if s.date_range_start]
            date_ends = [s.date_range_end for s in import_sessions if s.date_range_end]
            if date_starts and date_ends:
                earliest = min(date_starts)
                latest = max(date_ends)
                years_of_history = round((latest - earliest).days / 365.25, 1)

        # Neighboring licensees
        neighboring_count = (
            db.query(sa_func.count(WilbertProgramEnrollment.id))
            .filter(
                WilbertProgramEnrollment.program_code == "vault",
                WilbertProgramEnrollment.is_active == True,  # noqa: E712
                WilbertProgramEnrollment.company_id != company_id,
            )
            .scalar()
            or 0
        )

        # Time savings estimate (hours/month)
        # Based on what was set up: each feature area saves estimated time
        time_savings = _estimate_time_savings(
            fh_count=fh_count,
            product_count=product_count,
            compliance_items=compliance_items,
            has_import=total_imported > 0,
            employee_count=employee_count,
        )

        # ROI estimate
        roi = _estimate_roi(
            fh_count=fh_count,
            monthly_orders_estimate=fh_count * 4,  # ~4 orders/FH/month
            time_savings_hours=time_savings["total_hours"],
        )

        return {
            "company_name": company.name,
            "programs": program_summary,
            "program_count": len(programs),
            "product_count": product_count,
            "products_with_pricing": products_with_price,
            "pricing_configured": products_with_price > 0,
            "location_count": location_count,
            "employee_count": employee_count,
            "funeral_home_count": fh_count,
            "cemetery_count": cemetery_count,
            "compliance_items_enabled": compliance_items,
            "historical_orders_imported": total_imported,
            "import_sessions": len(import_sessions),
            "years_of_history": years_of_history,
            "neighboring_licensees": neighboring_count,
            "time_savings": time_savings,
            "roi_estimate": roi,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def generate_first_briefing_data(db: Session, company_id: str) -> dict:
        """Generate morning briefing data for day one after onboarding.

        Returns compliance items due soon, FH count, product readiness,
        and recommendations for the first week.
        """
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            return {"error": "Company not found"}

        # Compliance items needing attention
        compliance_configs = (
            db.query(TenantItemConfig)
            .filter(
                TenantItemConfig.company_id == company_id,
                TenantItemConfig.registry_type == "compliance",
                TenantItemConfig.is_enabled == True,  # noqa: E712
            )
            .all()
        )

        compliance_summary = []
        for config in compliance_configs:
            item_config = config.config or {}
            frequency = item_config.get("frequency", "unknown")
            compliance_summary.append({
                "item_key": config.item_key,
                "display_name": config.display_name,
                "frequency": frequency,
                "needs_initial_setup": True,  # First time — all need setup
            })

        # Funeral home stats
        fh_count = (
            db.query(sa_func.count(CompanyEntity.id))
            .filter(
                CompanyEntity.company_id == company_id,
                CompanyEntity.is_funeral_home == True,  # noqa: E712
            )
            .scalar()
            or 0
        )

        # Product readiness
        product_count = (
            db.query(sa_func.count(Product.id))
            .filter(
                Product.company_id == company_id,
                Product.is_active == True,  # noqa: E712
            )
            .scalar()
            or 0
        )
        products_without_price = (
            db.query(sa_func.count(Product.id))
            .filter(
                Product.company_id == company_id,
                Product.is_active == True,  # noqa: E712
                (Product.price.is_(None)) | (Product.price == 0),
            )
            .scalar()
            or 0
        )

        # First week recommendations
        recommendations = []

        if products_without_price > 0:
            recommendations.append({
                "priority": "high",
                "action": "Set pricing",
                "detail": f"{products_without_price} products still need prices set before you can invoice.",
                "link": "/products",
            })

        if fh_count == 0:
            recommendations.append({
                "priority": "high",
                "action": "Add funeral homes",
                "detail": "No funeral home customers found. Add your customers to start taking orders.",
                "link": "/crm",
            })

        if compliance_summary:
            recommendations.append({
                "priority": "medium",
                "action": "Review compliance calendar",
                "detail": f"{len(compliance_summary)} compliance items are tracked. Review dates and set reminders.",
                "link": "/compliance",
            })

        recommendations.append({
            "priority": "low",
            "action": "Try entering an order",
            "detail": "Place a test order to see the full workflow in action.",
            "link": "/orders/new",
        })

        return {
            "company_name": company.name,
            "date": datetime.now(timezone.utc).date().isoformat(),
            "compliance_items": compliance_summary,
            "compliance_count": len(compliance_summary),
            "funeral_home_count": fh_count,
            "product_count": product_count,
            "products_needing_prices": products_without_price,
            "recommendations": recommendations,
            "welcome_message": (
                f"Welcome to Bridgeable, {company.name}! Your workspace is set up with "
                f"{product_count} products, {fh_count} funeral homes, and "
                f"{len(compliance_summary)} compliance items being tracked. "
                f"Here's what to focus on this week."
            ),
        }


def _estimate_time_savings(
    fh_count: int,
    product_count: int,
    compliance_items: int,
    has_import: bool,
    employee_count: int,
) -> dict:
    """Estimate monthly time savings in hours based on what was configured."""
    savings = {}

    # Order processing: ~5 min/order saved with quick orders, ~100 orders/month for avg licensee
    orders_per_month = max(fh_count * 4, 20)
    savings["order_processing"] = round(orders_per_month * 5 / 60, 1)

    # Invoicing/billing: ~2 hours/month for statement generation
    savings["invoicing"] = 2.0 if fh_count > 0 else 0.0

    # Compliance tracking: ~30 min/item/month for manual tracking
    savings["compliance"] = round(compliance_items * 0.5, 1)

    # Delivery scheduling: ~1 hour/day saved
    savings["scheduling"] = 20.0 if fh_count > 5 else 10.0

    # Data entry elimination from import
    savings["data_entry"] = 8.0 if has_import else 0.0

    # Safety program: ~4 hours/month
    savings["safety"] = 4.0 if employee_count > 0 else 0.0

    total = sum(savings.values())
    savings["total_hours"] = round(total, 1)

    return savings


def _estimate_roi(
    fh_count: int,
    monthly_orders_estimate: int,
    time_savings_hours: float,
) -> dict:
    """Estimate ROI based on time savings and operational improvements."""
    # Assume $35/hour for office staff time
    hourly_rate = 35.0
    monthly_labor_savings = round(time_savings_hours * hourly_rate, 2)

    # Reduced errors: ~2% of orders have errors costing ~$50 each to fix
    error_savings = round(monthly_orders_estimate * 0.02 * 50, 2)

    # Faster collections: ~1% improvement in collection speed
    avg_monthly_revenue = monthly_orders_estimate * 800  # ~$800 avg order
    collection_improvement = round(avg_monthly_revenue * 0.01 * 0.05, 2)  # 5% of 1%

    total_monthly = monthly_labor_savings + error_savings + collection_improvement

    return {
        "monthly_labor_savings": monthly_labor_savings,
        "monthly_error_reduction": error_savings,
        "monthly_collection_improvement": collection_improvement,
        "total_monthly_value": round(total_monthly, 2),
        "total_annual_value": round(total_monthly * 12, 2),
        "assumptions": {
            "hourly_rate": hourly_rate,
            "monthly_orders": monthly_orders_estimate,
            "avg_order_value": 800,
        },
    }
