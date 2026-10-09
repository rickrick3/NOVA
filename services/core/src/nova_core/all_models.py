"""Imports every module's ORM models so that ``Base.metadata`` is complete.

Used by the migration environment and by the schema drift test.
"""

from nova_core.audit import models as audit_models
from nova_core.identity import models as identity_models
from nova_core.projects import models as project_models
from nova_core.storage import models as storage_models

__all__ = ["audit_models", "identity_models", "project_models", "storage_models"]
