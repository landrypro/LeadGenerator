from collections.abc import Mapping, Sequence
from typing import Any

from ...domain.lead import Lead
from ..errors import EmptyExportError
from ..ports.exporter import LeadExporter


class ExportLeadsUseCase:
    def __init__(self, exporter: LeadExporter) -> None:
        self._exporter = exporter

    def execute(self, leads: Sequence[Lead], search: Mapping[str, Any]) -> bytes:
        if not leads:
            raise EmptyExportError
        return self._exporter.export(leads, search)
