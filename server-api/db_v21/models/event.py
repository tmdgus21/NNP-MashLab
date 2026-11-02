"""Room activity events."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db_v21.base import Base, now, uid


class RoomEvent(Base):
    __tablename__ = "room_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    room_id: Mapped[str] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), index=True
    )
    actor_member_id: Mapped[str | None] = mapped_column(
        ForeignKey("room_members.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
