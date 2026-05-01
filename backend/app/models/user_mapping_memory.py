import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from app.db.base import Base

class UserMappingMemory(Base):
    __tablename__ = "user_mapping_memory"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    original_name = Column(String, nullable=False)
    mapped_to = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    last_used_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
