import hashlib
import secrets
import hmac
import json
import os
from copy import deepcopy

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select

from ai_conditions import ParseConditionRequest, parse_condition
from database import AIDraft, ConsentRow, Member, Proposal, Room, RoomEvent, Submission, now, session, uid
from optimizer import solve
from admin import lifecycle
from admin.security import enabled as admin_enabled
from workflow_models import Conditions, ConsentInput, CreateMeeting, JoinMeeting, ParseInput, Revision, Submit

router = APIRouter(prefix="/v1", tags=["Persistent meetings"])


def db_session():
    with session() as db, db.begin():
        yield db


def fail(status, message):
    raise HTTPException(status, detail=message)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def creation_identity(db, key, scope, request):
    if not key:
        return secrets.token_urlsafe(32), None, None, None
    if len(key) < 32 or len(key) > 128:
        fail(422, "Idempotency-Key는 32~128자여야 합니다.")
    secret = os.getenv("APP_SESSION_SECRET")
    if not secret and os.getenv("DATABASE_URL", "").startswith("sqlite"):
        secret = "isolated-test-secret-not-for-production"
    if not secret:
        fail(503, "세션 설정이 준비되지 않았습니다.")
    key_hash = token_hash(scope + ":" + key)
    fingerprint = token_hash(json.dumps(request.model_dump(), sort_keys=True, ensure_ascii=False))
    token = hmac.new(secret.encode(), key_hash.encode(), hashlib.sha256).hexdigest()
    existing = db.scalar(select(Member).where(Member.request_key_hash == key_hash))
    if existing and existing.request_hash != fingerprint:
        fail(409, "동일한 요청 키에 다른 입력을 사용할 수 없습니다.")
    if existing:
        room = db.scalar(select(Room).where(Room.id == existing.room_id).with_for_update())
        if room.status == "deleted":
            fail(410, "방장이 삭제한 모임입니다.")
        lifecycle.check(db, room)
        return token, key_hash, fingerprint, {"meeting": meeting_view(db, room), "actorId": existing.id, "token": token}
    return token, key_hash, fingerprint, None


def identity(db, authorization):
    if not authorization or not authorization.startswith("Bearer "):
        fail(401, "참가자 인증이 필요합니다.")
    member = db.scalar(select(Member).where(Member.token_hash == token_hash(authorization[7:])))
    if not member:
        fail(401, "유효하지 않은 참가자 인증입니다.")
    return member


def access(db, room_id, authorization, expected=None, host=False, mutable=False, allow_deleted=False):
    member = identity(db, authorization)
    if member.room_id != room_id:
        fail(403, "다른 모임에는 접근할 수 없습니다.")
    room = db.scalar(select(Room).where(Room.id == room_id).with_for_update())
    if not room:
        fail(404, "모임을 찾을 수 없습니다.")
    if host and room.host_id != member.id:
        fail(403, "방장만 할 수 있는 작업입니다.")
    if room.status == "deleted":
        if allow_deleted:
            return room, member
        fail(410, "방장이 삭제한 모임입니다.")
    lifecycle.check(db, room, write=mutable or expected is not None)
    if mutable and room.status == "finalized":
        fail(409, "이미 최종 확정된 모임입니다.")
    if expected is not None and expected != room.revision:
        fail(409, "다른 변경이 있습니다. 새로고침 후 다시 시도해 주세요.")
    return room, member


def members(db, room):
    return list(db.scalars(select(Member).where(Member.room_id == room.id).order_by(Member.created_at, Member.id)))


def latest_submission(db, member_id, current=True):
    query = select(Submission).where(Submission.member_id == member_id)
    if current and admin_enabled():
        from admin.models import Lifecycle
        member = db.get(Member, member_id)
        life = db.get(Lifecycle, member.room_id)
        if life and life.starts_at: query = query.where(Submission.created_at >= life.starts_at)
    return db.scalar(query.order_by(Submission.version.desc()).limit(1))


def latest_proposal(db, room):
    query = select(Proposal).where(Proposal.room_id == room.id)
    if admin_enabled():
        life = lifecycle.ensure(db, room)
        query = query.where(Proposal.round > life.base_round)
    return db.scalar(query.order_by(Proposal.round.desc()).limit(1))


