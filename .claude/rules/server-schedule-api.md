---
paths:
  - "server-api/schedule/**"
  - "server-api/main.py"
  - "server-api/tests/test_schedule_*.py"
---
# 서버 API 규칙 (schedule 라우터)

- 엔드포인트 기준은 `docs/potato-meet/architecture.md` 표. 표에 없는 엔드포인트는 만들지 않는다.
- 조율 수동 실행 엔드포인트는 없다(Q6: 자동 실행, 개인 제출·전원 완료는 3분 유예 후 마감일 뿐 즉시 조율 아님). Qwen 요약은 요청 안에서 기다리지 않고 커밋 후 백그라운드로, 설명만 한다.
- 참여(join)는 입력 OPEN·3분 유예 중에만(그 외 409). 시간 DTO는 30분 경계 `[start,end)`(경계 아님 422). 입력 중 응답에는 인원 수만(멤버 식별자·남의 불가 격자 금지), 후보 응답부터 가능 멤버 닉네임. 투표는 그 조율 완료자(403)·본인 가능 후보(422)만, 빈 투표 허용. 확정 후 변경 409.
- `schedule/`은 `workflow.py`, `optimizer.py`, `ai_conditions.py`, `workflow_models.py`를 import하지 않는다(컷오버 후 제거 대상). 재사용은 `user_auth`, `database`, `db_v21`만.
- 인증: `Authorization: Bearer` → `user_auth.account_from_authorization()`. 권한은 `deps.py`의 `require_member` / `require_owner` 의존성으로만.
- Pydantic 입력은 `ConfigDict(extra="forbid", str_strip_whitespace=True)`, 응답 키는 camelCase(기존 API와 동일).
- 트랜잭션: `with session() as db, db.begin():`. 상태 전이·결과 저장은 rooms 행 `FOR UPDATE` 안에서, `revision += 1`. revision 불일치 409.
- 생성·참여는 `Idempotency-Key` 재시도 안전(기존 `request_key_hash` 패턴).
- 에러: 401/403/404/409, 본문 `{"detail": ...}`. 메시지는 한국어.
- `main.py`에서 `workflow_router` 제거·`schedule_router` 등록은 컷오버 작업으로만(승인 필요).
- 실시간: `schedule/events.py` 브로드캐스터로 SSE 발행. **커밋 이후에만** 발행하고, 이벤트 본문에 개인정보·전체 데이터를 넣지 않는다(이름 + meetingId + revision).
- 테스트: unittest + `DATABASE_URL=sqlite://`, `ADMIN_ENABLED=0`. 실제 운영 서버·Qwen에 붙는 `live_*` 스타일 테스트는 만들지 않는다.
