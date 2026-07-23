from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LoginLimitStatus:
    blocked: bool
    retry_after_seconds: int = 0


class LoginRateLimiter(Protocol):
    async def check(self, *, client_address: str, email_dimension: str) -> LoginLimitStatus: ...

    async def record_failure(self, *, client_address: str, email_dimension: str) -> LoginLimitStatus: ...

    async def reset_after_success(self, *, client_address: str, email_dimension: str) -> None: ...
