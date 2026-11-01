# NNP-MashLab DB 스키마 현황 (정리본)

**갱신:** 2026-11-02  
**브랜치 기준:** `develop` (코드)  
**운영 DB:** 아직 `mashpotato-server-db` + `ok_*` (앱 `.env` 미전환)  
**신규 DB 이름:** `mashlab_v21` (생성됨, Alembic head 적용은 별도 승인)

---

## 1. 한눈에

| 구분 | 상태 |
|------|------|
| 운영 중 DB | `mashpotato-server-db` (`ok_*`) — **연결 유지** |
| 앱 ORM / API | **`db_v21`로 이식 완료** (`models.py` 재export, `workflow`/`admin`) |
| Alembic (신규) | `alembic.v21.ini` / head **`20261101_0004`** |
| Alembic (구 경로) | `alembic.ini` → `ok_*` (deploy.sh 그대로, 컷오버 전) |
| 데이터 이전 | 없음 (의도적) |
| 운영 연결 전환 | **미실행** (승인 후 `DB_NAME` / deploy) |

---

## 2. 이중 구조

```
코드 경로 (지금)
  models.py → db_v21 (별칭: Member/config/host_id …)
  admin/* → accounts / room_controls / idempotency_records
  migrations_v21/  (0001 → 0002 → 0003 → 0004)
  단위 테스트: DATABASE_URL=sqlite:// → Base.metadata.create_all

운영 DB (아직)
  mashpotato-server-db / ok_*
  deploy.sh → alembic -c alembic.ini upgrade head

신규 DB (준비)
  mashlab_v21
  alembic -c alembic.v21.ini upgrade head   # 승인 후
```

컷오버 전까지 루트 `.env`의 `DB_NAME`은 운영 DB를 가리킨다.  
**주의:** 코드를 v21 ORM으로 바꾼 뒤 운영 `ok_*` DB에 그대로 붙이면 테이블명이 달라 기동 실패한다.  
운영 전환 전에 `mashlab_v21` upgrade + `DB_NAME` 변경이 필요하다.

---

## 3. 신규 v2.1 테이블 (22)

### 계정·세션 (3)
- `accounts` — USER/ADMIN, 이메일 로그인, admin 보안 필드
- `account_sessions` — 로그인 세션 (`token_hash`, `csrf`, `revoked_at`)
- `password_reset_tokens`

### 방·참가·역할 (3)
- `rooms` — 일정, `lifecycle_status`, API용 `progress_status`/`meeting_settings`/`dirty`/`current_round`/`host_member_id`
- `room_members` — `account_id`, `token_hash`, idempotency hashes
- `room_roles`

### AI·조건 (4)
- `ai_drafts` — JSON + `parse_status`
- `condition_submissions` — `confirmed` JSON
- `condition_available_slots` / `condition_role_preferences`

### 배정·동의 (4)
- `proposals` — `round` UNIQUE, JSON + solver statuses (OPTIMAL/FEASIBLE 포함)
- `proposal_condition_inputs` / `proposal_assignments` / `proposal_consents`

### 관리자·이벤트
- `service_controls` / `room_controls` / `admin_audit_logs` / `announcements` / `room_events`
- `admin_otps` / `admin_rate_limits`
- `idempotency_records` (+ `payload` for extension replay)

### 만들지 않음
- `room_cycles` — 연장 멱등은 `idempotency_records`; 회차 메타는 `meeting_settings._lifecycle`

---

## 4. API 이식 요약

| 영역 | 방식 |
|------|------|
| Guest 참가 | `ensure_guest_account()` → `room_members.account_id` |
| Room config/status/host/round | synonym → `meeting_settings` / `progress_status` / `host_member_id` / `current_round` |
| Admin lifecycle | `Lifecycle` 뷰 (`_lifecycle` JSON + `room_controls`) |
| Admin session | `account_sessions` (`token_hash`, `revoked_at`) |
| Extend idempotency | `idempotency_records` scope `extend:{room_id}` |

---

## 5. 문서 위치

| 문서 | 용도 |
|------|------|
| [docs/db-schema-status.md](db-schema-status.md) | **현재 상태 총정리 (이 파일)** |
| [docs/v21-api-port-changelog.md](v21-api-port-changelog.md) | **API 이식 변경 상세 (파일·스키마·동작)** |
| [server-api/db_v21/README.md](../server-api/db_v21/README.md) | 모델·검증 명령 |
| [server-api/db_v21/COMPAT.md](../server-api/db_v21/COMPAT.md) | ok_* → v21 매핑 |
| [infra/alembic-v21-cutover.md](../infra/alembic-v21-cutover.md) | mashlab_v21 적용·컷오버 |

---

## 6. 검증 명령 (비운영)

```sh
cd server-api
python -m unittest tests.test_v21_schema tests.test_workflow tests.test_admin -v

# 빈 mashlab_v21 (승인 후)
# DATABASE_URL=postgresql+psycopg://...@127.0.0.1:5432/mashlab_v21
# alembic -c alembic.v21.ini upgrade head
# alembic -c alembic.v21.ini current   # → 20261101_0004
```

---

## 7. 다음 작업 순서

1. (승인) 빈 `mashlab_v21`에 `alembic.v21.ini upgrade head` → `20261101_0004`
2. (승인) `.env` `DB_NAME=mashlab_v21`, `deploy.sh` → `alembic.v21.ini`
3. 동작 확인 후 구 DB는 보관, 삭제는 별도 승인
