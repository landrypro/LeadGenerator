"""Le paquet P53-10 échoue fermé sur les preuves absentes ou sensibles."""

from __future__ import annotations

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from scripts.p53_10_evidence import JUNIT_REPORTS, REPORTS, generate, source_fingerprint, verify_packet

MANIFEST = Path("docs/recettes/p53-10/manifest.json")
REVISION = "20261025_0062"
GIT_SHA = "a" * 40
RUN_ID = "b" * 32


def _fixture_reports(root: Path) -> None:
    root.mkdir(exist_ok=True)
    now = datetime.now(UTC).isoformat()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cases: set[str] = set()
    for scenario in manifest["scenarios"]:
        for oracle in scenario["oracles"]:
            for template in oracle.get("cases", []):
                if oracle.get("currencies") and "{currency}" in template:
                    cases.update(template.replace("{currency}", value) for value in manifest["currencies"])
                else:
                    cases.add(template)
    suite = ET.Element("testsuite", tests=str(len(cases)), errors="0", failures="0", skipped="0", timestamp=now)
    for item in sorted(cases):
        classname, name = item.split("::", 1)
        ET.SubElement(suite, "testcase", classname=classname, name=name)
    for name in JUNIT_REPORTS:
        (root / name).write_bytes(ET.tostring(suite, encoding="utf-8"))
    (root / "alembic-current.txt").write_text(f"{REVISION} (head)\n", encoding="utf-8")
    for name, operation in (
        ("alembic-upgrade.log", "Running upgrade"),
        ("alembic-downgrade.log", "Running downgrade"),
        ("alembic-reupgrade.log", "Running upgrade"),
    ):
        (root / name).write_text(f"{operation} passed\n", encoding="utf-8")
    (root / "vitest-console.log").write_text("253 tests passed\n", encoding="utf-8")
    p52 = root / "p52-08" / "evidence.json"
    p52.parent.mkdir(exist_ok=True)
    p52.write_text(json.dumps({"verdict": "passed", "source": "synthetic"}), encoding="utf-8")
    browser = root / "phase-4-6" / "browser-axe.json"
    browser.parent.mkdir(exist_ok=True)
    browser.write_text(
        json.dumps(
            {
                "verdict": "PASS",
                "failures": [],
                "checks": [{"errors": [], "violations": []} for _ in range(44)],
                "finishedAt": now,
            }
        ),
        encoding="utf-8",
    )
    evidence = root / "p53-10" / "runs" / RUN_ID
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "pytest-quality.xml").write_bytes((root / "pytest-quality.xml").read_bytes())
    (evidence / "run-context.json").write_text(
        json.dumps(
            {
                "source": "synthetic",
                "run_id": RUN_ID,
                "started_at": "2020-01-01T00:00:00+00:00",
                "git_revision": GIT_SHA,
                "git_dirty": True,
                "source_tree_sha256": "d" * 64,
            }
        ),
        encoding="utf-8",
    )
    (evidence / "alembic-reconstruction.json").write_text(
        json.dumps({"status": "passed", "revision": REVISION, "generated_at": now}), encoding="utf-8"
    )
    for name in ("alembic-upgrade.log", "alembic-downgrade.log", "alembic-reupgrade.log"):
        (evidence / name).write_bytes((root / name).read_bytes())
    assert all((root / name).is_file() for name in REPORTS)


