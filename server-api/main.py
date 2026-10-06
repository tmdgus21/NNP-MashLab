from datetime import date, time
from secrets import choice
from uuid import uuid4

from fastapi import FastAPI
from pydantic import BaseModel, Field


class RoleInput(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    need_count: int = Field(ge=1)


class RoomCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    date: date
    start_time: time
    end_time: time
    owner_nickname: str = Field(min_length=1, max_length=30)
    roles: list[RoleInput] = Field(min_length=1)


app = FastAPI()

# 학습용 임시 저장소입니다. 서버를 재시작하면 내용이 사라집니다.
rooms = {}


@app.get("/")
def read_root():
    return {
        "status": "success",
        "message": "FastAPI가 실행 중입니다."
    }


@app.post("/rooms", status_code=201)
def create_room(request: RoomCreateRequest):
    room_id = str(uuid4())

    characters = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    room_code = "".join(choice(characters) for _ in range(8))

    room = {
        "room_id": room_id,
        "code": room_code,
        "title": request.title,
        "date": request.date,
        "start_time": request.start_time,
        "end_time": request.end_time,
        "members": [
            {
                "nickname": request.owner_nickname,
                "is_owner": True
            }
        ],
        "roles": [
            role.model_dump() for role in request.roles
        ]
    }

    rooms[room_id] = room
    return room