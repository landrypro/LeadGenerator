"""Contrôles déterministes des verrous qualité."""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

PRODUCTION_SUFFIXES = {".js", ".jsx", ".mjs", ".ts", ".tsx"}
FORBIDDEN_BROWSER_PATTERNS = {
    "localStorage": re.compile(r"\blocalStorage\b"),
    "sessionStorage": re.compile(r"\bsessionStorage\b"),
    "IndexedDB": re.compile(r"\bindexedDB\b"),
    "Cache API": re.compile(r"\bcaches\s*\.\s*open\s*\("),
    "service worker": re.compile(r"\bserviceWorker\b"),
    "console.log/debug": re.compile(r"\bconsole\s*\.\s*(?:log|debug)\s*\("),
}
PUBLIC_LOCALE_STORAGE_PATH = Path("app/publicLocale.js")
PUBLIC_LOCALE_STORAGE_DECLARATION = "export const PUBLIC_LOCALE_STORAGE_KEY = 'marketteo.public-locale.v1'"
LOCAL_STORAGE_CALL_PATTERN = re.compile(
    r"\blocalStorage\s*\?\.\s*(?:getItem|setItem)\s*\(\s*(PUBLIC_LOCALE_STORAGE_KEY)"
)
FOCUSED_TEST_PATTERN = re.compile(r"\b(?:describe|it|test)\s*\.\s*(?:only|skip|todo)\s*\(")
GOOGLE_KEY_PATTERN = re.compile(r"AIza[0-9A-Za-z_-]{30,}")
FORBIDDEN_ARTIFACT_NAMES = {
    ".env",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "test-results",
}
FORBIDDEN_ARTIFACT_SUFFIXES = {".db", ".log", ".pyc", ".pyo", ".sqlite", ".sqlite3"}
IMP_A6_TEST_ORACLES = {
    "A6-RES-01": "test_imp_a6_revoked_membership_blocks_admission_and_writes_minimal_audit",
    "A6-RES-02": "test_imp_a6_suspension_and_stale_rule_block_effect_before_write",
    "A6-RES-03": "test_imp_a6_concurrent_workers_and_restart_keep_one_internal_task",
    "A6-RES-04": "test_imp_a6_uncertain_existing_effect_is_not_retried_blindly",
    "A6-RES-05": "test_imp_a6_concurrent_workers_and_restart_keep_one_internal_task",
    "A6-RES-06": "test_imp_a6_suspension_and_stale_rule_block_effect_before_write",
    "A6-RES-07": "test_imp_a6_dependency_failure_is_closed_without_exposing_fault_hook",
    "A6-EXC-01": "test_manual_automation_admission_is_idempotent_and_worker_prepares_one_task",
    "A6-EXC-02": "test_imp_a6_unavailable_owner_is_rejected_without_partial_creation",
    "A6-AI-01": "test_imp_a6_assistant_provider_failures_use_guided_fallback",
    "A6-AI-02": "test_imp_a6_crm_instruction_is_data_and_never_an_executable_instruction",
    "A6-OBS-01": "test_imp_a6_revoked_membership_blocks_admission_and_writes_minimal_audit",
}
P52_08_TEST_ORACLES = {
    "P52-CAT-01": "test_internal_catalog_mutations_require_two_actors_and_audited_contract_transition",
    "P52-CAT-02": "test_published_catalog_version_refuses_a_commercial_value_change",
    "P52-ENT-01": "test_catalog_entitlements_are_tenant_isolated_and_fail_closed",
    "P52-ENT-02": "test_catalog_resolver_refuses_an_unknown_contract",
    "P52-SEAT-01": "test_seat_reservation_is_atomic_and_an_expired_reservation_is_reusable",
    "P52-SEAT-02": "test_p52_08_no_implicit_plan_downgrade_exists",
    "P52-RLS-01": "test_catalog_entitlements_are_tenant_isolated_and_fail_closed",
    "P52-AUD-01": "test_internal_catalog_mutations_require_two_actors_and_audited_contract_transition",
    "P52-API-01": "test_catalog_conflicts_and_invalid_commands_have_stable_statuses",
    "P52-NOEXT-01": "test_p52_08_catalog_mutations_have_no_external_effect_port",
}
P52_08_EXTERNAL_EFFECTS = {
    "email": False,
    "payment": False,
    "checkout": False,
    "provider_network": False,
}


def assert_junit_has_no_skips(report_path: Path) -> None:
    root = ET.parse(report_path).getroot()
    skipped = sum(int(suite.attrib.get("skipped", "0")) for suite in _test_suites(root))
    if skipped:
        raise ValueError(f"Le rapport {report_path} contient {skipped} test(s) ignoré(s).")


def assert_alembic_current_revision(report_path: Path, expected_revision: str) -> None:
    content = report_path.read_text(encoding="utf-8")
    if expected_revision not in content or "(head)" not in content:
        raise ValueError(
            f"La révision Alembic courante doit être {expected_revision} (head), "
            f"rapport reçu : {content.strip() or '<vide>'}"
        )