def event(db, room, message):
    db.add(RoomEvent(room_id=room.id, message=message))


def empty_plan(round_number):
    return {"round": round_number, "status": "idle", "assignments": [], "notices": []}


def meeting_view(db, room):
    db.flush()
    proposal = latest_proposal(db, room)
    rows = members(db, room)
    participants = []
    for p in rows:
        submission = latest_submission(db, p.id)
        consent = db.scalar(select(ConsentRow).where(ConsentRow.proposal_id == proposal.id, ConsentRow.member_id == p.id)) if proposal and not room.dirty else None
        participants.append({"id": p.id, "name": p.nickname, "conditions": submission.confirmed if submission else Conditions().model_dump(), "submitted": submission is not None, "conditionVersion": submission.version if submission else 0, "consent": consent.status if consent else "pending", "consentRound": proposal.round if consent else 0, "reviewNote": consent.note if consent else ""})
    prior = None
    if proposal:
        previous = proposal if room.dirty else db.scalar(select(Proposal).where(Proposal.room_id == room.id, Proposal.round < proposal.round).order_by(Proposal.round.desc()).limit(1))
        prior = deepcopy(previous.plan) if previous else None
    return {"id": room.id, "code": room.code, "hostId": room.host_id, "timezone": "Asia/Seoul", **{k: v for k, v in room.config.items() if k != "name"}, "revision": room.revision, "round": room.round, "status": room.status, "participants": participants, "plan": deepcopy(proposal.plan) if proposal and not room.dirty else empty_plan(room.round), "previousPlan": prior, "history": list(db.scalars(select(RoomEvent.message).where(RoomEvent.room_id == room.id).order_by(RoomEvent.created_at, RoomEvent.id)))[-100:]}


def new_meeting(db, request, request_key=None):
    token, key_hash, fingerprint, replay = creation_identity(db, request_key, "create", request)
    if replay:
        return replay
    member_id, room_id = uid(), uid()
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(10):
        code = "".join(secrets.choice(alphabet) for _ in range(8))
        if not db.scalar(select(Room.id).where(Room.code == code)):
            break
    room = Room(id=room_id, code=code, host_id=member_id, config=request.model_dump(), revision=1, round=0, status="collecting", dirty=True)
    db.add(room)
    db.flush()
    db.add(Member(id=member_id, room_id=room_id, nickname=request.name, token_hash=token_hash(token), request_key_hash=key_hash, request_hash=fingerprint))
    if admin_enabled(): lifecycle.ensure(db, room)
    event(db, room, "모임이 생성됐습니다.")
    return {"meeting": meeting_view(db, room), "actorId": member_id, "token": token}


@router.post("/meetings", status_code=201)
def create_meeting(request: CreateMeeting, db=Depends(db_session), idempotency_key: str | None = Header(default=None)):
    return new_meeting(db, request, idempotency_key)


@router.post("/meetings/join", status_code=201)
def join_meeting(request: JoinMeeting, db=Depends(db_session), idempotency_key: str | None = Header(default=None)):
    token, key_hash, fingerprint, replay = creation_identity(db, idempotency_key, "join", request)
    if replay:
        return replay
    room = db.scalar(select(Room).where(Room.code == request.code.upper()).with_for_update())
    if not room or room.status == "deleted":
        fail(404, "초대 코드를 확인해 주세요.")
    if key_hash:
        _, _, _, replay = creation_identity(db, idempotency_key, "join", request)
        if replay:
            return replay
    lifecycle.check(db, room, write=True)
    if room.status == "finalized":
        fail(409, "확정된 모임에는 참가할 수 없습니다.")
    existing = members(db, room)
    if len(existing) >= 20:
        fail(409, "현재 모임은 최대 20명까지 참여할 수 있습니다.")
    if any(p.nickname.casefold() == request.name.casefold() for p in existing):
        fail(409, "이미 사용 중인 닉네임입니다. 기존 참여자는 저장된 인증으로 접속해 주세요.")
    member_id = uid()
    db.add(Member(id=member_id, room_id=room.id, nickname=request.name, token_hash=token_hash(token), request_key_hash=key_hash, request_hash=fingerprint))
    room.dirty, room.status = True, "collecting"
    room.revision += 1
    event(db, room, f"{request.name}님이 참가했습니다. 다음 배정에 새 동의가 필요합니다.")
    return {"meeting": meeting_view(db, room), "actorId": member_id, "token": token}


