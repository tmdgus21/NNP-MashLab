import os, unittest, secrets, importlib.util
from datetime import timedelta
from unittest.mock import patch
os.environ.setdefault('DATABASE_URL','sqlite://')
from fastapi.testclient import TestClient
from sqlalchemy import select
from database import initialize, session, now, Room, Proposal, Submission
from main import app
from admin.models import AdminBase, Account, OTP, AdminSession, Lifecycle, CycleArchive, RateBucket
from admin import security as sec
from admin.lifecycle import expire, extend, ensure
from database import engine

class AdminTests(unittest.TestCase):
 def setUp(self):
  self.env=patch.dict(os.environ,{'ADMIN_ENABLED':'1','ADMIN_SECRET':'local-test-secret-at-least-thirty-two-characters','ADMIN_ORIGIN':'https://testserver'});self.env.start()
  initialize();AdminBase.metadata.create_all(engine())
  with session() as db,db.begin():
   db.query(RateBucket).delete()
   self.email='test-'+secrets.token_hex(5)+'@example.test'
   a=Account(email=self.email,password_hash=sec.PASSWORDS.hash('test-password-long'),role='SUPER_ADMIN');db.add(a);db.flush();self.account_id=a.id
  self.client=TestClient(app,base_url='https://testserver')
  self.sent=[]
  self.mail=patch('admin.security.send_otp',side_effect=lambda email,code:self.sent.append((email,code)));self.mail.start()
  self.csrf=self.client.get('/admin-api/auth/csrf').json()['csrf']
  self.headers={'Origin':'https://testserver','X-CSRF-Token':self.csrf}
 def tearDown(self): self.mail.stop();self.env.stop();self.client.close()
 def login(self): return self.client.post('/admin-api/auth/login',json={'email':self.email,'password':'test-password-long'},headers=self.headers)
 def verify(self,challenge,code): return self.client.post('/admin-api/auth/verify',json={'challenge':challenge,'code':code},headers=self.headers)
 def auth(self):
  v=self.login();self.assertEqual(v.status_code,200,v.text)
  result=self.verify(v.json()['challenge'],self.sent[-1][1]);self.assertEqual(result.status_code,200,result.text)
  self.admin_headers={'Origin':'https://testserver','X-CSRF-Token':result.json()['csrf']};return result
 def room(self,days=5):
  config={'title':'관리 검증 '+secrets.token_hex(3),'name':'방장','dates':[(now()+timedelta(days=days)).date().isoformat()],'roles':['진행'],'duration':60,'windowStart':540,'windowEnd':720}
  result=self.client.post('/v1/meetings',json=config);self.assertEqual(result.status_code,201,result.text);return result.json()
 def test_each_login_otp_and_cookie_logout(self):
  self.assertEqual(self.client.get('/admin-api/rooms').status_code,401)
  login=self.login();self.assertEqual(login.status_code,200)
  self.assertNotIn('token',login.json());self.assertEqual(self.client.get('/admin-api/auth/me').status_code,401)
  reply=self.verify(login.json()['challenge'],self.sent[-1][1]);self.assertEqual(reply.status_code,200)
  cookie=reply.headers['set-cookie'];self.assertIn('HttpOnly',cookie);self.assertIn('Secure',cookie);self.assertNotIn('Max-Age',cookie.split(', __Host-conditional-preauth')[0]);self.assertNotIn('expires=',cookie.split(', __Host-conditional-preauth')[0].lower())
  self.assertEqual(self.client.get('/admin-api/auth/me').status_code,200)
  headers={'Origin':'https://testserver','X-CSRF-Token':reply.json()['csrf']}
  self.assertEqual(self.client.post('/admin-api/auth/logout',json={},headers=headers).status_code,200)
  self.assertEqual(self.client.get('/admin-api/auth/me').status_code,401)
  self.csrf=self.client.get('/admin-api/auth/csrf').json()['csrf'];self.headers['X-CSRF-Token']=self.csrf
  with session() as db,db.begin(): db.get(OTP,self.account_id).sent=now()-timedelta(minutes=2)
  self.assertEqual(self.login().status_code,200);self.assertEqual(len(self.sent),2);self.assertEqual(self.client.get('/admin-api/auth/me').status_code,401)
 def test_otp_expiry_reuse_resend_and_csrf(self):
  self.assertEqual(self.client.post('/admin-api/auth/login',json={'email':self.email,'password':'test-password-long'}).status_code,403)
  first=self.login().json();self.assertEqual(self.client.post('/admin-api/auth/resend',json={'challenge':first['challenge']},headers=self.headers).status_code,429)
  with session() as db,db.begin(): db.get(OTP,self.account_id).expires=now()-timedelta(seconds=1)
  self.assertEqual(self.verify(first['challenge'],self.sent[-1][1]).status_code,401)
  with session() as db,db.begin(): db.get(OTP,self.account_id).sent=now()-timedelta(minutes=2)
  second=self.login().json();code=self.sent[-1][1];self.assertEqual(self.verify(second['challenge'],code).status_code,200)
  # Obtain a new preauth CSRF without creating a session; used OTP still cannot log in again.
  self.headers['X-CSRF-Token']=self.client.get('/admin-api/auth/csrf').json()['csrf']
  self.assertEqual(self.verify(second['challenge'],code).status_code,401)
 def test_combined_five_failures_freeze_and_manual_unlock(self):
  for _ in range(3): self.assertEqual(self.client.post('/admin-api/auth/login',json={'email':self.email,'password':'wrong'},headers=self.headers).status_code,401)
  challenge=self.login().json()['challenge']
  with session() as db: self.assertEqual(db.get(Account,self.account_id).failures,3)
  bad='000000' if self.sent[-1][1]!='000000' else '000001'
  for _ in range(2): self.verify(challenge,bad)
  with session() as db:
   account=db.get(Account,self.account_id);self.assertTrue(account.frozen);self.assertEqual(account.failures,5)
  self.assertEqual(self.login().status_code,403)
  # Operator manually unlocks; password alone must not reset count.
  with session() as db,db.begin(): db.get(Account,self.account_id).frozen=False;db.get(OTP,self.account_id).sent=now()-timedelta(minutes=2)
  self.auth()
  with session() as db: self.assertEqual(db.get(Account,self.account_id).failures,0)
 def test_session_max_age_and_rbac(self):
  self.auth()
  with session() as db,db.begin():
   row=db.scalar(select(AdminSession).where(AdminSession.account_id==self.account_id));row.expires=now()-timedelta(seconds=1)
  self.assertEqual(self.client.get('/admin-api/auth/me').status_code,401)
 def test_rooms_filters_transfer_disable_and_viewer(self):
  self.auth();host=self.room();rid=host['meeting']['id'];host_headers={'Authorization':'Bearer '+host['token']}
  guest=self.client.post('/v1/meetings/join',json={'code':host['meeting']['code'],'name':'새방장'}).json()
  listing=self.client.get('/admin-api/rooms',params={'q':host['meeting']['code']});self.assertEqual(listing.status_code,200,listing.text);self.assertEqual(listing.json()['total'],1)
  detail=self.client.get('/admin-api/rooms/'+rid).json();self.assertEqual(len(detail['meeting']['participants']),2)
  def action(name,**extra):
   revision=self.client.get('/admin-api/rooms/'+rid).json()['revision']
   return self.client.post('/admin-api/rooms/'+rid+'/actions',headers=self.admin_headers,json={'action':name,'expectedRevision':revision,'reason':'검증용 관리자 작업',**extra})
  self.assertEqual(action('transfer',memberId=guest['actorId']).status_code,200)
  revision=self.client.get('/v1/meetings/'+rid,headers=host_headers).json()['revision']
  self.assertEqual(self.client.post('/v1/meetings/'+rid+'/calculations',headers=host_headers,json={'expectedRevision':revision}).status_code,403)
  self.assertEqual(action('disable').status_code,200)
  self.assertEqual(self.client.get('/v1/meetings/'+rid,headers=host_headers).status_code,403)
  self.assertEqual(action('enable').status_code,200)
  self.assertEqual(self.client.get('/v1/meetings/'+rid,headers=host_headers).status_code,200)
  with session() as db,db.begin(): db.get(Account,self.account_id).role='VIEWER'
  self.assertEqual(action('disable').status_code,403)
  self.assertEqual(self.client.get('/admin-api/accounts').status_code,403)
 def test_expiry_extension_history_and_idempotency(self):
  self.auth();host=self.room();rid=host['meeting']['id'];headers={'Authorization':'Bearer '+host['token']}
  with session() as db,db.begin():
   room=db.get(Room,rid);life=ensure(db,room);room.config=dict(room.config,dates=[(now()-timedelta(days=2)).date().isoformat()]);expire(db,room)
   self.assertEqual(life.state,'EXPIRED');revision=room.revision
  body={'action':'extend','expectedRevision':revision,'reason':'새 일정으로 재개 승인','dates':[(now()+timedelta(days=6)).date().isoformat()]}
  key=secrets.token_hex(20);h=self.admin_headers|{'Idempotency-Key':key}
  response=self.client.post('/admin-api/rooms/'+rid+'/actions',json=body,headers=h);self.assertEqual(response.status_code,200,response.text)
  repeat=self.client.post('/admin-api/rooms/'+rid+'/actions',json=body,headers=h);self.assertEqual(repeat.status_code,200,repeat.text);self.assertTrue(repeat.json()['replayed'])
  current=self.client.get('/v1/meetings/'+rid,headers=headers).json();self.assertEqual(current['code'],host['meeting']['code']);self.assertFalse(current['participants'][0]['submitted']);self.assertEqual(current['participants'][0]['consent'],'pending');self.assertEqual(current['plan']['assignments'],[])
  with session() as db: self.assertEqual(len(list(db.scalars(select(CycleArchive).where(CycleArchive.room_id==rid)))),1)
  body['dates']=[(now()+timedelta(days=7)).date().isoformat()]
  self.assertEqual(self.client.post('/admin-api/rooms/'+rid+'/actions',json=body,headers=h).status_code,409)
 def test_confirmed_expiry_cancelled_and_late_actual_end(self):
  host=self.room();rid=host['meeting']['id']
  with session() as db,db.begin():
   room=db.get(Room,rid);room.config=dict(room.config,dates=[(now()-timedelta(days=2)).date().isoformat()]);room.status='finalized'
   life=ensure(db,room);life.actual_end=now()+timedelta(hours=2)
   expire(db,room);self.assertEqual(life.state,'ACTIVE')
   expire(db,room,now()+timedelta(hours=3));self.assertEqual(life.state,'CLOSED_CONFIRMED')
   rev=room.revision;expire(db,room,now()+timedelta(days=3));self.assertEqual(room.revision,rev)
  cancelled=self.room()
  with session() as db,db.begin():
   room=db.get(Room,cancelled['meeting']['id']);room.status='cancelled';self.assertEqual(expire(db,room).state,'CANCELLED')
 def test_admin_unlock_csrf_self_protection_and_session_revocation(self):
  self.auth()
  with session() as db,db.begin():
   other=Account(email='locked-'+secrets.token_hex(5)+'@example.test',password_hash=sec.PASSWORDS.hash('long-test-password'),role='OPERATOR',frozen=True,failures=5);db.add(other);db.flush();oid=other.id
   db.add(AdminSession(digest=sec.digest('revoked-test-token'),account_id=oid,csrf='unused',expires=now()+timedelta(hours=1)))
  path='/admin-api/accounts/'+oid+'/actions';body={'action':'unfreeze','expectedRevision':1,'reason':'운영자 확인 후 수동 해제'}
  self.assertEqual(self.client.post(path,json=body).status_code,403)
  self.assertEqual(self.client.post(path,json=body,headers=self.admin_headers).status_code,200)
  with session() as db:
   self.assertFalse(db.get(Account,oid).frozen);self.assertEqual(db.get(Account,oid).failures,5)
   self.assertTrue(db.get(AdminSession,sec.digest('revoked-test-token')).revoked)
  self.assertEqual(self.client.post('/admin-api/accounts/'+self.account_id+'/actions',json=body,headers=self.admin_headers).status_code,403)
 def test_extension_preserves_finalized_plan_and_requires_new_consent(self):
  self.auth();host=self.room();rid=host['meeting']['id'];headers={'Authorization':'Bearer '+host['token']};base='/v1/meetings/'+rid
  def view(): return self.client.get(base,headers=headers).json()
  def conditions_for(day): return {'roles':['진행'],'availability':[{'date':day,'start':540,'end':720}]}
  def change(path,method='post',**extra):return self.client.request(method,base+path,headers=headers,json={'expectedRevision':view()['revision'],**extra})
  self.assertEqual(change('/conditions','put',conditions=conditions_for(host['meeting']['dates'][0])).status_code,200)
  self.assertEqual(change('/calculations').status_code,200)
  old_round=view()['round'];self.assertEqual(change('/consent','put',consent='agreed',note='',round=old_round).status_code,200)
  self.assertEqual(change('/finalize').status_code,200)
  new_day=(now()+timedelta(days=7)).date().isoformat()
  extended=self.client.post(base+'/extensions',headers=headers|{'Idempotency-Key':secrets.token_hex(20)},json={'dates':[new_day],'expectedRevision':view()['revision'],'reason':'참석 및 조건 재확인 연장'})
  self.assertEqual(extended.status_code,200,extended.text);self.assertEqual(view()['plan']['assignments'],[])
  self.assertEqual(change('/calculations').status_code,409)
  self.assertEqual(change('/conditions','put',conditions=conditions_for(new_day)).status_code,200)
  self.assertEqual(change('/calculations').status_code,200)
  self.assertEqual(change('/consent','put',consent='agreed',note='',round=old_round).status_code,409)
  self.assertEqual(change('/finalize').status_code,409)
  self.assertEqual(change('/consent','put',consent='agreed',note='',round=view()['round']).status_code,200)
  self.assertEqual(change('/finalize').status_code,200)
  with session() as db:
   proposals=list(db.scalars(select(Proposal).where(Proposal.room_id==rid)))
   self.assertEqual(len(proposals),2);self.assertTrue(all(p.finalized_at for p in proposals))
   versions=list(db.scalars(select(Submission.version).where(Submission.member_id==host['actorId']).order_by(Submission.version)))
   self.assertEqual(versions,[1,2])
 def test_migration_repeat_preserves_existing_rooms(self):
  host=self.room();spec=importlib.util.spec_from_file_location('migration003','migrations/003_admin.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  module.upgrade();module.upgrade()
  with session() as db:self.assertEqual(db.get(Room,host['meeting']['id']).code,host['meeting']['code'])
 def test_account_rate_limit(self):
  self.login()
  with session() as db,db.begin():db.get(RateBucket,sec.digest('account:'+self.email)).count=20
  self.assertEqual(self.login().status_code,429)
 def test_smtp_failure_never_returns_otp_or_session(self):
  with patch('admin.security.send_otp',side_effect=RuntimeError('secret SMTP password')):
   response=self.login();self.assertEqual(response.status_code,503);self.assertNotIn('secret',response.text)
  self.assertEqual(self.client.get('/admin-api/auth/me').status_code,401)

if __name__=='__main__': unittest.main()
