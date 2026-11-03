"""Decimal discipline for payroll.

⚠️ `float` IS REJECTED, NOT CONVERTED. The dispatch's constraint is "Decimal
(Numeric), never float", and a conversion helper that accepted floats would
satisfy the letter of that while reintroducing exactly the error it forbids:
`Decimal(0.1)` is `0.1000000000000000055511151231257827021181583404541015625`,
and a dues figure built from it rounds correctly almost always — which is worse
than rounding wrong every time, because it cannot be caught by a test.

So the guard makes a float unexpressible at the boundary rather than asking
callers not to pass one (CLAUDE.md §11 "Removal before recognition").

Strings and ints are accepted: `"24.54"` and `40` are exact.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

#: Excel's ROUND is half-up. Python's Decimal default is ROUND_HALF_EVEN, which
#: disagrees on exact half-cents — 0.125 -> 0.12 rather than 0.13. Every money
#: quantize in this package goes through round2 so the mode is declared once.
CENTS = Decimal("0.01")


def to_decimal(value: object, field: str = "value") -> Decimal:
    """Coerce to Decimal, refusing float outright."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        # bool is an int subclass; a boolean in an arithmetic field is a bug.
        raise TypeError(f"{field}: expected a Decimal-compatible number, got bool")
    if isinstance(value, float):
        raise TypeError(
            f"{field}: float is not accepted ({value!r}). Payroll arithmetic is "
            f"Decimal-exact; pass a Decimal, an int, or a string literal."
        )
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        return Decimal(value)
    raise TypeError(f"{field}: cannot interpret {type(value).__name__} as Decimal")


def round2(value: Decimal) -> Decimal:
    """Round to cents, half-up, matching Excel's ROUND."""
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)
