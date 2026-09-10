from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.application.errors import (
    GoogleSearchInProgress,
    InvalidGoogleSelectionGrant,
    InvalidMapSnapshotGrant,
    MapSnapshotGrantInProgress,
)
from backend.app.application.models import (
    GoogleAccessOwner,
    GooglePlaceSearchCriteria,
    GoogleSearchQuotaPolicy,
    MapSnapshot,
)
from backend.app.application.ports.maps import MapImage
from backend.app.application.ports.places import PlaceCandidate
from backend.app.application.use_cases import GetMapSnapshotUseCase, SearchGooglePlacesUseCase
from backend.app.bootstrap import create_app
from backend.app.config import Settings
from backend.app.container import AppContainer
from backend.app.domain.identity import (
    AuthenticatedIdentity,
    MembershipIdentity,
    MembershipRole,
    MembershipStatus,
    OrganizationStatus,
    UserIdentity,
    UserStatus,
)
from backend.app.infrastructure.clock import SystemClock
from backend.app.infrastructure.google.quota_policy import SettingsGoogleSearchPolicyProvider
from backend.app.infrastructure.redis import (
    RedisGenerationGuard,
    RedisGoogleSearchQuota,
    RedisGoogleSelectionGrantStore,
    RedisMapSnapshotGrantStore,
    RedisResource,
)

pytestmark = pytest.mark.integration

CSRF_TOKEN = "redis-google-state-csrf"
SESSION_TOKEN = "redis-google-state-session"


def redis_url() -> str:
    value = os.environ.get("TEST_REDIS_URL", "")
    if value:
        return value
    if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
        pytest.fail("TEST_REDIS_URL est obligatoire pour les protections Google Redis.")
    pytest.skip("TEST_REDIS_URL est requis pour les protections Google Redis.")


def owner() -> GoogleAccessOwner:
    return GoogleAccessOwner(user_id=uuid4(), organization_id=uuid4())


async def cleanup(resource: RedisResource, environment: str) -> None:
    keys = [key async for key in resource.client.scan_iter(match=f"prospect:{{{environment}}}:v1:*")]
    if keys:
        await resource.client.delete(*keys)


async def test_redis_adapters_share_lock_and_tokens_between_two_pools() -> None:
    environment = f"google-state-{uuid4().hex}"
    first_resource = RedisResource(redis_url(), connect_timeout_seconds=2, max_connections=3)
    second_resource = RedisResource(redis_url(), connect_timeout_seconds=2, max_connections=3)
    access_owner = owner()
    first_guard = RedisGenerationGuard(first_resource.client, environment=environment, ttl_seconds=2)
    second_guard = RedisGenerationGuard(second_resource.client, environment=environment, ttl_seconds=2)
    first_maps = RedisMapSnapshotGrantStore(first_resource.client, environment=environment, ttl_seconds=10)
    second_maps = RedisMapSnapshotGrantStore(second_resource.client, environment=environment, ttl_seconds=10)
    first_selection = RedisGoogleSelectionGrantStore(first_resource.client, environment=environment, ttl_seconds=10)
    second_selection = RedisGoogleSelectionGrantStore(second_resource.client, environment=environment, ttl_seconds=10)
    try:
        async with first_guard.hold(access_owner):
            with pytest.raises(GoogleSearchInProgress):
                async with second_guard.hold(access_owner):
                    pass
        async with second_guard.hold(access_owner):
            pass

        map_token = await first_maps.issue(MapSnapshot(46.8139, -71.208, 15), access_owner)
        intruder = GoogleAccessOwner(user_id=uuid4(), organization_id=access_owner.organization_id)
        with pytest.raises(InvalidMapSnapshotGrant):
            async with second_maps.redeem(map_token, intruder):
                pass
        async with second_maps.redeem(map_token, access_owner) as snapshot:
            assert snapshot.center_latitude == 46.8139
            with pytest.raises(MapSnapshotGrantInProgress):
                async with first_maps.redeem(map_token, access_owner):
                    pass
        with pytest.raises(InvalidMapSnapshotGrant):
            async with first_maps.redeem(map_token, access_owner):
                pass

        selection_token = await first_selection.issue(
            ("place-a", "place-b", "place-a"), access_owner, now=datetime.now(UTC)
        )
        assert await second_selection.resolve(selection_token, access_owner, now=datetime.now(UTC)) == (
            "place-a",
            "place-b",
        )
        await second_resource.client.script_flush()
        assert await second_selection.resolve(selection_token, access_owner, now=datetime.now(UTC)) == (
            "place-a",
            "place-b",
        )
        with pytest.raises(InvalidGoogleSelectionGrant):
            await second_selection.resolve(selection_token, owner(), now=datetime.now(UTC))

        key = first_selection._key(selection_token)
        assert await first_resource.client.pttl(key) > 0
        assert selection_token not in key and "place-a" not in key
        await first_resource.client.pexpire(key, 1)
        await asyncio.sleep(0.05)
        with pytest.raises(InvalidGoogleSelectionGrant):
            await second_selection.resolve(selection_token, access_owner, now=datetime.now(UTC))
    finally:
        await cleanup(first_resource, environment)
        await first_resource.close()
        await second_resource.close()


