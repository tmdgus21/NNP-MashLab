# NNP-MashLab DB 스키마 현황 (정리본)

**갱신:** 2026-11-02  
**브랜치 기준:** `develop` (코드)  
**운영 DB:** 아직 `mashpotato-server-db` + `ok_*`  
**신규 DB 이름:** `mashlab_v21` (생성됨, 앱 미연결)

---

## 1. 한눈에

| 구분 | 상태 |
|------|------|
| 운영 중 스키마 | `ok_*` + `ok_admin_*` |
| 신규 스키마 코드 | `server-api/db_v21/` **구현 완료** |
| Alembic (신규) | `alembic.v21.ini` / head `20261101_0002` |
| Alembic (운영 경로) | `alembic.ini` → `ok_*` baseline (deploy.sh 그대로) |
| API (`workflow`/`admin`) | 아직 `ok_*` 모델 사용 |
| 데이터 이전 | 없음 (의도적) |
| 운영 연결 전환 | **미실행** (승인 후) |

---

## 2. 이중 구조

```
운영 경로 (지금)
  models.py / admin/models.py
  migrations/  (20261016_0001 + 003_admin create_all)
  deploy.sh → alembic -c alembic.ini upgrade head
  DB: mashpotato-server-db

신규 경로 (준비됨, 미연결)
  db_v21/
  migrations_v21/  (0001 → 0002)
  alembic -c alembic.v21.ini upgrade head
  DB: mashlab_v21
```

두 체인은 **병행**한다. 컷오버 전까지 deploy/`.env`는 운영 경로를 유지한다.

---

## 3. 신규 v2.1 테이블 (22)

### 계정·세션 (3)
- `accounts` — USER/ADMIN, 이메일 로그인, admin 보안 필드
- `account_sessions` — 로그인 세션 (`token_hash`, `csrf`, `revoked_at`)
- `password_reset_tokens`

### 방·참가·역할 (3)
- `rooms` — 일정, `lifecycle_status`, `revision`, `deleted_at`
- `room_members` — 방별 닉네임, `token_hash`, **idempotency** (`request_key_hash`/`request_hash`)
- `room_roles`

### AI·조건 (4)
- `ai_drafts` — `raw_text` + `model_output`/`app_draft`/`questions` JSON + `parse_status`
- `condition_submissions` — `version` + **`confirmed` JSON**
- `condition_available_slots`
- `condition_role_preferences`

### 배정·동의 (4)
- `proposals` — `round` UNIQUE, `input_snapshot`/`plan` JSON, status
- `proposal_condition_inputs`
- `proposal_assignments`
- `proposal_consents`

### 관리자·이벤트 (5 + 보안 3)
- `service_controls`
- `room_controls`
- `admin_audit_logs`
- `announcements`
- `room_events`
- `admin_otps`
- `admin_rate_limits`
- `idempotency_records` — create/join 외 중복 요청 (admin 연장 등)

### 만들지 않음
- `room_cycles` / `room_cycle_archives` — 한 방 = 한 행사, 재배정은 `proposals.round`
- AI 초안 전용 테이블 3개, `consent_events`

---

## 4. JSON vs 정규화 규칙

| 영역 | 조회 기준 (정규화) | 스냅샷/추가항목 (JSON) |
|------|-------------------|------------------------|
| 조건 | slots / role_preferences | `confirmed` |
| 배정 | inputs / assignments / consents | `input_snapshot`, `plan` |
| AI | — | `model_output`, `app_draft`, `questions` |

쓰기 시 같은 payload에서 JSON과 정규화 행을 함께 만들어야 한다.

---

## 5. 문서 위치

| 문서 | 용도 |
|------|------|
| [docs/db-schema-status.md](db-schema-status.md) | **현재 상태 총정리 (이 파일)** |
| [server-api/db_v21/README.md](../server-api/db_v21/README.md) | 모델·검증 명령 |
| [server-api/db_v21/COMPAT.md](../server-api/db_v21/COMPAT.md) | ok_* → v21 API 이식 매핑 |
| [infra/alembic-v21-cutover.md](../infra/alembic-v21-cutover.md) | mashlab_v21 적용·컷오버 절차 |
| [infra/alembic-cutover.md](../infra/alembic-cutover.md) | 레거시 ok_* Alembic |
| [docs/gpt-handoff-db-schema-v2.1-gap-checklist.md](gpt-handoff-db-schema-v2.1-gap-checklist.md) | 과거 갭 분석 (히스토리; 아래 갱신 요약 참고) |

---

## 6. 검증 명령 (비운영)

```sh
cd server-api
python -m unittest tests.test_v21_schema -v

# 또는 빈 DB
# DATABASE_URL=postgresql+psycopg://...@127.0.0.1:5432/mashlab_v21
# alembic -c alembic.v21.ini upgrade head
# alembic -c alembic.v21.ini current   # → 20261101_0002
```

---

## 7. 다음 작업 순서

1. (승인) 빈 `mashlab_v21`에 `alembic.v21.ini upgrade head`
2. `workflow.py` / `admin/*`를 `db_v21`으로 이식 ([COMPAT.md](../server-api/db_v21/COMPAT.md))
3. (승인) `.env` `DB_NAME=mashlab_v21`, `deploy.sh` → `alembic.v21.ini`
4. 동작 확인 후 구 DB는 보관, 삭제는 별도 승인
