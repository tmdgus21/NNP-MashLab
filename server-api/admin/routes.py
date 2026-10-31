from datetime import date, datetime
from typing import Literal
from fastapi import APIRouter, Depends, Request, Header, HTTPException
from pydantic import Field
from sqlalchemy import select, func, text
from database import Room, Member, Submission, Proposal, ConsentRow, RoomEvent
from .auth import db_session, Input
from .models import Account, Audit, Lifecycle, CycleArchive
from .security import authenticate, error, log, revoke
from .lifecycle import ensure, extend, expire
router = APIRouter(prefix='/admin-api', tags=['Super Admin'])
class Action(Input):
    reason: str = Field(min_length=5, max_length=1000)
    expectedRevision: int = Field(ge=1)
    action: Literal['disable','enable','transfer','extend','actual_end']
    memberId: str | None = None
    dates: list[date] = Field(default_factory=list, max_length=7)
    actualEnd: datetime | None = None
class AccountAction(Input):
    reason: str = Field(min_length=5, max_length=1000)
    expectedRevision: int = Field(ge=1)
    action: Literal['freeze','unfreeze','role']
    role: Literal['SUPER_ADMIN','OPERATOR','VIEWER'] | None = None

def room_row(db, room):
    life = ensure(db, room)
    host = db.get(Member, room.host_id)
    count = db.scalar(select(func.count()).select_from(Member).where(Member.room_id == room.id))
    return {'id':room.id,'title':room.config['title'],'code':room.code,'host':host.nickname if host else '알 수 없음','participants':count,'scheduledDate':life.scheduled_date,'round':room.round,'cycle':life.cycle,'progress':room.status,'lifecycle':life.state,'management':life.management,'revision':room.revision,'closesAt':life.closes_at.isoformat(),'actualEnd':life.actual_end.isoformat() if life.actual_end else None}

@router.get('/rooms')
def rooms(request: Request, q: str='', state: str='', management: str='', start: date | None=None, end: date | None=None, sort: str='created', direction: Literal['asc','desc']='desc', page: int=1, size: int=20, db=Depends(db_session)):
    authenticate(db, request)
    if len(q)>100 or page<1 or not 1<=size<=100: error(422, '검색 범위를 확인하세요.')
    fields = {'created':Room.created_at,'title':Room.config['title'].as_string(),'date':Lifecycle.scheduled_date,'round':Room.round}
    if sort not in fields: error(422, '정렬 기준이 올바르지 않습니다.')
    query = select(Room).join(Lifecycle, Lifecycle.room_id==Room.id)
    if q: query=query.where(Room.config['title'].as_string().icontains(q, autoescape=True) | Room.code.icontains(q, autoescape=True))
    if state:
        if state in ('ACTIVE','CLOSED_CONFIRMED','EXPIRED','CANCELLED'): query=query.where(Lifecycle.state==state)
        elif state in ('collecting','reviewing','finalized'): query=query.where(Room.status==state)
        else: error(422, '진행 상태를 확인하세요.')
    if management:
        if management not in ('ENABLED','DISABLED'): error(422, '관리 상태를 확인하세요.')
        query=query.where(Lifecycle.management==management)
    if start: query=query.where(Lifecycle.scheduled_date>=start.isoformat())
    if end: query=query.where(Lifecycle.scheduled_date<=end.isoformat())
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    order=fields[sort].desc() if direction=='desc' else fields[sort].asc()
    rows=db.scalars(query.order_by(order,Room.id).offset((page-1)*size).limit(size))
    return {'items':[room_row(db,r) for r in rows],'total':total,'page':page,'size':size}

@router.get('/rooms/{room_id}')
def detail(room_id: str, request: Request, db=Depends(db_session)):
    authenticate(db, request)
    room=db.get(Room,room_id)
    if not room: error(404,'모임이 없습니다.')
    from workflow import meeting_view
    view=meeting_view(db,room)
    submissions=[]
    for member in view['participants']:
        submissions += [{'memberId':member['id'],'name':member['name'],'version':s.version,'conditions':s.confirmed,'createdAt':s.created_at.isoformat()} for s in db.scalars(select(Submission).where(Submission.member_id==member['id']).order_by(Submission.version))]
    proposals=[]
    for p in db.scalars(select(Proposal).where(Proposal.room_id==room_id).order_by(Proposal.round.desc())):
        proposals.append({'round':p.round,'solverStatus':p.solver_status,'plan':p.plan,'finalizedAt':p.finalized_at.isoformat() if p.finalized_at else None,'consents':[{'memberId':c.member_id,'status':c.status,'note':c.note} for c in db.scalars(select(ConsentRow).where(ConsentRow.proposal_id==p.id))]})
    return {**room_row(db,room),'meeting':view,'submissions':submissions,'proposals':proposals,'cycles':[{'cycle':c.cycle,'snapshot':c.snapshot} for c in db.scalars(select(CycleArchive).where(CycleArchive.room_id==room_id).order_by(CycleArchive.cycle.desc()))],'actions':[audit_row(a) for a in db.scalars(select(Audit).where(Audit.target==room_id).order_by(Audit.created_at.desc()).limit(100))]}

