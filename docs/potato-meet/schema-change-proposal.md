# Potato Meet DB 변경 제안서 (승인 전 · 마이그레이션 미생성)

> 기준일: 2026-11-16  
> 비교 대상: 팀원 `models.zip`(검토용 초안) vs 저장소 `server-api/db_v21/` + `migrations_v21/` (head **`20261101_0004`**) vs 하네스 `data-model.md`(정책 동기화 후)  
> **이 문서는 설계 제안만 한다. Alembic 리비전 생성·운영 DB 변경·배포는 사용자 승인 전 금지.**

## 1. 현황 (읽기 전용 확인)

| 항목 | 결과 |
|---|---|
| Alembic head (저장소) | `20261101_0004` (`migrations_v21/versions/` 4개 파일) |
| 운영 DB 접속/변경 | **미실행** |
| RLS | 저장소에 RLS 정책 없음 → **이번 작업으로 도입하지 않음** (후속 제안만) |
| `rooms.deleted_at` 30일 물리삭제 배치 | 코드베이스에서 **미발견** (정책만 존재) |
| 로컬 `.env` `ADMIN_ENABLED` | `1` (하네스 문서 기본 서술 `0`과 불일치) → **값 변경 안 함** |

## 2. 일관 설계 선택 (중복 금지)

팀원안(`scheduling_rounds` …)과 하네스안(`schedule_collections` …)을 **동시에 만들지 않는다**.

**채택 기준안: 하네스 `schedule_*` 계열**을 2026-11-16 정책으로 수정한 형태  
(`docs/potato-meet/data-model.md` §2).

이유:
- 기존 v21 `rooms`/`room_members`/`accounts` 재사용과 정합.
- 입력 기간(OPEN 1개)·재조정 cycle·투표 run이 분리되어 상태 전이가 명확.
- 팀원안의 5분 `slot_index`(0–287)·무제한에 가까운 `extension_count`/`DATE_EXTENSION` kind는 확정 정책과 충돌.

팀원 `scheduling.py`는 **참고·제외(또는 개념만 흡수)** 로 분류한다.

## 3. 기존 v21 테이블

| 테이블 | 판정 | 근거 |
|---|---|---|
| `accounts`, `account_sessions` | **재사용** | R1 로그인 |
| `rooms` | **재사용(+소수 검토)** | `starts_at`/`ends_at`으로 날짜 범위 표현 유지. 팀원 `schedule_start_date`/`schedule_end_date` **추가 불필요**(중복). `meeting_settings.duration` 등 길이 필드는 API에서 더 이상 요구하지 않음(컬럼 삭제는 후순위) |
| `room_members`, `room_events` | **재사용** | 역할·멱등·활동 기록 |
| `room_roles`, `condition_*`, `proposals*`, `ai_drafts`, `room_controls` | **유지·조율 경로 미사용** | CP-SAT/관리 레거시. DROP 금지(승인 전). Potato Meet `schedule_*`와 병행 |
| `deleted_at` | **유지** | 논리삭제. 30일 물리삭제 배치는 **별도 승인** 후 구현 |

## 4. 팀원 모델 테이블별 분류

| 팀원 테이블 | 판정 | 이유 · 대응 |
|---|---|---|
| `scheduling_rounds` | **제외(이름) / 개념→수정 채택** | 회차 개념은 `schedule_collections`(+`schedule_runs`)로 흡수. 팀원 `DATE_EXTENSION`/`WAITING_FOR_SECOND`/연장 상한 4는 정책 위반 |
| `round_participants` | **수정 채택(개념)** | 입장 스냅샷·완료 표시 → `schedule_responses` + (필요 시) 조율 포함 플래그는 `schedule_runs`/`included` 로직으로. 별도 테이블은 최소화 |
| `unavailable_slots` | **제외** | 5분 셀 저장. 정책은 **가능 구간** 제출(`schedule_response_ranges`, 30분 경계) |
| `schedule_candidates` | **수정 채택** | 이름 유사. harness: `run_id`+TIMESTAMPTZ 구간+`sort_order`+`available_count≥2`+길이≥60. 팀원 `start_slot/end_slot`·5분·≥12슬롯 제약은 폐기 |
| `voting_participants` | **수정 채택** | 빈 투표 완료 구분에 필요 → harness `schedule_vote_ballots`(또는 동등) |
| `candidate_votes` | **수정 채택** | → `schedule_votes` (복수 선택, 가능 후보만) |
| `schedule_confirmations` | **수정 채택** | → `schedule_results` (방당 1확정·불변). 회차별 히스토리가 필요하면 run 단위 확장은 후속 |
| `notification_preferences` | **수정 채택** | → `notification_settings` |
| `notification_deliveries` | **수정 채택** | → `notification_log` (+ `push_devices`) |
| `scheduling_events` | **수정 채택(선택)** | SSE는 프로세스 내 Queue로도 가능. DB outbox는 다중 워커 대비 **후속**. 1차는 필수 아님 |
| `Room.schedule_*_date` (팀원 room.py) | **제외** | `starts_at`/`ends_at`로 충분 |

