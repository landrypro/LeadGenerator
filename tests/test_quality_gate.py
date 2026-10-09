import json
from pathlib import Path

import pytest

from scripts.quality_gate import (
    assert_alembic_current_revision,
    assert_artifact_is_safe,
    assert_browser_sources_are_safe,
    assert_junit_has_no_skips,
    write_automation_imp_a6_evidence,
)


def test_quality_gate_alembic_expectations_track_the_current_head() -> None:
    expected_revision = "20261008_0050"
    local_gate = Path("scripts/Test-QualityGateLocal.ps1").read_text(encoding="utf-8")
    pipeline = Path("azure-pipelines.yml").read_text(encoding="utf-8")

    assert f"$expectedAlembicRevision = '{expected_revision}'" in local_gate
    assert f"expectedAlembicRevision: '{expected_revision}'" in pipeline
    assert "P52-07 expose l'API interne" in local_gate


def test_junit_gate_accepts_zero_skip_and_rejects_one(tmp_path: Path) -> None:
    report = tmp_path / "report.xml"
    report.write_text('<testsuites><testsuite tests="2" skipped="0" /></testsuites>', encoding="utf-8")
    assert_junit_has_no_skips(report)
    report.write_text('<testsuite tests="2" skipped="1" />', encoding="utf-8")
    with pytest.raises(ValueError, match="1 test"):
        assert_junit_has_no_skips(report)


def test_alembic_current_gate_requires_expected_head(tmp_path: Path) -> None:
    report = tmp_path / "alembic-current.txt"
    report.write_text("20260813_0008 (head)\n", encoding="utf-8")
    assert_alembic_current_revision(report, "20260813_0008")
    report.write_text("20260809_0007\n", encoding="utf-8")
    with pytest.raises(ValueError, match="20260813_0008"):
        assert_alembic_current_revision(report, "20260813_0008")


def test_browser_gate_rejects_storage_console_and_focused_tests(tmp_path: Path) -> None:
    (tmp_path / "safe.jsx").write_text("export const safe = true", encoding="utf-8")
    assert_browser_sources_are_safe(tmp_path)
    (tmp_path / "unsafe.js").write_text(
        "localStorage.setItem('token', 'secret'); console.log('secret')", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="localStorage"):
        assert_browser_sources_are_safe(tmp_path)
    (tmp_path / "unsafe.js").unlink()
    (tmp_path / "focused.test.jsx").write_text("it.only('focused', () => {})", encoding="utf-8")
    with pytest.raises(ValueError, match="only/skip/todo"):
        assert_browser_sources_are_safe(tmp_path)


def test_browser_gate_allows_only_the_public_locale_preference(tmp_path: Path) -> None:
    app = tmp_path / "app"
    app.mkdir()
    public_locale = app / "publicLocale.js"
    public_locale.write_text(
        "export const PUBLIC_LOCALE_STORAGE_KEY = 'marketteo.public-locale.v1'\n"
        "globalThis.localStorage?.setItem(PUBLIC_LOCALE_STORAGE_KEY, 'fr-CA')\n"
        "globalThis.localStorage?.getItem(PUBLIC_LOCALE_STORAGE_KEY)\n",
        encoding="utf-8",
    )
    assert_browser_sources_are_safe(tmp_path)

    public_locale.write_text(
        "export const PUBLIC_LOCALE_STORAGE_KEY = 'marketteo.public-locale.v1'\n"
        "globalThis.localStorage?.setItem('session-token', 'secret')\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="localStorage"):
        assert_browser_sources_are_safe(tmp_path)


def test_artifact_gate_rejects_secrets_and_forbidden_files(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<main>Prospect CRM</main>", encoding="utf-8")
    assert_artifact_is_safe(tmp_path)
    (tmp_path / "bundle.js").write_text(f"const key = 'AIza{'A' * 35}'", encoding="utf-8")
    with pytest.raises(ValueError, match="clé Google"):
        assert_artifact_is_safe(tmp_path)
    (tmp_path / "bundle.js").unlink()
    cache = tmp_path / "backend" / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "module.pyc").write_bytes(b"cache")
    with pytest.raises(ValueError, match="fichier interdit"):
        assert_artifact_is_safe(tmp_path)


def test_imp_a6_evidence_is_minimized_and_requires_every_oracle(tmp_path: Path) -> None:
    from scripts.quality_gate import IMP_A6_TEST_ORACLES

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "source": "synthetic",
                "contains_pii": False,
                "contains_provider_secrets": False,
                "activation_authorized": False,
                "fault_injection": {
                    "runtime_endpoint": False,
                    "runtime_flag": False,
                    "test_doubles_only": True,
                },
                "scenarios": [{"id": scenario_id} for scenario_id in IMP_A6_TEST_ORACLES],
            }
        ),
        encoding="utf-8",
    )
    junit = tmp_path / "pytest.xml"
    cases = "".join(f'<testcase name="{name}" />' for name in set(IMP_A6_TEST_ORACLES.values()))
    junit.write_text(f"<testsuite>{cases}</testsuite>", encoding="utf-8")
    alembic = tmp_path / "alembic.txt"
    alembic.write_text("20261004_0035 (head)\n", encoding="utf-8")
    output = tmp_path / "automation-imp-a6" / "evidence.json"

    write_automation_imp_a6_evidence(manifest, junit, alembic, output, "20261004_0035", "1234567890abcdef")

    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["contains_pii"] is False
    assert evidence["contains_free_text"] is False
    assert evidence["activation_authorized"] is False
    assert {row["scenario_id"] for row in evidence["scenarios"]} == set(IMP_A6_TEST_ORACLES)

    junit.write_text("<testsuite />", encoding="utf-8")
    with pytest.raises(ValueError, match="Preuve pytest absente"):
        write_automation_imp_a6_evidence(manifest, junit, alembic, output, "20261004_0035", "1234567890abcdef")
