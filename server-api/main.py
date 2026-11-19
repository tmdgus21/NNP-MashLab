from datetime import date, time
import asyncio
from contextlib import asynccontextmanager
import logging

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
from user_auth import router as user_auth_router
from admin.auth import router as admin_auth_router
from admin.routes import router as admin_router
from admin.security import enabled as admin_enabled
from admin.lifecycle import sweep as admin_sweep
from schedule import router as schedule_router
from schedule import service as schedule_service
from schedule.events import bind_loop



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
    bind_loop(asyncio.get_running_loop())
    tasks = []

    async def schedule_sweep_worker():
        while True:
            await asyncio.sleep(60)
            try:
                await asyncio.to_thread(schedule_service.sweep)
            except Exception:
                logging.getLogger(__name__).error(
                    "Schedule sweep failed; retrying next interval", exc_info=True
                )

    # Potato Meet grace / 24h input / voting deadlines — always on
    try:
        await asyncio.to_thread(schedule_service.sweep)
    except Exception:
        logging.getLogger(__name__).warning(
            "Initial schedule sweep skipped", exc_info=True
        )
    tasks.append(asyncio.create_task(schedule_sweep_worker()))

    if admin_enabled():
        # Explicit migration must already be applied; never create admin tables here.
        await asyncio.to_thread(admin_sweep)

        async def admin_expiry_worker():
            while True:
                await asyncio.sleep(60)
                try:
                    await asyncio.to_thread(admin_sweep)
                except Exception:
                    logging.getLogger(__name__).error(
                        "Lifecycle sweep failed; retrying next interval"
                    )

        tasks.append(asyncio.create_task(admin_expiry_worker()))
    try:
        yield
    finally:
        bind_loop(None)
        for task in tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(lifespan=lifespan)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")
app.include_router(ai_router)
# Potato Meet schedule first so overlapping /v1/meetings* use the new contract.
# Legacy workflow routes that do not overlap (conditions/calculations/…) stay mounted.
app.include_router(schedule_router)
app.include_router(workflow_router)
app.include_router(user_auth_router)
app.include_router(public_router)
app.include_router(admin_auth_router)
app.include_router(admin_router)

@app.middleware('http')
async def admin_lifecycle_checks(request, call_next):
    if admin_enabled() and (request.url.path.startswith(('/v1/', '/admin-api/', '/rooms'))):
        try: await asyncio.to_thread(admin_sweep)
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
    if request.start_time.second or request.end_time.second or request.start_time.microsecond or request.end_time.microsecond:
        raise HTTPException(422, detail="초 없이 분 단위로 입력해 주세요.")
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
