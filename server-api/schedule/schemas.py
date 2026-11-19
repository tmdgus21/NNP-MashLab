"""Pydantic schemas for Potato Meet schedule API (camelCase JSON)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


class ApiModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
        alias_generator=to_camel,
    )


class TimeRangeIn(ApiModel):
    start: datetime
    end: datetime

    @field_validator("start", "end", mode="before")
    @classmethod
    def _parse(cls, value: Any) -> Any:
        if isinstance(value, str):
            from schedule.timeutil import parse_iso_dt

            return parse_iso_dt(value)
        return value


class CreateMeetingIn(ApiModel):
    title: str = Field(min_length=1, max_length=100)
    nickname: str = Field(min_length=1, max_length=30)
    start_date: date
    end_date: date


class JoinMeetingIn(ApiModel):
    code: str = Field(pattern=r"^[A-Za-z2-9]{8}$")
    nickname: str = Field(min_length=1, max_length=30)


class SubmitResponseIn(ApiModel):
    available: list[TimeRangeIn] = Field(default_factory=list, max_length=500)


class VoteIn(ApiModel):
    candidate_ids: list[str] = Field(default_factory=list, max_length=50)


class RevisionIn(ApiModel):
    expected_revision: int = Field(ge=1)