def test_p53_10_evidence_is_exact_minimized_and_replayable(tmp_path: Path) -> None:
    _fixture_reports(tmp_path)
    first = generate(MANIFEST, tmp_path, REVISION, GIT_SHA, RUN_ID)
    again = generate(MANIFEST, tmp_path, REVISION, GIT_SHA, RUN_ID)

    assert first["verdict"] == again["verdict"] == "passed"
    assert len(first["scenarios"]) == 20
    assert first["git_dirty"] is True
    assert first["source_tree_sha256"] == "d" * 64
    assert first["deferred_scenarios"] == ["P53-SBX-01"]
    rec = next(item for item in first["scenarios"] if item["scenario_id"] == "P53-REC-01")
    assert {oracle["id"] for oracle in rec["oracles"]} == {"projection_divergence", "timeout_after_effect"}
    assert first["report_sha256"] == again["report_sha256"]
    run = tmp_path / "p53-10" / "runs" / RUN_ID
    assert (run / "packet.sha256").is_file()
    expected_hash = (run / "packet.sha256").read_text(encoding="ascii").split()[0]
    actual_hash = hashlib.sha256((run / "packet.zip").read_bytes()).hexdigest()
    assert expected_hash == actual_hash
    assert verify_packet(run / "packet.zip", run / "packet.sha256", run / "pytest-quality.xml")["run_id"] == RUN_ID
    with ZipFile(run / "packet.zip") as archive:
        assert set(archive.namelist()) == {"manifest.json", "evidence.json", "case-results.json", "junit-extract.xml"}
        assert b"sk_test_" not in archive.read("evidence.json")
        ledger = json.loads(archive.read("case-results.json"))
        assert ledger["source_report_sha256"] == first["report_sha256"]["pytest-quality.xml"]
        extract = ET.fromstring(archive.read("junit-extract.xml"))
        assert int(extract.attrib["tests"]) == len(ledger["cases"])
        assert {f"{case.attrib['classname']}::{case.attrib['name']}" for case in extract} == {
            case["id"] for case in ledger["cases"]
        }


def test_p53_10_rejects_missing_case_skip_and_stale_report(tmp_path: Path) -> None:
    _fixture_reports(tmp_path)
    report = tmp_path / "pytest-quality.xml"
    timestamp = datetime.now(UTC).isoformat()
    report.write_text(
        f'<testsuite tests="1" timestamp="{timestamp}"><testcase classname="wrong" name="wrong" /></testsuite>',
        encoding="utf-8",
    )
    (tmp_path / "p53-10" / "runs" / RUN_ID / "pytest-quality.xml").write_bytes(report.read_bytes())
    with pytest.raises(ValueError, match="Preuve JUnit manquante"):
        generate(MANIFEST, tmp_path, REVISION, GIT_SHA, RUN_ID)

    _fixture_reports_after_existing_root(tmp_path)
    report.write_text(
        f'<testsuite tests="1" skipped="1" timestamp="{timestamp}">'
        '<testcase classname="x" name="y"><skipped /></testcase></testsuite>',
        encoding="utf-8",
    )
    (tmp_path / "p53-10" / "runs" / RUN_ID / "pytest-quality.xml").write_bytes(report.read_bytes())
    with pytest.raises(ValueError, match="skip"):
        generate(MANIFEST, tmp_path, REVISION, GIT_SHA, RUN_ID)

    _fixture_reports_after_existing_root(tmp_path)
    context = tmp_path / "p53-10" / "runs" / RUN_ID / "run-context.json"
    payload = json.loads(context.read_text(encoding="utf-8"))
    payload["started_at"] = "2099-01-01T00:00:00+00:00"
    context.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="antérieur"):
        generate(MANIFEST, tmp_path, REVISION, GIT_SHA, RUN_ID)


def _fixture_reports_after_existing_root(root: Path) -> None:
    # Réinitialise les seuls rapports JUnit en gardant le même dossier temporaire.
    fresh = root / "fresh"
    _fixture_reports(fresh)
    for name in JUNIT_REPORTS:
        (root / name).write_bytes((fresh / name).read_bytes())
    (root / "p53-10" / "runs" / RUN_ID / "pytest-quality.xml").write_bytes((root / "pytest-quality.xml").read_bytes())


