from ...application.models import GoogleAccessOwner, GoogleSearchQuotaPolicy
from ...config import Settings


class SettingsGoogleSearchPolicyProvider:
    """Politique transitoire : paramètres serveur, sans contrat commercial implicite."""

    def __init__(self, settings: Settings) -> None:
        self._policy = GoogleSearchQuotaPolicy(
            enabled=True,
            user_daily_limit=settings.google_search_user_daily_limit,
            organization_daily_limit=settings.google_search_organization_daily_limit,
            warning_threshold_percent=settings.google_search_quota_warning_percent,
            policy_code=settings.google_search_quota_policy_code,
        )

    async def resolve(self, owner: GoogleAccessOwner) -> GoogleSearchQuotaPolicy:
        del owner
        return self._policy
