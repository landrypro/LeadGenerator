import pytest

from backend.app.domain.identity import InvalidEmail, InvalidPassword, normalize_email, validate_new_password
from backend.app.infrastructure.security import Argon2PasswordHasher


def test_email_normalization_uses_nfkc_casefold_and_idna() -> None:
    normalized = normalize_email("  ÉLODIE@Exämple.ca  ")

    assert normalized.display == "ÉLODIE@Exämple.ca"
    assert normalized.normalized == "élodie@xn--exmple-cua.ca"
    assert normalize_email("Ａlex@Ｅxample.ca").normalized == "alex@example.ca"


def test_equivalent_unicode_emails_collide_on_the_same_normalized_value() -> None:
    composed = normalize_email("équipe@example.ca")
    decomposed = normalize_email("e\u0301quipe@EXAMPLE.ca")

    assert composed.normalized == decomposed.normalized


@pytest.mark.parametrize("email", ["", "sans-arobase", "a@localhost", "a @example.ca", "a@-example.ca"])
def test_invalid_email_is_rejected(email: str) -> None:
    with pytest.raises(InvalidEmail):
        normalize_email(email)


async def test_password_is_neither_normalized_nor_silently_truncated() -> None:
    composed = "é" + "mot-de-passe-solide"
    decomposed = "e\u0301" + "mot-de-passe-solide"
    hasher = Argon2PasswordHasher()

    validate_new_password(composed)
    encoded = await hasher.hash(composed)

    assert await hasher.verify(composed, encoded)
    assert not await hasher.verify(decomposed, encoded)


@pytest.mark.parametrize("password", ["court", "x" * 129])
def test_new_password_length_is_enforced(password: str) -> None:
    with pytest.raises(InvalidPassword):
        validate_new_password(password)