## 5. 신규 테이블 제안 요약 (리비전 후보 `YYYYMMDD_0005`, 미생성)

자세한 DDL 스케치는 `data-model.md` §2. 핵심 제약만:

| 테이블 | 핵심 제약 |
|---|---|
| `schedule_collections` | `UNIQUE(room_id,cycle)`; `cycle` 0–4; **`extended_count` 0–1**; room당 OPEN 1개(PG partial unique); `grace_until` |
| `schedule_responses` | PK `(collection_id, room_member_id)` |
| `schedule_response_ranges` | 30분 경계 서비스 검증; `ends_at > starts_at` |
| `schedule_runs` | collection 근거; `participant_count`/`voter_count` |
| `schedule_candidates` | `UNIQUE(run_id, sort_order)`; count≥2·≥60분 |
| `schedule_candidate_members` | 투표 자격·닉네임 공개 근거 |
| `schedule_votes` | PK `(candidate_id, room_member_id)` |
| `schedule_vote_ballots` | PK `(run_id, room_member_id)` — 빈 투표 vs 미투표 |
| `schedule_results` | PK `room_id`; 서비스 UPDATE/DELETE 금지 |
| `push_devices`, `notification_settings`, `notification_log` | R9 |

### 동일 방 정합성
- 후보·투표·멤버 FK에 `room_id` 중복 저장 또는 composite FK로 교차 검증(구현 시 선택).
- 입장/마감 경합: `rooms` `FOR UPDATE` + collection 상태 검사.

### Downgrade 위험
- 신규 테이블 DROP만이면 낮음. `rooms` 기존 컬럼 삭제는 고위험 → 1차 제안에서 **비권장**.

### API/DTO 영향
- 생성: `{title, nickname, startDate, endDate}` — **duration/window 제거**.
- 입력: `available[{start,end}]` 30분 경계.
- 투표: `candidateIds` + 빈 배열 허용(ballot만 기록); 불가 후보 422.
- 참여: CLOSED 이후 409.

### 데이터 이전
- 기존 CP-SAT 방 데이터는 Potato Meet 조율 테이블로 **자동 이전하지 않음**(Q13 확정: 조회+방장 삭제만). 데이터가 없으면 이전 작업 없음.

## 6. 코드 vs 정책 충돌 (구현 2차에서 처리)

| 현재 코드 | 확정 정책 | 비고 |
|---|---|---|
| `workflow_models`/`optimizer` 등 **1분 단위** 허용(최근 main) | UI·경계 **30분** | 정책 우선. 2차에서 서버·앱 정합 |
| 모임 생성 시 `duration`/`windowStart`/`windowEnd` | 길이 미입력, 겹침 구간이 후보 | schedule 라우터로 대체 예정 |
| CP-SAT 역할 배정 | 미사용(조율 경로) | 컷오버 전 병행 |

## 7. 테스트 계획 위치

`docs/potato-meet/test-plan-20261116.md` (명세만 · 1차 미실행).

## 8. 승인 요청 항목

1. 위 **schedule_\*** 일관안을 2차 구현·Alembic `0005` 초안 작성의 기준으로 할지.
2. `schedule_vote_ballots` 도입 여부(빈 투표 구분).
3. `scheduling_events` DB outbox를 1차에 넣을지(기본: 보류).
4. 기존 `condition_*`/`proposals*` DROP 여부(기본: **유지**).
5. 30일 물리삭제 배치 설계·가동 여부(기본: 정책만, 배치 미가동).
6. `ADMIN_ENABLED` 운영/로컬 불일치 해소 방향(값 변경은 별도 승인).

**2차 진행(2026-11-17):** `db_v21/models/schedule.py` + Alembic `20261117_0005` 초안·SQLite `upgrade head` 검증까지 로컬 작성. SSE outbox 보류, 기존 테이블 유지. 다음: `schedule/` API 골격 → 단위 테스트. 운영 `potato_server_v2` 적용·`main` push는 **또 다른 승인**.
