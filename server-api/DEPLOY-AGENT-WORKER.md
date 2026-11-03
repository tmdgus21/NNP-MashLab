# Agent Worker 운영 배포 메모 (미적용)

이 문서는 변경 목록일 뿐이며 운영 시스템에는 적용되지 않았다.

## 실행
    python agent_worker_main.py            # 상시 실행
    python agent_worker_main.py --once     # 큐가 비면 종료 (점검용)
    python agent_worker_main.py --max-runs N

## 환경변수 (모두 선택, 기본값 표기)
| 이름 | 기본 |
|---|---|
| AGENT_WORKER_ID | host-pid-random |
| AGENT_WORKER_POLL_INTERVAL_SECONDS | 2.0 |
| AGENT_WORKER_LEASE_SECONDS | 60 (최소 3) |
| AGENT_WORKER_HEARTBEAT_INTERVAL_SECONDS | lease/3 |
| AGENT_WORKER_SOLVER_TIME_LIMIT_SECONDS | 5.0 |
| AGENT_WORKER_MAX_ATTEMPTS | 3 |
| AGENT_WORKER_ERROR_BACKOFF_INITIAL_SECONDS / _MAX_SECONDS | 1.0 / 30.0 |
| AGENT_WORKER_LOG_LEVEL | INFO |
| AGENT_WORKER_DISPATCH (API 측) | NOT_CONFIGURED |

DB 접속은 API와 동일한 DATABASE_URL 또는 DB_* 변수를 사용한다.

## 배포 시 필요한 변경
1. API·Worker 이미지 모두에 potato_agent 설치: `pip install ./experiments/potato-agent`
   (현 Dockerfile 빌드 컨텍스트는 server-api/ 뿐이므로 컨텍스트 또는 wheel 제공 방식 결정 필요).
   현재는 소스 경로 sys.path 폴백이 남아 있어 설치 없이도 로컬에서 동작한다.
2. Worker 프로세스 1개를 별도 컨테이너/서비스로 추가, 명령은 `python agent_worker_main.py`,
   종료 시그널은 SIGTERM (현재 Run 완료 후 종료, 2회째 시그널은 즉시 종료 → lease 만료 후 복구).
3. Worker 가동 확인 후에만 API에 `AGENT_WORKER_DISPATCH=DB_POLLING` 설정.
   이 값은 설정 표시일 뿐 Worker 생존을 검증하지 않는다.
4. 마이그레이션 변경 없음.

## PostgreSQL Checkpointer (25.3-4.7, 미적용·미검증)
- 패키지: `langgraph-checkpoint-postgres==3.1.3` (langgraph 1.2.19 / checkpoint 4.3.1 / psycopg 3.3.x와 `pip check` 통과), `psycopg-pool`.
- 스키마는 Alembic이 아니라 LangGraph `setup()`이 만든다. 배포 시 1회, 별도 단계로 실행:
  `python -c "from potato_agent.checkpoint import open_postgres_checkpointer as o; o('<URL>', setup=True).__enter__()"` (격리 DB에서 먼저 검증할 것).
- Worker 활성화: `AGENT_WORKER_CHECKPOINT_BACKEND=postgres`, `AGENT_WORKER_CHECKPOINT_DATABASE_URL=<URL>` (기본은 memory = 기존 동작).
- PG 격리 테스트: `POTATO_TEST_POSTGRES_URL=<격리 DB URL>` 지정 시에만 실행, 없으면 SKIP.

## 후보 선택·동의·승인 영속화 (25.3-4.8, 미적용·PostgreSQL 미검증)
- 마이그레이션 `20261103_0008` (additive): `agent_candidates.graph_candidate_id`(+Run 내 unique), `agent_runs.decision_version / graph_synced_version / sync_owner / sync_lease_expires_at / base_checkpoint_ref / finalized_at / finalized_by_member_id`. 기존 행은 기본값 0/NULL로 유지된다. **기존에 저장된 후보는 graph_candidate_id가 NULL이라 선택 불가(CANDIDATE_MISMATCH)** — 새 Run부터 적용된다.
- API 프로세스에 그래프 동기화를 켜려면 `AGENT_CHECKPOINT_DATABASE_URL` 설정. 미설정이면 DB 전용(graphSync는 `NOT_APPLICABLE` 또는 `PENDING`).
- 새 경로: GET `/v2/rooms/{room}/agent-runs/{run}/decision`, POST `.../select`, `.../consent`, `.../approval`, `.../finalize`.

