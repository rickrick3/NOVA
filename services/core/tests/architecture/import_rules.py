"""Static check of the dependency rules in docs/phase-0/03-modules.md §2."""

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

SERVICE_SURFACE = frozenset({"service", "schemas", "deps"})
PROVIDER_SDKS = frozenset({"anthropic", "ollama", "openai", "tavily"})
EXEMPT_FILES = frozenset({"app.py", "__main__.py", "all_models.py"})
KERNEL = "kernel"
PROVIDERS = "providers"


@dataclass(frozen=True)
class Violation:
    rule: str
    importer: str
    imported: str


def _absolute(module: str | None, level: int, importer_package: list[str]) -> str | None:
    if level == 0:
        return module
    base = importer_package[: len(importer_package) - (level - 1)]
    return ".".join([*base, module] if module else base) or None


def _imported_names(tree: ast.AST, importer_package: list[str], package_name: str) -> Iterator[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            module = _absolute(node.module, node.level, importer_package)
            if module is None:
                continue
            parts = module.split(".")
            # "from nova_core.projects import service" names the submodule, not the package
            if parts[0] == package_name and len(parts) <= 2:
                for alias in node.names:
                    yield f"{module}.{alias.name}"
            else:
                yield module


def find_violations(package_dir: Path, package_name: str = "nova_core") -> list[Violation]:
    violations: list[Violation] = []
    for path in sorted(package_dir.rglob("*.py")):
        relative = path.relative_to(package_dir)
        if len(relative.parts) == 1 and relative.name in EXEMPT_FILES:
            continue
        importer_package = [package_name, *relative.parts[:-1]]
        importer = ".".join([*importer_package, relative.stem])
        own_module = relative.parts[0] if len(relative.parts) > 1 else None
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        for imported in _imported_names(tree, importer_package, package_name):
            parts = imported.split(".")
            if parts[0] in PROVIDER_SDKS and own_module != PROVIDERS:
                violations.append(Violation("provider-sdk-outside-providers", importer, imported))
                continue
            if parts[0] != package_name or len(parts) < 2:
                continue
            target = parts[1]
            if not (package_dir / target).is_dir() or target == own_module:
                continue
            if own_module == KERNEL:
                violations.append(Violation("kernel-imports-business", importer, imported))
            elif own_module is not None and target != KERNEL:
                surface = parts[2] if len(parts) > 2 else None
                if surface not in SERVICE_SURFACE:
                    violations.append(Violation("cross-module-internal", importer, imported))
    return violations
