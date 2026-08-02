import hashlib
import secrets

from ...domain.provisioning import InvitationToken


class SecureInvitationTokenGenerator:
    def generate(self) -> InvitationToken:
        raw = secrets.token_urlsafe(32)
        return InvitationToken(raw=raw, hash=hashlib.sha256(raw.encode("ascii")).hexdigest())
