import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_provider: Mapped[str] = mapped_column(
        SAEnum("email", "google", "microsoft", name="auth_provider_enum"),
        default="email"
    )
    role: Mapped[str] = mapped_column(
        SAEnum("user", "admin", "master_admin", name="user_role_enum"),
        nullable=False,
        default="user",
        server_default="user",
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Tokens issued before this timestamp are considered invalid. Bumped on
    # password change so old JWTs cannot be used after a credential rotation.
    password_changed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Soft-delete: when set, the user can no longer authenticate; data is
    # retained for audit/recovery until a separate purge job runs.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
