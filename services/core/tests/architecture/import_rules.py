"""Static check of the dependency rules in docs/phase-0/03-modules.md §2."""

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

SERVICE_SURFACE = frozenset({"service", "schemas", "deps"})
PROVIDER_SDKS = frozenset({"anthropic", "ollama", "openai", "tavily"})
# The composition files may import anything, and nothing else may import them:
# otherwise they become a side door to every module's internals.
COMPOSITION_FILES = frozenset({"app", "__main__", "all_models"})
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
            is_package_of_modules = len(parts) == 2 and parts[1] not in COMPOSITION_FILES
            # "from nova_core.projects import service" names the submodule, not the package
            if parts[0] == package_name and (len(parts) == 1 or is_package_of_modules):
                for alias in node.names:
                    yield f"{module}.{alias.name}"
            else:
                yield module


def _is_unit(package_dir: Path, name: str) -> bool:
    """A sub-package, or a top-level file that is not a composition file."""
    if (package_dir / name).is_dir():
        return True
    return (package_dir / f"{name}.py").is_file() and name not in COMPOSITION_FILES


def find_violations(package_dir: Path, package_name: str = "nova_core") -> list[Violation]:
    violations: list[Violation] = []
    for path in sorted(package_dir.rglob("*.py")):
        relative = path.relative_to(package_dir)
        top_level = len(relative.parts) == 1
        if top_level and relative.stem in COMPOSITION_FILES:
            continue
        # A top-level file other than the composition files is a unit with no privileges.
        own_unit = relative.stem if top_level else relative.parts[0]
        if own_unit == "__init__":
            own_unit = None
        importer_package = [package_name, *relative.parts[:-1]]
        importer = ".".join([*importer_package, relative.stem])
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        for imported in _imported_names(tree, importer_package, package_name):
            parts = imported.split(".")
            if parts[0] in PROVIDER_SDKS and own_unit != PROVIDERS:
                violations.append(Violation("provider-sdk-outside-providers", importer, imported))
                continue
            if parts[0] != package_name or len(parts) < 2:
                continue
            target = parts[1]
            if target in COMPOSITION_FILES:
                violations.append(Violation("imports-composition-root", importer, imported))
                continue
            if not _is_unit(package_dir, target) or target == own_unit:
                continue
            if own_unit == KERNEL:
                violations.append(Violation("kernel-imports-business", importer, imported))
            elif own_unit is not None and target != KERNEL:
                surface = parts[2] if len(parts) > 2 else None
                if surface not in SERVICE_SURFACE:
                    violations.append(Violation("cross-module-internal", importer, imported))
    return violations
