import pytest

from backend.app.application.errors import ProvisioningServiceUnavailable
from backend.app.application.ports.provisioning import ProvisionResultCode
from backend.app.infrastructure.postgres.provisioning_gateway import (
    _acceptance_result,
    _json_object,
    _result_code,
    _view_from_row,
)


@pytest.mark.parametrize(
    ("operation",),
    (
        (lambda: _json_object("{json-invalide"),),
        (lambda: _result_code(ProvisionResultCode, {}),),
        (lambda: _view_from_row({}, replayed=False),),
        (lambda: _acceptance_result({"code": "accepted"}),),
    ),
)
def test_invalid_postgresql_contracts_are_translated_without_leaking_adapter_errors(operation) -> None:
    with pytest.raises(ProvisioningServiceUnavailable):
        operation()
