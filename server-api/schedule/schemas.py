"""Pydantic schemas for Potato Meet schedule API (camelCase JSON)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    start_date: date | None = None
    end_date: date | None = None
    selected_dates: list[date] | None = None

    @model_validator(mode="after")
    def _xor_date_modes(self) -> CreateMeetingIn:
        has_range = self.start_date is not None or self.end_date is not None
        has_list = self.selected_dates is not None
        if has_range and has_list:
            raise ValueError(
                "selectedDates와 startDate/endDate는 함께 보낼 수 없습니다."
            )
        if has_list:
            if not self.selected_dates:
                raise ValueError("날짜를 1개 이상 선택해 주세요.")
            return self
        if self.start_date is None or self.end_date is None:
            raise ValueError("startDate와 endDate, 또는 selectedDates가 필요합니다.")
        return self


class JoinMeetingIn(ApiModel):
    code: str = Field(pattern=r"^[A-Za-z2-9]{8}$")
    nickname: str = Field(min_length=1, max_length=30)


class SubmitResponseIn(ApiModel):
    available: list[TimeRangeIn] = Field(default_factory=list, max_length=500)


class VoteIn(ApiModel):
    candidate_ids: list[str] = Field(default_factory=list, max_length=50)


class RevisionIn(ApiModel):
    expected_revision: int = Field(ge=1)
