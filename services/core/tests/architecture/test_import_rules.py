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


def test_checker_closes_the_bypasses_through_top_level_files(tmp_path):
    pkg = tmp_path / "nova_core"
    sources = {
        "all_models.py": "from nova_core.projects import models as project_models\n",
        "app.py": "from nova_core.projects.api import router\n",
        "projects/models.py": "",
        "projects/service.py": "",
        # another module reaching tables through the composition files
        "audit/service.py": "from nova_core.all_models import project_models\n",
        "kernel/db.py": "import nova_core.app\n",
        # a top-level shim has no privileges, and neither have its importers
        "shim.py": "from nova_core.projects.models import Project\n",
        "storage/service.py": "from nova_core.shim import Project\n",
        "storage/repository.py": "from nova_core.projects.service import ProjectService\n",
    }
    for rel, src in sources.items():
        path = pkg / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        (path.parent / "__init__.py").touch()
        path.write_text(src, encoding="utf-8")
    found = sorted((v.rule, v.importer) for v in find_violations(pkg))
    assert found == [
        ("cross-module-internal", "nova_core.shim"),
        ("cross-module-internal", "nova_core.storage.service"),
        ("imports-composition-root", "nova_core.audit.service"),
        ("imports-composition-root", "nova_core.kernel.db"),
    ]