@router.get("/session")
def restore(authorization: str | None = Header(default=None), db=Depends(db_session)):
    member = identity(db, authorization)
    room, member = access(db, member.room_id, authorization)
    return {"meeting": meeting_view(db, room), "actorId": member.id}


@router.get("/meetings/{room_id}")
def get_meeting(room_id: str, authorization: str | None = Header(default=None), db=Depends(db_session)):
    room, _ = access(db, room_id, authorization)
    return meeting_view(db, room)


@router.delete("/meetings/{room_id}")
def delete_meeting(room_id: str, request: Revision, authorization: str | None = Header(default=None), db=Depends(db_session)):
    # Logical deletion preserves audit/history, but all public access is revoked.
    # The host can safely retry after a lost response, even with the old revision.
    room, _ = access(db, room_id, authorization, request.expectedRevision, host=True, allow_deleted=True)
    if room.status != "deleted":
        room.status = "deleted"
        room.revision += 1
        event(db, room, "방장이 모임을 삭제했습니다.")
    return {"deleted": True}


def validate_conditions(db, room, member, conditions):
    roles = set(room.config["roles"])
    if any(set(value) - roles for value in (conditions.roles, conditions.requiredRoles, conditions.roleUnavailable, conditions.rolePreferences)):
        fail(422, "모임에 없는 역할입니다.")
    for interval in conditions.availability + conditions.unavailable + conditions.timePreferences:
        if interval.date not in room.config["dates"]:
            fail(422, "후보 날짜에 해당하는 시간만 제출해 주세요.")
    ids = {p.id for p in members(db, room)} - {member.id}
    companions = [r.participantId for r in conditions.companionRequirements] + ([conditions.companionId] if conditions.companionId else [])
    if any(person not in ids for person in companions):
        fail(422, "동반자는 같은 모임의 다른 참가자여야 합니다.")
    if conditions.aiDraftId:
        draft = db.get(AIDraft, conditions.aiDraftId)
        if not draft or draft.member_id != member.id:
            fail(403, "다른 참가자의 AI 초안을 사용할 수 없습니다.")
        if draft.questions and not conditions.ambiguitiesResolved:
            fail(422, "AI 확인사항을 수정하고 확인 완료를 선택해 주세요.")


@router.post("/meetings/{room_id}/conditions/preview")
def preview(room_id: str, request: Submit, authorization: str | None = Header(default=None), db=Depends(db_session)):
    room, member = access(db, room_id, authorization, request.expectedRevision, mutable=True)
    validate_conditions(db, room, member, request.conditions)
    before = meeting_view(db, room)
    participants = deepcopy(before["participants"])
    for p in participants:
        if p["id"] == member.id:
            p["conditions"], p["submitted"] = request.conditions.model_dump(), True
    if all(p["submitted"] for p in participants):
        after = solve(room.config, participants, room.round + 1)
    else:
        after = empty_plan(room.round + 1)
        after["notices"] = [{"id": "collecting", "kind": "info", "title": "조건 수집 중", "detail": "모든 참가자가 조건을 제출하면 배정할 수 있습니다."}]
    return {"revision": room.revision, "before": before["plan"], "after": after, "changes": ["확정 조건을 새 버전으로 저장합니다.", "재배정 시 새 회차를 만들며 이전 동의는 재사용하지 않습니다."]}


@router.put("/meetings/{room_id}/conditions")
def submit(room_id: str, request: Submit, authorization: str | None = Header(default=None), db=Depends(db_session)):
    room, member = access(db, room_id, authorization, request.expectedRevision, mutable=True)
    validate_conditions(db, room, member, request.conditions)
    previous = latest_submission(db, member.id, current=False)
    db.add(Submission(member_id=member.id, version=previous.version + 1 if previous else 1, confirmed=request.conditions.model_dump(), ai_draft_id=request.conditions.aiDraftId))
    room.dirty, room.status = True, "collecting"
    room.revision += 1
    event(db, room, f"{member.nickname}님이 조건을 확정 제출했습니다.")
    return meeting_view(db, room)


