# GPT Handoff: DB Schema 갭 체크리스트 (이력)

**갱신:** 2026-11-02  
**상태:** 이 문서의 초기 결론(“v2.1 미구현”)은 **구버전**이다.

## 최신 진실은 여기

→ **[docs/db-schema-status.md](db-schema-status.md)**  
→ 모델/검증: [server-api/db_v21/README.md](../server-api/db_v21/README.md)  
→ 컷오버: [infra/alembic-v21-cutover.md](../infra/alembic-v21-cutover.md)  
→ API 이식 맵: [server-api/db_v21/COMPAT.md](../server-api/db_v21/COMPAT.md)

## 2026-11-02 기준 요약

| 항목 | 답 |
|------|----|
| v2.1 ORM/Alembic 코드 있나? | **예** (`db_v21`, head `20261101_0002`, 22테이블) |
| 운영 DB가 v2.1인가? | **아니오** (`mashpotato-server-db` + `ok_*`) |
| 신규 DB 이름 | `mashlab_v21` (앱 미연결) |
| API가 v2.1인가? | **아니오** (아직 `workflow`/`admin`은 ok_*) |
| 데이터 이전 | 없음 |
| 다음 | 빈 DB upgrade → API 이식 → (승인) 연결 전환 |

## 초기 갭 분석 (참고용, 2026-11-01)

당시 기준: 운영은 `ok_*`만 존재하고 v2.1 모델은 레포에 없었음.  
인프라(외부 PG, `DB_*`, Alembic 방향, main-only 배포)는 이미 가이드와 대체로 일치했음.

상세 테이블 대 테이블 갭은 당시 PDF/`ok_*` 기준으로 작성되었으며,  
**현재 코드의 단일 기준은 `db-schema-status.md`이다.**
