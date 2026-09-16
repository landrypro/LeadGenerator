"""Port historique du verrou Google.

Les adaptateurs mémoire ne sont plus réexportés ici : ils restent des doublures de tests explicites.
"""

from .application.errors import GoogleSearchInProgress
from .application.ports.generation_guard import GenerationGuard

__all__ = ["GenerationGuard", "GoogleSearchInProgress"]
