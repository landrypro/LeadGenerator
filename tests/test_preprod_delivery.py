from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_TOOL = ROOT / "scripts" / "preprod_release_manifest.py"
SHA = "a" * 40
DIGEST = "sha256:" + "b" * 64
IMAGE = f"123456789012.dkr.ecr.ca-central-1.amazonaws.com/marketteo/prospect-crm@{DIGEST}"


def _run_manifest(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(MANIFEST_TOOL), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _write_preprod_env(path: Path, *, image: str = IMAGE) -> None:
    path.write_text(
        "\n".join(
            (
                f"PREPROD_APP_IMAGE={image}",
                f"RELEASE_GIT_SHA={SHA}",
                f"RELEASE_IMAGE_DIGEST={DIGEST}",
            )
        )
        + "\n",
        encoding="utf-8",
    )


def test_release_manifest_is_created_and_matches_the_preprod_environment(tmp_path: Path) -> None:
    manifest = tmp_path / "release-manifest.json"
    env_file = tmp_path / ".env.preprod"
    _write_preprod_env(env_file)

    created = _run_manifest(
        "create",
        "--output",
        str(manifest),
        "--git-sha",
        SHA,
        "--image",
        IMAGE,
        "--image-digest",
        DIGEST,
        "--app-version",
        "5.1.0",
        "--alembic-revision",
        "20261004_0035",
    )
    assert created.returncode == 0, created.stderr
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "p5.1-release-manifest-v1"
    assert payload["image"] == IMAGE
    assert payload["manifest_sha256"]

    verified = _run_manifest("validate", "--manifest", str(manifest), "--env-file", str(env_file))
    assert verified.returncode == 0, verified.stderr


def test_release_manifest_rejects_an_environment_with_another_digest(tmp_path: Path) -> None:
    manifest = tmp_path / "release-manifest.json"
    env_file = tmp_path / ".env.preprod"
    _write_preprod_env(env_file, image=IMAGE.replace("b" * 64, "c" * 64))
    assert (
        _run_manifest(
            "create",
            "--output",
            str(manifest),
            "--git-sha",
            SHA,
            "--image",
            IMAGE,
            "--image-digest",
            DIGEST,
            "--app-version",
            "5.1.0",
            "--alembic-revision",
            "20261004_0035",
        ).returncode
        == 0
    )

    verified = _run_manifest("validate", "--manifest", str(manifest), "--env-file", str(env_file))
    assert verified.returncode != 0
    assert "image préproduction" in verified.stderr


def test_preprod_compose_only_accepts_an_immutable_application_image() -> None:
    compose = (ROOT / "compose.preprod.yaml").read_text(encoding="utf-8")
    assert "build:" not in compose
    assert "PREPROD_APP_IMAGE" in compose
    assert "PREPROD_ENV_FILE" in compose
    assert ":latest" not in compose


def test_preprod_pipeline_is_manual_and_gates_preprod_deployment() -> None:
    pipeline = (ROOT / "azure-pipelines.preprod.yml").read_text(encoding="utf-8")
    assert "trigger: none" in pipeline
    assert "pr: none" in pipeline
    assert "deployPreproduction" in pipeline
    assert "Test-QualityGateLocal.ps1" in pipeline
    assert "aws ecr describe-images" in pipeline
    assert 'environment: "marketteo-preproduction"' in pipeline
    assert "preprod-backup.sh" in pipeline


def test_parameter_store_renderer_keeps_secret_values_out_of_the_template() -> None:
    template = (ROOT / ".env.preprod.example").read_text(encoding="utf-8")
    renderer = (ROOT / "scripts" / "preprod-render-env.sh").read_text(encoding="utf-8")
    assert "PREPROD_PARAMETER_PREFIX=/marketteo/preproduction" in template
    assert "--with-decryption" in renderer
    assert "PREPROD_ENV_RENDERED" in renderer
    assert "set -x" not in renderer
