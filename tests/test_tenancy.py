from uuid import uuid4

import pytest

from backend.app.application.tenancy import TenantContext


def test_tenant_context_accepts_server_identifiers() -> None:
    context = TenantContext(
        actor_id=uuid4(),
        organization_id=uuid4(),
        request_id="request-123",
    )

    assert context.request_id == "request-123"


@pytest.mark.parametrize("request_id", ["", "x" * 129, "request\nforged"])
def test_tenant_context_rejects_unsafe_request_identifier(request_id: str) -> None:
    with pytest.raises(ValueError):
        TenantContext(actor_id=uuid4(), organization_id=uuid4(), request_id=request_id)
