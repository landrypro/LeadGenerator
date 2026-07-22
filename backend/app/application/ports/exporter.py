from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from ...domain.lead import Lead


class LeadExporter(Protocol):
    def export(self, leads: Sequence[Lead], search: Mapping[str, Any]) -> bytes: ...
