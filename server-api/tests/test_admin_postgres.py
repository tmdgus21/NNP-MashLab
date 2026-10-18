"""Run only against an explicitly selected disposable local PostgreSQL database.
Never set ADMIN_PG_TESTS against a shared or production database.
"""
import os, unittest, secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from fastapi.testclient import TestClient
from sqlalchemy import select
from database import initialize, engine, session, Room, now
from admin.models import AdminBase, CycleArchive
from admin.lifecycle import extend, expire
from main import app
from unittest.mock import patch

@unittest.skipUnless(os.getenv('ADMIN_PG_TESTS')=='1','isolated local PostgreSQL required')
class PostgresConcurrency(unittest.TestCase):
 def test_parallel_extension_and_expiration(self):
  self.assertEqual(engine().dialect.name,'postgresql')
  with patch.dict(os.environ,{'ADMIN_ENABLED':'1'}):
   initialize();AdminBase.metadata.create_all(engine())
   with TestClient(app) as client:
    day=(now()+timedelta(days=3)).date().isoformat()
    r=client.post('/v1/meetings',json={'name':'동시성 테스트','title':'격리 DB 테스트','dates':[day],'roles':['진행'],'duration':30,'windowStart':540,'windowEnd':600})
    self.assertEqual(r.status_code,201,r.text);rid=r.json()['meeting']['id'];revision=r.json()['meeting']['revision']
   key=secrets.token_hex(20);new_day=(now()+timedelta(days=5)).date().isoformat()
   def work(_):
    with session() as db,db.begin():
     room=db.scalar(select(Room).where(Room.id==rid).with_for_update())
     expire(db,room)
     return extend(db,room,[new_day],revision,key,'test-operator','동시 요청 멱등성 검증',admin=True)
   with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(work,range(4)))
   self.assertEqual(sum(not r['replayed'] for r in results),1)
   with session() as db:self.assertEqual(len(list(db.scalars(select(CycleArchive).where(CycleArchive.room_id==rid)))),1)
