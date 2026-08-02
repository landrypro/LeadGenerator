from backend.app.cli import bootstrap_platform_admin as cli
from backend.app.config import Settings
from backend.app.domain.identity import InvalidPassword


class Database:
    identity_unit_of_work = object()

    async def close(self) -> None:
        pass


class InvalidPasswordBootstrap:
    def __init__(self, *args) -> None:
        del args

    async def execute(self, **kwargs):
        del kwargs
        raise InvalidPassword("Le mot de passe doit contenir entre 12 et 128 caractères.")


async def test_bootstrap_reports_short_password_without_traceback(monkeypatch, capsys) -> None:
    monkeypatch.setenv("BOOTSTRAP_PLATFORM_ADMIN_CONFIRM", cli.CONFIRMATION_VALUE)
    monkeypatch.setenv("BOOTSTRAP_PLATFORM_ADMIN_EMAIL", "admin@example.ca")
    monkeypatch.setenv("BOOTSTRAP_PLATFORM_ADMIN_DISPLAY_NAME", "Administrateur")
    monkeypatch.setattr(
        cli.Settings,
        "from_env",
        classmethod(lambda cls: Settings(database_url="postgresql+asyncpg://owner:secret@db/prospect")),
    )
    passwords = iter(("court", "court"))
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(passwords))
    monkeypatch.setattr(cli, "PostgresDatabase", lambda *args, **kwargs: Database())
    monkeypatch.setattr(cli, "BootstrapPlatformAdministratorUseCase", InvalidPasswordBootstrap)

    result = await cli.run()

    output = capsys.readouterr().out
    assert result == 2
    assert "Bootstrap refusé" in output
    assert "12 et 128 caractères" in output
    assert "Traceback" not in output
