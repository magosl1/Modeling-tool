"""Shared utilities for financial engines."""
from decimal import Decimal

ZERO = Decimal("0")


def d(val) -> Decimal:
    """Convert any value to Decimal, treating None as zero."""
    if val is None:
        return ZERO
    return Decimal(str(val))
