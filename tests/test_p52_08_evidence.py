import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.app.application.ports.catalog import CatalogAuditedUnitOfWork, CatalogMutationGateway
from backend.app.application.use_cases.catalog import CatalogAdministrationUseCases
from backend.app.domain.catalog import ENTITLEMENT_REGISTRY, PlanCode
from backend.app.presentation.api.schemas import ChangeCatalogContractStateRequest
from scripts.quality_gate import P52_08_EXTERNAL_EFFECTS, P52_08_TEST_ORACLES, write_p52_08_evidence

EVIDENCE_ROOT = Path("docs/recettes/p52-08")


def test_p52_08_archives_a_synthetic_closed_plan_entitlement_matrix() -> None:
    manifest = json.loads((EVIDENCE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    matrix = json.loads((EVIDENCE_ROOT / "matrice-plan-droit.json").read_text(encoding="utf-8"))

    assert manifest["source"] == "synthetic"
    assert manifest["external_effects"] == P52_08_EXTERNAL_EFFECTS
    assert {row["id"] for row in manifest["scenarios"]} == set(P52_08_TEST_ORACLES)
    assert matrix["source"] == "synthetic"
    assert matrix["commercial_prices_included"] is False
    assert [row["plan_code"] for row in matrix["plan_matrix"]] == [code.value for code in PlanCode]
    assert {row["key"] for row in matrix["entitlements"]} == {key.value for key in ENTITLEMENT_REGISTRY}
    for row in matrix["entitlements"]:
        definition = ENTITLEMENT_REGISTRY[next(key for key in ENTITLEMENT_REGISTRY if key.value == row["key"])]
        assert (row["kind"], row["unit"], row["scope"]) == (
            definition.kind.value,
            definition.unit,
            definition.scope,
        )


def test_p52_08_no_implicit_plan_downgrade_exists() -> None:
    """P52-SEAT-02 : aucun changement de plan caché ne peut désactiver un membre."""

    assert "plan_version_id" not in ChangeCatalogContractStateRequest.model_fields
    assert "change_contract_plan_version" not in CatalogMutationGateway.__dict__


def test_p52_08_catalog_mutations_have_no_external_effect_port() -> None:
    """P52-NOEXT-01 : le cas d'usage n'accepte que stockage transactionnel et horloge."""

    assert tuple(inspect.signature(CatalogAdministrationUseCases).parameters) == ("factory", "clock")
    assert {"mutations", "audit", "commit"} <= set(CatalogAuditedUnitOfWork.__dict__)
    assert not {"email", "payment", "checkout", "provider_network"} & set(CatalogAuditedUnitOfWork.__dict__)


def test_p52_08_evidence_requires_every_synthetic_oracle() -> None:
    manifest = EVIDENCE_ROOT / "manifest.json"
    Path("test-results").mkdir(exist_ok=True)
    with TemporaryDirectory(dir="test-results", prefix="p52-08-evidence-") as temporary_directory:
        temporary_path = Path(temporary_directory)
        junit = temporary_path / "pytest.xml"
        cases = "".join(f'<testcase name="{name}" />' for name in set(P52_08_TEST_ORACLES.values()))
        junit.write_text(f"<testsuite>{cases}</testsuite>", encoding="utf-8")
        alembic = temporary_path / "alembic.txt"
        alembic.write_text("20261008_0050 (head)\n", encoding="utf-8")
        output = temporary_path / "p52-08" / "evidence.json"

        write_p52_08_evidence(manifest, junit, alembic, output, "20261008_0050", "1234567890abcdef")

        evidence = json.loads(output.read_text(encoding="utf-8"))
        assert evidence["external_effects"] == P52_08_EXTERNAL_EFFECTS
        assert {row["scenario_id"] for row in evidence["scenarios"]} == set(P52_08_TEST_ORACLES)

        junit.write_text("<testsuite />", encoding="utf-8")
        try:
            write_p52_08_evidence(manifest, junit, alembic, output, "20261008_0050", "1234567890abcdef")
        except ValueError as error:
            assert "Preuve pytest absente" in str(error)
        else:
            raise AssertionError("Une preuve P52-08 incomplète doit être refusée.")
