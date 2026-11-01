<<<<<<< HEAD
"""AI draft — raw text and parse status only (v2.1)."""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
=======
"""AI drafts — raw text, parse status, and JSON payloads (restored from ok_ai_drafts)."""
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, Text
>>>>>>> 4a28f5df6e17f8be24ab6bebfa6f3bc599e6b284
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
<<<<<<< HEAD
=======
    model_output: Mapped[dict] = mapped_column(JSON, default=dict)
    app_draft: Mapped[dict] = mapped_column(JSON, default=dict)
    questions: Mapped[list] = mapped_column(JSON, default=list)
>>>>>>> 4a28f5df6e17f8be24ab6bebfa6f3bc599e6b284
    parse_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
