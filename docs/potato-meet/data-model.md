# Potato Meet 데이터 모델 (PostgreSQL 18 · Alembic v21 체인)

- 대상 DB: 운영 `potato_server_v2`, 로컬 `mashlab_v21`(docker-compose.local.yml), 테스트 `sqlite://`
- 설정: `server-api/alembic.v21.ini` → `migrations_v21/`, 메타데이터 `db_v21.Base`
- 현재 head(초안): `20261121_0007` (`down_revision=20261120_0006`). 형식 `YYYYMMDD_NNNN`.
- v1(`migrations/`, ok_*)은 사용하지 않는다.
- 변경은 반드시 `schema-change` 스킬.
- 2026-11-17 2차: `db_v21/models/schedule.py` + Alembic `20261117_0005` **로컬 초안**. 운영 DB 적용·배포·`main` push는 별도 승인. SSE outbox·기존 테이블 DROP 없음.
- GUEST-only 방장 삭제: `guest-owner-delete-analysis.md`. 1분 vs 30분: `slot-1min-vs-30min-analysis.md`.

## 1. 재사용하는 v21 테이블 (구조 변경 없음)
| 테이블 | Potato Meet에서의 의미 | 사용 컬럼 |
|---|---|---|
| `accounts` | 로그인 계정 (R1) | `account_type='USER'`, `login_email`, `password_hash`, **`nickname` VARCHAR(30) NOT NULL** (중복 허용, `20261121_0007`) |
| `account_sessions` | Bearer 토큰 | `token_hash`, `expires_at`, `revoked_at` |
| `user_auth_challenges` | USER 이메일 OTP (R1, `20261120_0006`) | `email`, `purpose` REGISTER\|LOGIN, `challenge` UNIQUE, `code_digest`(HMAC), `password_hash`(가입 대기), `expires_at`, `sent_at`, `used_at`, `attempt_count`; `account_id` FK **ON DELETE SET NULL** — **admin_otps와 분리** |
| `rooms` | 모임 (R2) | `title`, `code`(8자리), `starts_at`, `ends_at`(선택일 min~max 호환 범위), `meeting_settings.selectedDates`(`YYYY-MM-DD[]`), `host_member_id`, `created_by_account_id`, `progress_status`, `lifecycle_status`, `revision`, `deleted_at` |
| `room_members` | 방장/팀원 (R3) | `room_role` OWNER=방장 / MEMBER=팀원, `nickname`(모임 스냅샷·계정 변경 미반영), `account_id`(**nullable**, FK **ON DELETE SET NULL**, `20261126_0008` — 계정 삭제 시 익명화), `membership_status`; UNIQUE는 `(room_id, account_id)`만 (`uq_room_members_room_nickname` **제거** `20261121_0007`) |
| `room_events` | 활동 기록 | `event_type`, `message`, `actor_member_id` |

사용하지 않음(건드리지 않음): `condition_submissions`, `condition_available_slots`(입력 기간·마감 구조와 맞지 않아 신규 테이블 사용), `room_roles`, `condition_role_preferences`, `ai_drafts`, `proposals*`, `room_controls` 등 CP-SAT/관리 관련.

### 값 매핑 규칙
- 복수 날짜 → `meeting_settings.selectedDates` = 선택일 ISO 목록. `rooms.starts_at` = 최소일 00:00 Asia/Seoul, `rooms.ends_at` = **최대일 다음날** 00:00 Asia/Seoul. 레거시 범위만 있는 모임은 `[starts_at, ends_at)` 연속일을 선택일로 취급
- 상태 매핑 (기존 CHECK 안에서만 사용)

| 앱 상태 | `progress_status` | `lifecycle_status` |
|---|---|---|
| COLLECTING (입력 중) | `collecting` | `COLLECTING_CONDITIONS` |
| VOTING (투표 중) | `reviewing` | `WAITING_FOR_CONSENT` |
| CONFIRMED (확정) | `finalized` | `CONFIRMED` |
| 조율 불가 (재조정 4회 실패·남은 시간 없음·연장 1회 뒤에도 완료자 2명 미만) | `cancelled` | `CANCELLED` |
| 삭제됨 (R8) | `deleted` (+ `deleted_at`) | 변경 없음 |

- 시간 구간은 모두 반열린 `[starts_at, ends_at)`, Asia/Seoul **30분 경계**(`SLOT_MINUTES=30`). 경계 아님·범위 밖은 422
- **지난 모임**은 저장 컬럼이 아니다: 확정된(`CONFIRMED`) 후보의 `ends_at` < 서버 `now`로 판단한다
- **삭제**는 소프트(`progress_status='deleted'`, `deleted_at`). 삭제 요청 **30일 뒤 물리 삭제** 정책이며 정리 배치는 아직 구현되지 않았을 수 있다(구현 전까지 행 유지)

