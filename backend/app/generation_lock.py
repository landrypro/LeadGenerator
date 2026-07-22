"""Façade de compatibilité de l’ancien verrou local."""

from .application.errors import AddressGenerationInProgress
from .infrastructure.memory.generation_guard import InMemoryGenerationGuard

AddressGenerationRegistry = InMemoryGenerationGuard

__all__ = ["AddressGenerationInProgress", "AddressGenerationRegistry"]
