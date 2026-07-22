"""Façade de compatibilité de l’export Excel historique."""

from .infrastructure.export.excel import (
    DANGEROUS_EXCEL_PREFIXES,
    HEADERS,
    ExcelLeadExporter,
    build_workbook,
    safe_excel_value,
)

__all__ = [
    "DANGEROUS_EXCEL_PREFIXES",
    "HEADERS",
    "ExcelLeadExporter",
    "build_workbook",
    "safe_excel_value",
]
