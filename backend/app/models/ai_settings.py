"""UserAISettings — stores encrypted API keys and model preferences per user."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserAISettings(Base):
    __tablename__ = "user_ai_settings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    provider: Mapped[str] = mapped_column(
        SAEnum("google", "anthropic", "openai", name="ai_provider_enum"),
        nullable=False, default="google",
    )
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    # Last 4 chars of the plain key, stored separately so we can render a
    # masked preview without ever decrypting the key on a read path.
    api_key_last4: Mapped[str] = mapped_column(String(4), nullable=False, default="")
    cheap_model: Mapped[str] = mapped_column(
        String(100), nullable=False, default="gemini-2.5-flash"
    )
    smart_model: Mapped[str] = mapped_column(
        String(100), nullable=False, default="gemini-2.5-pro"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
