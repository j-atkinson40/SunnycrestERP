"""
Module registry — defines all available feature modules and their metadata.

Each company has a set of enabled modules stored in the company_modules table.
Navigation, routes, and API endpoints check module access before rendering.
"""

AVAILABLE_MODULES: dict[str, dict] = {
    "core": {
        "label": "Core",
        "description": "Essential business management features including user management, roles, and company settings.",
        "default_enabled": True,
        "locked": True,  # Cannot be disabled
    },
    "products": {
        "label": "Product Catalog",
        "description": "Product database with categories, pricing tiers, and bulk import capabilities.",
        "default_enabled": True,
        "locked": False,
    },
    "inventory": {
        "label": "Inventory Management",
        "description": "Track stock levels, record transactions, set reorder points, and manage warehouse locations.",
        "default_enabled": True,
        "locked": False,
    },
    "sales": {
        "label": "Sales & Customers",
        "description": "Customer database, charge accounts, quotes, sales orders, invoices, and accounts receivable.",
        "default_enabled": True,
        "locked": False,
    },
    "hr_time": {
        "label": "HR & Time Tracking",
        "description": "Flexible time and attendance, early release model, PTO management, employee records, and payroll export.",
        "default_enabled": False,
        "locked": False,
    },
    "driver_delivery": {
        "label": "Driver & Delivery",
        "description": "Route scheduling, mobile delivery confirmation, mileage logging, and stop management.",
        "default_enabled": False,
        "locked": False,
    },
    "pos": {
        "label": "Point of Sale",
        "description": "Counter sales screen, barcode scanning, cash and card payments, thermal receipts, and end-of-day reconciliation.",
        "default_enabled": False,
        "locked": False,
    },
    "project_mgmt": {
        "label": "Project Management",
        "description": "Job creation, task assignment, timelines, resource allocation, and status reporting.",
        "default_enabled": False,
        "locked": False,
    },
    "purchasing": {
        "label": "Purchasing & Vendors",
        "description": "Vendor database, purchase orders, and accounts payable tracking.",
        "default_enabled": True,
        "locked": False,
    },
    "analytics": {
        "label": "Advanced Analytics",
        "description": "Custom dashboard builder, trend analysis, forecasting, and scheduled report delivery.",
        "default_enabled": False,
        "locked": False,
    },
    "safety_management": {
        "label": "Safety Management",
        "description": "OSHA compliance, training records, equipment inspections, incident reporting, SDS management, and audit preparation.",
        "default_enabled": False,
        "locked": False,
    },
}


def get_default_enabled_modules() -> list[str]:
    """Return list of module keys that are enabled by default for new companies."""
    return [key for key, meta in AVAILABLE_MODULES.items() if meta["default_enabled"]]