def test_p53_10_rejects_sensitive_artifact_and_revision_mismatch(tmp_path: Path) -> None:
    _fixture_reports(tmp_path)
    report = tmp_path / "alembic-upgrade.log"
    run_report = tmp_path / "p53-10" / "runs" / RUN_ID / "alembic-upgrade.log"
    report.write_text("Running upgrade sk_test_abcdefghijklmnop\n", encoding="utf-8")
    run_report.write_bytes(report.read_bytes())
    with pytest.raises(ValueError, match="Contenu sensible"):
        generate(MANIFEST, tmp_path, REVISION, GIT_SHA, RUN_ID)
    assert not (tmp_path / "p53-10" / "runs" / RUN_ID / "packet.zip").exists()

    report.write_text("Running upgrade passed\n", encoding="utf-8")
    run_report.write_bytes(report.read_bytes())
    with pytest.raises(ValueError, match="Révision Alembic"):
        generate(MANIFEST, tmp_path, "20261023_0058", GIT_SHA, RUN_ID)


def test_p53_10_rejects_secret_in_manifest_before_archiving(tmp_path: Path) -> None:
    _fixture_reports(tmp_path)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["scenarios"][0]["oracles"][0]["id"] = "sk_test_abcdefghijklmnop"
    unsafe = tmp_path / "manifest.json"
    unsafe.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="Contenu sensible"):
        generate(unsafe, tmp_path, REVISION, GIT_SHA, RUN_ID)
    assert not (tmp_path / "p53-10" / "runs" / RUN_ID / "packet.zip").exists()


def test_p53_10_rejects_removed_oracle_and_preserves_an_older_packet(tmp_path: Path) -> None:
    _fixture_reports(tmp_path)
    older = tmp_path / "p53-10" / "runs" / ("c" * 32) / "packet.zip"
    older.parent.mkdir(parents=True)
    older.write_bytes(b"older-packet")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    scenario = next(item for item in manifest["scenarios"] if item["id"] == "P53-WEB-02")
    scenario["oracles"] = scenario["oracles"][:1]
    incomplete = tmp_path / "manifest.json"
    incomplete.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="Oracles requis manquants"):
        generate(incomplete, tmp_path, REVISION, GIT_SHA, RUN_ID)
    assert older.read_bytes() == b"older-packet"


def test_p53_10_rejects_weakened_oracle_case_mapping(tmp_path: Path) -> None:
    _fixture_reports(tmp_path)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    scenario = next(item for item in manifest["scenarios"] if item["id"] == "P53-WEB-02")
    scenario["oracles"][0]["cases"] = [
        "tests.test_p53_10_evidence::test_p53_10_evidence_is_exact_minimized_and_replayable"
    ]
    weakened = tmp_path / "weakened-manifest.json"
    weakened.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="Correspondances oracle/cas"):
        generate(weakened, tmp_path, REVISION, GIT_SHA, RUN_ID)


@pytest.mark.parametrize("report", ["vitest-console.log", "p52-08/evidence.json"])
def test_p53_10_scans_related_reports_before_declaring_security_passed(tmp_path: Path, report: str) -> None:
    _fixture_reports(tmp_path)
    (tmp_path / report).write_text("sk_test_abcdefghijklmnop\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Contenu sensible"):
        generate(MANIFEST, tmp_path, REVISION, GIT_SHA, RUN_ID)