## Qwen 자연어 변경 API (25.3-4.9, 미적용·PostgreSQL 미검증)
- 마이그레이션 `20261103_0009`: 신규 테이블 `agent_change_proposals` (additive). 0008 선행 필수.
- 경로: POST `/v2/rooms/{room}/agent-change-proposals` (`Idempotency-Key` 필수), GET `/{id}`, POST `/{id}/approve`, POST `/{id}/reject`.
- Qwen 접속: 환경변수 `POTATO_LLAMA_CPP_URL` (기본 `http://127.0.0.1:18081`). 클라이언트가 loopback만 허용하고 포트 8080은 거부한다. 서버가 없으면 503 `QWEN_UNAVAILABLE`.
- 승인 시 `rooms.agent_input_revision`과 `rooms.revision`이 1 증가하고, 이전 Run은 STALE, 새 Run은 QUEUED로 생성된다 (Worker가 CP-SAT 재계산).
- Live 테스트: `POTATO_TEST_QWEN_URL=<테스트 8081>` 지정 시에만 실행.

## 최종 상태 정합성 (25.3-4.10, 미적용·PostgreSQL 미검증)
- 마이그레이션 `20261103_0010`: `agent_runs.finalized_room_round` + 부분 unique 인덱스(`room_id, finalized_room_round WHERE finalized_at IS NOT NULL`). 0008·0010이 아직 어떤 DB에도 적용되지 않은 상태에서만 안전하게 생성된다(이미 방당 확정 Run이 둘 이상이면 인덱스 생성 실패).
- 조회 정본: GET `/v2/rooms/{room}/agent-final-result` (현재 회차 `rooms.current_round`의 확정 Run). `rooms.progress_status/lifecycle_status`는 /v1 역할 배정 확정 상태이며 Agent 흐름이 쓰지 않는다.
- 확정 후 재조정은 /v1의 기존 신규 회차(`extend` → `current_round` 증가) 이후에만 입력 변경 승인이 가능하다.

## v1/v2 도메인 경계와 조정 회차 (25.3-4.11, 미적용·PostgreSQL 미검증)
- **앞 절(25.3-4.10)의 "/v1 `extend`로 새 회차" 서술은 폐기한다.** 확정 회차는 `rooms.coordination_round`(신규)에 묶이고, `rooms.current_round`(/v1 역할 배정 회차, /v1 calculations마다 증가)와 무관하다.
- 마이그레이션 `20261103_0011`: `rooms.coordination_round`(기본 0), 테이블 `coordination_rounds`. `agent_runs.finalized_room_round`는 이제 조정 회차 값을 저장한다(컬럼명 유지). 적용 순서: 0008 → 0009 → 0010 → 0011.
- 신규 API: POST `/v2/rooms/{room}/coordination-rounds` (`Idempotency-Key` 필수, 본문 `expectedRound`, 선택 `reason`). 방장 전용.
- Potato Meet 방 판별: `meeting_settings.coordination` 존재 여부(명시적 유형 컬럼 없음). /v1로 만든 방에는 이 키가 없어 모든 가드가 no-op.
- /v1 변경(Potato 방 한정): calculations·consent·finalize·extensions 거부, 현재 조정 회차 확정 후 conditions/join 거부, join·conditions·호스트 이관 시 `agent_input_revision` 증가.
- `start_agent_run`은 현재 조정 회차가 확정된 방에서 409 `ROUND_ALREADY_FINALIZED` (기존 Idempotency-Key 재전송은 기존 Run을 그대로 반환).

## 4인 MVP 리허설 (PostgreSQL · 실 서버 · 별도 Worker 프로세스)
격리 PostgreSQL(운영 아님)에서 `alembic -c alembic.v21.ini upgrade head`(0001→0011) 적용/롤백, 이어서:
    python -m uvicorn main:app --port 8765          # DATABASE_URL=postgresql+psycopg://...
    python agent_worker_main.py                     # 별도 프로세스, 같은 DATABASE_URL
    python scripts/potato_mvp_rehearsal.py --base http://127.0.0.1:8765
PostgreSQL 체크포인터 모드: 스키마 1회 `open_postgres_checkpointer(url, setup=True)` 후
API에 `AGENT_CHECKPOINT_DATABASE_URL`, Worker에 `AGENT_WORKER_CHECKPOINT_BACKEND=postgres`와
`AGENT_WORKER_CHECKPOINT_DATABASE_URL`을 설정하고 `--expect-graph-sync SYNCED`로 검증한다.
`--stop-after-select FILE` 후 API·Worker를 모두 재시작하고 `--resume FILE`로 재시작 복구를 검증한다.
리허설 스크립트는 운영 호스트(oranganman)를 거부한다.
