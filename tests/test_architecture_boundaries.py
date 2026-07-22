import ast
from pathlib import Path

APP_ROOT = Path(__file__).parents[1] / "backend" / "app"


def imported_roots(directory: Path) -> set[str]:
    roots: set[str] = set()
    for path in directory.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
    return roots


def test_domain_has_no_framework_or_outer_layer_dependency() -> None:
    imports = imported_roots(APP_ROOT / "domain")

    assert imports.isdisjoint({"application", "infrastructure", "presentation"})
    assert imports.isdisjoint({"fastapi", "pydantic", "httpx", "openpyxl"})


def test_application_has_no_framework_or_adapter_dependency() -> None:
    imports = imported_roots(APP_ROOT / "application")

    assert imports.isdisjoint({"infrastructure", "presentation"})
    assert imports.isdisjoint({"fastapi", "pydantic", "httpx", "openpyxl"})
