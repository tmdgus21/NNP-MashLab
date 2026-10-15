from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Interval(Input):
    date: str
    start: int = Field(ge=0, le=1410, multiple_of=30)
    end: int = Field(ge=30, le=1440, multiple_of=30)

    @model_validator(mode="after")
    def valid(self):
        date.fromisoformat(self.date)
        if self.start >= self.end:
            raise ValueError("종료는 시작 이후여야 합니다.")
        return self


class TimePreference(Interval):
    kind: Literal["available", "unavailable"] = "available"


class Companion(Input):
    participantId: str
    relation: Literal["together", "apart"]
    strength: Literal["required", "preferred"]


class Conditions(Input):
    roles: list[str] = Field(default_factory=list, max_length=6)
    availability: list[Interval] = Field(default_factory=list, max_length=100)
    preference: Literal["balanced", "early", "late"] = "balanced"
    companionId: str | None = None
    note: str = Field(default="", max_length=1000)
    unavailable: list[Interval] = Field(default_factory=list, max_length=100)
    requiredRoles: list[str] = Field(default_factory=list, max_length=6)
    roleUnavailable: list[str] = Field(default_factory=list, max_length=6)
    rolePreferences: list[str] = Field(default_factory=list, max_length=6)
    timePreferences: list[TimePreference] = Field(default_factory=list, max_length=100)
    companionRequirements: list[Companion] = Field(default_factory=list, max_length=20)
    aiDraftId: str | None = None
    ambiguitiesResolved: bool = False


class CreateMeeting(Input):
    title: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=30)
    dates: list[str] = Field(min_length=1, max_length=7)
    roles: list[str] = Field(min_length=1, max_length=6)
    roleNeeds: dict[str, int] = Field(default_factory=dict)
    duration: int = Field(ge=30, le=1440, multiple_of=30)
    windowStart: int = Field(ge=0, le=1410, multiple_of=30)
    windowEnd: int = Field(ge=30, le=1440, multiple_of=30)

    @model_validator(mode="after")
    def valid(self):
        for value in self.dates:
            date.fromisoformat(value)
        if self.windowEnd - self.windowStart < self.duration:
            raise ValueError("활동 시간보다 후보 시간 범위가 짧습니다.")
        if len(set(self.roles)) != len(self.roles) or any(not role.strip() or len(role) > 30 for role in self.roles):
            raise ValueError("역할 이름은 중복 없이 1~30자여야 합니다.")
        if set(self.roleNeeds) - set(self.roles) or any(type(n) is not int or n < 1 or n > 20 for n in self.roleNeeds.values()):
            raise ValueError("역할별 필요인원은 1~20명이어야 합니다.")
        self.roleNeeds = {role: self.roleNeeds.get(role, 1) for role in self.roles}
        self.dates = sorted(set(self.dates))
        return self


class JoinMeeting(Input):
    code: str = Field(pattern=r"^[A-Za-z2-9]{8}$")
    name: str = Field(min_length=1, max_length=30)


class Revision(Input):
    expectedRevision: int = Field(ge=1)


class Submit(Revision):
    conditions: Conditions


class ConsentInput(Revision):
    consent: Literal["pending", "agreed", "review"]
    note: str = Field(default="", max_length=1000)
    round: int = Field(ge=1)


class ParseInput(Input):
    text: str = Field(min_length=1, max_length=1500)
    meeting_date: str