async def test_redis_quota_is_atomic_idempotent_and_bounded_under_concurrency() -> None:
    environment = f"google-quota-{uuid4().hex}"
    first_resource = RedisResource(redis_url(), connect_timeout_seconds=2, max_connections=16)
    second_resource = RedisResource(redis_url(), connect_timeout_seconds=2, max_connections=16)
    first_quota = RedisGoogleSearchQuota(first_resource.client, environment=environment)
    second_quota = RedisGoogleSearchQuota(second_resource.client, environment=environment)
    now = datetime(2026, 8, 25, 12, tzinfo=UTC)
    policy = GoogleSearchQuotaPolicy(True, 20, 100, 80, "test_policy")
    access_owner = owner()
    try:
        idempotent_owner = owner()
        idempotent_operation = uuid4()
        first = await first_quota.reserve(idempotent_owner, policy, idempotent_operation, now=now)
        replayed = await second_quota.reserve(idempotent_owner, policy, idempotent_operation, now=now)
        assert first.allowed is True
        assert replayed == first
        idempotent_keys = first_quota._keys(idempotent_owner, now.date().isoformat(), idempotent_operation)
        assert await first_resource.client.get(idempotent_keys[0]) == b"1"
        assert await first_resource.client.get(idempotent_keys[1]) == b"1"

        accepted = await asyncio.gather(
            *(
                (first_quota if index % 2 else second_quota).reserve(access_owner, policy, uuid4(), now=now)
                for index in range(20)
            )
        )
        assert all(reservation.allowed for reservation in accepted)
        assert sum(reservation.user_warning_created for reservation in accepted) == 1

        denied_operation = uuid4()
        denied = await first_quota.reserve(access_owner, policy, denied_operation, now=now)
        replayed_denial = await second_quota.reserve(access_owner, policy, denied_operation, now=now)
        assert denied.allowed is False
        assert denied.scope == "user"
        assert replayed_denial == denied

        period = now.date().isoformat()
        user_key, organization_key, operation_key, warning_key, _ = first_quota._keys(
            access_owner, period, denied_operation
        )
        assert await first_resource.client.get(user_key) == b"20"
        assert await first_resource.client.get(organization_key) == b"20"
        assert await first_resource.client.pttl(user_key) > 0
        assert await first_resource.client.pttl(organization_key) > 0
        assert await first_resource.client.pttl(operation_key) > 0
        assert await first_resource.client.pttl(warning_key) > 0

        organization_id = uuid4()
        organization_policy = GoogleSearchQuotaPolicy(True, 20, 100, 80, "test_policy")
        organization_owners = [GoogleAccessOwner(uuid4(), organization_id) for _ in range(5)]

        # Keep overlap between both pools without turning the Docker/WSL port forward
        # into the subject under test by opening one hundred TCP connections at once.
        reservation_limit = asyncio.Semaphore(16)

        async def reserve_for_organization(index: int):
            async with reservation_limit:
                return await (first_quota if index % 2 else second_quota).reserve(
                    organization_owners[index % len(organization_owners)],
                    organization_policy,
                    uuid4(),
                    now=now,
                )

        organization_results = await asyncio.gather(*(reserve_for_organization(index) for index in range(100)))
        assert all(reservation.allowed for reservation in organization_results)
        assert sum(reservation.organization_warning_created for reservation in organization_results) == 1
        organization_denied = await first_quota.reserve(
            GoogleAccessOwner(uuid4(), organization_id), organization_policy, uuid4(), now=now
        )
        assert organization_denied.allowed is False
        assert organization_denied.scope == "organization"

        await second_resource.client.script_flush()
        noscript_result = await first_quota.reserve(GoogleAccessOwner(uuid4(), uuid4()), policy, uuid4(), now=now)
        assert noscript_result.allowed is True
    finally:
        await cleanup(first_resource, environment)
        await first_resource.close()
        await second_resource.close()


