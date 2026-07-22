"""Point d’entrée ASGI conservé pour uvicorn et les déploiements existants."""

from .bootstrap import create_app

app = create_app()

__all__ = ["app", "create_app"]
