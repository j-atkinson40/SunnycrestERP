"""THE ROUNDING POLICY — stated once (audit #2, Session Four).

Money rounds at DEFINED boundaries: line totals, tax amounts, grand
totals. Half-cent behavior is BANKER'S ROUNDING (ROUND_HALF_EVEN) —
verified as the policy of record, not picked fresh: the existing
invoice/statement core math (`sales_service._compute_line_total`,
`_compute_totals`, `tax_service.compute_tax`) has always used
`quantize(Decimal("0.01"))` with Python's default rounding, which IS
half-even. This module makes that explicit and gives every computation
site one helper to share.

(ROUND_HALF_UP appears elsewhere in derived-pricing utilities — finance
charges, price increases, inter-licensee markups. Those are pricing
POLICIES, not invoice arithmetic; they keep their own explicit rounding.)
"""
from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal

CENT = Decimal("0.01")


def round_money(value) -> Decimal:
    """Round to the cent — banker's rounding, the invoice-math policy."""
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_EVEN)


def line_total(quantity, unit_price) -> Decimal:
    """A line's total: qty × price, rounded at the line boundary."""
    return round_money(Decimal(str(quantity)) * Decimal(str(unit_price)))