@router.post("/meetings/{room_id}/calculations")
def calculate(room_id: str, request: Revision, authorization: str | None = Header(default=None), db=Depends(db_session)):
    room, _ = access(db, room_id, authorization, request.expectedRevision, host=True, mutable=True)
    view = meeting_view(db, room)
    if not all(p["submitted"] for p in view["participants"]):
        fail(409, "모든 참가자의 조건 제출이 필요합니다.")
    next_round = room.round + 1
    plan = solve(room.config, view["participants"], next_round)
    snapshot = {"config": room.config, "participants": view["participants"], "versions": {p["id"]: p["conditionVersion"] for p in view["participants"]}}
    db.add(Proposal(room_id=room.id, round=next_round, source_revision=room.revision, input_snapshot=snapshot, plan=plan, solver_status=plan["solverStatus"]))
    room.round, room.dirty, room.status = next_round, False, "reviewing"
    room.revision += 1
    event(db, room, f"{next_round}차 배정: {plan['solverStatus']}. 이번 회차에 새 동의가 필요합니다.")
    return meeting_view(db, room)


def current_feasible(db, room):
    proposal = latest_proposal(db, room)
    if room.dirty or not proposal or proposal.solver_status not in ("OPTIMAL", "FEASIBLE"):
        fail(409, "최신 조건을 만족하는 배정안을 먼저 생성해 주세요.")
    return proposal


@router.put("/meetings/{room_id}/consent")
def consent(room_id: str, request: ConsentInput, authorization: str | None = Header(default=None), db=Depends(db_session)):
    room, member = access(db, room_id, authorization, request.expectedRevision, mutable=True)
    proposal = current_feasible(db, room)
    if request.round != proposal.round:
        fail(409, "이전 회차에는 동의할 수 없습니다.")
    row = db.scalar(select(ConsentRow).where(ConsentRow.proposal_id == proposal.id, ConsentRow.member_id == member.id))
    if not row:
        row = ConsentRow(proposal_id=proposal.id, member_id=member.id, status=request.consent, note=request.note)
        db.add(row)
    else:
        row.status, row.note = request.consent, request.note
    room.revision += 1
    label = {"agreed": "동의", "pending": "동의 철회", "review": "검토 요청"}[request.consent]
    event(db, room, f"{proposal.round}차 {member.nickname}: {label}")
    return meeting_view(db, room)


@router.post("/meetings/{room_id}/finalize")
def finalize(room_id: str, request: Revision, authorization: str | None = Header(default=None), db=Depends(db_session)):
    room, _ = access(db, room_id, authorization, request.expectedRevision, host=True, mutable=True)
    proposal = current_feasible(db, room)
    view = meeting_view(db, room)
    if proposal.input_snapshot["versions"] != {p["id"]: p["conditionVersion"] for p in view["participants"]}:
        fail(409, "배정 이후 조건이 변경됐습니다.")
    if not all(p["consent"] == "agreed" and p["consentRound"] == proposal.round for p in view["participants"]):
        fail(409, "이번 회차에 전원 동의해야 확정할 수 있습니다.")
    proposal.finalized_at = now()
    plan = deepcopy(proposal.plan)
    for assignment in plan["assignments"]:
        assignment["status"] = "confirmed"
    proposal.plan = plan
    room.status, room.revision = "finalized", room.revision + 1
    if admin_enabled(): lifecycle.expire(db, room)
    event(db, room, f"방장이 {proposal.round}차 담당표를 최종 확정했습니다.")
    return meeting_view(db, room)