def test_p53_10_packet_verifier_rejects_modified_case_results(tmp_path: Path) -> None:
    _fixture_reports(tmp_path)
    generate(MANIFEST, tmp_path, REVISION, GIT_SHA, RUN_ID)
    run = tmp_path / "p53-10" / "runs" / RUN_ID
    packet = run / "packet.zip"
    with ZipFile(packet) as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
    ledger = json.loads(contents["case-results.json"])
    ledger["cases"].pop()
    contents["case-results.json"] = json.dumps(ledger).encode("utf-8")
    with ZipFile(packet, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in contents.items():
            archive.writestr(name, content)
    (run / "packet.sha256").write_text(hashlib.sha256(packet.read_bytes()).hexdigest() + "  packet.zip\n")

    with pytest.raises(ValueError, match="Métadonnées du paquet"):
        verify_packet(packet, run / "packet.sha256")


def test_p53_10_packet_verifier_rejects_malformed_counts(tmp_path: Path) -> None:
    _fixture_reports(tmp_path)
    generate(MANIFEST, tmp_path, REVISION, GIT_SHA, RUN_ID)
    run = tmp_path / "p53-10" / "runs" / RUN_ID
    packet = run / "packet.zip"
    with ZipFile(packet) as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
    evidence = json.loads(contents["evidence.json"])
    evidence["junit_counts"]["pytest-quality.xml"]["tests"] = "many"
    contents["evidence.json"] = json.dumps(evidence).encode("utf-8")
    with ZipFile(packet, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in contents.items():
            archive.writestr(name, content)
    (run / "packet.sha256").write_text(hashlib.sha256(packet.read_bytes()).hexdigest() + "  packet.zip\n")

    with pytest.raises(ValueError, match="Comptes JUnit"):
        verify_packet(packet, run / "packet.sha256")


def test_p53_10_packet_verifier_rejects_activation_claim(tmp_path: Path) -> None:
    _fixture_reports(tmp_path)
    generate(MANIFEST, tmp_path, REVISION, GIT_SHA, RUN_ID)
    run = tmp_path / "p53-10" / "runs" / RUN_ID
    packet = run / "packet.zip"
    with ZipFile(packet) as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
    evidence = json.loads(contents["evidence.json"])
    evidence["activation_authorized"] = True
    contents["evidence.json"] = json.dumps(evidence).encode("utf-8")
    with ZipFile(packet, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in contents.items():
            archive.writestr(name, content)
    (run / "packet.sha256").write_text(hashlib.sha256(packet.read_bytes()).hexdigest() + "  packet.zip\n")

    with pytest.raises(ValueError, match="Métadonnées du paquet"):
        verify_packet(packet, run / "packet.sha256")


def test_p53_10_packet_verifier_rejects_weakened_junit_extract(tmp_path: Path) -> None:
    _fixture_reports(tmp_path)
    generate(MANIFEST, tmp_path, REVISION, GIT_SHA, RUN_ID)
    run = tmp_path / "p53-10" / "runs" / RUN_ID
    packet = run / "packet.zip"
    with ZipFile(packet) as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
    extract = ET.fromstring(contents["junit-extract.xml"])
    extract.remove(extract[0])
    contents["junit-extract.xml"] = ET.tostring(extract, encoding="utf-8")
    evidence = json.loads(contents["evidence.json"])
    evidence["junit_extract_sha256"] = hashlib.sha256(contents["junit-extract.xml"]).hexdigest()
    contents["evidence.json"] = json.dumps(evidence).encode("utf-8")
    with ZipFile(packet, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in contents.items():
            archive.writestr(name, content)
    (run / "packet.sha256").write_text(hashlib.sha256(packet.read_bytes()).hexdigest() + "  packet.zip\n")

    with pytest.raises(ValueError, match="Extrait JUnit"):
        verify_packet(packet, run / "packet.sha256")


def test_p53_10_packet_verifier_checks_the_archived_raw_junit(tmp_path: Path) -> None:
    _fixture_reports(tmp_path)
    generate(MANIFEST, tmp_path, REVISION, GIT_SHA, RUN_ID)
    run = tmp_path / "p53-10" / "runs" / RUN_ID
    assert verify_packet(run / "packet.zip", run / "packet.sha256", run / "pytest-quality.xml")
    (run / "pytest-quality.xml").write_text("<testsuite tests='0' />", encoding="utf-8")
    with pytest.raises(ValueError, match="Rapport JUnit source différent"):
        verify_packet(run / "packet.zip", run / "packet.sha256", run / "pytest-quality.xml")


def test_p53_10_source_fingerprint_includes_uncommitted_and_untracked_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    tracked = repo / "tracked.py"
    tracked.write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "tracked.py"], check=True)
    untracked = repo / "untracked.py"
    untracked.write_text("other = 1\n", encoding="utf-8")
    before = source_fingerprint(repo)
    tracked.write_text("value = 2\n", encoding="utf-8")
    assert source_fingerprint(repo) != before
    tracked.write_text("value = 1\n", encoding="utf-8")
    untracked.write_text("other = 2\n", encoding="utf-8")
    assert source_fingerprint(repo) != before
