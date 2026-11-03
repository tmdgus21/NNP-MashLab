from datetime import datetime, time, timedelta, timezone, date
from zoneinfo import ZoneInfo
from copy import deepcopy
import hashlib, json
from fastapi import HTTPException
from sqlalchemy import select
from database import Room, Proposal, RoomEvent, session, now
from models import RoomControl, room_time_bounds, sync_room_roles
from .models import Lifecycle, CycleArchive
from .security import enabled, utc, log, digest as hash_digest

SEOUL = ZoneInfo('Asia/Seoul')


def deadline(db, room):
    scheduled = max(room.config.get('dates') or ['1970-01-01'])
    actual = None
    if room.status == 'finalized':
        plan = db.scalar(select(Proposal).where(Proposal.room_id == room.id, Proposal.round == room.round))
        if plan and plan.plan.get('assignments'):
            intervals = [a['interval'] for a in plan.plan['assignments']]
            scheduled = max(i['date'] for i in intervals)
            actual = max(
                datetime.combine(date.fromisoformat(i['date']), time(), SEOUL) + timedelta(minutes=i['end'])
                for i in intervals
            )
    cutoff = datetime.combine(date.fromisoformat(scheduled) + timedelta(days=1), time(), SEOUL).astimezone(timezone.utc)
    return scheduled, max(cutoff, actual.astimezone(timezone.utc)) if actual else cutoff


def _control(db, room):
    control = db.get(RoomControl, room.id)
    if not control:
        control = RoomControl(room_id=room.id, control_status='ACTIVE')
        db.add(control)
        db.flush()
    return control


def ensure(db, room):
    control = _control(db, room)
    life = Lifecycle(room, control)
    if not (room.meeting_settings or {}).get('_lifecycle'):
        scheduled, cutoff = deadline(db, room)
        life.scheduled_date = scheduled
        life.closes_at = cutoff
        life.cycle = 1
        life.base_round = -1
        life.state = 'CANCELLED' if room.status in ('cancelled', 'deleted') else 'ACTIVE'
        life.management = 'ENABLED'
        life.persist()
        db.flush()
        life = Lifecycle(room, control)
    return life


def expire(db, room, at=None):
    life = ensure(db, room)
    if life.state != 'ACTIVE':
        return life
    scheduled, cutoff = deadline(db, room)
    life.scheduled_date = scheduled
    life.closes_at = max(cutoff, utc(life.actual_end)) if life.actual_end else cutoff
    if room.status in ('cancelled', 'deleted'):
        life.state = 'CANCELLED'
    elif utc(life.closes_at) <= (at or now()):
        life.state = 'CLOSED_CONFIRMED' if room.status == 'finalized' else 'EXPIRED'
    else:
        life.persist()
        return life
    room.revision += 1
    life.persist()
    db.add(RoomEvent(room_id=room.id, message=f'모임 회차 종료: {life.state} (개최 여부 미확인)', event_type='CYCLE_CLOSE'))
    log(db, 'system', 'cycle.close', room.id, data={'cycle': life.cycle, 'state': life.state})
    return life


def check(db, room, write=False):
    if not enabled():
        return
    life = expire(db, room)
    if life.management != 'ENABLED':
        raise HTTPException(403, '관리자가 비활성화한 모임입니다.')
    if write and life.state != 'ACTIVE':
        raise HTTPException(409, '종료된 회차는 읽기 전용입니다. 새 회차 승인이 필요합니다.')


def sweep():
    if not enabled():
        return
    with session() as db, db.begin():
        ids = list(
            db.scalars(
                select(Room.id)
                .where(Room.deleted_at.is_(None))
                .order_by(Room.id)
                .limit(500)
            )
        )
        for room_id in ids:
            room = db.scalar(select(Room).where(Room.id == room_id).with_for_update())
            if room:
                expire(db, room)


def extend(db, room, dates, expected, key, actor, reason, admin=False):
    from workflow import meeting_view
    from workflow_models import CreateMeeting

    fingerprint = hashlib.sha256(json.dumps({'dates': dates, 'actor': actor, 'reason': reason}, sort_keys=True).encode()).hexdigest()
    scope = f'extend:{room.id}'
    key_hash = hash_digest(scope + ':' + key)
    existing = db.scalar(
        select(CycleArchive).where(CycleArchive.scope == scope, CycleArchive.key_hash == key_hash)
    )
    if existing:
        if existing.request_hash != fingerprint:
            raise HTTPException(409, '같은 요청 키에 다른 연장을 적용할 수 없습니다.')
        cycle = (existing.payload or {}).get('cycle', 0)
        return {'cycle': cycle + 1, 'replayed': True}
    life = expire(db, room)
    if room.status in ('cancelled', 'deleted') or life.state == 'CANCELLED':
        raise HTTPException(409, '취소된 모임은 연장할 수 없습니다.')
    if life.management != 'ENABLED':
        raise HTTPException(409, '비활성 모임을 먼저 재활성화하세요.')
    if expected != room.revision:
        raise HTTPException(409, '최신 모임을 다시 조회하세요.')
    if not admin and life.state != 'ACTIVE':
        raise HTTPException(403, '날짜 경과 후 재개는 관리자 승인이 필요합니다.')
    if min(dates) <= life.scheduled_date or min(dates) < now().astimezone(SEOUL).date().isoformat():
        raise HTTPException(422, '기존 예정일 이후의 새로운 날짜를 선택하세요.')
    config = dict(room.config, dates=dates)
    config.pop('_lifecycle', None)
    CreateMeeting.model_validate(config)
    snapshot = {
        'meeting': meeting_view(db, room),
        'lifecycle': {'state': life.state, 'scheduledDate': life.scheduled_date, 'cycle': life.cycle},
        'reason': reason,
    }
    db.add(
        CycleArchive(
            scope=scope,
            key_hash=key_hash,
            request_hash=fingerprint,
            resource_type='room',
            resource_id=room.id,
            payload={'cycle': life.cycle, 'snapshot': deepcopy(snapshot)},
        )
    )
    new_cycle = life.cycle + 1
    base_round = room.round
    starts_at, ends_at = room_time_bounds(config)
    # Replace settings first, then re-apply lifecycle so _lifecycle is not wiped
    room.meeting_settings = dict(config)
    room.title = config.get('title') or room.title
    room.starts_at, room.ends_at = starts_at, ends_at
    room.status, room.dirty = 'collecting', True
    room.lifecycle_status = 'COLLECTING_CONDITIONS'
    room.round += 1
    room.revision += 1
    sync_room_roles(db, room, config.get('roles') or [], config.get('roleNeeds'))
    life.cycle = new_cycle
    life.starts_at = now()
    life.base_round = base_round
    life.state = 'ACTIVE'
    life.actual_end = None
    life.scheduled_date, life.closes_at = deadline(db, room)
    life.management = 'ENABLED'
    log(db, actor, 'cycle.extend', room.id, reason, {'cycle': life.cycle, 'dates': dates})
    db.add(
        RoomEvent(
            room_id=room.id,
            message=f'{life.cycle}번째 모임 회차 시작: 참석 여부와 조건 재확인 필요',
            event_type='CYCLE_EXTEND',
        )
    )
    return {'cycle': life.cycle, 'replayed': False}
