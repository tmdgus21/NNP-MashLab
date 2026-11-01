import os
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_ENABLED"] = "0"
import unittest
from copy import deepcopy
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import select
import database as database_module
database_module._engine = None
from main import app
from database import AIDraft, ConsentRow, Member, Proposal, RoomEvent, Submission, initialize, session
from models import ConditionAvailableSlot, ConditionRolePreference, ProposalAssignment, ProposalConditionInput
from workflow_models import Conditions, CreateMeeting
from optimizer import solve
from ai_conditions import ParsedCondition


CONFIG = {"title":"통합 검증", "name":"방장", "dates":["2026-10-17"], "roles":["진행","기록"], "roleNeeds":{"진행":1,"기록":1}, "duration":60, "windowStart":540, "windowEnd":720}


def conditions(roles, **extra):
    return Conditions(roles=roles, availability=[{"date":"2026-10-17","start":540,"end":720}], **extra).model_dump()


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        initialize()
        self.client=TestClient(app)
        self.host=self.client.post('/v1/meetings',json=CONFIG).json()
        self.id=self.host['meeting']['id']
        self.guest=self.client.post('/v1/meetings/join',json={"code":self.host['meeting']['code'],"name":"참여자"}).json()

    def headers(self, actor):
        return {"Authorization":"Bearer "+actor['token']}

    def get(self):
        return self.client.get('/v1/meetings/'+self.id,headers=self.headers(self.host)).json()

    def mutate(self, path, actor=None, method='post', **body):
        return getattr(self.client,method)('/v1/meetings/'+self.id+path,headers=self.headers(actor or self.host),json={"expectedRevision":self.get()['revision'],**body})

    def submit_all(self):
        self.assertEqual(self.mutate('/conditions',method='put',conditions=conditions(['진행'], requiredRoles=['진행'])).status_code,200)
        self.assertEqual(self.mutate('/conditions',self.guest,method='put',conditions=conditions(['기록'])).status_code,200)

    def agree_all(self):
        for actor in [self.host,self.guest]:
            self.assertEqual(self.mutate('/consent',actor,method='put',consent='agreed',note='',round=self.get()['round']).status_code,200)

    def test_full_round_flow(self):
        self.assertEqual(len(self.host['meeting']['code']),8)
        self.submit_all()
        with session() as db:
            host_sub=db.scalar(select(Submission).where(Submission.member_id==self.host['actorId']))
            slots=list(db.scalars(select(ConditionAvailableSlot).where(ConditionAvailableSlot.condition_submission_id==host_sub.id)))
            prefs=list(db.scalars(select(ConditionRolePreference).where(ConditionRolePreference.condition_submission_id==host_sub.id)))
            self.assertEqual(len(slots),1)
            self.assertGreaterEqual(len(prefs),1)
            self.assertEqual(host_sub.confirmed['roles'],['진행'])
        calculation=self.mutate('/calculations')
        self.assertEqual(calculation.status_code,200,calculation.text)
        self.assertEqual(calculation.json()['plan']['solverStatus'],'OPTIMAL')
        self.assertEqual(self.get()['round'],1)
        with session() as db:
            proposal=db.scalar(select(Proposal).where(Proposal.room_id==self.id,Proposal.round==1))
            inputs=list(db.scalars(select(ProposalConditionInput).where(ProposalConditionInput.proposal_id==proposal.id)))
            assigns=list(db.scalars(select(ProposalAssignment).where(ProposalAssignment.proposal_id==proposal.id)))
            self.assertEqual(len(inputs),2)
            self.assertEqual(len(assigns),len(proposal.plan['assignments']))
        self.assertEqual(self.mutate('/finalize').status_code,409)
        self.agree_all()
        self.assertEqual(self.get()['status'],'reviewing')
        self.assertEqual(self.mutate('/consent',self.guest,method='put',consent='pending',note='',round=1).status_code,200)
        self.assertEqual(self.mutate('/finalize').status_code,409)
        self.agree_all()
        before=self.get()
        preview=self.mutate('/conditions/preview',self.guest,conditions=conditions(['기록'],preference='late'))
        self.assertEqual(preview.status_code,200,preview.text)
        self.assertEqual(self.get()['revision'],before['revision'])
        self.mutate('/conditions',self.guest,method='put',conditions=conditions(['기록'],preference='late'))
        self.assertEqual(self.mutate('/finalize').status_code,409)
        self.assertTrue(all(p['consent']=='pending' for p in self.get()['participants']))
        self.assertEqual(self.mutate('/calculations').status_code,200)
        self.assertEqual(self.get()['round'],2)
        self.assertEqual(self.mutate('/consent',method='put',consent='agreed',note='',round=1).status_code,409)
        self.assertEqual(self.mutate('/finalize').status_code,409)
        self.agree_all()
        self.assertEqual(self.mutate('/finalize',self.guest).status_code,403)
        final=self.mutate('/finalize')
        self.assertEqual(final.status_code,200,final.text)
        self.assertEqual(final.json()['status'],'finalized')
        self.assertTrue(all(a['status']=='confirmed' for a in final.json()['plan']['assignments']))
        self.assertEqual(self.mutate('/conditions',method='put',conditions=conditions(['진행'])).status_code,409)
        with session() as db:
            proposals=list(db.scalars(select(Proposal).where(Proposal.room_id==self.id)))
            self.assertEqual(len(proposals),2)
            for proposal in proposals:
                self.assertEqual(len(list(db.scalars(select(ConsentRow).where(ConsentRow.proposal_id==proposal.id)))),2)

    def test_host_delete_revokes_access_and_is_retryable(self):
        path = '/v1/meetings/' + self.id
        body = {'expectedRevision': self.get()['revision']}
        self.assertEqual(self.client.request('DELETE', path, json=body).status_code, 401)
        self.assertEqual(self.client.request('DELETE', path, json=body, headers=self.headers(self.guest)).status_code, 403)
        outsider = self.client.post('/v1/meetings', json=CONFIG).json()
        self.assertEqual(self.client.request('DELETE', path, json=body, headers=self.headers(outsider)).status_code, 403)
        self.assertEqual(self.client.request('DELETE', path, json={'expectedRevision': 1}, headers=self.headers(self.host)).status_code, 409)
        for _ in range(2):
            result = self.client.request('DELETE', path, json=body, headers=self.headers(self.host))
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json(), {'deleted': True})
        for actor in [self.host, self.guest]:
            headers = self.headers(actor)
            self.assertEqual(self.client.get(path, headers=headers).status_code, 410)
            self.assertEqual(self.client.get('/v1/session', headers=headers).status_code, 410)
            self.assertEqual(self.client.get(path + '/proposals', headers=headers).status_code, 410)
            self.assertEqual(self.client.put(path + '/conditions', json=body | {'conditions': conditions(['진행'])}, headers=headers).status_code, 410)
        self.assertEqual(self.client.post('/v1/meetings/join', json={'code':self.host['meeting']['code'], 'name':'새참여자'}).status_code, 404)
        self.assertEqual(self.client.get('/v1/meetings/' + outsider['meeting']['id'], headers=self.headers(outsider)).status_code, 200)

    def test_idempotent_entry_and_public_invite(self):
        from uuid import uuid4
        headers={'Idempotency-Key':str(uuid4())}
        first=self.client.post('/v1/meetings',json=CONFIG,headers=headers)
        second=self.client.post('/v1/meetings',json=CONFIG,headers=headers)
        self.assertEqual(first.status_code,201)
        self.assertEqual(first.json(),second.json())
        self.assertEqual(self.client.post('/v1/meetings',json=CONFIG|{'name':'다른 이름'},headers=headers).status_code,409)
        join={'code':first.json()['meeting']['code'],'name':'새 참여자'}
        one=self.client.post('/v1/meetings/join',json=join,headers=headers)
        two=self.client.post('/v1/meetings/join',json=join,headers=headers)
        self.assertEqual(one.status_code,201)
        self.assertEqual(one.json(),two.json())
        self.assertEqual(self.client.get('/join',params={'code':join['code']}).status_code,200)
        self.assertEqual(self.client.get('/join',params={'code':'invalid'}).status_code,422)

    def test_member_events_flush_actor_before_room_event_fk(self):
        """Regression: room_events.actor_member_id must reference an inserted room_members row."""
        created=self.client.post('/v1/meetings',json=CONFIG)
        self.assertEqual(created.status_code,201,created.text)
        host_id=created.json()['actorId']
        room_id=created.json()['meeting']['id']
        joined=self.client.post('/v1/meetings/join',json={'code':created.json()['meeting']['code'],'name':'FK검증'})
        self.assertEqual(joined.status_code,201,joined.text)
        guest_id=joined.json()['actorId']
        with session() as db:
            created_event=db.scalar(select(RoomEvent).where(RoomEvent.room_id==room_id,RoomEvent.event_type=='ROOM_CREATED'))
            joined_event=db.scalar(select(RoomEvent).where(RoomEvent.room_id==room_id,RoomEvent.event_type=='MEMBER_JOINED'))
            self.assertIsNotNone(created_event)
            self.assertIsNotNone(joined_event)
            self.assertEqual(created_event.actor_member_id,host_id)
            self.assertEqual(joined_event.actor_member_id,guest_id)
            self.assertIsNotNone(db.get(Member,created_event.actor_member_id))
            self.assertIsNotNone(db.get(Member,joined_event.actor_member_id))

    def test_condition_slots_use_asia_seoul_wall_clock(self):
        """09:00~12:00 input must persist as Asia/Seoul 09:00~12:00 on TIMESTAMPTZ columns."""
        from zoneinfo import ZoneInfo
        from db_v21.write_sync import _interval_bounds
        seoul=ZoneInfo('Asia/Seoul')
        start,end=_interval_bounds('2026-10-17',540,720)
        self.assertEqual(start.astimezone(seoul).strftime('%Y-%m-%d %H:%M'),'2026-10-17 09:00')
        self.assertEqual(end.astimezone(seoul).strftime('%Y-%m-%d %H:%M'),'2026-10-17 12:00')
        self.assertIsNotNone(start.tzinfo)
        self.assertIsNotNone(end.tzinfo)
        payload=conditions(['진행'])  # default availability is 09:00~12:00 (540~720)
        self.assertEqual(payload['availability'],[{'date':'2026-10-17','start':540,'end':720}])
        self.assertEqual(self.mutate('/conditions',method='put',conditions=payload).status_code,200)
        with session() as db:
            submission=db.scalar(select(Submission).where(Submission.member_id==self.host['actorId']))
            slot=db.scalar(select(ConditionAvailableSlot).where(ConditionAvailableSlot.condition_submission_id==submission.id))
            self.assertIsNotNone(slot)
            self.assertEqual(slot.starts_at.astimezone(seoul).strftime('%Y-%m-%d %H:%M'),'2026-10-17 09:00')
            self.assertEqual(slot.ends_at.astimezone(seoul).strftime('%Y-%m-%d %H:%M'),'2026-10-17 12:00')

    def test_auth_self_only_and_conflicts(self):
        self.assertEqual(self.client.get('/v1/meetings/'+self.id).status_code,401)
        outsider=self.client.post('/v1/meetings',json=CONFIG).json()
        self.assertEqual(self.client.get('/v1/meetings/'+self.id,headers=self.headers(outsider)).status_code,403)
        self.assertEqual(self.mutate('/calculations',self.guest).status_code,403)
        self.assertEqual(self.mutate('/conditions',self.guest,method='put',conditions=conditions(['기록']),actorId=self.host['actorId']).status_code,422)
        stale=self.get()['revision']
        self.mutate('/conditions',self.guest,method='put',conditions=conditions(['기록']))
        self.assertEqual(self.client.put('/v1/meetings/'+self.id+'/conditions',headers=self.headers(self.host),json={'expectedRevision':stale,'conditions':conditions(['진행'])}).status_code,409)
        self.assertFalse(next(p for p in self.get()['participants'] if p['id']==self.host['actorId'])['submitted'])
        self.assertEqual(self.client.post('/v1/meetings/join',json={'code':self.host['meeting']['code'],'name':'방장'}).status_code,409)

    def test_ai_raw_draft_confirmed_separation(self):
        async def parser(request):
            return ParsedCondition(availability=[],role_preferences=[{'role':'기록','strength':'preferred'}],role_unavailable=[],companion_requirement=[],ambiguities=['선호 정도를 확인하세요.'])
        with patch('workflow.parse_condition',parser):
            response=self.client.post('/v1/meetings/'+self.id+'/conditions/parse',headers=self.headers(self.guest),json={'text':'기록이 좋아요','meeting_date':'2026-10-17'})
        self.assertEqual(response.status_code,200,response.text)
        parsed=response.json()
        self.assertFalse(next(p for p in self.get()['participants'] if p['id']==self.guest['actorId'])['submitted'])
        value=conditions(['기록'],aiDraftId=parsed['parseId'])
        self.assertEqual(self.mutate('/conditions',self.guest,method='put',conditions=value).status_code,422)
        value.update(ambiguitiesResolved=True,rolePreferences=[])
        self.assertEqual(self.mutate('/conditions',self.guest,method='put',conditions=value).status_code,200)
        self.assertEqual(self.mutate('/conditions',method='put',conditions=value).status_code,403)
        with session() as db:
            draft=db.get(AIDraft,parsed['parseId'])
            confirmed=db.scalar(select(Submission).where(Submission.member_id==self.guest['actorId']))
            self.assertEqual(draft.raw_text,'기록이 좋아요')
            self.assertEqual(draft.model_output['role_preferences'][0]['role'],'기록')
            self.assertEqual(confirmed.confirmed['rolePreferences'],[])
            member=db.get(Member,self.guest['actorId'])
            self.assertNotEqual(member.token_hash,self.guest['token'])


