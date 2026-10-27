"""Consolide les preuves P5.3 du simulateur sans archiver de données brutes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo

SCHEMA_VERSION = "P53-10.3"
CURRENCIES = ["CAD", "USD", "EUR", "XAF"]
# Empreinte fixe des liens oracle → cas, indépendante du manifeste éditable.
FIXED_CASE_CONTRACT_SHA256 = "a79e77ce62f3f74ccaf24a26bc7c6fffd1670eb8b9815fdc66025943a7c166bc"
REQUIRED_ORACLES = {
    "P53-CAT-01": {"server_price_authority"},
    "P53-CHK-01": {"concurrent_single_session"},
    "P53-CHK-02": {"timeout_no_second_checkout"},
    "P53-SIM-01": {"replay_and_collision"},
    "P53-WEB-01": {"signature_and_freshness"},
    "P53-WEB-02": {"hundred_deliveries_one_admission", "one_durable_projection"},
    "P53-WEB-03": {"stale_event_does_not_regress"},
    "P53-WEB-04": {"digest_collision_quarantined"},
    "P53-SUB-01": {"paid_subscription_and_currency"},
    "P53-SUB-02": {"failure_grace_suspend_recover"},
    "P53-CAN-01": {"schedule_and_revoke"},
    "P53-CAN-02": {"end_of_period_canceled"},
    "P53-REF-01": {"eligibility_and_idempotency"},
    "P53-REC-01": {"projection_divergence", "timeout_after_effect"},
    "P53-REC-02": {"price_currency_mismatch_blocked"},
    "P53-REC-03": {"restart_proven_or_unresolved"},
    "P53-REC-04": {"manual_scope_auth_audit"},
    "P53-RLS-01": {"tenant_isolation"},
    "P53-SEC-01": {"minimal_responses", "minimal_audit", "artifact_scan"},
    "P53-NOEXT-01": {"instrumented_network_and_smtp", "disabled_provider"},
}
REPORTS = (
    "pytest-quality.xml",
    "pytest-p53-01.xml",
    "pytest-p53-03.xml",
    "pytest-p53-04.xml",
    "pytest-p53-05.xml",
    "pytest-p53-06.xml",
    "pytest-p53-07.xml",
    "pytest-p53-08.xml",
    "vitest.xml",
    "alembic-current.txt",
    "alembic-upgrade.log",
    "alembic-downgrade.log",
    "alembic-reupgrade.log",
    "vitest-console.log",
    "p52-08/evidence.json",
    "phase-4-6/browser-axe.json",
)
JUNIT_REPORTS = tuple(name for name in REPORTS if name.endswith(".xml"))
SECRET_RULES = {
    "provider-secret": re.compile(rb"\b(?:sk_(?:test|live)|whsec|rk_(?:test|live))_[A-Za-z0-9]{12,}\b"),
    "payment-session-url": re.compile(
        rb"https?://(?:checkout\.stripe\.com|billing\.stripe\.com|billing-simulator\.local)/\S+", re.I
    ),
    "bank-card-number": re.compile(
        rb"(?<![0-9A-Fa-f-])(?:\d[ ]?){15}\d(?![0-9A-Fa-f-])|(?<![0-9A-Fa-f-])\d{4}(?:-\d{4}){3}(?![0-9A-Fa-f-])"
    ),
    "email-address": re.compile(rb"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
}
# Valeurs littérales de deux cas négatifs déjà présents dans les noms JUnit.
# Leur portée est limitée aux fixtures de tests, jamais aux logs ou audits applicatifs.
SAFE_JUNIT_FIXTURES = (b"a@-example.ca", b"password@crm.example")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_fingerprint(root: Path) -> str:
    """Empreinte les octets des fichiers Git suivis et non ignorés, même non commités."""
    listing = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        check=True,
    ).stdout
    names = sorted(set(item.decode("utf-8", "surrogateescape") for item in listing.split(b"\0") if item))
    digest = hashlib.sha256()
    for name in names:
        path = root / name
        digest.update(name.encode("utf-8", "surrogateescape") + b"\0")
        if path.is_symlink():
            digest.update(b"link\0" + os.readlink(path).encode("utf-8", "surrogateescape") + b"\0")
        elif path.is_file():
            file_digest = hashlib.sha256()
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    file_digest.update(chunk)
            digest.update(b"file\0" + file_digest.digest())
        elif not path.exists():
            digest.update(b"missing\0")
        else:
            raise ValueError(f"Chemin Git non ordinaire : {name}.")
    return digest.hexdigest()


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Un horodatage de preuve ne porte pas de fuseau horaire.")
    return parsed.astimezone(UTC)


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Objet JSON attendu : {path.name}")
    return value


def _case_contract_digest(scenarios: list[dict[str, object]]) -> str:
    contract = {
        scenario["id"]: [
            {
                "id": oracle["id"],
                "cases": oracle.get("cases", []),
                "currencies": oracle.get("currencies", False),
                "control": oracle.get("control"),
            }
            for oracle in sorted(scenario["oracles"], key=lambda item: item["id"])
        ]
        for scenario in scenarios
    }
    canonical = json.dumps(contract, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validate_manifest(manifest: dict[str, object]) -> list[dict[str, object]]:
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("source") != "synthetic":
        raise ValueError("Le manifeste P53-10 doit être versionné et synthétique.")
    if manifest.get("provider_modes") != ["disabled", "simulated"] or manifest.get("currencies") != CURRENCIES:
        raise ValueError("Modes fournisseur ou devises P53-10 incomplets.")
    if any(
        manifest.get(flag) is not False
        for flag in ("contains_pii", "contains_provider_secrets", "activation_authorized")
    ):
        raise ValueError("Le manifeste P53-10 ne doit autoriser ni donnée sensible ni activation.")
    if manifest.get("deferred_scenarios") != ["P53-SBX-01"]:
        raise ValueError("Seule la preuve Stripe sandbox P53-SBX-01 peut être reportée.")
    scenarios = manifest.get("scenarios")
    if not isinstance(scenarios, list) or any(not isinstance(item, dict) for item in scenarios):
        raise ValueError("Liste de scénarios P53-10 invalide.")
    ids = [item.get("id") for item in scenarios]
    if (
        any(not isinstance(item, str) for item in ids)
        or len(ids) != len(REQUIRED_ORACLES)
        or set(ids) != set(REQUIRED_ORACLES)
    ):
        raise ValueError("Le manifeste P53-10 ne couvre pas exactement les scénarios locaux attendus.")
    for scenario in scenarios:
        oracles = scenario.get("oracles")
        if not isinstance(oracles, list) or any(not isinstance(oracle, dict) for oracle in oracles):
            raise ValueError(f"Oracles invalides pour {scenario['id']}.")
        oracle_ids = [oracle.get("id") for oracle in oracles]
        if (
            any(not isinstance(item, str) for item in oracle_ids)
            or len(oracle_ids) != len(REQUIRED_ORACLES[scenario["id"]])
            or set(oracle_ids) != REQUIRED_ORACLES[scenario["id"]]
        ):
            raise ValueError(f"Oracles requis manquants ou modifiés pour {scenario['id']}.")
    if _case_contract_digest(scenarios) != FIXED_CASE_CONTRACT_SHA256:
        raise ValueError("Correspondances oracle/cas P53-10 différentes du contrat approuvé.")
    return scenarios


def _case_ids(oracle: dict[str, object], scenario_id: str) -> list[str]:
    templates = oracle.get("cases")
    oracle_id = oracle.get("id")
    if not isinstance(templates, list) or not templates or any(not isinstance(item, str) for item in templates):
        raise ValueError(f"Cas JUnit absent pour {scenario_id}/{oracle_id}.")
    if oracle.get("currencies") is True:
        if not any("{currency}" in template for template in templates):
            raise ValueError(f"Variantes des quatre devises absentes pour {scenario_id}/{oracle_id}.")
        return [
            template.replace("{currency}", currency)
            for template in templates
            for currency in (CURRENCIES if "{currency}" in template else [""])
        ]
    if any("{currency}" in template for template in templates):
        raise ValueError(f"Expansion des devises non déclarée pour {scenario_id}/{oracle_id}.")
    return templates


def _read_junit(path: Path) -> tuple[dict[str, ET.Element], dict[str, int], list[datetime]]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    if not suites:
        raise ValueError(f"Aucune suite JUnit dans {path.name}.")
    timestamps = []
    for suite in suites:
        timestamp = suite.attrib.get("timestamp")
        if not timestamp:
            raise ValueError(f"Horodatage JUnit absent : {path.name}.")
        timestamps.append(_utc(timestamp))
    counts = {
        key: sum(int(suite.attrib.get(key, "0")) for suite in suites)
        for key in ("tests", "errors", "failures", "skipped")
    }
    cases = list(root.iter("testcase"))
    if (
        counts["tests"] < 1
        or counts["tests"] != len(cases)
        or any(counts[key] for key in ("errors", "failures", "skipped"))
    ):
        raise ValueError(f"JUnit incomplet, en échec ou avec skip : {path.name}.")
    selected: dict[str, ET.Element] = {}
    for case in cases:
        if any(case.find(tag) is not None for tag in ("failure", "error", "skipped")):
            raise ValueError(f"Cas JUnit en échec ou ignoré : {path.name}.")
        key = f"{case.attrib.get('classname', '')}::{case.attrib.get('name', '')}"
        if key in selected:
            raise ValueError(f"Cas JUnit dupliqué : {key}.")
        selected[key] = case
    return selected, counts, timestamps


def _check_sensitive_content(name: str, content: bytes) -> None:
    if name.endswith(".xml"):
        for fixture in SAFE_JUNIT_FIXTURES:
            content = content.replace(fixture, b"<synthetic-test-fixture>")
    for label, pattern in SECRET_RULES.items():
        if pattern.search(content):
            raise ValueError(f"Contenu sensible détecté ({label}) dans {name} ; valeur non affichée.")


def _scan_sensitive(paths: dict[str, Path]) -> None:
    for name, path in paths.items():
        _check_sensitive_content(name, path.read_bytes())


def _check_browser(path: Path) -> tuple[int, datetime]:
    report = _read_json(path)
    checks = report.get("checks")
    if (
        report.get("verdict") != "PASS"
        or report.get("failures") != []
        or not isinstance(checks, list)
        or len(checks) != 44
    ):
        raise ValueError("La recette navigateur 4.6 est absente ou non conforme.")
    if any(not isinstance(item, dict) or item.get("errors") or item.get("violations") for item in checks):
        raise ValueError("La recette navigateur contient des erreurs ou violations axe.")
    finished_at = report.get("finishedAt")
    if not isinstance(finished_at, str):
        raise ValueError("Horodatage navigateur manquant.")
    return len(checks), _utc(finished_at)


def _write_zip(path: Path, files: dict[str, bytes]) -> None:
    with ZipFile(path, "w") as archive:
        for name, content in sorted(files.items()):
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, content)


def _selected_junit_extract(case_ids: set[str], source_digest: str, timestamp: datetime) -> bytes:
    suite = ET.Element(
        "testsuite",
        {
            "name": "p53-10-selected-cases",
            "tests": str(len(case_ids)),
            "errors": "0",
            "failures": "0",
            "skipped": "0",
            "timestamp": timestamp.isoformat(),
            "source_report_sha256": source_digest,
        },
    )
    for case_id in sorted(case_ids):
        classname, name = case_id.split("::", 1)
        ET.SubElement(suite, "testcase", {"classname": classname, "name": name, "status": "passed"})
    return ET.tostring(suite, encoding="utf-8", xml_declaration=True) + b"\n"


def generate(
    manifest_path: Path, results_root: Path, expected_revision: str, git_revision: str, run_id: str
) -> dict[str, object]:
    if not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise ValueError("Identifiant d'exécution P53-10 invalide.")
    output_dir = results_root / "p53-10" / "runs" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale in ("evidence.json", "case-results.json", "junit-extract.xml", "packet.zip", "packet.sha256"):
        (output_dir / stale).unlink(missing_ok=True)

    _scan_sensitive({"manifest.json": manifest_path})
    manifest = _read_json(manifest_path)
    scenarios = _validate_manifest(manifest)
    if not re.fullmatch(r"[0-9a-f]{40}", git_revision):
        raise ValueError("Révision Git P53-10 invalide.")
    context = _read_json(output_dir / "run-context.json")
    if context.get("source") != "synthetic" or context.get("git_revision") != git_revision:
        raise ValueError("Le contexte du verrou ne correspond pas au SHA Git fourni.")
    if context.get("run_id") != run_id:
        raise ValueError("Identifiant d'exécution P53-10 différent du contexte.")
    started_at = context.get("started_at")
    if not isinstance(started_at, str):
        raise ValueError("Début d'exécution P53-10 absent.")
    started = _utc(started_at)
    if not isinstance(context.get("git_dirty"), bool):
        raise ValueError("État Git du verrou absent.")
    source_digest = context.get("source_tree_sha256")
    if not isinstance(source_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", source_digest):
        raise ValueError("Empreinte de l'arbre source P53-10 absente.")

    paths = {name: results_root / name for name in REPORTS}
    reconstruction_name = f"p53-10/runs/{run_id}/alembic-reconstruction.json"
    paths[reconstruction_name] = output_dir / "alembic-reconstruction.json"
    paths[f"p53-10/runs/{run_id}/run-context.json"] = output_dir / "run-context.json"
    raw_junit_name = f"p53-10/runs/{run_id}/pytest-quality.xml"
    paths[raw_junit_name] = output_dir / "pytest-quality.xml"
    for log_name in ("alembic-upgrade.log", "alembic-downgrade.log", "alembic-reupgrade.log"):
        paths[f"p53-10/runs/{run_id}/{log_name}"] = output_dir / log_name
    retry_log = "alembic-pytest-retry-upgrade.log"
    if (output_dir / retry_log).is_file():
        paths[retry_log] = results_root / retry_log
        paths[f"p53-10/runs/{run_id}/{retry_log}"] = output_dir / retry_log
    for name, path in paths.items():
        if not path.is_file() or path.stat().st_mtime < started.timestamp() - 2:
            raise ValueError(f"Rapport P53-10 absent ou antérieur à l'exécution : {name}.")
    if _digest(paths["pytest-quality.xml"]) != _digest(paths[raw_junit_name]):
        raise ValueError("Copie JUnit durable P53-10 différente du rapport source.")
    for log_name, operation in (
        ("alembic-upgrade.log", "Running upgrade"),
        ("alembic-downgrade.log", "Running downgrade"),
        ("alembic-reupgrade.log", "Running upgrade"),
    ):
        if _digest(paths[log_name]) != _digest(paths[f"p53-10/runs/{run_id}/{log_name}"]):
            raise ValueError(f"Journal Alembic de l'exécution différent : {log_name}.")
        if operation not in paths[log_name].read_text(encoding="utf-8-sig"):
            raise ValueError(f"Opération Alembic absente du journal : {log_name}.")
    if retry_log in paths and _digest(paths[retry_log]) != _digest(paths[f"p53-10/runs/{run_id}/{retry_log}"]):
        raise ValueError("Journal Alembic de la reprise pytest différent.")
    if paths["alembic-current.txt"].read_text(encoding="utf-8-sig").strip() != f"{expected_revision} (head)":
        raise ValueError("Révision Alembic courante non conforme.")
    reconstruction = _read_json(paths[reconstruction_name])
    if reconstruction.get("status") != "passed" or reconstruction.get("revision") != expected_revision:
        raise ValueError("Preuve de reconstruction/rollback Alembic non conforme.")

    cases: dict[str, ET.Element] = {}
    counts: dict[str, dict[str, int]] = {}
    junit_times: list[datetime] = []
    for name in JUNIT_REPORTS:
        report_cases, report_counts, timestamps = _read_junit(paths[name])
        counts[name] = report_counts
        junit_times.extend(timestamps)
        if name == "pytest-quality.xml":
            cases = report_cases
    browser_count, browser_time = _check_browser(paths["phase-4-6/browser-axe.json"])
    if not started <= browser_time <= datetime.now(UTC) + timedelta(minutes=2):
        raise ValueError("Le rapport navigateur ne vient pas de l'exécution courante.")
    if any(
        not started - timedelta(seconds=2) <= moment <= browser_time + timedelta(minutes=2) for moment in junit_times
    ):
        raise ValueError("Les horodatages JUnit ne correspondent pas à l'exécution courante.")
    _scan_sensitive(paths)

    results: list[dict[str, object]] = []
    selected_case_ids: set[str] = set()
    for scenario in scenarios:
        scenario_id = scenario["id"]
        oracles = scenario.get("oracles")
        if not isinstance(oracles, list) or not oracles:
            raise ValueError(f"Oracle manquant pour {scenario_id}.")
        seen_oracles: set[str] = set()
        oracle_results: list[dict[str, object]] = []
        for oracle in oracles:
            if not isinstance(oracle, dict) or not isinstance(oracle.get("id"), str):
                raise ValueError(f"Oracle invalide pour {scenario_id}.")
            oracle_id = oracle["id"]
            if oracle_id in seen_oracles:
                raise ValueError(f"Oracle dupliqué pour {scenario_id}.")
            seen_oracles.add(oracle_id)
            if oracle.get("control") == "artifact_scan" and scenario_id == "P53-SEC-01":
                oracle_results.append({"id": oracle_id, "status": "passed", "control": "artifact_scan"})
                continue
            case_ids = _case_ids(oracle, scenario_id)
            missing = [case_id for case_id in case_ids if case_id not in cases]
            if missing:
                raise ValueError(f"Preuve JUnit manquante pour {scenario_id}/{oracle_id} : {missing[0]}.")
            selected_case_ids.update(case_ids)
            oracle_results.append({"id": oracle_id, "status": "passed", "cases": case_ids})
        results.append({"scenario_id": scenario_id, "status": "passed", "oracles": oracle_results})

    digests = {name: _digest(path) for name, path in paths.items()}
    case_results = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "source_report": "pytest-quality.xml",
        "source_report_sha256": digests["pytest-quality.xml"],
        "cases": [{"id": case_id, "status": "passed"} for case_id in sorted(selected_case_ids)],
    }
    case_results_bytes = (json.dumps(case_results, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _check_sensitive_content("case-results.json", case_results_bytes)
    junit_extract = _selected_junit_extract(selected_case_ids, digests["pytest-quality.xml"], started)
    _check_sensitive_content("junit-extract.xml", junit_extract)
    evidence: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "run_started_at": started.isoformat(),
        "source": "synthetic",
        "provider_modes": ["disabled", "simulated"],
        "currencies": CURRENCIES,
        "git_base_revision": git_revision,
        "git_dirty": context["git_dirty"],
        "source_tree_sha256": source_digest,
        "alembic_revision": expected_revision,
        "contains_pii": False,
        "contains_provider_secrets": False,
        "activation_authorized": False,
        "deferred_scenarios": ["P53-SBX-01"],
        "controls": {"artifact_scan": "passed", "alembic_reconstruction": "passed", "browser_axe": "passed"},
        "browser_paths": browser_count,
        "junit_counts": counts,
        "report_sha256": digests,
        "scanned_artifacts": sorted(paths),
        "manifest_sha256": _digest(manifest_path),
        "case_results_sha256": hashlib.sha256(case_results_bytes).hexdigest(),
        "junit_extract_sha256": hashlib.sha256(junit_extract).hexdigest(),
        "scenarios": results,
        "verdict": "passed",
    }
    evidence_bytes = (json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _check_sensitive_content("evidence.json", evidence_bytes)
    (output_dir / "case-results.json").write_bytes(case_results_bytes)
    (output_dir / "junit-extract.xml").write_bytes(junit_extract)
    (output_dir / "evidence.json").write_bytes(evidence_bytes)
    _write_zip(
        output_dir / "packet.zip",
        {
            "manifest.json": manifest_path.read_bytes(),
            "evidence.json": evidence_bytes,
            "case-results.json": case_results_bytes,
            "junit-extract.xml": junit_extract,
        },
    )
    (output_dir / "packet.sha256").write_text(_digest(output_dir / "packet.zip") + "  packet.zip\n", encoding="ascii")
    return evidence


def verify_packet(packet_path: Path, sha_path: Path, raw_junit_path: Path | None = None) -> dict[str, object]:
    expected_digest = sha_path.read_text(encoding="ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{64}  packet\.zip", expected_digest):
        raise ValueError("Empreinte du paquet P53-10 invalide.")
    if _digest(packet_path) != expected_digest.split()[0]:
        raise ValueError("Empreinte du paquet P53-10 différente du fichier archivé.")
    with ZipFile(packet_path) as archive:
        expected_names = {"manifest.json", "evidence.json", "case-results.json", "junit-extract.xml"}
        if set(archive.namelist()) != expected_names or len(archive.namelist()) != len(expected_names):
            raise ValueError("Le paquet P53-10 ne contient pas les quatre pièces attendues.")
        contents = {name: archive.read(name) for name in expected_names}
    for name, content in contents.items():
        _check_sensitive_content(name, content)
    manifest = json.loads(contents["manifest.json"])
    evidence = json.loads(contents["evidence.json"])
    case_results = json.loads(contents["case-results.json"])
    if not all(isinstance(item, dict) for item in (manifest, evidence, case_results)):
        raise ValueError("Structure du paquet P53-10 invalide.")
    scenarios = _validate_manifest(manifest)
    run_id = evidence.get("run_id")
    report_digests = evidence.get("report_sha256")
    git_base_revision = evidence.get("git_base_revision")
    alembic_revision = evidence.get("alembic_revision")
    source_tree_sha256 = evidence.get("source_tree_sha256")
    if (
        evidence.get("schema_version") != SCHEMA_VERSION
        or evidence.get("verdict") != "passed"
        or evidence.get("source") != "synthetic"
        or evidence.get("provider_modes") != ["disabled", "simulated"]
        or evidence.get("currencies") != CURRENCIES
        or evidence.get("deferred_scenarios") != ["P53-SBX-01"]
        or any(
            evidence.get(flag) is not False
            for flag in ("contains_pii", "contains_provider_secrets", "activation_authorized")
        )
        or not isinstance(evidence.get("git_dirty"), bool)
        or not isinstance(git_base_revision, str)
        or not re.fullmatch(r"[0-9a-f]{40}", git_base_revision)
        or not isinstance(source_tree_sha256, str)
        or not re.fullmatch(r"[0-9a-f]{64}", source_tree_sha256)
        or not isinstance(alembic_revision, str)
        or not re.fullmatch(r"[0-9]{8}_[0-9]{4}", alembic_revision)
        or evidence.get("controls")
        != {"artifact_scan": "passed", "alembic_reconstruction": "passed", "browser_axe": "passed"}
        or evidence.get("browser_paths") != 44
        or not isinstance(run_id, str)
        or not re.fullmatch(r"[0-9a-f]{32}", run_id)
        or not isinstance(report_digests, dict)
        or evidence.get("manifest_sha256") != hashlib.sha256(contents["manifest.json"]).hexdigest()
        or evidence.get("case_results_sha256") != hashlib.sha256(contents["case-results.json"]).hexdigest()
        or evidence.get("junit_extract_sha256") != hashlib.sha256(contents["junit-extract.xml"]).hexdigest()
        or case_results.get("schema_version") != SCHEMA_VERSION
        or case_results.get("run_id") != run_id
        or case_results.get("source_report") != "pytest-quality.xml"
        or case_results.get("source_report_sha256") != report_digests.get("pytest-quality.xml")
    ):
        raise ValueError("Métadonnées du paquet P53-10 incohérentes.")
    for key in ("run_started_at", "generated_at"):
        timestamp = evidence.get(key)
        if not isinstance(timestamp, str):
            raise ValueError(f"Horodatage du paquet P53-10 invalide : {key}.")
        _utc(timestamp)
    expected_reports = set(REPORTS) | {
        f"p53-10/runs/{run_id}/alembic-reconstruction.json",
        f"p53-10/runs/{run_id}/run-context.json",
        f"p53-10/runs/{run_id}/pytest-quality.xml",
        f"p53-10/runs/{run_id}/alembic-upgrade.log",
        f"p53-10/runs/{run_id}/alembic-downgrade.log",
        f"p53-10/runs/{run_id}/alembic-reupgrade.log",
    }
    retry_log = "alembic-pytest-retry-upgrade.log"
    if retry_log in report_digests or f"p53-10/runs/{run_id}/{retry_log}" in report_digests:
        expected_reports.update({retry_log, f"p53-10/runs/{run_id}/{retry_log}"})
    if (
        set(report_digests) != expected_reports
        or evidence.get("scanned_artifacts") != sorted(expected_reports)
        or any(
            not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) for value in report_digests.values()
        )
    ):
        raise ValueError("Portée ou empreintes des artefacts P53-10 incohérentes.")
    counts = evidence.get("junit_counts")
    if (
        not isinstance(counts, dict)
        or set(counts) != set(JUNIT_REPORTS)
        or any(
            not isinstance(item, dict)
            or not isinstance(item.get("tests"), int)
            or isinstance(item.get("tests"), bool)
            or item["tests"] < 1
            or any(item.get(key) != 0 for key in ("errors", "failures", "skipped"))
            for item in counts.values()
        )
    ):
        raise ValueError("Comptes JUnit du paquet P53-10 non conformes.")
    listed_cases = case_results.get("cases")
    if not isinstance(listed_cases, list) or any(not isinstance(item, dict) for item in listed_cases):
        raise ValueError("Liste des cas du paquet P53-10 invalide.")
    case_ids = [item.get("id") for item in listed_cases]
    if (
        any(not isinstance(case_id, str) or not case_id for case_id in case_ids)
        or any(item.get("status") != "passed" for item in listed_cases)
        or len(case_ids) != len(set(case_ids))
    ):
        raise ValueError("Résultats des cas du paquet P53-10 non conformes.")
    scenario_results = evidence.get("scenarios")
    if not isinstance(scenario_results, list) or len(scenario_results) != len(scenarios):
        raise ValueError("Scénarios du paquet P53-10 incomplets.")
    expected_case_ids: set[str] = set()
    if any(not isinstance(item, dict) or not isinstance(item.get("scenario_id"), str) for item in scenario_results):
        raise ValueError("Identifiants des scénarios du paquet P53-10 invalides.")
    by_scenario = {item["scenario_id"]: item for item in scenario_results}
    if len(by_scenario) != len(scenarios):
        raise ValueError("Scénarios du paquet P53-10 dupliqués.")
    for scenario in scenarios:
        result = by_scenario.get(scenario["id"])
        if not isinstance(result, dict) or result.get("status") != "passed":
            raise ValueError(f"Scénario P53-10 absent ou non conforme : {scenario['id']}.")
        actual_oracles = result.get("oracles")
        if not isinstance(actual_oracles, list) or len(actual_oracles) != len(scenario["oracles"]):
            raise ValueError(f"Oracles du paquet P53-10 incomplets : {scenario['id']}.")
        if any(not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in actual_oracles):
            raise ValueError(f"Identifiants des oracles du paquet P53-10 invalides : {scenario['id']}.")
        by_oracle = {item["id"]: item for item in actual_oracles}
        if len(by_oracle) != len(actual_oracles):
            raise ValueError(f"Oracles du paquet P53-10 dupliqués : {scenario['id']}.")
        for oracle in scenario["oracles"]:
            result_oracle = by_oracle.get(oracle["id"])
            if not isinstance(result_oracle, dict) or result_oracle.get("status") != "passed":
                raise ValueError(f"Oracle P53-10 absent ou non conforme : {scenario['id']}/{oracle['id']}.")
            if oracle.get("control") == "artifact_scan":
                if result_oracle.get("control") != "artifact_scan":
                    raise ValueError("Contrôle des artefacts P53-10 absent.")
                continue
            expected = _case_ids(oracle, scenario["id"])
            if result_oracle.get("cases") != expected:
                raise ValueError(f"Cas de l'oracle P53-10 modifiés : {scenario['id']}/{oracle['id']}.")
            expected_case_ids.update(expected)
    if set(case_ids) != expected_case_ids:
        raise ValueError("Le relevé JUnit expurgé ne correspond pas aux scénarios P53-10.")
    extract = ET.fromstring(contents["junit-extract.xml"])
    extracted_cases = list(extract)
    if (
        extract.tag != "testsuite"
        or extract.attrib.get("name") != "p53-10-selected-cases"
        or extract.attrib.get("timestamp") != evidence["run_started_at"]
        or extract.attrib.get("source_report_sha256") != report_digests["pytest-quality.xml"]
        or extract.attrib.get("tests") != str(len(expected_case_ids))
        or any(extract.attrib.get(key) != "0" for key in ("errors", "failures", "skipped"))
        or len(extracted_cases) != len(expected_case_ids)
        or any(
            case.tag != "testcase"
            or set(case.attrib) != {"classname", "name", "status"}
            or case.attrib["status"] != "passed"
            or list(case)
            for case in extracted_cases
        )
        or {f"{case.attrib['classname']}::{case.attrib['name']}" for case in extracted_cases} != expected_case_ids
    ):
        raise ValueError("Extrait JUnit expurgé du paquet P53-10 non conforme.")
    if raw_junit_path is not None:
        raw_digest = _digest(raw_junit_path)
        if (
            raw_digest != report_digests["pytest-quality.xml"]
            or raw_digest != report_digests[f"p53-10/runs/{run_id}/pytest-quality.xml"]
        ):
            raise ValueError("Rapport JUnit source différent du paquet P53-10.")
        raw_cases, raw_counts, _ = _read_junit(raw_junit_path)
        if raw_counts != counts["pytest-quality.xml"] or not expected_case_ids <= set(raw_cases):
            raise ValueError("Cas ou compteurs JUnit source différents du paquet P53-10.")
    return evidence


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "fingerprint":
        parser = argparse.ArgumentParser(description="Empreinte l'arbre source de cette exécution.")
        parser.add_argument("workspace", type=Path)
        args = parser.parse_args(argv[1:])
        try:
            print(source_fingerprint(args.workspace))
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            print(f"Échec de l'empreinte source P53-10 : {error}", file=sys.stderr)
            return 1
        return 0
    if argv and argv[0] == "verify":
        parser = argparse.ArgumentParser(description="Vérifie le paquet expurgé P53-10.")
        parser.add_argument("packet", type=Path)
        parser.add_argument("sha256", type=Path)
        parser.add_argument("raw_junit", type=Path, nargs="?")
        args = parser.parse_args(argv[1:])
        try:
            evidence = verify_packet(args.packet, args.sha256, args.raw_junit)
        except (OSError, ValueError, BadZipFile, ET.ParseError, json.JSONDecodeError) as error:
            print(f"Échec de vérification du paquet P53-10 : {error}", file=sys.stderr)
            return 1
        print(f"Paquet P53-10 vérifié : {evidence['run_id']}.")
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("results_root", type=Path)
    parser.add_argument("expected_revision")
    parser.add_argument("git_revision")
    parser.add_argument("run_id")
    args = parser.parse_args(argv)
    try:
        evidence = generate(args.manifest, args.results_root, args.expected_revision, args.git_revision, args.run_id)
    except (OSError, ValueError, ET.ParseError, json.JSONDecodeError) as error:
        print(f"Échec du verrou P53-10 : {error}", file=sys.stderr)
        return 1
    print(f"P53-10 : {len(evidence['scenarios'])} scénarios locaux prouvés ; paquet expurgé produit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
