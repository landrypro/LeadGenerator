"""Construit et vérifie le manifeste immuable de préproduction P5.1."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Final

_SHA = re.compile(r"^[0-9a-f]{7,40}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_REQUIRED_ENV: Final = ("PREPROD_APP_IMAGE", "RELEASE_GIT_SHA", "RELEASE_IMAGE_DIGEST")


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{number}: variable d'environnement invalide")
        name, value = line.split("=", maxsplit=1)
        if not name or value.startswith(('"', "'")):
            raise ValueError(f"{path}:{number}: format d'environnement non supporté")
        values[name] = value
    return values


def _validate(git_sha: str, digest: str, image: str) -> None:
    if not _SHA.fullmatch(git_sha):
        raise ValueError("Le SHA Git doit être hexadécimal et contenir 7 à 40 caractères.")
    if not _DIGEST.fullmatch(digest):
        raise ValueError("Le digest OCI doit être de la forme sha256:<64 hexadécimaux>.")
    if not image.endswith(f"@{digest}") or ":latest" in image:
        raise ValueError("PREPROD_APP_IMAGE doit référencer exactement le digest OCI et ne jamais utiliser latest.")


def create_manifest(args: argparse.Namespace) -> None:
    _validate(args.git_sha, args.image_digest, args.image)
    payload = {
        "schema_version": "p5.1-release-manifest-v1",
        "git_sha": args.git_sha,
        "image": args.image,
        "image_digest": args.image_digest,
        "app_version": args.app_version,
        "alembic_revision": args.alembic_revision,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["manifest_sha256"] = hashlib.sha256(encoded).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_manifest(args: argparse.Namespace) -> None:
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    expected = {
        "schema_version",
        "git_sha",
        "image",
        "image_digest",
        "app_version",
        "alembic_revision",
        "manifest_sha256",
    }
    if set(payload) != expected:
        raise ValueError("Le manifeste contient des champs inattendus ou incomplets.")
    _validate(str(payload["git_sha"]), str(payload["image_digest"]), str(payload["image"]))
    unsigned = {key: value for key, value in payload.items() if key != "manifest_sha256"}
    encoded = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if hashlib.sha256(encoded).hexdigest() != payload["manifest_sha256"]:
        raise ValueError("L'empreinte du manifeste est invalide.")
    if args.env_file:
        values = _read_env(args.env_file)
        missing = [name for name in _REQUIRED_ENV if not values.get(name)]
        if missing:
            raise ValueError(f"Variables préproduction absentes : {', '.join(missing)}")
        if values["PREPROD_APP_IMAGE"] != payload["image"]:
            raise ValueError("L'image préproduction diffère du manifeste.")
        if values["RELEASE_GIT_SHA"].lower() != payload["git_sha"]:
            raise ValueError("Le SHA préproduction diffère du manifeste.")
        if values["RELEASE_IMAGE_DIGEST"].lower() != payload["image_digest"]:
            raise ValueError("Le digest préproduction diffère du manifeste.")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subparsers = result.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("--git-sha", required=True)
    create.add_argument("--image", required=True)
    create.add_argument("--image-digest", required=True)
    create.add_argument("--app-version", required=True)
    create.add_argument("--alembic-revision", required=True)
    create.add_argument("--output", type=Path, required=True)
    create.set_defaults(handler=create_manifest)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--manifest", type=Path, required=True)
    validate.add_argument("--env-file", type=Path)
    validate.set_defaults(handler=validate_manifest)
    return result


def main() -> int:
    arguments = parser().parse_args()
    try:
        arguments.handler(arguments)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"Manifest préproduction invalide : {error}") from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
