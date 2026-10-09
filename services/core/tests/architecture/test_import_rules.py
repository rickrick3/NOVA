from pathlib import Path

import nova_core
from tests.architecture.import_rules import find_violations


def test_checker_detects_each_rule(tmp_path):
    pkg = tmp_path / "nova_core"
    sources = {
        "kernel/db.py": "from nova_core.projects.models import Project\n",
        "projects/models.py": "",
        "projects/service.py": "import anthropic\n",
        "audit/service.py": (
            "from nova_core.projects.repository import ProjectRepository\n"
            "from nova_core.projects.service import ProjectService\n"
        ),
        "app.py": "from nova_core.projects.api import router\n",
    }
    for rel, src in sources.items():
        path = pkg / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        (path.parent / "__init__.py").touch()
        path.write_text(src, encoding="utf-8")
    assert sorted(v.rule for v in find_violations(pkg)) == [
        "cross-module-internal",
        "kernel-imports-business",
        "provider-sdk-outside-providers",
    ]


def test_real_package_respects_the_rules():
    assert find_violations(Path(nova_core.__file__).parent) == []
