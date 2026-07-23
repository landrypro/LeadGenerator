from typing import Protocol


class AsyncResource(Protocol):
    async def close(self) -> None: ...
