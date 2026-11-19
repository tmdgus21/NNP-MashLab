---
name: schema-change
description: Potato Meet의 PostgreSQL 테이블 변경을 v21 Alembic 체인에서 처리합니다. 재사용 테이블 확인, 변경안 승인 요청, 답신 대기, 승인 시 db_v21 모델 수정과 alembic.v21.ini 리비전 생성·검토, sqlite 테스트, 로컬 mashlab_v21 적용 승인 요청과 적용, 스키마 테스트·DTO·문서 동기화, 운영 반영은 deploy-handoff로 넘기기까지 진행합니다. "테이블 추가", "컬럼 변경", "마이그레이션", "DB 구조", "리비전" 같은 요청이나 「승인:」「수정:」「취소:」 입력에 사용합니다.
model: opus
---
1. `docs/potato-meet/data-model.md`에서 기존 v21 테이블로 해결되는지 먼저 본다. 재사용 테이블의 구조 변경은 피하고, 꼭 필요하면 이유를 적는다.
2. 현재 head를 확인한다: `cd server-api && DATABASE_URL=sqlite:// alembic -c alembic.v21.ini heads`.
3. 변경안 승인 요청 카드를 보낸다: 테이블·컬럼·타입·NULL·기본값·제약 이름(`ck_`/`uq_`), 기존 데이터 영향, downgrade 데이터 손실, 영향받는 API·DTO, 새 리비전 ID(`YYYYMMDD_NNNN`). 승인 전에는 파일을 만들지 않는다.
4. 답신을 기다린다. 「수정:」이면 3번으로, 「취소:」이면 무변경 종료.
5. 「승인:」이면 `server-api/db_v21/models/schedule.py`(필요 시 `__init__.py` 등록)를 수정한다.
6. 리비전을 만든다: `cd server-api && DATABASE_URL=postgresql+psycopg://mashlab:mashlab@127.0.0.1:5432/mashlab_v21 alembic -c alembic.v21.ini revision --autogenerate --rev-id <YYYYMMDD_NNNN> -m "<영어 동사로 시작>"`. 로컬 DB가 없으면 기존 리비전 형식을 본떠 직접 작성한다. 기존 리비전 파일은 수정하지 않는다.
7. 리비전을 검토한다: 기존 테이블에 의도치 않은 변경이 섞였는지, CHECK·인덱스·`ON DELETE` 누락, sqlite/PostgreSQL 방언 분기, `downgrade()`가 정확히 되돌리는지, 추가형(additive)인지.
8. `tests/test_v21_schema.py`의 `EXPECTED_TABLES`를 갱신하고 `DATABASE_URL=sqlite:// ADMIN_ENABLED=0 python -m unittest tests.test_v21_schema -v`를 통과시킨다.
9. `upgrade()`/`downgrade()` 핵심을 보여주고 "로컬 mashlab_v21에 적용할까요?" 승인을 요청한 뒤 답신을 기다린다.
10. 「승인:」이면 로컬 DB에 `alembic -c alembic.v21.ini upgrade head` → `current`로 확인한다. 「수정:」이면 새 리비전으로 보정하거나, 아직 적용 안 한 방금 만든 파일의 삭제를 사용자에게 요청하고 9번으로 돌아간다.
11. 운영 `potato_server_v2` 반영은 하지 않는다. downgrade·stamp도 사용자가 실행한다. 운영 반영은 `deploy-handoff`로 넘긴다(deploy.sh가 upgrade head 실행).
12. 동기화한다: `server-api/schedule/schemas.py`, Kotlin DTO·mapper·도메인 모델, `docs/potato-meet/data-model.md`. 전체 서버 테스트를 실행한다.
13. 완료 보고: 리비전 ID와 down_revision, 변경 요약, 적용한 DB(sqlite/로컬), 동기화한 파일, 운영 반영 시 주의점.
