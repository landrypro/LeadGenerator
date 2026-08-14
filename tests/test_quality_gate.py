from pathlib import Path

import pytest

from scripts.quality_gate import (
    assert_alembic_current_revision,
    assert_artifact_is_safe,
    assert_browser_sources_are_safe,
    assert_junit_has_no_skips,
)


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