@router.post('/rooms/{room_id}/actions')
def action(room_id: str, body: Action, request: Request, idempotency_key: str | None=Header(default=None), db=Depends(db_session)):
    actor,_=authenticate(db,request,write=True)
    if actor.role not in ('SUPER_ADMIN','OPERATOR'): error(403,'모임 관리 권한이 필요합니다.')
    room=db.scalar(select(Room).where(Room.id==room_id).with_for_update())
    if not room: error(404,'모임이 없습니다.')
    life=expire(db,room)
    if body.action=='extend':
        if not idempotency_key or not 16<=len(idempotency_key)<=100 or not body.dates: error(422,'새 날짜와 요청 식별자가 필요합니다.')
        result=extend(db,room,sorted(set(d.isoformat() for d in body.dates)),body.expectedRevision,idempotency_key,actor.id,body.reason,admin=True)
        return {**result,'room':room_row(db,room)}
    if room.revision!=body.expectedRevision: error(409,'모임이 변경됐습니다. 다시 조회하세요.')
    before={'hostId':room.host_id,'management':life.management}
    if body.action=='transfer':
        member=db.get(Member,body.memberId)
        if not member or member.room_id!=room.id: error(422,'같은 모임의 참여자를 선택하세요.')
        if room.status in ('deleted','cancelled') or life.state=='CANCELLED': error(409,'취소된 모임입니다.')
        room.host_id=member.id
    elif body.action=='actual_end':
        if life.state!='ACTIVE' or not body.actualEnd or body.actualEnd.tzinfo is None: error(422,'진행 중인 회차의 시간대가 포함된 종료 시각이 필요합니다.')
        before['actualEnd']=life.actual_end.isoformat() if life.actual_end else None
        life.actual_end=body.actualEnd
        expire(db,room)
    else: life.management='DISABLED' if body.action=='disable' else 'ENABLED'
    room.revision+=1
    log(db,actor.id,'room.'+body.action,room.id,body.reason,{'before':before,'after':{'hostId':room.host_id,'management':life.management,'actualEnd':life.actual_end.isoformat() if life.actual_end else None}})
    db.add(RoomEvent(room_id=room.id,message=f'관리자 조치: {body.action} / {body.reason}'))
    return {'room':room_row(db,room)}

def audit_row(a): return {'id':a.id,'actor':a.actor,'action':a.action,'target':a.target,'reason':a.reason,'data':a.data,'createdAt':a.created_at.isoformat()}
@router.get('/audit')
def audit(request: Request, page: int=1, db=Depends(db_session)):
    authenticate(db,request,super_only=True)
    if page<1: error(422,'페이지를 확인하세요.')
    return {'items':[audit_row(a) for a in db.scalars(select(Audit).order_by(Audit.created_at.desc(),Audit.id).offset((page-1)*30).limit(30))],'total':db.scalar(select(func.count()).select_from(Audit))}
@router.get('/accounts')
def accounts(request: Request, db=Depends(db_session)):
    authenticate(db,request,super_only=True)
    return {'items':[{'id':a.id,'email':a.email,'role':a.role,'approved':a.approved,'frozen':a.frozen,'failures':a.failures,'revision':a.revision} for a in db.scalars(select(Account).order_by(Account.email))]}
@router.post('/accounts/{account_id}/actions')
def change_account(account_id: str, body: AccountAction, request: Request, db=Depends(db_session)):
    if db.bind.dialect.name=='postgresql': db.execute(text('SELECT pg_advisory_xact_lock(781926443)'))
    actor,_=authenticate(db,request,write=True,super_only=True)
    if account_id==actor.id: error(403,'자기 계정의 권한이나 동결 상태는 변경할 수 없습니다.')
    target=db.scalar(select(Account).where(Account.id==account_id).with_for_update())
    if not target: error(404,'관리자가 없습니다.')
    if target.revision!=body.expectedRevision: error(409,'관리자 정보가 변경됐습니다.')
    if body.action=='role' and not body.role: error(422,'권한을 선택하세요.')
    before={'role':target.role,'frozen':target.frozen}
    if body.action=='role': target.role=body.role
    elif body.action=='freeze': target.frozen=True
    else:
        target.frozen=False
        # Counter resets only after successful 2FA, including after manual unlock.
    target.revision+=1
    revoke(db,target.id)
    log(db,actor.id,'account.'+body.action,target.id,body.reason,{'before':before,'after':{'role':target.role,'frozen':target.frozen}})
    return {'ok':True}
