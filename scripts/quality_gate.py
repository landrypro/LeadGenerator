"""Contrôles déterministes des verrous qualité."""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
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
                failures.append(f"{path}: utilisation interdite ({label})")
    for path in sorted(source_root.rglob("*.test.*")):
        if FOCUSED_TEST_PATTERN.search(path.read_text(encoding="utf-8")):
            failures.append(f"{path}: test only/skip/todo interdit")
    if failures:
        raise ValueError("\n".join(failures))


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
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "junit-no-skips":
            assert_junit_has_no_skips(arguments.report)
        elif arguments.command == "alembic-current":
            assert_alembic_current_revision(arguments.report, arguments.expected_revision)
        elif arguments.command == "browser-sources":
            assert_browser_sources_are_safe(arguments.source)
        else:
            assert_artifact_is_safe(arguments.directory)
    except (OSError, ET.ParseError, ValueError) as error:
        print(f"Échec du verrou qualité : {error}", file=sys.stderr)
        return 1
    print("Verrou qualité ciblé : conforme.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
