"""Imports every module's ORM models so that ``Base.metadata`` is complete.

Used by the migration environment and by the schema drift test.
"""

from nova_core.storage import models as storage_models

__all__ = ["storage_models"]