def map_ai(parsed, meeting, member_id):
    draft, questions = {}, list(parsed.ambiguities)
    for item in parsed.availability:
        if not item.date:
            questions.append("날짜를 선택하고 시간 블록을 직접 확인해 주세요.")
            continue
        start, end = [sum(int(v) * factor for v, factor in zip(clock.split(":"), (60, 1))) for clock in (item.start, item.end)]
        if start % 30 or end % 30 or item.date.isoformat() not in meeting["dates"]:
            questions.append(f"{item.start}~{item.end}: 후보 날짜와 30분 시간 블록으로 직접 수정해 주세요.")
            continue
        interval = {"date": item.date.isoformat(), "start": start, "end": end}
        if item.strength == "preferred":
            draft.setdefault("timePreferences", []).append(interval | {"kind": item.kind})
        else:
            draft.setdefault("availability" if item.kind == "available" else "unavailable", []).append(interval)
    for item in parsed.role_preferences:
        if item.role in meeting["roles"]:
            draft.setdefault("requiredRoles" if item.strength == "required" else "rolePreferences", []).append(item.role)
        else:
            questions.append(f"모임에 없는 역할 '{item.role}'을 직접 수정해 주세요.")
    for role in parsed.role_unavailable:
        if role in meeting["roles"]:
            draft.setdefault("roleUnavailable", []).append(role)
        else:
            questions.append(f"모임에 없는 역할 '{role}'을 직접 수정해 주세요.")
    for item in parsed.companion_requirement:
        matches = [p for p in meeting["participants"] if p["name"] == item.person and p["id"] != member_id]
        if len(matches) == 1:
            draft.setdefault("companionRequirements", []).append({"participantId": matches[0]["id"], "relation": item.relation, "strength": item.strength})
        else:
            questions.append(f"동반자 '{item.person}'을 참가자 목록에서 직접 선택해 주세요.")
    return draft, list(dict.fromkeys(questions))


@router.post("/meetings/{room_id}/conditions/parse")
async def parse_for_member(room_id: str, request: ParseInput, authorization: str | None = Header(default=None)):
    # Close transaction before awaiting Qwen; parsing never changes submitted conditions.
    with session() as db, db.begin():
        room, member = access(db, room_id, authorization, mutable=True)
        view = meeting_view(db, room)
        member_id = member.id
        if request.meeting_date not in view["dates"]:
            fail(422, "모임의 후보 날짜를 선택해 주세요.")
    parsed = await parse_condition(ParseConditionRequest(text=request.text, meeting_date=request.meeting_date))
    draft, questions = map_ai(parsed, view, member_id)
    with session() as db, db.begin():
        access(db, room_id, authorization, mutable=True)
        row = AIDraft(member_id=member_id, raw_text=request.text, model_output=parsed.model_dump(mode="json"), app_draft=draft, questions=questions)
        db.add(row)
        db.flush()
        return {"draft": draft | {"aiDraftId": row.id, "ambiguitiesResolved": not bool(questions)}, "questions": questions, "source": "server", "parseId": row.id, "raw": parsed.model_dump(mode="json")}


@router.get("/meetings/{room_id}/proposals")
def proposals(room_id: str, authorization: str | None = Header(default=None), db=Depends(db_session)):
    access(db, room_id, authorization)
    return [{"id": p.id, "round": p.round, "sourceRevision": p.source_revision, "solverStatus": p.solver_status, "plan": p.plan, "finalized": p.finalized_at is not None} for p in db.scalars(select(Proposal).where(Proposal.room_id == room_id).order_by(Proposal.round))]


class Extension(Revision):
    dates: list[str]
    reason: str

@router.post('/meetings/{room_id}/extensions')
def host_extension(room_id: str, request: Extension, authorization: str | None = Header(default=None), idempotency_key: str | None = Header(default=None), db=Depends(db_session)):
    if not admin_enabled(): fail(404, '연장 기능이 활성화되지 않았습니다.')
    member = identity(db, authorization)
    room = db.scalar(select(Room).where(Room.id == room_id).with_for_update())
    if not room or member.room_id != room_id or room.host_id != member.id: fail(403, '현재 방장만 연장할 수 있습니다.')
    if not idempotency_key or not 16 <= len(idempotency_key) <= 100 or not 5 <= len(request.reason.strip()) <= 1000 or not 1 <= len(request.dates) <= 7: fail(422, '새 날짜, 사유와 요청 식별자가 필요합니다.')
    try:
        from datetime import date
        dates = sorted(set(date.fromisoformat(d).isoformat() for d in request.dates))
    except ValueError: fail(422, '날짜 형식을 확인하세요.')
    return lifecycle.extend(db, room, dates, request.expectedRevision, idempotency_key, member.id, request.reason)
