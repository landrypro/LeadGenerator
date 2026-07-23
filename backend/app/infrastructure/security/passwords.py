import asyncio

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type


class Argon2PasswordHasher:
    def __init__(self) -> None:
        self._hasher = PasswordHasher(
            time_cost=3,
            memory_cost=65_536,
            parallelism=4,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )
        self._dummy_hash = self._hasher.hash("mot-de-passe-factice-non-utilisable")

    async def hash(self, password: str) -> str:
        return await asyncio.to_thread(self._hasher.hash, password)

    async def verify(self, password: str, encoded_hash: str) -> bool:
        return await asyncio.to_thread(self._verify_sync, password, encoded_hash)

    def _verify_sync(self, password: str, encoded_hash: str) -> bool:
        try:
            return bool(self._hasher.verify(encoded_hash, password))
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return False

    async def verify_dummy(self, password: str) -> None:
        await self.verify(password, self._dummy_hash)

    async def needs_rehash(self, encoded_hash: str) -> bool:
        try:
            return self._hasher.check_needs_rehash(encoded_hash)
        except InvalidHashError:
            return True
