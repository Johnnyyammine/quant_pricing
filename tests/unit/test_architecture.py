"""The engine must stay a pure library: no web, API or UI imports."""

import ast
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[2] / "engine"
FORBIDDEN = {"api", "fastapi", "starlette", "pydantic", "uvicorn", "httpx", "QuantLib"}


def _imported_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_engine_has_no_forbidden_imports():
    files = sorted(ENGINE.rglob("*.py"))
    assert files
    violations = {str(f.relative_to(ENGINE)): sorted(_imported_roots(f) & FORBIDDEN) for f in files}
    assert {k: v for k, v in violations.items() if v} == {}
