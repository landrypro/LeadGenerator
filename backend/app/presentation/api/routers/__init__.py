from .auth import router as auth_router
from .google_places import router as google_places_router
from .health import router as health_router
from .invitations import router as invitations_router
from .maps import router as maps_router
from .organization import router as organization_router
from .platform import router as platform_router

__all__ = [
    "auth_router",
    "google_places_router",
    "health_router",
    "invitations_router",
    "maps_router",
    "organization_router",
    "platform_router",
]