## 2. 신규 테이블 (`db_v21/models/schedule.py`, 리비전 0005)
```
schedule_collections              -- 입력 기간 (단일 세션 + 자동 마감, R4)
  id               String(36) PK
  room_id          FK rooms.id ON DELETE CASCADE, index
  cycle            Integer NOT NULL        -- 0 = 처음, 1~4 = 재조정 n회 (CHECK BETWEEN 0 AND 4), UNIQUE(room_id, cycle)
  kind             String(10) NOT NULL     -- CHECK IN ('NORMAL','READJUST')
  hints_enabled    Boolean NOT NULL        -- 재조정이면 true
  scope_starts_at  DateTime(tz) NOT NULL   -- 이번에 묻는 날짜 범위
  scope_ends_at    DateTime(tz) NOT NULL   -- CHECK scope_ends_at > scope_starts_at
  opened_at        DateTime(tz) NOT NULL
  closes_at        DateTime(tz) NOT NULL   -- opened_at + 24시간 (1회 연장 시 +24시간, 항상 rooms.ends_at 이하)
  grace_until      DateTime(tz) NULL       -- 전원 완료(≥2)로 전이될 때만 now+3분 (Q38). 유예 중 재제출로 갱신하지 않음. 신규 참가로 전원 완료 깨지면 NULL. 유예 중 제출·참여 허용
  status           String(10) NOT NULL     -- CHECK IN ('OPEN','CLOSED')  (참여 허용 = OPEN, 유예 중 포함)
  closed_at        DateTime(tz) NULL
  closed_reason    String(20) NULL         -- CHECK IN ('ALL_DONE','DEADLINE')
  extended_count   Integer NOT NULL DEFAULT 0  -- 완료자 2명 미만 24시간 연장 횟수 (Q24). CHECK (extended_count BETWEEN 0 AND 1) = ck_schedule_collections_extended_count, 최대 1회
  -- room_id당 OPEN은 1개 (PostgreSQL partial unique index, sqlite는 서비스 검사)

schedule_responses                -- 한 사람의 제출 (완료 = 행 존재)
  collection_id    FK schedule_collections.id ON DELETE CASCADE  ┐ PK
  room_member_id   FK room_members.id ON DELETE CASCADE          ┘
  submitted_at     DateTime(tz) NOT NULL   -- 재제출 시 갱신

schedule_response_ranges          -- 제출한 최종 '가능' 구간 (30분 경계)
  id               String(36) PK
  collection_id    FK schedule_collections.id ON DELETE CASCADE, index
  room_member_id   FK room_members.id ON DELETE CASCADE, index
  starts_at        DateTime(tz) NOT NULL
  ends_at          DateTime(tz) NOT NULL   -- CHECK ends_at > starts_at
  -- 재제출 = 내 행 삭제 후 재삽입 (한 트랜잭션). 앱 격자(30분 칸)는 화면 표현일 뿐, 서버에는 최종 '가능' 구간만 저장
  -- CHECK: starts_at/ends_at 모두 30분 경계(서비스 검증, 경계 아님 422)

schedule_runs                     -- AI 조율 1회 실행
  id               String(36) PK
  room_id          FK rooms.id ON DELETE CASCADE, index
  collection_id    FK schedule_collections.id ON DELETE SET NULL  -- 근거가 된 입력 기간
  max_count        Integer NOT NULL        -- M
  participant_count Integer NOT NULL       -- N = 이번 입력 기간 완료자 수 (조율 대상)
  voter_count      Integer NULL            -- 투표 대상자 수 = 입력 완료자 수 (Q33)
  ai_summary       Text NULL               -- Qwen 요약 JSON {v:2, summary, comparison[]} (옛 행은 평문), 실패 시 NULL (백그라운드로 채움)
  voting_started_at DateTime(tz) NULL      -- 후보 2개+일 때 투표 시작 시각
  voting_ends_at   DateTime(tz) NULL       -- min(시작+6시간, 가장 이른 후보 시작−30분) (Q30)
  excluded_soon_count Integer NOT NULL DEFAULT 0  -- 투표 시간 부족으로 제외한 후보 수
  closed_at        DateTime(tz) NULL
  closed_reason    String(20) NULL         -- CHECK IN ('ALL_VOTED','TIMEOUT')
  created_by_member_id FK room_members.id ON DELETE SET NULL
  created_at       DateTime(tz)

schedule_candidates               -- 실행 결과 후보 구간
  id               String(36) PK
  run_id           FK schedule_runs.id ON DELETE CASCADE, index
  room_id          FK rooms.id ON DELETE CASCADE, index
  starts_at        DateTime(tz) NOT NULL
  ends_at          DateTime(tz) NOT NULL   -- CHECK ends_at > starts_at
  available_count  Integer NOT NULL
  sort_order       Integer NOT NULL        -- 추천 순서 (1이 가장 높음), UNIQUE(run_id, sort_order)
                                           -- 정렬 = available_count DESC → (ends_at − starts_at) DESC → starts_at ASC
                                           -- 후보 조건: available_count ≥ 2, 길이 ≥ 60분, 30분 경계 [start,end), 자정에서 분리, 조율 시각 이전 부분 제거

schedule_candidate_members        -- 후보별 가능 멤버 (정규화)
  candidate_id     FK schedule_candidates.id ON DELETE CASCADE  ┐ PK
  room_member_id   FK room_members.id ON DELETE CASCADE         ┘

schedule_votes                    -- 중복 투표: 1행 = 1명 × 1후보
  candidate_id     FK schedule_candidates.id ON DELETE CASCADE  ┐ PK
  room_member_id   FK room_members.id ON DELETE CASCADE         ┘
  room_id          FK rooms.id ON DELETE CASCADE, index
  voted_at         DateTime(tz)

schedule_vote_ballots             -- 투표 완료 표시 (빈 투표 = 완료이되 득표 0)
  run_id           FK schedule_runs.id ON DELETE CASCADE         ┐ PK
  room_member_id   FK room_members.id ON DELETE CASCADE         ┘
  submitted_at     DateTime(tz) NOT NULL   -- 재투표 시 갱신
  -- "투표 완료" 판정(조기 마감·k/N 표시)은 schedule_votes가 아니라 이 행 존재로 한다.
  -- 후보를 하나도 고르지 않은 제출도 이 행만 생기고 schedule_votes 행은 없다. 행 없음 = 미투표
  -- 투표 자격: 해당 run의 입력 기간(collection)에 schedule_responses가 있는 멤버만, 후보는 schedule_candidate_members에 본인이 있는 것만

schedule_results                  -- 확정 (한 번 기록하면 불변: UPDATE/DELETE 서비스 경로 없음)
  room_id          FK rooms.id ON DELETE CASCADE, PK
  candidate_id     FK schedule_candidates.id ON DELETE CASCADE
  method           String(10) NOT NULL     -- CHECK IN ('AUTO','VOTE')
  vote_count       Integer NULL            -- VOTE일 때 승자 득표
  tie_broken       Boolean NOT NULL DEFAULT false  -- 동점을 추천 순서로 정했는지
  confirmed_at     DateTime(tz)
```
### 알림 (R9)
```
push_devices                      -- 기기 푸시 토큰
  id               String(36) PK
  account_id       FK accounts.id ON DELETE CASCADE, index
  token            String(512) UNIQUE NOT NULL   -- 로그·응답에 원문 출력 금지
  platform         String(10) NOT NULL           -- CHECK IN ('ANDROID')
  created_at, updated_at  DateTime(tz)
  revoked_at       DateTime(tz) NULL             -- 로그아웃·발송 실패(토큰 무효) 시

notification_settings             -- 계정 단위 on/off (기본 모두 true)
  account_id       FK accounts.id ON DELETE CASCADE, PK
  start_enabled    Boolean NOT NULL DEFAULT true
  remind_enabled   Boolean NOT NULL DEFAULT true
  extend_enabled   Boolean NOT NULL DEFAULT true
  updated_at       DateTime(tz)

notification_log                  -- 발송 기록·중복 방지
  id               String(36) PK
  room_id          FK rooms.id ON DELETE CASCADE, index
  account_id       FK accounts.id ON DELETE CASCADE
  kind             String(10) NOT NULL           -- CHECK IN ('START','REMIND','EXTEND')
  event_key        String(80) NOT NULL           -- 예: collection:<id>:open, voting:<run_id>:remind
  status           String(10) NOT NULL           -- CHECK IN ('QUEUED','SENT','FAILED','SKIPPED')
  created_at, sent_at
  UNIQUE(room_id, kind, event_key, account_id)
```

