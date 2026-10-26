from types import SimpleNamespace
from uuid import uuid4

from backend.app.cli import create_stripe_sandbox_approver as cli
from backend.app.config import Settings


class Unit:
    def __init__(self, count: int) -> None:
        self.count = count
        self.identities = self
        self.session = self
        self.created: dict[str, object] | None = None
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def platform_administrator_exists(self) -> bool:
        return True

    async def scalar(self, _query):
        return self.count

    async def get_by_normalized_email(self, _email):
        return None

    async def create_platform_administrator(self, **kwargs):
        self.created = kwargs
        return SimpleNamespace(id=uuid4())

    async def commit(self) -> None:
        self.committed = True


class Database:
    def __init__(self, unit: Unit) -> None:
        self.unit = unit
        self.closed = False

    def identity_unit_of_work(self) -> Unit:
        return self.unit

    async def close(self) -> None:
        self.closed = True


class Hasher:
    async def hash(self, password: str) -> str:
        assert password == "local-test-password"
        return "hashed-only"


def configure(monkeypatch, *, mode: str = "stripe_sandbox", count: int = 1):
    monkeypatch.setenv("STRIPE_SANDBOX_APPROVER_CONFIRM", cli.CONFIRMATION_VALUE)
    monkeypatch.setenv("MIGRATION_DATABASE_URL", "postgresql+asyncpg://owner:local@db/test")
    monkeypatch.setattr(
        cli.Settings,
        "from_env",
        classmethod(
            lambda cls: Settings(
                app_env="development",
                billing_provider_mode=mode,
                billing_stripe_test_secret_key="sk_test_local",
                billing_stripe_webhook_secret="whsec_local",
            )
        ),
    )
    prompts = iter(("local-test-password", "local-test-password"))
    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt: next(prompts))
    monkeypatch.setattr(cli, "Argon2PasswordHasher", Hasher)
    database = Database(Unit(count))
    monkeypatch.setattr(cli, "PostgresDatabase", lambda *_args, **_kwargs: database)
    return database


async def test_creates_only_a_local_test_approver_without_printing_password(monkeypatch, capsys) -> None:
    database = configure(monkeypatch)

    result = await cli.run()

    assert result == 0
    assert database.unit.committed
    assert database.unit.created is not None
    assert database.unit.created["email_normalized"] == cli.DEFAULT_EMAIL
    assert database.unit.created["password_hash"] == "hashed-only"
    assert database.closed
    assert "local-test-password" not in capsys.readouterr().out


async def test_refuses_more_than_one_existing_platform_admin(monkeypatch) -> None:
    database = configure(monkeypatch, count=2)

    result = await cli.run()

    assert result == 1
    assert database.unit.created is None
    assert not database.unit.committed


async def test_refuses_non_sandbox_mode_before_prompt_or_database(monkeypatch) -> None:
    database = configure(monkeypatch, mode="disabled")

    result = await cli.run()

    assert result == 2
    assert database.unit.created is None
    assert not database.closed
