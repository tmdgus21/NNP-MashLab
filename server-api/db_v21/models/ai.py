"""AI draft — raw text and parse status only (v2.1)."""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db_v21.base import Base, now, uid


class AiDraft(Base):
    __tablename__ = "ai_drafts"
    __table_args__ = (
        CheckConstraint(
            "parse_status IN ('PENDING', 'COMPLETED', 'FAILED')",
            name="ck_ai_drafts_parse_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    room_member_id: Mapped[str] = mapped_column(
        ForeignKey("room_members.id", ondelete="CASCADE"), index=True
    )
    raw_text: Mapped[str] = mapped_column(Text)
    parse_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
