from uuid import uuid4

import pytest

from backend.app.application.models import GoogleAccessOwner, GoogleSearchQuotaPolicy
from backend.app.config import Settings
from backend.app.infrastructure.google.quota_policy import SettingsGoogleSearchPolicyProvider


async def test_settings_policy_provider_returns_the_server_policy_only() -> None:
    provider = SettingsGoogleSearchPolicyProvider(
        Settings(
            google_search_user_daily_limit=7,
            google_search_organization_daily_limit=31,
            google_search_quota_warning_percent=75,
            google_search_quota_policy_code="test_policy_v1",
        )
    )

    policy = await provider.resolve(GoogleAccessOwner(uuid4(), uuid4()))

    assert policy == GoogleSearchQuotaPolicy(True, 7, 31, 75, "test_policy_v1")


@pytest.mark.parametrize(
    "policy",
    [
        GoogleSearchQuotaPolicy(True, 0, 100, 80, "test_policy"),
    ],
)
def test_google_quota_policy_accepts_an_explicit_zero_limit(policy: GoogleSearchQuotaPolicy) -> None:
    assert policy.user_daily_limit == 0


@pytest.mark.parametrize(
    "arguments",
    [
        (True, -1, 100, 80, "test_policy"),
        (True, 20, 100, 101, "test_policy"),
        (True, 20, 100, 80, "Plan Commercial"),
    ],
)
def test_google_quota_policy_rejects_invalid_values(arguments: tuple[bool, int, int, int, str]) -> None:
    with pytest.raises(ValueError):
        GoogleSearchQuotaPolicy(*arguments)
