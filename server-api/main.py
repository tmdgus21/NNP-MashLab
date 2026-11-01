from datetime import date, time
import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.exc import IntegrityError, OperationalError
from ai_conditions import router as ai_router
from database import initialize
from workflow import db_session, new_meeting, router as workflow_router, join_meeting
from workflow_models import CreateMeeting, JoinMeeting
from public_routes import router as public_router
from admin.auth import router as admin_auth_router
from admin.routes import router as admin_router
from admin.security import enabled as admin_enabled
from admin.lifecycle import sweep
import logging



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


@asynccontextmanager
async def lifespan(app):
    for attempt in range(30):
        try:
            initialize()
            break
        except OperationalError:
            if attempt == 29:
                raise
            await asyncio.sleep(2)
    task = None
    if admin_enabled():
        # Explicit migration must already be applied; never create admin tables here.
        await asyncio.to_thread(sweep)
        async def expiry_worker():
            while True:
                await asyncio.sleep(60)
                try: await asyncio.to_thread(sweep)
                except Exception: logging.getLogger(__name__).error('Lifecycle sweep failed; retrying next interval')
        task = asyncio.create_task(expiry_worker())
    try: yield
    finally:
        if task:
            task.cancel()
            try: await task
            except asyncio.CancelledError: pass


app = FastAPI(lifespan=lifespan)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")
app.include_router(ai_router)
app.include_router(workflow_router)
app.include_router(public_router)
app.include_router(admin_auth_router)
app.include_router(admin_router)

@app.middleware('http')
async def admin_lifecycle_checks(request, call_next):
    if admin_enabled() and (request.url.path.startswith(('/v1/', '/admin-api/', '/rooms'))):
        try: await asyncio.to_thread(sweep)
        except Exception:
            return JSONResponse(status_code=503, content={'detail':'관리 데이터 준비 상태를 확인해 주세요.'})
    response = await call_next(request)
    if request.url.path.startswith('/admin-api/'):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
    return response



@app.exception_handler(IntegrityError)
async def conflict_error(request, exc):
    return JSONResponse(status_code=409, content={"detail": "중복된 입력 또는 동시 변경입니다. 새로고침 후 다시 시도해 주세요."})


@app.exception_handler(OperationalError)
async def database_error(request, exc):
    return JSONResponse(status_code=503, content={"detail": "저장소 연결에 실패했습니다. 잠시 후 재시도하세요."})


@app.get("/")
def read_root():
    return {
        "status": "success",
        "message": "FastAPI가 실행 중입니다."
    }


@app.post("/rooms", status_code=201)
def create_room(request: RoomCreateRequest, db=Depends(db_session)):
    if request.start_time.second or request.end_time.second or request.start_time.minute % 30 or request.end_time.minute % 30:
        raise HTTPException(422, detail="30분 단위 시간을 입력해 주세요.")
    start = request.start_time.hour * 60 + request.start_time.minute
    end = request.end_time.hour * 60 + request.end_time.minute
    if end <= start:
        raise HTTPException(422, detail="종료는 시작 이후여야 합니다.")
    try:
        value = CreateMeeting(title=request.title, name=request.owner_nickname, dates=[request.date.isoformat()], roles=[role.name for role in request.roles], roleNeeds={role.name: role.need_count for role in request.roles}, duration=end-start, windowStart=start, windowEnd=end)
    except ValidationError:
        raise HTTPException(422, detail="역할, 필요 인원과 시간 범위를 확인해 주세요.")
    result = new_meeting(db, value)
    room = result["meeting"]
    return {
        "room_id": room["id"],
        "code": room["code"],
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
        ],
        "member_id": result["actorId"], "access_token": result["token"]
    }


class LegacyJoin(BaseModel):
    code: str
    nickname: str


@app.post("/rooms/join", status_code=201)
def join_room(request: LegacyJoin, db=Depends(db_session)):
    try:
        value = JoinMeeting(code=request.code, name=request.nickname)
    except ValidationError:
        raise HTTPException(422, detail="8자리 코드와 닉네임을 확인해 주세요.")
    return join_meeting(value, db, None)
