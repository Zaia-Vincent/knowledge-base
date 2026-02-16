"""SQLAlchemy ORM model for chat request logs."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class ChatRequestLogModel(Base):
    """ORM model — maps to the 'chat_request_logs' table."""

    __tablename__ = "chat_request_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    model: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="success", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    feature: Mapped[str] = mapped_column(
        String(50), default="chat", nullable=False, index=True,
    )
    tools_called: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    tool_call_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    request_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<ChatRequestLogModel(id={self.id}, model='{self.model}', "
            f"feature='{self.feature}', provider='{self.provider}', cost={self.cost})>"
        )
