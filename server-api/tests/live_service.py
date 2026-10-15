"""Explicit live acceptance test. Creates labeled rooms; never deletes user data."""
import json
import os
import time
from pathlib import Path
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import httpx

BASE=os.getenv('LIVE_BASE_URL','https://oranganman.site')
client=httpx.Client(base_url=BASE,timeout=90)
checks=[]
def check(name,value):
    checks.append({'check':name,'pass':bool(value)})
    assert value,name
def request(method,path,actor=None,body=None,expected=200,headers=None):
    h=headers or {}
    if actor:h=h|{'Authorization':'Bearer '+actor['token']}
    result=client.request(method,path,headers=h,json=body)
    assert result.status_code==expected,(path,result.status_code,result.text)
    return result.json()

if __name__=='__main__':
    config={'title':'운영 통합 검증 '+str(uuid4())[:8],'name':'방장','dates':['2026-10-17'],'roles':['진행','기록'],'roleNeeds':{'진행':1,'기록':1},'duration':60,'windowStart':540,'windowEnd':720}
    key={'Idempotency-Key':str(uuid4())}
    host=request('POST','/v1/meetings',body=config,expected=201,headers=key)
    duplicate=request('POST','/v1/meetings',body=config,expected=201,headers=key)
    check('create retry returns same session',host==duplicate)
    room=host['meeting']['id']; prefix='/v1/meetings/'+room
    guest=request('POST','/v1/meetings/join',body={'code':host['meeting']['code'],'name':'참여자'},expected=201,headers={'Idempotency-Key':str(uuid4())})
    def get():return request('GET',prefix,host)
    def mutate(path,actor=host,method='POST',expected=200,**body):
        return request(method,prefix+path,actor,{'expectedRevision':get()['revision'],**body},expected)
    def condition(role,**extra):return {'roles':[role],'availability':[{'date':'2026-10-17','start':540,'end':720}],**extra}
    check('8 digit code',len(host['meeting']['code'])==8)
    request('GET',prefix,expected=401)
    mutate('/calculations',guest,expected=403)
    check('identity and host authorization',True)
    started=time.monotonic()
    parsed=request('POST',prefix+'/conditions/parse',guest,{'text':'기록 역할을 선호해요. 진행 역할은 못 해요.','meeting_date':'2026-10-17'})
    ai_seconds=round(time.monotonic()-started,3)
    check('real Qwen parse',parsed['source']=='server' and parsed['parseId'] and '진행' in parsed['raw']['role_unavailable'])
    check('AI does not submit conditions',not next(p for p in get()['participants'] if p['id']==guest['actorId'])['submitted'])
    mutate('/conditions',method='PUT',conditions=condition('진행',requiredRoles=['진행'],companionRequirements=[{'participantId':guest['actorId'],'relation':'together','strength':'required'}]))
    mutate('/conditions',guest,method='PUT',conditions=condition('기록',roleUnavailable=['진행'],rolePreferences=['기록'],aiDraftId=parsed['parseId'],ambiguitiesResolved=True))
    stale=get()['revision']
    def concurrent_update(_):
        return client.put(prefix+'/conditions',headers={'Authorization':'Bearer '+guest['token']},json={'expectedRevision':stale,'conditions':condition('기록')}).status_code
    with ThreadPoolExecutor(2) as pool: codes=sorted(pool.map(concurrent_update,range(2)))
    check('concurrent changes serialize',codes==[200,409])
    plan=mutate('/calculations')
    check('actual CP-SAT feasible plan',plan['plan']['solverStatus'] in ['OPTIMAL','FEASIBLE'] and len(plan['plan']['assignments'])==2)
    for actor in [host,guest]:mutate('/consent',actor,method='PUT',consent='agreed',round=1)
    check('all agreed does not auto finalize',get()['status']=='reviewing')
    mutate('/consent',guest,method='PUT',consent='pending',round=1)
    mutate('/finalize',expected=409)
    check('withdrawal blocks finalize',True)
    mutate('/conditions',guest,method='PUT',conditions=condition('기록',preference='late'))
    mutate('/calculations')
    check('new round invalidates consents',get()['round']==2 and all(p['consent']=='pending' for p in get()['participants']))
    mutate('/consent',guest,method='PUT',consent='agreed',round=1,expected=409)
    for actor in [host,guest]:mutate('/consent',actor,method='PUT',consent='agreed',round=2)
    mutate('/finalize',guest,expected=403)
    final=mutate('/finalize')
    check('host finalization persists',final['status']=='finalized' and request('GET','/v1/session',host)['meeting']['status']=='finalized')
    mutate('/conditions',guest,method='PUT',conditions=condition('기록'),expected=409)
    impossible=request('POST','/v1/meetings',body=config|{'title':'운영 배정불가 검증'},expected=201)
    ip='/v1/meetings/'+impossible['meeting']['id']
    saved=request('PUT',ip+'/conditions',impossible,{'expectedRevision':1,'conditions':condition('진행')})
    result=request('POST',ip+'/calculations',impossible,{'expectedRevision':saved['revision']})
    check('infeasible has no fake assignments',result['plan']['solverStatus']=='INFEASIBLE' and result['plan']['assignments']==[])
    legacy=request('POST','/rooms',body={'title':'기존 API 회귀 검증','date':'2026-10-17','start_time':'09:00','end_time':'10:00','owner_nickname':'회귀방장','roles':[{'name':'진행','need_count':1}]},expected=201)
    check('legacy rooms remains compatible',len(legacy['code'])==8 and legacy['members'][0]['is_owner'])
    check('public invitation',client.get('/join',params={'code':host['meeting']['code']}).status_code==200)
    report={'checks':checks,'qwen_seconds':ai_seconds,'room_id':room,'code':host['meeting']['code'],'status':final['status']}
    print(json.dumps(report,ensure_ascii=False,indent=2))
    # Private persistence probe across API restarts. Never print bearer tokens.
    path=Path('/tmp/conditional-ok-live-session.json')
    path.touch(mode=0o600,exist_ok=True); os.chmod(path,0o600)
    path.write_text(json.dumps(host))
