"""Façade de compatibilité des anciens schémas HTTP."""

from .presentation.api.schemas import (
    ExportRequest,
    Lead,
    LeadGenerationRequest,
    LeadGenerationResponse,
    MapPoint,
    MapSnapshotRequest,
    MapSnapshotTokenRequest,
    RequesterInfo,
    SearchRequest,
    SearchResponse,
    SearchStats,
)

__all__ = [
    "ExportRequest",
    "Lead",
    "LeadGenerationRequest",
    "LeadGenerationResponse",
    "MapPoint",
    "MapSnapshotRequest",
    "MapSnapshotTokenRequest",
    "RequesterInfo",
    "SearchRequest",
    "SearchResponse",
    "SearchStats",
]