class CurrentSession:
    def __init__(self, identity: AuthenticatedIdentity) -> None:
        self._identity = identity

    async def execute(self, token: str) -> AuthenticatedIdentity:
        assert token == SESSION_TOKEN
        return self._identity


class BlockingPlacesGateway:
    def __init__(self) -> None:
        self.calls = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def search(self, criteria: GooglePlaceSearchCriteria) -> list[PlaceCandidate]:
        del criteria
        self.calls += 1
        self.started.set()
        await self.release.wait()
        return [
            PlaceCandidate(
                place_id="redis-google-place",
                name="Nom temporaire Google",
                address="Adresse temporaire",
                google_maps_url="https://maps.google.com/?cid=1",
                latitude=46.8139,
                longitude=-71.208,
                primary_type="plumber",
                business_status="OPERATIONAL",
            )
        ]


class FakeStaticMapGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def fetch(self, payload: MapSnapshot) -> MapImage:
        self.calls += 1
        assert payload.points
        return MapImage(content=b"redis-map", media_type="image/png")


def identity_for(access_owner: GoogleAccessOwner) -> AuthenticatedIdentity:
    membership = MembershipIdentity(
        id=uuid4(),
        organization_id=access_owner.organization_id,
        organization_name="Organisation Redis",
        role=MembershipRole.SALES,
        status=MembershipStatus.ACTIVE,
        organization_status=OrganizationStatus.ACTIVE,
        created_at=datetime.now(UTC),
    )
    user = UserIdentity(
        id=access_owner.user_id,
        email="redis@example.ca",
        display_name="Redis",
        password_hash="not-serialized",
        status=UserStatus.ACTIVE,
        platform_role=None,
        last_active_organization_id=access_owner.organization_id,
        version=1,
        memberships=(membership,),
    )
    return AuthenticatedIdentity(user, membership, CSRF_TOKEN)


def request_headers(client: AsyncClient) -> dict[str, str]:
    client.cookies.set("prospect_session", SESSION_TOKEN)
    return {"Origin": "http://test", "X-CSRF-Token": CSRF_TOKEN}


def search_payload() -> dict[str, object]:
    return {
        "query": "plombier",
        "center_latitude": 46.8139,
        "center_longitude": -71.208,
        "radius_km": 15,
        "include_service_area_businesses": True,
        "language_code": "fr",
        "region_code": "CA",
    }