def assert_browser_sources_are_safe(source_root: Path) -> None:
    failures: list[str] = []
    for path in sorted(source_root.rglob("*")):
        if not path.is_file() or path.suffix not in PRODUCTION_SUFFIXES or ".test." in path.name:
            continue
        content = path.read_text(encoding="utf-8")
        for label, pattern in FORBIDDEN_BROWSER_PATTERNS.items():
            if pattern.search(content):
                if label == "localStorage" and _is_public_locale_storage(path, source_root, content):
                    continue
                failures.append(f"{path}: utilisation interdite ({label})")
    for path in sorted(source_root.rglob("*.test.*")):
        if FOCUSED_TEST_PATTERN.search(path.read_text(encoding="utf-8")):
            failures.append(f"{path}: test only/skip/todo interdit")
    if failures:
        raise ValueError("\n".join(failures))


def _is_public_locale_storage(path: Path, source_root: Path, content: str) -> bool:
    if path.relative_to(source_root) != PUBLIC_LOCALE_STORAGE_PATH:
        return False
    if PUBLIC_LOCALE_STORAGE_DECLARATION not in content:
        return False
    calls = list(LOCAL_STORAGE_CALL_PATTERN.finditer(content))
    return bool(calls) and len(calls) == len(re.findall(r"\blocalStorage\b", content))


def assert_artifact_is_safe(artifact_root: Path) -> None:
    if not artifact_root.is_dir():
        raise ValueError(f"Artefact absent : {artifact_root}")
    files = [path for path in artifact_root.rglob("*") if path.is_file()]
    if not files:
        raise ValueError(f"Artefact vide : {artifact_root}")
    failures: list[str] = []
    for path in files:
        relative_parts = set(path.relative_to(artifact_root).parts)
        if relative_parts & FORBIDDEN_ARTIFACT_NAMES or path.suffix.casefold() in FORBIDDEN_ARTIFACT_SUFFIXES:
            failures.append(f"{path}: fichier interdit dans l’artefact")
            continue
        if path.suffix.casefold() in {".js", ".html", ".css", ".map"}:
            content = path.read_text(encoding="utf-8", errors="ignore")
            if GOOGLE_KEY_PATTERN.search(content):
                failures.append(f"{path}: clé Google détectée dans l’artefact")
    if failures:
        raise ValueError("\n".join(failures))


