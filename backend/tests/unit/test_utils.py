"""Tests for app.services.utils — the Decimal coercion helper."""
from decimal import Decimal

from app.services.utils import ZERO, d


def test_d_converts_none_to_zero():
    assert d(None) == ZERO


def test_d_converts_int():
    assert d(5) == Decimal("5")


def test_d_converts_float_without_binary_noise():
    # The whole point of going through str() is avoiding Decimal(0.1) garbage.
    assert d(0.1) == Decimal("0.1")


def test_d_preserves_decimal():
    value = Decimal("3.14")
    assert d(value) == value
