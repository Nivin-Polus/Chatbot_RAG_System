from sqlalchemy import Column, String, LargeBinary, ForeignKey, DateTime
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.models.base import Base


class FileBinary(Base):
    __tablename__ = "file_binaries"

    file_id = Column(String(36), ForeignKey("file_metadata.file_id", ondelete="CASCADE"), primary_key=True)
    data = Column(LONGBLOB, nullable=False)
    mime_type = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    file_metadata = relationship("FileMetadata", back_populates="binary", uselist=False)
