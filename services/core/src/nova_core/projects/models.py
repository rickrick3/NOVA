from datetime import datetime

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from nova_core.kernel.db import Base, UTCDateTime


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    llm_privacy: Mapped[str] = mapped_column(String(16))
    web_access: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    # The "free space" project that holds conversations not yet filed anywhere (INV-12).
    is_default: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)
