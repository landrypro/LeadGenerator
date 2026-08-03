"""Façade du verrou Google local mono-instance."""

from .application.errors import GoogleSearchInProgress
from .infrastructure.memory.generation_guard import InMemoryGenerationGuard

GenerationRegistry = InMemoryGenerationGuard

__all__ = ["GenerationRegistry", "GoogleSearchInProgress"]
