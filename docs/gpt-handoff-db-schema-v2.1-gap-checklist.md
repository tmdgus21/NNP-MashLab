<<<<<<< HEAD
# GPT Handoff: DB Schema v2.1 vs Current Repo Gap Checklist

**목적:** ChatGPT/Cursor가 NNP-MashLab의 *현재 구현*과 *DB Schema v2.1 설계서* 차이를 바로 이해하도록 하는 컨텍스트 문서.  
**기준일:** 2026-11-01  
**비교 대상:**
- 설계: `NNP_MashLab_DB_Schema_v2_1_Rebuilt.pdf` + `NNP_MashLab_Cursor_DB_Alembic_Implementation_Guide.pdf`
- 코드: `main` / `develop`의 `server-api` (운영 `ok_*` 스키마)

**한줄 요약:**  
인프라(외부 PostgreSQL, `DB_*`, Alembic 방향)는 가이드와 맞지만, **논리 스키마는 v2.1(19테이블)이 아니라 현재 `ok_*` JSON 중심 스키마**다. v2.1은 아직 미구현이다.

---

## 0. 현재 운영/인프라 상태 (가이드와 대체로 일치)

| 항목 | 현재 | 가이드 v2.1 | 갭 |
|------|------|-------------|----|
| DB | 호스트 PostgreSQL (Compose `postgres` 서비스 제거) | Docker DB 컨테이너 금지, 호스트 PG18 | 일치 |
| 접속 env | 루트 `.env`의 `DB_USER/PASSWORD/NAME/HOST/PORT` | 동일 | 일치 |
| 파생 파일 | `prepare_database_env.py` → `.env.database` | 가이드에 명시 없음 (기존 유지 OK) | 유지 |
| 백업 | `infra/backup_database.py` (호스트 백업 시 `172.*` → `127.0.0.1`) | 운영 백업 후 마이그레이션 | 일치 방향 |
| Alembic | `server-api/migrations` + `alembic.ini` | Alembic 단일 관리 | 부분 일치 (아래) |
| `create_all` | 운영 PG에서는 사용 안 함; sqlite 테스트만 | 운영 `create_all` 금지 | 일치 |
| Caddy/Prometheus/Grafana | 유지 | 건드리지 말 것 | 일치 |
| CI 배포 | `main`만 배포 | feature 자동배포 금지 | 일치 |
| 데이터 이전 | 없음 | v2.1도 이전 범위 제외 | 일치(의도) |

---

## 1. 현재 실제 테이블 (구현됨)

### 1-A. 코어 (`server-api/models.py`, Alembic baseline `20261016_0001`)

| 테이블 | 핵심 컬럼/특징 |
|--------|----------------|
| `ok_rooms` | `code`, `host_id`, `config`(JSON), `revision`, `round`, `status`, `dirty` |
| `ok_members` | `room_id`, `nickname`, `token_hash`, `(room_id,nickname)` UNIQUE |
| `ok_ai_drafts` | `raw_text`, `model_output`/`app_draft`/`questions`(JSON) |
| `ok_condition_submissions` | `member_id`, `version`, `confirmed`(JSON), `ai_draft_id` |
| `ok_proposals` | `round`, `source_revision`, `input_snapshot`/`plan`(JSON), `solver_status` |
| `ok_consents` | `(proposal_id, member_id)` UNIQUE, `status`, `note` |
| `ok_room_events` | `room_id`, `message` |
| `ok_schema_versions` | 레거시 버전 마커 |

### 1-B. Admin (별도 `AdminBase`, `server-api/migrations/003_admin.py`의 `create_all`)

| 테이블 | 비고 |
|--------|------|
| `ok_admin_accounts` | 이메일/비번/role/frozen 등 |
| `ok_admin_otps` | OTP |
| `ok_admin_sessions` | 세션 |
| `ok_admin_audit` | 감사 로그 |
| `ok_admin_rate_limits` | 레이트리밋 |
| `ok_room_lifecycle` | 방 수명주기/관리 상태 |
| `ok_room_cycles` | 사이클 아카이브 |

**중요:** admin 테이블은 **Alembic versions 체인이 아니라** 명시 스크립트 `003_admin.py --apply` + `create_all`이다. 가이드의 “Alembic 단일 관리”와 불일치.

---

## 2. v2.1 목표 19테이블 vs 현재 갭

상태 범례: `없음` / `부분` / `다름` / `있음(유사)`

### 계정·인증 (3) — 거의 전부 없음

| v2.1 | 현재 | 상태 | 메모 |
|------|------|------|------|
| `accounts` | 없음 | 없음 | 현재는 계정 없이 닉네임+방코드+멤버 토큰 |
| `account_sessions` | 없음 (`ok_admin_sessions`는 admin 전용) | 없음 | 일반 사용자 세션 테이블 없음 |
| `password_reset_tokens` | 없음 | 없음 | |

### 방·참여자·역할 (3)

| v2.1 | 현재 | 상태 | 메모 |
|------|------|------|------|
| `rooms` | `ok_rooms` | 부분/다름 | `starts_at/ends_at/lifecycle_status/deleted_at/created_by_account_id` 없음. 일정은 `config` JSON |
| `room_members` | `ok_members` | 부분/다름 | `account_id`, `room_role`, `membership_status`, `left_at` 없음. `token_hash` 중심 |
| `room_roles` | 정규화 테이블 없음 | 없음 | 역할은 config/JSON에 존재 가능 |

### AI (1)

| v2.1 | 현재 | 상태 | 메모 |
|------|------|------|------|
| `ai_drafts` | `ok_ai_drafts` | 부분/다름 | v2.1: `raw_text`+`parse_status`만. 현재: `questions`/`model_output`/`app_draft` JSON 보관 (가이드는 질문·시간·역할 초안 테이블 제외) |

### 조건 (3)

| v2.1 | 현재 | 상태 | 메모 |
|------|------|------|------|
| `condition_submissions` | `ok_condition_submissions` | 부분 | 버전 UNIQUE는 유사. 슬롯/선호는 JSON `confirmed` |
| `condition_available_slots` | 없음 | 없음 | 30분 블록 정규화 필요 |
| `condition_role_preferences` | 없음 | 없음 | 복합 PK 선호 테이블 없음 |

### 배정·동의 (4)

| v2.1 | 현재 | 상태 | 메모 |
|------|------|------|------|
| `proposals` | `ok_proposals` | 부분/다름 | `proposal_status`/`invalidated_at`/`created_by_member_id` 등 컬럼 차이. plan이 JSON |
| `proposal_condition_inputs` | `input_snapshot` JSON으로 흡수 | 없음(정규화) | |
| `proposal_assignments` | `plan` JSON으로 흡수 | 없음(정규화) | |
| `proposal_consents` | `ok_consents` | 있음(유사) | 이름·일부 컬럼만 다름 |

### 관리자·이벤트 (5)

| v2.1 | 현재 | 상태 | 메모 |
|------|------|------|------|
| `service_controls` | 없음 (유사 개념이 lifecycle/management에 흩어짐) | 없음/다름 | |
| `room_controls` | `ok_room_lifecycle` | 다름 | 스키마·의미 다름 |
| `admin_audit_logs` | `ok_admin_audit` | 부분/다름 | target FK 전략 미정렬 |
| `announcements` | 없음 | 없음 | |
| `room_events` | `ok_room_events` | 부분 | `actor_member_id`/`event_type` 빈약·없음 가능 |

### 가이드에서 제외한 4테이블 (구현하지 말 것)

- `ai_draft_questions`
- `ai_draft_availability`
- `ai_draft_role_preferences`
- `consent_events`  
→ 현재도 별도 테이블 없음. 단, `ok_ai_drafts.questions` JSON은 가이드 취지(중간 초안 비저장)와 긴장 관계.

---

## 3. Alembic / ORM 구조 갭

| 가이드 요구 | 현재 | 갭 |
|-------------|------|----|
| 단일 `DeclarativeBase`에 19모델 등록 | 코어 `Base` + admin `AdminBase` 이중 | 베이스 분리 |
| `app/db/models/*.py` 권장 구조 | 플랫 `models.py` + `admin/models.py` | 경로 다름(강제 변경 금지 — 통합만) |
| 초기 리비전 = 빈 DB 기준 19테이블 | baseline = `ok_*` 8테이블(+schema_versions) | 스키마 세대 다름 |
| admin도 Alembic | admin은 `003_admin.py` + `create_all` | Alembic 단일화 미완 |
| 운영에 임의 upgrade/DROP 금지 | `deploy.sh`가 `alembic upgrade head` 실행 | 기존 DB는 stamp-first (`infra/alembic-cutover.md`) |
| 데이터 이전 코드 작성 금지 | 이전 코드 없음 | 일치 |

---

## 4. API / 도메인 규칙 갭 (가이드 DoD 기준)

| DoD 항목 | 현재 | 갭 |
|----------|------|----|
| 19테이블 ORM + 빈 PG에서 생성 | `ok_*`만 | 미달 |
| 계정 이메일 로그인 USER/ADMIN | 일반 유저 계정 없음; admin만 별도 | 미달 |
| REMOVED 재입장 금지 | membership_status 모델 없음 | 미달 |
| 방장 1명 DB/트랜잭션 보장 | `host_id` 필드 수준 | 부분 |
| 조건 version ↑ + proposal INVALIDATED | revision/dirty/round 로직 존재, status enum은 v2.1과 다름 | 부분 |
| 슬롯 30분·배정 시간 겹침 DB 제약 | JSON + 앱 검증 위주 | 미달(정규화/CHECK) |
| 전원 동의 후 방장 확정 | workflow에 동의/확정 로직 있음 | 부분(스키마 다름) |
| 논리삭제 `deleted_at` + 30일 배치 | 없음 | 미달 |
| 관리자 감사 보존 정책 | `ok_admin_audit` 존재 | 부분 |
| schemas/repositories/services 계층 | 사실상 `workflow.py` 중심 | 후속 단계 |

---

## 5. 구현 전 미확정 항목 (가이드 §09 — 아직 코드로 못 박지 말 것)

1. 컬럼별 정확한 자료형 / NOT NULL / DEFAULT  
2. FK ON DELETE (방 삭제 vs 감사 로그 보존)  
3. 동일 방 소속 검증을 DB 복합 FK로 할지 서비스 트랜잭션으로 할지  
4. `admin_audit_logs.target_type/target_id` vs 명시적 FK  
5. v2.1을 **신규 스키마로 교체**할지, **`ok_*`와 병행**할지 (가이드는 이전 제외·신규 설계)

---

## 6. GPT에게 부탁할 때 권장 지시문

다음을 전제로 답하라:

1. 현재 프로덕션/레포의 진실은 **`ok_*` + `ok_admin_*`** 이다.  
2. v2.1 PDF는 **목표 논리 설계**이며 아직 ORM/Alembic에 반영되지 않았다.  
3. 인프라(외부 PG, `DB_*`, Caddy, 모니터링, main-only 배포)는 유지한다.  
4. 운영 DB에 DROP/RESET/자동 파괴/비밀값 출력을 제안하지 않는다.  
5. 데이터 마이그레이션(ok_* → v2.1) 코드는 범위 밖이다.  
6. 파일 경로를 가이드의 `app/db/...`로 강제 rename하지 말고, 기존 `server-api/models.py` 등에 역할만 맞춰 통합 방안을 제시한다.  
7. 산출물은: (a) 단계별 구현 계획 (b) 19테이블 모델/리비전 초안 전략 (c) 기존 ok_*와의 관계(병행/교체) (d) 미확정 설계 추천안.

---

## 7. 주요 파일 경로 (현재)

```
server-api/models.py
server-api/database.py
server-api/migrations/env.py
server-api/migrations/versions/20261016_0001_ok_baseline.py
server-api/migrations/003_admin.py          # Alembic versions 아님
server-api/admin/models.py
infra/alembic-cutover.md
infra/prepare_database_env.py
infra/backup_database.py
infra/deploy.sh
.env / .env.example                         # DB_*
```

---

## 8. 빠른 판정

| 질문 | 답 |
|------|----|
| v2.1 이미 적용됐나? | **아니오** |
| 지금 Alembic head가 v2.1인가? | **아니오** (`ok_*` baseline) |
| admin이 v2.1 테이블인가? | **아니오** (`ok_admin_*` / lifecycle) |
| 인프라는 v2.1 가이드와 맞나? | **대체로 예** |
| 다음 큰 작업은? | v2.1 19모델 + Alembic 초기 리비전(빈 DB) + API는 후속; ok_* 전략 결정 필요 |
=======
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
>>>>>>> 4a28f5df6e17f8be24ab6bebfa6f3bc599e6b284