class SolverTests(unittest.TestCase):
    def setUp(self):
        self.config=CreateMeeting(**CONFIG).model_dump()
        self.people=[{'id':'a','conditions':conditions(['진행'])},{'id':'b','conditions':conditions(['기록'])}]

    def solve(self):
        return solve(self.config,self.people,1)

    def test_availability_union_and_unavailable(self):
        self.people[0]['conditions']['availability']=[{'date':'2026-10-17','start':540,'end':570},{'date':'2026-10-17','start':570,'end':600}]
        self.assertEqual(self.solve()['solverStatus'],'OPTIMAL')
        self.people[0]['conditions']['unavailable']=[{'date':'2026-10-17','start':570,'end':600}]
        self.assertEqual(self.solve()['solverStatus'],'INFEASIBLE')

    def test_role_capability_unavailable_required_and_staffing(self):
        for patch_value in [{'roles':[]},{'roleUnavailable':['진행']},{'requiredRoles':['기록']}]:
            with self.subTest(patch_value=patch_value):
                self.people[0]['conditions']=conditions(['진행']) | patch_value
                self.assertEqual(self.solve()['solverStatus'],'INFEASIBLE')
        self.people[0]['conditions']=conditions(['진행'])
        self.config['roleNeeds']['진행']=2
        self.assertEqual(self.solve()['solverStatus'],'INFEASIBLE')
        self.people.append({'id':'c','conditions':conditions(['진행'])})
        self.assertEqual(len(self.solve()['assignments']),3)

    def test_companion_required_and_apart(self):
        self.people.append({'id':'c','conditions':conditions([])})
        self.people[0]['conditions']['companionRequirements']=[{'participantId':'c','relation':'together','strength':'required'}]
        self.assertEqual(self.solve()['solverStatus'],'INFEASIBLE')
        self.people[0]['conditions']['companionRequirements']=[{'participantId':'b','relation':'apart','strength':'required'}]
        self.assertEqual(self.solve()['solverStatus'],'INFEASIBLE')

    def test_soft_never_violates_hard_and_unknown(self):
        self.people[0]['conditions']['preference']='late'
        self.people[0]['conditions']['unavailable']=[{'date':'2026-10-17','start':660,'end':720}]
        result=self.solve()
        self.assertEqual(result['assignments'][0]['interval']['end'],660)
        self.assertEqual(solve(self.config,self.people,1,max_seconds=0)['solverStatus'],'UNKNOWN')


if __name__=='__main__':
    unittest.main()
