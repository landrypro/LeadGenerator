import asyncio

from redis.asyncio import Redis

from backend.app.application.ports.health import DependencyHealth


class RedisResource:
    def __init__(self, url: str, *, connect_timeout_seconds: float, max_connections: int) -> None:
        self._connect_timeout_seconds = connect_timeout_seconds
        self._client: Redis = Redis.from_url(
            url,
            decode_responses=False,
            socket_connect_timeout=connect_timeout_seconds,
            socket_timeout=connect_timeout_seconds,
            max_connections=max_connections,
        )

    @property
    def name(self) -> str:
        return "redis"

    @property
    def client(self) -> Redis:
        return self._client

    async def check(self) -> DependencyHealth:
        try:
            async with asyncio.timeout(self._connect_timeout_seconds):
                await self._client.ping()
        except Exception:
            return DependencyHealth(name=self.name, state="unavailable")
        return DependencyHealth(name=self.name, state="ok")

    async def close(self) -> None:
        await self._client.aclose()
