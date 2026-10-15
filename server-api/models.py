from datetime import date, datetime, time
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, Time, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB


class Base(DeclarativeBase):
    pass


class Room(Base):  # 모임의 기본 정보, 방 코드, 운영 시간, 현재 상태와 버전을 관리한다.
    __tablename__ = "rooms"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(8), unique=True)
    title: Mapped[str] = mapped_column(String(100))
    date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    status: Mapped[str] = mapped_column(String(20))
    version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime)

class Member(Base):  # 방에 참여한 사용자의 닉네임과 방장 여부를 관리한다.
    __tablename__ = "members"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    room_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("rooms.id"))
    nickname: Mapped[str] = mapped_column(String(30))
    is_owner: Mapped[bool] = mapped_column(Boolean)
    joined_at: Mapped[datetime] = mapped_column(DateTime)

class Role(Base):   # 방에서 사용할 역할과 역할별 필요 인원을 관리한다.
    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    room_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("rooms.id"))
    name: Mapped[str] = mapped_column(String(30))
    need_count: Mapped[int] = mapped_column(Integer)

class Availability(Base):  # 참가자가 가능한 시간대와 해당 조건의 버전을 저장한다.
    __tablename__ = "availability"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    member_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("members.id"))
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    version: Mapped[int] = mapped_column(Integer)

class Preference(Base):  # 참가자의 가능 역할, 선호 여부, 간단한 조건 메모를 저장한다.
    __tablename__ = "preferences"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    member_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("members.id"))
    role_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("roles.id"))
    preferred: Mapped[bool] = mapped_column(Boolean)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer)

class Plan(Base):   # OR-Tools가 생성한 역할 배정안의 버전과 상태를 관리한다.
    __tablename__ = "plans"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    room_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("rooms.id"))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime)

class Assignment(Base):  # 배정안 안에서 누가 어떤 역할을 어느 시간에 맡는지 저장한다.
    __tablename__ = "assignments"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("plans.id"))
    member_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("members.id"))
    role_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("roles.id"))
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    completed: Mapped[bool] = mapped_column(Boolean)

class Consent(Base):  # 참가자의 배정안 동의 여부와 동의 시각을 저장한다.
    __tablename__ = "consents"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("plans.id"))
    member_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("members.id"))
    agreed: Mapped[bool] = mapped_column(Boolean)
    agreed_at: Mapped[datetime] = mapped_column(DateTime)

class AiDraft(Base):  # 자연어 조건과 AI가 해석한 구조화 초안을 저장하고 사용자 확인 여부를 저장한다.
    __tablename__ = "ai_drafts"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    member_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("members.id"))
    input_text: Mapped[str] = mapped_column(Text)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime)