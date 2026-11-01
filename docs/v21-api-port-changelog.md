# v2.1 API 이식 변경 상세 (2026-11-02)

FastAPI `workflow` / `admin`을 레거시 `ok_*` ORM에서 `db_v21`으로 전환한 작업 기록.  
**범위:** 애플리케이션 코드·스키마 보강·테스트·문서.  
**비범위:** 운영 `.env` `DB_NAME` 변경, `mashlab_v21`에 Alembic 적용, `deploy.sh` 전환, 데이터 마이그레이션, 운영 DB DROP.

기준 커밋(이전): `c6a2ca9` (스키마·문서만). 본 문서는 그 위에 올린 **코드 이식** 내용을 설명한다.

---

## 1. 목표와 제약

| 목표 | 내용 |
|------|------|
| API 형태 유지 | `/v1/meetings…`, `/admin-api…` 요청·응답 JSON 형태는 최대한 동일 |
| 물리 스키마 | `db_v21` 테이블명·제약 (`rooms`, `room_members`, `accounts` …) |
| 운영 안전 | live DB / deploy는 승인 전까지 건드리지 않음 |
| 단위 테스트 | `DATABASE_URL=sqlite://` + `Base.metadata.create_all` 로 검증 |

---

## 2. 변경 파일 목록

### 신규
| 경로 | 역할 |
|------|------|
| `server-api/migrations_v21/versions/20261101_0003_room_api_compat.py` | Room API 호환 컬럼 + idempotency `payload` + 제약 완화 |
| `docs/v21-api-port-changelog.md` | 이 문서 |

### 수정 — ORM / 엔트리
| 경로 | 요약 |
|------|------|
| `server-api/models.py` | `ok_*` 정의 삭제 → `db_v21` 재export + synonym 별칭 + 헬퍼 |
| `server-api/database.py` | 동일 심볼 export; init 메시지에 `alembic.v21.ini` 안내 |
| `server-api/db_v21/models/room.py` | API 호환 컬럼 추가 |
| `server-api/db_v21/models/proposal.py` | solver/consent status CHECK 확장 |
| `server-api/db_v21/models/admin.py` | `idempotency_records.payload` JSON |
| `server-api/db_v21/models/account.py` | `account_sessions`의 `expires_at > created_at` CHECK 제거 |

### 수정 — API
| 경로 | 요약 |
|------|------|
| `server-api/workflow.py` | guest account, room 생성 필드, event_type, lifecycle_status 동기화 |
| `server-api/admin/models.py` | AdminBase/`ok_admin_*` 제거 → db_v21 별칭 + `Lifecycle` 뷰 |
| `server-api/admin/security.py` | 세션을 `token_hash`로 조회; audit/revoke 필드 적응 |
| `server-api/admin/auth.py` | ADMIN 계정만 로그인; `last_login_at` |
| `server-api/admin/lifecycle.py` | Lifecycle 뷰 + RoomControl + IdempotencyRecord 연장 |
| `server-api/admin/routes.py` | Lifecycle 테이블 JOIN 제거; host 이전 시 `room_role` 갱신 |
| `server-api/admin/cli.py` | `account_type=ADMIN` 등 v21 필드 |

### 수정 — 테스트 / 문서
| 경로 | 요약 |
|------|------|
| `server-api/tests/test_admin.py` | AdminBase 제거, Account 생성 필드, CycleArchive 조회, 세션 만료 테스트 |
| `server-api/tests/test_admin_postgres.py` | 동일 CycleArchive scope 조회 |
| `server-api/tests/test_v21_schema.py` | `0003` 컬럼 검증 |
| `docs/db-schema-status.md` | 이식 완료 / head `0003` / 다음 승인 단계 |
| `infra/alembic-v21-cutover.md` | 포트 완료·head·승인 항목 갱신 |
| `server-api/db_v21/README.md` / `COMPAT.md` | 현황 반영 |

### 생성되면 안 쓰는 로컬 산출물
- `server-api/_v21_check.db` — 로컬 alembic 점검용일 수 있음. **커밋하지 말 것.**

---

## 3. 스키마 보강 (`20261101_0003`)

기존 head `20261101_0002`(22테이블)만으로는 workflow가 쓰던 `config` JSON / `status` / `round` / `host_id` / dirty를 표현할 수 없어 **Room·Idempotency·CHECK**를 보강했다.

### 3.1 `rooms` 추가 컬럼

| 컬럼 | 타입 | 기본 | 용도 |
|------|------|------|------|
| `host_member_id` | `String(36)` nullable, index | null | API `hostId` / 방장 검사 (OWNER member id) |
| `progress_status` | `String(20)` | `collecting` | 레거시 `ok_rooms.status` (`collecting`/`reviewing`/`finalized`/`deleted`/`cancelled`) |
| `meeting_settings` | `JSON` | `{}` | CreateMeeting dump + `_lifecycle` 관리 메타 |
| `dirty` | `Boolean` | true | 배정안 무효화 플래그 |
| `current_round` | `Integer` | 0 | 레거시 `ok_rooms.round` |

ORM CHECK:
- `progress_status IN ('collecting','reviewing','finalized','deleted','cancelled')`
- 기존 `lifecycle_status` (COLLECTING_CONDITIONS …) 는 **도메인 상태**로 병행 유지

### 3.2 `idempotency_records.payload`

- nullable JSON
- 방 연장(extend) 시 사이클 스냅샷 저장 → 동일 키 재요청 시 replay

### 3.3 제약 변경

| 대상 | 변경 |
|------|------|
| `proposals.solver_status` | `PENDING/COMPLETED/FAILED` + **`OPTIMAL/FEASIBLE/INFEASIBLE/UNBOUNDED/ERROR/idle`** (optimizer 출력 직접 저장) |
| `proposal_consents.status` | 대문자 v2.1 + **소문자 API** `pending`/`agreed`/`review` |
| `account_sessions` | `expires_at > created_at` CHECK **제거** (강제 만료·로그아웃을 위해 expires를 과거로 돌릴 수 있어야 함) |

Alembic `0003`는 SQLite/PG 차이를 고려해 CHECK drop/create를 try/except로 감쌌다.

---

## 4. `models.py` 진입점

### 이전
- `ok_rooms`, `ok_members`, … 를 `DeclarativeBase`에 직접 정의
- `admin.models.AdminBase`는 **별도 Base** (테이블만 admin 쪽)

### 이후
- 단일 `db_v21.Base` (workflow + admin 동일 메타데이터)
- SQLAlchemy `synonym`으로 레거시 속성명 유지:

| 공개 이름 | 실제 컬럼 |
|-----------|-----------|
| `Room.status` | `progress_status` |
| `Room.round` | `current_round` |
| `Room.config` | `meeting_settings` |
| `Room.host_id` | `host_member_id` |
| `RoomMember.created_at` | `joined_at` |
| `AiDraft.member_id` | `room_member_id` |
| `ConditionSubmission.member_id` | `room_member_id` |
| `ConditionSubmission.created_at` | `submitted_at` |
| `ProposalConsent.member_id` | `room_member_id` |

타입 별칭:
- `Member = RoomMember`
- `Submission = ConditionSubmission`
- `AIDraft = AiDraft`
- `ConsentRow = ProposalConsent`

헬퍼:
- `room_time_bounds(settings)` — `dates` → `starts_at`/`ends_at` (CHECK `ends_at > starts_at` 만족)
- `sync_room_roles(db, room, roles, role_needs)` — `room_roles` 재작성
- `ensure_guest_account(db, nickname)` — 참가용 disposable `accounts` (USER, `guest-{uuid}@local.invalid`, argon2 해시)

`SchemaVersion`은 빈 stub (Alembic이 스키마 소유).

---

## 5. `workflow.py` 이식 상세

### 5.1 모임 생성 (`new_meeting`)
1. idempotency 키 처리 (기존과 동일, 대상 테이블은 `room_members`)
2. `ensure_guest_account` → host account
3. `Room`에 `title`, `starts_at`/`ends_at`, `lifecycle_status=COLLECTING_CONDITIONS`, `config=model_dump()`, `host_id=member_id`, `created_by_account_id`
4. `RoomMember` OWNER + `token_hash` + idempotency hashes
5. `sync_room_roles`
6. admin 활성 시 `lifecycle.ensure`
7. `RoomEvent(event_type=ROOM_CREATED, …)`

### 5.2 참가 (`join_meeting`)
- guest account + `room_role=MEMBER`
- `progress_status=collecting`, `lifecycle_status=COLLECTING_CONDITIONS`
- event `MEMBER_JOINED`

### 5.3 멤버 목록
- `membership_status == 'ACTIVE'`만

### 5.4 조건 / 배정 / 동의 / 확정
- Submission / Proposal / Consent 필드명 synonym으로 기존 코드 경로 유지
- Proposal 생성 시 `proposal_status=WAITING_FOR_CONSENT`
- finalize 시 `proposal_status=CONFIRMED`, `lifecycle_status=CONFIRMED`, `progress_status=finalized`
- 삭제 시 `deleted` + `lifecycle_status=CANCELLED` + `deleted_at=now()`

### 5.5 `meeting_view`
- `meeting_settings`에서 `name`, `_lifecycle` 키를 응답에서 제외 (클라이언트에 내부 메타 유출 방지)

### 5.6 `latest_submission` (admin 활성 시)
- 예전: `db.get(Lifecycle, room_id)` (ORM 행)
- 지금: `lifecycle.ensure(db, room)` 뷰 → `starts_at` 이후 제출만 “현재 회차”로 인정

### 5.7 `RoomEvent`
- 필수 `event_type` 부여 (`INFO`, `ROOM_CREATED`, `CONDITION_SUBMITTED`, `PROPOSAL_CREATED`, `FINALIZED`, …)
- 선택 `actor_member_id`

### 5.8 AI draft
- `parse_status=COMPLETED` 명시

---

## 6. Admin 이식 상세

### 6.1 `admin/models.py`

**삭제:** `AdminBase`, `ok_admin_*` / `ok_room_lifecycle` / `ok_room_cycles` 매핑 클래스.

**별칭:**
| 공개 | 실제 |
|------|------|
| `Account.email` | `login_email` |
| `Account.role` | `admin_role` |
| `Account.frozen` | property ↔ `account_status == 'FROZEN'` |
| `AdminSession` | `AccountSession` |
| `AdminSession.digest` | `token_hash` |
| `AdminSession.expires` | `expires_at` |
| `AdminSession.revoked` | property ↔ `revoked_at` |
| `OTP` | `AdminOtp` |
| `Audit` | `AdminAuditLog` (+ actor/action/target/created_at synonym) |
| `RateBucket` | `AdminRateLimit` |
| `CycleArchive` | `IdempotencyRecord` |

**`Lifecycle` (비 ORM 뷰 클래스):**
- 저장: `room.meeting_settings["_lifecycle"]` + `room_controls.control_status`
- 필드: `cycle`, `state`, `management`(ENABLED↔ACTIVE / DISABLED↔SUSPENDED), `scheduled_date`, `closes_at`, `actual_end`, `starts_at`, `base_round`
- property가 room JSON을 항상 읽어, `ensure`/`expire`가 새 인스턴스를 만들어도 같은 room을 보면 최신 값 유지

### 6.2 `admin/security.py`
- 세션 조회: `db.get(AdminSession, digest)` → `select … where token_hash == digest(token)`
- `revoke`: `revoked_at=now()`, OTP `used=True`
- `log`: `AdminAuditLog(admin_account_id, action_type, target_type, target_id, reason)` — free-form `data` JSON 없음 → reason에 문자열 병합
- `authenticate`: `account_type == 'ADMIN'` 검사

### 6.3 `admin/auth.py`
- 로그인 쿼리: `Account.email` + `account_type=='ADMIN'`
- 세션 발급 시 `last_login_at` 갱신
- `AdminSession(digest=…, expires=…)` synonym으로 `token_hash`/`expires_at`에 기록

### 6.4 `admin/lifecycle.py`
- `ensure`: `RoomControl` 없으면 ACTIVE 생성; `_lifecycle` 없으면 deadline으로 초기화
- `expire` / `check` / `sweep`: Lifecycle 뷰 기준 (더 이상 `Lifecycle` 테이블 JOIN 없음)
- `extend`:
  1. fingerprint + `idempotency_records` (`scope=extend:{room_id}`, `key_hash`, `payload`)
  2. `meeting_settings`를 새 dates config로 교체한 **뒤** lifecycle 필드를 다시 기록 (중간에 wipe되지 않게 순서 고정)
  3. `sync_room_roles`, round+1, dirty/collecting
  4. 이벤트 `CYCLE_EXTEND`

### 6.5 `admin/routes.py`
- 목록: `Room` ± `RoomControl`; lifecycle state/date 필터는 ensure 후 파이썬 필터(소규모 admin 전제)
- 상세: 연장 이력 = `idempotency_records` where `scope=extend:{id}`
- transfer: 이전 OWNER → MEMBER, 신규 → OWNER, `host_member_id` 갱신
- disable/enable: `life.management` → RoomControl
- accounts: `account_type=='ADMIN'`만

### 6.6 `admin/cli.py`
- create 시 `account_type=ADMIN`, `admin_role`, `account_status=ACTIVE`

---

## 7. 테스트 변경

### `test_admin.py`
- `AdminBase.metadata.create_all` 제거 → `initialize()`만 (v21 Base에 admin 테이블 포함)
- Account 생성 시 `login_email` / `account_type` / `admin_role` / `account_status`
- CycleArchive 조회: `room_id` → `scope == f'extend:{rid}'`
- 세션 revoke 검증: PK digest → `token_hash` select; 토큰 문자열을 테스트마다 유니크하게
- 세션 만료 테스트: `created_at`을 과거로 민 뒤 `expires`를 과거로 (구 CHECK 잔존 DB에도 안전)
- `003_admin` 마이그레이션 반복 테스트 → `initialize()` 보존 테스트로 교체

### `test_admin_postgres.py`
- AdminBase 제거; CycleArchive scope 조회

### `test_v21_schema.py`
- rooms 신규 컬럼·`idempotency_records.payload` assert

### 검증 결과 (로컬)
```text
python -m unittest tests.test_workflow tests.test_admin tests.test_v21_schema -v
Ran 22 tests … OK
```

---

## 8. 레거시 → v2.1 동작 대응표 (런타임)

| 예전 동작 | 지금 |
|-----------|------|
| `ok_rooms.config` JSON | `rooms.meeting_settings` (+ title/시간 컬럼 동기) |
| `ok_rooms.host_id` | `rooms.host_member_id` + OWNER `room_members` |
| 참가자만 member 행 | member + guest `accounts` 행 |
| `ok_room_lifecycle` 행 | `_lifecycle` JSON + `room_controls` |
| `ok_room_cycles` 아카이브 | `idempotency_records` + `payload` |
| Admin 세션 PK = token digest | UUID PK + unique `token_hash` |
| Admin `frozen` bool | `account_status=FROZEN` |
| Admin audit `data` JSON | reason 문자열에 병합 (컬럼 없음) |

---

## 9. 고의로 하지 않은 것 / 후속 과제

| 항목 | 상태 |
|------|------|
| `mashlab_v21`에 `alembic upgrade head` | 미실행 (승인 필요) |
| `.env` `DB_NAME=mashlab_v21` | 미변경 |
| `deploy.sh` → `alembic.v21.ini` | 미변경 |
| `ok_*` → v21 데이터 이전 | 없음 (빈 DB 교체 전략) |
| condition slots/preferences 정규화 행을 submit마다 항상 기록 | 최소 이식에서는 `confirmed` JSON 위주; 쿼리 정규화는 후속 강화 가능 |
| proposal assignments 정규화 행을 calculate마다 기록 | 동일 — `plan` JSON이 API/optimizer 경로 |
| 운영 `ok_*` DB에 이 코드로 즉시 연결 | **금지** — 테이블명 불일치로 기동 실패 |

---

## 10. 컷오버 체크리스트 (승인 후)

1. 운영 DB 백업 (`infra/backup_database.py`)
2. `mashlab_v21` 비어 있는지 확인
3. `DATABASE_URL=…/mashlab_v21` 세션에서  
   `alembic -c alembic.v21.ini upgrade head` → current **`20261101_0003`**
4. 스모크: 모임 생성/참가/조건/배정/동의/확정, admin OTP 로그인
5. 승인 후 루트 `.env` `DB_NAME` 전환 + deploy Alembic을 v21로
6. 구 DB는 보관; 삭제는 별도 승인

상세 절차: [infra/alembic-v21-cutover.md](../infra/alembic-v21-cutover.md)  
현황 요약: [docs/db-schema-status.md](db-schema-status.md)  
필드 매핑: [server-api/db_v21/COMPAT.md](../server-api/db_v21/COMPAT.md)

---

## 11. 후속 점검 수정 (2026-11-02, 동일 브랜치)

| 항목 | 조치 |
|------|------|
| 이메일 회원가입 | `/v1/auth/register\|login\|me\|logout` 추가; Guest는 `account_type=GUEST` (`0004`); 모임은 선택 헤더 `X-Account-Authorization` |
| JSON+정규화 | `db_v21/write_sync.py` — 조건 submit / 배정 calculate 시 slots·prefs·inputs·assignments 동시 기록 |
| Alembic `0003` | bare `except: pass` 제거; PG는 `DROP IF EXISTS`+`ADD`, SQLite는 `batch_alter_table`, 미지원 dialect는 raise |
| 관리자 테스트 | OTP·실패 동결·연장 멱등·rate limit — `tests.test_admin` 통과 |

## 12. 한 줄 요약

**API 표면은 유지한 채 ORM·테이블을 v2.1로 옮겼고, Room/Idempotency 호환 컬럼(`0003`)과 Lifecycle 뷰로 admin 연장·만료를 재구현했다. 이메일 USER 인증·정규화 쓰기·마이그레이션 안전성까지 보강했다. 운영 DB 연결 전환은 아직이다.**
