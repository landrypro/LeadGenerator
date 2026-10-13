import pytest

from backend.app.infrastructure.postgres.billing_projection import _result_code


def test_billing_projection_result_is_closed() -> None:
    assert _result_code({"result_code": "transitioned"}) == "transitioned"
    assert _result_code('{"result_code":"processed"}') == "processed"
    with pytest.raises(RuntimeError, match="invalid_result"):
        _result_code({"other": "value"})
