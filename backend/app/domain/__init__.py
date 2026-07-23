"""Règles et objets métier indépendants des frameworks et fournisseurs externes."""

from .google_place import GooglePlaceSearchResult, GooglePlaceSearchStats, GooglePlaceSummary
from .identity import (
    AuthenticatedIdentity,
    CreatedSession,
    MembershipIdentity,
    MembershipRole,
    MembershipStatus,
    OrganizationStatus,
    PlatformRole,
    SessionRecord,
    UserIdentity,
    UserStatus,
    capabilities_for,
    normalize_email,
    select_active_organization,
    validate_new_password,
)
from .lead import Lead, SearchResult, SearchStats

__all__ = [
    "AuthenticatedIdentity",
    "CreatedSession",
    "GooglePlaceSearchResult",
    "GooglePlaceSearchStats",
    "GooglePlaceSummary",
    "Lead",
    "MembershipIdentity",
    "MembershipRole",
    "MembershipStatus",
    "OrganizationStatus",
    "PlatformRole",
    "SearchResult",
    "SearchStats",
    "SessionRecord",
    "UserIdentity",
    "UserStatus",
    "capabilities_for",
    "normalize_email",
    "select_active_organization",
    "validate_new_password",
]