async def test_two_fastapi_containers_share_google_lock_and_map_token() -> None:
    environment = f"google-http-{uuid4().hex}"
    first_resource = RedisResource(redis_url(), connect_timeout_seconds=2, max_connections=3)
    second_resource = RedisResource(redis_url(), connect_timeout_seconds=2, max_connections=3)
    access_owner = owner()
    identity = identity_for(access_owner)
    places = BlockingPlacesGateway()
    maps = FakeStaticMapGateway()
    settings = Settings(
        google_maps_api_key="places-test-key",
        google_maps_static_api_key="maps-test-key",
        cors_allowed_origins=("http://test",),
    )

    def build(resource: RedisResource) -> AppContainer:
        grants = RedisMapSnapshotGrantStore(resource.client, environment=environment, ttl_seconds=10)
        selection = RedisGoogleSelectionGrantStore(resource.client, environment=environment, ttl_seconds=10)
        quota = RedisGoogleSearchQuota(resource.client, environment=environment)
        return AppContainer(
            settings=settings,
            search_google_places=SearchGooglePlacesUseCase(
                places,
                RedisGenerationGuard(resource.client, environment=environment, ttl_seconds=2),
                grants,
                selection,
                SettingsGoogleSearchPolicyProvider(settings),
                quota,
                SystemClock(),
            ),
            get_map_snapshot=GetMapSnapshotUseCase(grants, maps),
            get_current_session=CurrentSession(identity),  # type: ignore[arg-type]
        )

    first_app = create_app(container=build(first_resource))
    second_app = create_app(container=build(second_resource))
    try:
        async with (
            AsyncClient(transport=ASGITransport(app=first_app), base_url="http://test") as first_client,
            AsyncClient(transport=ASGITransport(app=second_app), base_url="http://test") as second_client,
        ):
            first_headers = request_headers(first_client)
            second_headers = request_headers(second_client)
            first_search = asyncio.create_task(
                first_client.post("/api/google/places/search", json=search_payload(), headers=first_headers)
            )
            await places.started.wait()
            second_search = await second_client.post(
                "/api/google/places/search", json=search_payload(), headers=second_headers
            )
            places.release.set()
            first_response = await first_search

            assert first_response.status_code == 200
            assert second_search.status_code == 409
            assert second_search.json()["error"]["code"] == "google_search_in_progress"
            assert places.calls == 1

            map_response = await second_client.post(
                "/api/map/snapshot",
                json={"token": first_response.json()["map_snapshot_token"]},
                headers=second_headers,
            )
            assert map_response.status_code == 200
            assert map_response.content == b"redis-map"
            assert maps.calls == 1
    finally:
        await cleanup(first_resource, environment)
        await first_resource.close()
        await second_resource.close()


async def test_two_fastapi_containers_share_an_organization_quota() -> None:
    environment = f"google-http-quota-{uuid4().hex}"
    first_resource = RedisResource(redis_url(), connect_timeout_seconds=2, max_connections=3)
    second_resource = RedisResource(redis_url(), connect_timeout_seconds=2, max_connections=3)
    access_owner = owner()
    identity = identity_for(access_owner)
    places = BlockingPlacesGateway()
    places.release.set()
    maps = FakeStaticMapGateway()
    settings = Settings(
        google_maps_api_key="places-test-key",
        google_maps_static_api_key="maps-test-key",
        google_search_organization_daily_limit=1,
        cors_allowed_origins=("http://test",),
    )

    def build(resource: RedisResource) -> AppContainer:
        grants = RedisMapSnapshotGrantStore(resource.client, environment=environment, ttl_seconds=10)
        selection = RedisGoogleSelectionGrantStore(resource.client, environment=environment, ttl_seconds=10)
        return AppContainer(
            settings=settings,
            search_google_places=SearchGooglePlacesUseCase(
                places,
                RedisGenerationGuard(resource.client, environment=environment, ttl_seconds=2),
                grants,
                selection,
                SettingsGoogleSearchPolicyProvider(settings),
                RedisGoogleSearchQuota(resource.client, environment=environment),
                SystemClock(),
            ),
            get_map_snapshot=GetMapSnapshotUseCase(grants, maps),
            get_current_session=CurrentSession(identity),  # type: ignore[arg-type]
        )

    first_app = create_app(container=build(first_resource))
    second_app = create_app(container=build(second_resource))
    try:
        async with (
            AsyncClient(transport=ASGITransport(app=first_app), base_url="http://test") as first_client,
            AsyncClient(transport=ASGITransport(app=second_app), base_url="http://test") as second_client,
        ):
            first_response = await first_client.post(
                "/api/google/places/search", json=search_payload(), headers=request_headers(first_client)
            )
            second_response = await second_client.post(
                "/api/google/places/search", json=search_payload(), headers=request_headers(second_client)
            )

        assert first_response.status_code == 200
        assert second_response.status_code == 429
        assert second_response.headers["cache-control"] == "no-store, max-age=0"
        assert int(second_response.headers["retry-after"]) > 0
        assert second_response.json()["error"]["code"] == "google_quota_exceeded"
        assert second_response.json()["error"]["fields"] == {"scope": "organization"}
        assert places.calls == 1
    finally:
        await cleanup(first_resource, environment)
        await first_resource.close()
        await second_resource.close()
