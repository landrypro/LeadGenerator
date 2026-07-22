from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..models import MapSnapshot


@dataclass(frozen=True, slots=True)
class MapImage:
    content: bytes
    media_type: str = "image/png"


class StaticMapGateway(Protocol):
    async def fetch(self, payload: MapSnapshot) -> MapImage: ...