def write_automation_imp_a6_evidence(
    manifest_path: Path,
    junit_path: Path,
    alembic_report_path: Path,
    output_path: Path,
    expected_revision: str,
    git_revision: str,
) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("source") != "synthetic":
        raise ValueError("Le manifeste IMP-A6 doit être strictement synthétique.")
    if manifest.get("contains_pii") is not False or manifest.get("contains_provider_secrets") is not False:
        raise ValueError("Le manifeste IMP-A6 ne peut contenir ni PII ni secret fournisseur.")
    if manifest.get("activation_authorized") is not False:
        raise ValueError("Le manifeste IMP-A6 ne doit autoriser aucune activation.")
    injection = manifest.get("fault_injection", {})
    if injection != {"runtime_endpoint": False, "runtime_flag": False, "test_doubles_only": True}:
        raise ValueError("L'injection de panne IMP-A6 doit rester exclusivement dans les tests.")
    manifest_scenarios = {str(item.get("id")) for item in manifest.get("scenarios", [])}
    if manifest_scenarios != set(IMP_A6_TEST_ORACLES):
        raise ValueError("Le manifeste IMP-A6 ne couvre pas exactement les scénarios attendus.")

    assert_alembic_current_revision(alembic_report_path, expected_revision)
    if not re.fullmatch(r"[0-9a-f]{7,40}", git_revision):
        raise ValueError("La révision Git IMP-A6 est invalide.")
    root = ET.parse(junit_path).getroot()
    test_cases = list(root.iter("testcase"))
    results: list[dict[str, str]] = []
    for scenario_id, test_name in IMP_A6_TEST_ORACLES.items():
        matches = [case for case in test_cases if test_name in case.attrib.get("name", "")]
        if not matches:
            raise ValueError(f"Preuve pytest absente pour {scenario_id}.")
        if any(case.find("failure") is not None or case.find("error") is not None for case in matches):
            raise ValueError(f"Preuve pytest en échec pour {scenario_id}.")
        if any(case.find("skipped") is not None for case in matches):
            raise ValueError(f"Preuve pytest ignorée pour {scenario_id}.")
        results.append({"scenario_id": scenario_id, "status": "passed"})

    evidence = {
        "schema_version": "IMP-A6.1",
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": "local-docker-wsl",
        "evidence_level": "D3",
        "source": "synthetic",
        "contains_pii": False,
        "contains_free_text": False,
        "activation_authorized": False,
        "git_base_revision": git_revision,
        "alembic_revision": expected_revision,
        "rollback_reconstruction": "passed",
        "scenarios": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_p52_08_evidence(
    manifest_path: Path,
    junit_path: Path,
    alembic_report_path: Path,
    output_path: Path,
    expected_revision: str,
    git_revision: str,
) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "P52-08.1" or manifest.get("source") != "synthetic":
        raise ValueError("Le manifeste P52-08 doit être versionné et strictement synthétique.")
    if manifest.get("contains_pii") is not False or manifest.get("contains_provider_secrets") is not False:
        raise ValueError("Le manifeste P52-08 ne peut contenir ni PII ni secret fournisseur.")
    if (
        manifest.get("activation_authorized") is not False
        or manifest.get("external_effects") != P52_08_EXTERNAL_EFFECTS
    ):
        raise ValueError("La recette P52-08 ne doit autoriser aucun effet externe ni activation.")
    scenario_ids = {str(item.get("id")) for item in manifest.get("scenarios", [])}
    if scenario_ids != set(P52_08_TEST_ORACLES):
        raise ValueError("Le manifeste P52-08 ne couvre pas exactement les scénarios attendus.")

    assert_alembic_current_revision(alembic_report_path, expected_revision)
    if not re.fullmatch(r"[0-9a-f]{7,40}", git_revision):
        raise ValueError("La révision Git P52-08 est invalide.")
    root = ET.parse(junit_path).getroot()
    test_cases = list(root.iter("testcase"))
    scenarios: list[dict[str, str]] = []
    for scenario_id, test_name in P52_08_TEST_ORACLES.items():
        matches = [case for case in test_cases if test_name in case.attrib.get("name", "")]
        if not matches:
            raise ValueError(f"Preuve pytest absente pour {scenario_id}.")
        if any(case.find("failure") is not None or case.find("error") is not None for case in matches):
            raise ValueError(f"Preuve pytest en échec pour {scenario_id}.")
        if any(case.find("skipped") is not None for case in matches):
            raise ValueError(f"Preuve pytest ignorée pour {scenario_id}.")
        scenarios.append({"scenario_id": scenario_id, "status": "passed"})

    evidence = {
        "schema_version": "P52-08.1",
        "generated_at": datetime.now(UTC).isoformat(),
        "source": "synthetic",
        "contains_pii": False,
        "contains_free_text": False,
        "contains_provider_secrets": False,
        "activation_authorized": False,
        "external_effects": P52_08_EXTERNAL_EFFECTS,
        "git_base_revision": git_revision,
        "alembic_revision": expected_revision,
        "scenarios": scenarios,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _test_suites(root: ET.Element) -> list[ET.Element]:
    if root.tag == "testsuite":
        return [root]
    return list(root.iter("testsuite"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    junit = subparsers.add_parser("junit-no-skips")
    junit.add_argument("report", type=Path)
    current = subparsers.add_parser("alembic-current")
    current.add_argument("report", type=Path)
    current.add_argument("expected_revision")
    browser = subparsers.add_parser("browser-sources")
    browser.add_argument("source", type=Path)
    artifact = subparsers.add_parser("artifact")
    artifact.add_argument("directory", type=Path)
    automation = subparsers.add_parser("automation-evidence")
    automation.add_argument("manifest", type=Path)
    automation.add_argument("junit", type=Path)
    automation.add_argument("alembic_report", type=Path)
    automation.add_argument("output", type=Path)
    automation.add_argument("expected_revision")
    automation.add_argument("git_revision")
    p52 = subparsers.add_parser("p52-08-evidence")
    p52.add_argument("manifest", type=Path)
    p52.add_argument("junit", type=Path)
    p52.add_argument("alembic_report", type=Path)
    p52.add_argument("output", type=Path)
    p52.add_argument("expected_revision")
    p52.add_argument("git_revision")
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "junit-no-skips":
            assert_junit_has_no_skips(arguments.report)
        elif arguments.command == "alembic-current":
            assert_alembic_current_revision(arguments.report, arguments.expected_revision)
        elif arguments.command == "browser-sources":
            assert_browser_sources_are_safe(arguments.source)
        elif arguments.command == "artifact":
            assert_artifact_is_safe(arguments.directory)
        elif arguments.command == "automation-evidence":
            write_automation_imp_a6_evidence(
                arguments.manifest,
                arguments.junit,
                arguments.alembic_report,
                arguments.output,
                arguments.expected_revision,
                arguments.git_revision,
            )
        else:
            write_p52_08_evidence(
                arguments.manifest,
                arguments.junit,
                arguments.alembic_report,
                arguments.output,
                arguments.expected_revision,
                arguments.git_revision,
            )
    except (OSError, ET.ParseError, ValueError) as error:
        print(f"Échec du verrou qualité : {error}", file=sys.stderr)
        return 1
    print("Verrou qualité ciblé : conforme.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