- 문자열 PK는 v21 관례대로 `String(36)` + `uid()`, 시간은 `DateTime(timezone=True)` + `now()`
- 제약 이름은 v21 관례 `ck_<table>_<name>`, `uq_<table>_<cols>`
- 테스트: `tests/test_v21_schema.py`의 `EXPECTED_TABLES`에 신규 12개 추가 (정책 동기화로 `schedule_vote_ballots` 1개 늘어 기존 11개 → 12개)

## 3. 권한·상태 규칙 (서버)
- 모든 모임 API: 요청자 계정의 `room_members`(ACTIVE)가 있어야 함, 없으면 404. `progress_status='deleted'`도 404
- 삭제: `room_role='OWNER'`만, 아니면 403
- 입력 제출: 입력 기간이 OPEN(유예 포함)이고 `now < closes_at`일 때만(아니면 409). 구간은 범위 안·30분 경계만(아니면 422)
- **참여(join) 잠금**(Q14): 입력 기간 OPEN 또는 `grace_until` 유예 중일 때만 허용. 입력 마감·후보 계산 시작 이후·`VOTING`·`CONFIRMED`·진행 중·지난 모임·기존 앱 모임(Q13)·`cancelled`·`deleted`는 **409**. 참여는 `closes_at`을 바꾸지 않음. 유예 중 참여 → `grace_until=NULL`. 초대만 받은 사람은 인원에 세지 않음
- **유예(Q38)**: ACTIVE 전원 완료(≥2)로 **전이**될 때만 `grace_until=now+3분`. 유예 중 재제출은 구간만 덮어쓰고 `grace_until` 유지. 다시 전원 완료되면 새 3분. 마감 시각 = `grace_until`과 `closes_at` 중 **먼저 도래한 쪽**. **제출만으로 조율하지 않음**. 마감 후 완료자 ≥2면 조율 (rooms `FOR UPDATE`, 멱등)
- **기존 앱 방**(Q13): `schedule_collections` 없음 등으로 식별. 조회·방장 삭제만. schedule 쓰기 API 409. 자동 변환 금지
- 마감 시 완료자 < 2: `extended_count=0`이면 `closes_at = min(closes_at+24시간, rooms.ends_at)`, `extended_count=1`. 이미 1이거나 늘릴 수 없으면 `cancelled`(조율 불가)
- 마감 시각 도달은 주기 작업·조회 시 같은 함수로 처리
- 힌트 집계 응답에는 **인원 수만**, 멤버 식별자 없음. 입력 중 칸별 응답도 인원 수만 (남의 불가 격자·개인 선택 미노출)
- 후보 응답(조율 이후)에는 후보별 가능 멤버 닉네임 포함, 멤버 목록 닉네임은 항상 포함. 이메일은 어디에도 없음
- 투표: VOTING이고 `now < voting_ends_at`일 때만(아니면 409). 비대상자 403, 참석 불가·타 run 후보 422. `candidateIds=[]` 허용(빈 투표 = `schedule_vote_ballots`만 기록, 완료로 셈)
- **확정 불변**: `schedule_results` 행이 있으면 입력·투표·재조정·참여 변경 거부(409), 결과 UPDATE/DELETE 경로 없음. 삭제만 가능
- **`rooms.starts_at`/`ends_at`은 생성 후 바뀌지 않는다**(Q35: 종료일 = 데드라인, 날짜 확장 없음)
- 생성 검증: 시작일 ≥ 서버 한국 시각의 오늘, 종료일 ≤ 오늘 + 1개월(달력, 말일 보정)
- 투표 대상자 = 그 조율의 입력 기간에 `schedule_responses`가 있는 멤버 (Q33). 아니면 투표 403. 조기 마감 = 대상자 전원의 `schedule_vote_ballots` 존재
- 모임 인원 상한 `MAX_MEMBERS`(설정값, 부하 테스트로 결정) 초과 참여는 409
- 재투표: 내 `schedule_votes`를 지우고 새로 삽입 (한 트랜잭션)
- 상태 전이와 결과 저장은 `rooms` 행 잠금(`FOR UPDATE`) 안에서 한 트랜잭션, `revision += 1`

## 4. Kotlin 도메인 모델 (요약)
```kotlin
enum class Role { OWNER, MEMBER }                 // UI 표시: 방장 / 팀원
enum class MeetingStatus { COLLECTING, VOTING, CONFIRMED, FAILED }
data class TimeRange(val start: ZonedDateTime, val end: ZonedDateTime)   // Asia/Seoul, 30분 경계 [start, end)
data class Candidate(val id: String, val range: TimeRange, val count: Int,
                     val memberIds: List<String>, val votes: Int)
```
