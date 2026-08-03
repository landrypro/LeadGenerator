"""Façade de compatibilité des jetons de carte en mémoire."""

from .application.errors import InvalidMapSnapshotGrant, MapSnapshotGrantCapacityReached, MapSnapshotGrantInProgress
from .infrastructure.memory.map_grants import InMemoryMapSnapshotGrantStore

MapSnapshotGrantRegistry = InMemoryMapSnapshotGrantStore

__all__ = [
    "InvalidMapSnapshotGrant",
    "MapSnapshotGrantCapacityReached",
    "MapSnapshotGrantInProgress",
    "MapSnapshotGrantRegistry",
]
