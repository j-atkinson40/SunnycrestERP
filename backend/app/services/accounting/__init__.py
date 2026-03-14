"""Accounting provider abstraction layer.

Supports toggling between accounting providers (Sage CSV, QuickBooks Online)
on a per-tenant basis. Each provider implements the AccountingProvider ABC.
"""

from app.services.accounting.base import AccountingProvider
from app.services.accounting.factory import get_provider

__all__ = ["AccountingProvider", "get_provider"]
