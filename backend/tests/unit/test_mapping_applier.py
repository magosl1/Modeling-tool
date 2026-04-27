"""Tests for app.services.mapping_applier."""
from __future__ import annotations

import pytest

from app.services.document_extractor import ExtractedDocument, SheetData
from app.services.mapping_applier import apply_mappings, parse_numeric


class TestParseNumeric:
    """Robust numeric parser must handle European, US, and messy inputs."""

    @pytest.mark.parametrize("val,expected", [
        # Native types passthrough
        (None, None),
        (0, 0.0),
        (123, 123.0),
        (876.2, 876.2),
        # European decimals (comma as decimal separator)
        ("876,2", 876.2),
        ("0,13", 0.13),
        ("25,8", 25.8),
        ("164,5", 164.5),
        # European thousands + decimal: dots for thousands, comma decimal
        ("1.218,3", 1218.3),
        ("1.682,4", 1682.4),
        ("1.234.567,89", 1234567.89),
        # US format: comma thousands, dot decimal
        ("1,218.3", 1218.3),
        ("1,234,567.89", 1234567.89),
        ("876.2", 876.2),
        # Plain integers
        ("100", 100.0),
        ("2024", 2024.0),
        # Pure-thousands strings (no decimal part)
        ("1.234", 1234.0),       # European thousands
        ("1.234.567", 1234567.0),
        ("1,234", 1234.0),       # US thousands (only 1,234 — fits pattern)
        # Parentheses negatives
        ("(3,4)", -3.4),
        ("(408,1)", -408.1),
        ("(1.218,3)", -1218.3),
        ("(100)", -100.0),
        # Currency / percent stripping
        ("€876,2", 876.2),
        ("$1,218.30", 1218.30),
        ("19%", 19.0),       # raw value, not divided
        # Trailing/leading minus
        ("-3,4", -3.4),
        ("3,4-", -3.4),
        # Excel error markers (Spanish + English)
        ("#¡REF!", None),
        ("#REF!", None),
        ("#DIV/0!", None),
        ("#NAME?", None),
        ("#¿NOMBRE?", None),
        ("#N/A", None),
        ("#¡VALOR!", None),
        # Blank-equivalents
        ("", None),
        ("   ", None),
        ("-", None),
        ("—", None),
        ("n/a", None),
        # Spaces (incl NBSP)
        ("1 218,3", 1218.3),
        (" 1.218,3", 1218.3),
        # Unparseable garbage
        ("abc", None),
        ("12abc34", None),
    ])
    def test_parse(self, val, expected):
        result = parse_numeric(val)
        if expected is None:
            assert result is None, f"parse_numeric({val!r}) = {result!r}, expected None"
        else:
            assert result == pytest.approx(expected), (
                f"parse_numeric({val!r}) = {result!r}, expected {expected}"
            )


class TestApplyMappings:
    def _doc(self, rows):
        return ExtractedDocument(
            file_type="excel",
            original_filename="test.xlsx",
            file_size_bytes=0,
            sheets=[SheetData(name="S1", rows=rows, row_count=len(rows),
                              col_count=max(len(r) for r in rows))],
        )

    def test_european_format_extraction(self):
        """European numbers must round-trip correctly through the pipeline."""
        doc = self._doc([
            ["P&G (Mn€)", "2024"],
            ["Importe neto de la cifra de negocios", "876,2"],
            ["Aprovisionamientos", "(408,1)"],
            ["Gastos de personal", "(113,1)"],
        ])
        mappings = [
            {"sheet_name": "S1", "row_index": 1, "original_name": "Importe...",
             "mapped_to": "Revenue", "confidence": 0.95},
            {"sheet_name": "S1", "row_index": 2, "original_name": "Aprov.",
             "mapped_to": "Cost of Goods Sold", "confidence": 0.9},
            {"sheet_name": "S1", "row_index": 3, "original_name": "Personal",
             "mapped_to": "SG&A", "confidence": 0.85},
        ]
        result = apply_mappings(doc, mappings)
        assert result["PNL"]["Revenue"][2024] == pytest.approx(876.2)
        assert result["PNL"]["Cost of Goods Sold"][2024] == pytest.approx(-408.1)
        assert result["PNL"]["SG&A"][2024] == pytest.approx(-113.1)

    def test_section_header_row_is_skipped(self):
        """A misclassified section header (whose value column is the year string
        '2024') must NOT inject 2024.0 as a value."""
        doc = self._doc([
            ["Header", "2024"],
            ["P&G (Mn€)", "2024"],   # echoed year text — header row
            ["Ventas", "100,0"],
        ])
        mappings = [
            # LLM misclassifies P&G section header as Revenue
            {"sheet_name": "S1", "row_index": 1, "original_name": "P&G (Mn€)",
             "mapped_to": "Revenue", "confidence": 0.5},
            {"sheet_name": "S1", "row_index": 2, "original_name": "Ventas",
             "mapped_to": "Revenue", "confidence": 0.95},
        ]
        result = apply_mappings(doc, mappings)
        # The 2024 echo must be skipped; only the real 100,0 row counts.
        assert result["PNL"]["Revenue"][2024] == pytest.approx(100.0)

    def test_excel_error_cells_dropped(self):
        doc = self._doc([
            ["Header", "2024"],
            ["Ventas", "#¡REF!"],
            ["Otros ingresos", "25,8"],
        ])
        mappings = [
            {"sheet_name": "S1", "row_index": 1, "original_name": "Ventas",
             "mapped_to": "Revenue", "confidence": 0.95},
            {"sheet_name": "S1", "row_index": 2, "original_name": "Otros",
             "mapped_to": "Other Non-Operating Income / (Expense)",
             "confidence": 0.8},
        ]
        result = apply_mappings(doc, mappings)
        # #¡REF! should NOT inject a bogus value
        assert 2024 not in result["PNL"].get("Revenue", {})
        assert result["PNL"]["Other Non-Operating Income / (Expense)"][2024] == pytest.approx(25.8)
