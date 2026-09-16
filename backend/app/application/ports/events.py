from typing import Protocol


class TechnicalEventLogger(Protocol):
    """Événements techniques à charge strictement contrôlée."""

    def info(self, event: str, *, request_id: str = "", **fields: str | int) -> None: ...

    def warning(self, event: str, *, request_id: str = "", **fields: str | int) -> None: ...

    def error(self, event: str, *, request_id: str = "", **fields: str | int) -> None: ...


class NullTechnicalEventLogger:
    def info(self, event: str, *, request_id: str = "", **fields: str | int) -> None:
        del event, request_id, fields

    def warning(self, event: str, *, request_id: str = "", **fields: str | int) -> None:
        del event, request_id, fields

    def error(self, event: str, *, request_id: str = "", **fields: str | int) -> None:
        del event, request_id, fields
