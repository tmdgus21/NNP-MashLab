---
paths:
  - "server-api/db_v21/**"
  - "server-api/migrations_v21/**"
  - "server-api/alembic*.ini"
  - "server-api/tests/test_v21_schema.py"
---
# DB · Alembic 규칙 (v21 체인)

- 스키마 원본은 `db_v21/models/`. 신규 테이블은 `db_v21/models/schedule.py`에, `db_v21/models/__init__.py`에 등록.
- 변경은 **반드시 `schema-change` 스킬**. 명령은 `alembic -c alembic.v21.ini …`만.
- 리비전 ID는 `YYYYMMDD_NNNN`(예: `20261108_0005`), 파일명 `<id>_<설명>.py`, `down_revision`은 현재 head.
- **기존 `migrations_v21/versions/*.py` 수정·삭제 금지**(훅 차단). 고칠 게 있으면 새 리비전.
- 기존 v21 테이블의 컬럼·CHECK를 바꾸지 않는다(재사용 매핑은 `docs/potato-meet/data-model.md`). 꼭 필요하면 승인 요청.
- 리비전은 PostgreSQL과 sqlite(단위 테스트) 둘 다 통과해야 한다. 방언 분기는 기존 0004처럼 `op.get_bind().dialect.name`.
- autogenerate 결과 검토: 이름 변경이 drop+add로 잡혔는지, CHECK·인덱스·`ON DELETE` 누락, 기존 테이블에 의도치 않은 변경이 섞였는지.
- `upgrade()`/`downgrade()` 둘 다 구현. 운영 배포는 추가형(additive)만 — deploy.sh는 DB를 되돌리지 않는다.
- 신규 테이블은 `tests/test_v21_schema.py`의 `EXPECTED_TABLES`에 추가.
