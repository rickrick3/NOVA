from datetime import datetime

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from nova_core.kernel.db import Base, UTCDateTime


class Blob(Base):
    __tablename__ = "blobs"

    sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    size: Mapped[int] = mapped_column(Integer)
    media_type: Mapped[str] = mapped_column(String(255))
    ref_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
