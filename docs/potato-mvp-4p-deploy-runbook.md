# Potato Meet 4인 MVP 배포 런북 (사용자 실행용)

이 문서는 **절차서**입니다. 문서를 쓴 쪽은 운영 서버·운영 DB에 접속하거나 아무것도 실행하지 않았습니다.
아래 명령은 모두 **사용자가 확인한 뒤 직접 실행**하는 것입니다. `[읽기전용]` 표시가 없으면 운영 상태를 바꿉니다.

## 릴리스 승인 게이트 (2026-11-03 기준) — 하나라도 FAIL/필수 SKIP이면 NO-GO

| # | 게이트 | 결과 | 근거 / 한계 |
|---|---|---|---|
| 1 | CI 서버 테스트 (CI 단계 그대로: 클린 venv, `pip install -r requirements.txt` + `potato-agent` 설치, `unittest discover`) | **PASS (로컬 재현)** | 242 tests OK (skipped=3), `CI_SERVER_ALL_OK`. 최초 재현에서 `potato_agent` 미설치로 12 import error → `gitmain.yml`에 설치 단계 추가 후 통과. **GitHub Actions 실제 실행은 아님** |
| 1b | RN 타입체크·Jest | **PASS (로컬)** | `tsc` 오류 0, Jest 113 passed / 4 skipped(라이브 서버 필요) / 22 suites |
| 1c | Android CI release job (JDK17, apksigner) | **SKIP** | 로컬에서 CI 러너 재현 불가. 로컬 Release 빌드는 debug 서명으로만 확인 |
| 2 | 실제 Docker 이미지 빌드 | **SKIP (필수)** | 이 PC에 Docker 없음. 빌드 컨텍스트를 에뮬레이션해 COPY 대상 전부 존재·비밀 미포함만 확인 |
| 3 | Compose 검증 | **PARTIAL PASS / 공식 `docker compose config` SKIP (필수)** | YAML 파싱, build context·dockerfile 존재, 서비스/네트워크 참조, 보간 변수 전부 `.env.example` 또는 기본값 존재까지 정적 확인 |
| 4 | 운영 DB(PG 18) 복사본 마이그레이션 | **SKIP (필수)** | 운영 접속 금지. 대체: PG 16.2 격리 DB에서 v1 데이터 포함 0004→0011 업그레이드, 전 행 보존 (PASS, 운영과 동일 버전 아님) |
| 5 | v1 회귀 | **PASS (로컬 PG 16.2 + sqlite)** | 마이그레이션 전후 v1 토큰·계산·동의·확정 정상, 전체 테스트 242 OK |
| 6 | v2 4인 E2E | **PASS (로컬)** | 실 uvicorn + 별도 Worker + PG 16.2 (`potato_mvp_rehearsal.py`). HTTPS·실기기 아님 |
| 7 | Worker 기동/헬스 | **로직 PASS (스텁) / 실제 SKIP (필수)** | `deploy.sh` 분기를 가짜 docker/curl로 시뮬레이션: 성공 exit 0, Worker 재시작 루프·claim failed·미기동·/v2 502·구 Caddy 설정 모두 exit 1. **실제 Docker 배포 검증이 아님** |
| 8 | Caddy HTTPS 라우팅 (`/v1`, `/v2`) | **SKIP (필수)** | Caddyfile/Caddyfile.admin에 `/v2/*` 추가를 정적으로 확인했을 뿐 reload·HTTPS 미검증 |
| 9 | Android 정식 서명 APK | **SKIP (필수)** | GitHub Secrets 기반 서명은 CI release job에서만 가능. 에뮬레이터/실기기 설치·실행도 미수행 |
| 10 | 비밀·로그 스캔 | **PASS** | 하드코딩 실제 비밀 없음(§4). `workflow.py`의 sqlite 전용 테스트 폴백 문자열, 테스트 픽스처, 문서 placeholder, gitignore된 표준 debug.keystore만 검출 |
| 11 | Android API URL 분리 | **PASS** | `__tests__/potato-api-url-split.test.ts`: 인증 4종 `/v1/auth/*`, 나머지 `/v2/rooms*`, `http://` 없음, 이중 `/v1` 없음 |

**판정: NO-GO** — 필수 SKIP(2, 3, 4, 7 실제, 8, 9)이 남아 있어 main 병합·배포 금지.

## 배포 가능 여부 판정 (실제로 확인된 근거만)

| 항목 | 상태 | 근거 |
|---|---|---|
| 서버 코드 + 마이그레이션 0001→0011 (빈 PG 16.2) | **확인됨** | 적용·롤백·재적용 통과 |
| 4인 흐름 (실 uvicorn + 별도 Worker + PG 16.2, 재시작 복구 포함) | **확인됨** | `server-api/scripts/potato_mvp_rehearsal.py` |
| **마이그레이션 0011, 실데이터 포함 경로** (PG 16.2) | **확인됨** | 실제 `/v1` API로 v1 데이터 생성 → 0004로 downgrade → head로 upgrade. 모든 행 보존, 기존 v1 토큰·계산·동의·확정 정상, 신규 컬럼 기본값 정상, Potato 방 공존 |
| Worker·API가 `DB_*` + 빈 `DATABASE_URL`(compose 방식)로 PG 접속 | **확인됨** | 위 마이그레이션된 DB에서 4인 리허설 통과 |
| 로그인 화면 로고 = 원본 | **확인됨** | APK 내 이미지가 원본과 픽셀 동일 |
| Release APK 접속 주소 | **확인됨** | `https://oranganman.site/v1` (localhost·평문 http 대상 없음) |
| 공개 `/join`을 Potato 코드로 열면 | **500 확인** | `KeyError: 'title'`. v1 코드는 200 |
| 컨테이너와 같은 순서의 클린 설치 + `deploy.sh` 테스트 게이트 | **확인됨** | 클린 venv, 락 제약 설치, 설치된 패키지로 import, 전체 테스트 242개 통과(3 SKIP) |
| Docker 이미지 빌드 자체, `docker compose config`, Caddy reload | **미확인** | 이 PC에 Docker 없음. YAML 문법만 확인 |
| 운영 DB(PG 18, 실데이터)에서의 마이그레이션 | **미확인** | 운영 접속 금지. §2-3 리허설 필요 |
| HTTPS 서버에 대한 폰 실기기 동작 | **미확인** | 실기기·실서버 없음 |
| Release APK | **빌드됨(디버그 서명)** | §6. 정식 서명은 CI 시크릿 필요 |

**결론: §2(운영 DB 복사본 리허설)와 §6(정식 서명 APK) 전에는 "배포 가능"이라고 판단할 근거가 없습니다.**
코드·구성 변경과 로컬 검증은 준비되었습니다.

## 0. 먼저 알아야 할 위험 (순서대로 읽을 것)

| # | 위험 | 근거 | 대응 |
|---|---|---|---|
| 1 | **`main`에 push하면 운영에 자동 배포**된다 | `.github/workflows/gitmain.yml` 의 `deploy` 작업: `push` + `refs/heads/main` 이면 SSH로 `infra/deploy.sh` 실행 | 이 변경은 `main`이 아닌 브랜치에서 검토하고, 배포 시점을 직접 정할 때만 `main`에 병합. 서명 APK만 필요하면 §6의 `workflow_dispatch` 사용 |
| 2 | 운영 DB의 현재 마이그레이션 위치와 데이터는 **확인된 적 없음** | 이 PC 검증은 빈 PostgreSQL **16.2**에서만 수행. 운영은 PG **18** (`infra/alembic-v21-cutover.md`) | §2의 "운영 DB 복사본 리허설"을 통과하기 전에는 배포하지 않는다 |
| 3 | Worker가 죽으면 Run이 **조용히 대기**한다 | API의 `workerDispatch`는 설정 표시일 뿐 생존을 검사하지 않음 | §7 장애 대응표, 시연 중 `docker logs backend-agent-worker` 확인 |
| 4 | `/v1/auth/register`는 이메일 인증·속도 제한 없이 누구나 가입 | 코드 확인(`user_auth.py`) | 시연 후 닫거나 제한 검토 |
| 5 | Caddy가 `/docs`, `/openapi.json`, `/metrics`를 **인터넷에 공개** | `infra/Caddyfile` 의 `@api` 목록 (기존 설정) | 시연 후 `/metrics` 등 제한 검토 |
| 6 | 공개 초대 페이지 `/join?code=`는 **v1 전용**이라 Potato 방 코드로 열면 오류가 나고 문구가 "조건부 OK" | `public_routes.py` 가 `room.config['title']` 을 조회 (Potato 방에는 없음) | 앱은 링크 대신 **코드만 공유**하도록 구현됨. 링크를 만들어 공유하지 말 것 |
| 7 | 기존 `/v1` 엔드포인트의 DB 커밋이 응답 **뒤**에 일어남 | `Depends(db_session)` (FastAPI 0.143). Potato 경로(`/v1/auth/*`, Run 생성)만 `scope="function"`으로 수정 | `/v1` 워크플로는 보존 원칙에 따라 미수정. 인지만 할 것 |
| 8 | 로컬 APK는 **디버그 키 서명** | 이 PC에 릴리스 키 없음. 실제 키는 GitHub Secrets | §6 |

## 1. 이번 준비에서 바뀐 구성 파일 (모두 원본을 `*.pre-potato.orig`로 보관)

| 파일 | 변경 | 이유 |
|---|---|---|
| `server-api/Dockerfile` | 빌드 컨텍스트를 **저장소 루트**로, `experiments/potato-agent`를 패키지로 설치, 빌드 시 import 검사 | 기존 이미지는 `potato_agent`가 없어 **API가 시작되지 못함** |
| `server-api/Dockerfile.dockerignore` (신규) | 루트 컨텍스트용 화이트리스트(`.venv`, `.env*`, `node_modules` 제외) | 컨텍스트 폭주·비밀 유입 방지 |
| `docker-compose.ai.yml` | `agent-worker`에 `.env.database`(DB 비밀) 연결 추가 | `server-api`와 같은 방식으로 Worker가 DB에 접속하도록 |
| `docker-compose.yml` | `server-api` 빌드 컨텍스트 변경, **`agent-worker` 서비스 추가**, `AGENT_WORKER_DISPATCH` 전달 | Worker가 없으면 Run이 영원히 `QUEUED` |
| `infra/Caddyfile` | `@api` 경로에 **`/v2/*` 추가** | 없으면 앱 요청이 대시보드(admin-web)로 감 |
| `infra/Caddyfile.admin` | 같은 `/v2/*` 추가 | `docker-compose.admin.yml`이 이 파일을 마운트함. 운영이 admin 오버레이를 쓰면 `/v2`가 누락되므로 |
| `server-api/requirements.txt` / `.lock` | `langgraph-checkpoint-sqlite` 추가 | `deploy.sh`와 CI가 실행하는 테스트가 필요로 함 (없으면 테스트 게이트에서 실패) |

되돌리기: 각 `*.pre-potato.orig` 를 원래 이름으로 복사.
`infra/deploy.sh`는 **수정하지 않았습니다**(검증된 안전장치 보존: DB 이름 사전검사, 백업, 컨테이너 내 테스트, 마이그레이션, 헬스체크, 이미지 롤백).
Worker는 §3에서 별도 명령으로 올립니다.

## 2. 배포 전 검증 (운영 변경 없음)

호스트에서 저장소 루트 기준. `compose` 는 `docker compose -f docker-compose.yml -f docker-compose.ai.yml` 의 약칭입니다.

1. **[읽기전용] 현재 마이그레이션 위치 확인** — *현재 운영 이미지*로 조회만:
   `compose run --rm --no-deps server-api alembic -c alembic.v21.ini current`
   결과를 기록합니다 (예: `20261101_0004`). 이 위치에서 `0011`까지 7~8개가 적용됩니다.
2. **백업 + 복원 드릴** (읽기 위주, 임시 DB만 생성/삭제): `python3 infra/backup_database.py --verify-restore`
3. **운영 DB 복사본에서 마이그레이션 리허설** (운영 DB 이름을 절대 쓰지 말 것):
   - 새 DB `potato_rehearsal` 생성 후 2번에서 만든 덤프를 복원 (`pg_restore --no-owner --no-acl -d potato_rehearsal ...`)
   - 새 이미지 빌드: `compose build server-api agent-worker`
   - `compose run --rm --no-deps -e DATABASE_URL=postgresql+psycopg://USER:PASS@172.19.0.1:5432/potato_rehearsal server-api alembic -c alembic.v21.ini upgrade head`
   - `... alembic -c alembic.v21.ini current` → `20261103_0011 (head)` 인지 확인
   - 실패하면 **배포 중단**. 오류 전문을 보관.
4. **복사본에서 v1 회귀**: 같은 `DATABASE_URL`(복사본)로 API를 임시 포트에서 띄워 기존 v1 모임 조회·참가·조건 제출·계산이 되는지 확인 (운영 DB에서 하지 말 것).
5. **복사본에서 Potato 리허설**: 임시 API와 Worker를 복사본에 붙이고 `server-api/scripts/potato_mvp_rehearsal.py --base http://127.0.0.1:<임시포트>` 실행 (스크립트는 `oranganman` 호스트를 거부합니다).
6. 컨테이너 안 테스트 게이트(= `deploy.sh`가 하는 것) 선확인:
   `compose run --rm --no-deps -e DATABASE_URL=sqlite:// -e ADMIN_ENABLED=0 server-api python -m unittest discover -s tests`

## 3. 배포 (사용자 승인 후)

1. 호스트 `.env`에 `AGENT_WORKER_DISPATCH=DB_POLLING` 추가 (선택, 표시용). **`POTATO_ALLOW_UNGATED_EXCLUSION`은 설정하지 말 것** (릴리스에서 초대자 제외 비활성 유지).
2. `bash infra/deploy.sh` — DB 이름 검사 → 백업 → 빌드 → 컨테이너 테스트 → `alembic upgrade head` → API 교체 → 헬스체크 → 실패 시 이전 이미지 복원.
3. Worker 가동: `compose up -d --no-deps --build agent-worker`
4. Caddy 설정 반영: 호스트의 `infra/Caddyfile`이 갱신된 뒤 `docker exec caddy-server caddy reload --config /etc/caddy/Caddyfile`
5. 배포 직후 점검 (읽기전용):
   - `curl -s https://oranganman.site/openapi.json | grep -c '/v2/rooms'` → 1 이상
   - `curl -i https://oranganman.site/v2/rooms` → **401 JSON** (HTML이면 Caddy 반영 안 됨)
   - `docker logs --tail 20 backend-agent-worker` → `worker potato-worker-1 starting`
   - 기존 v1: 알고 있는 기존 모임 코드로 `https://oranganman.site/join?code=<코드>` 가 열리는지

## 4. 환경변수·비밀·로그·HTTPS 점검 결과

| 항목 | 상태 | 비고 |
|---|---|---|
| DB 접속 | `DB_*` 또는 `DATABASE_URL` | Worker도 API와 **같은 값** 필요 (compose에 반영됨) |
| 마이그레이션 대상 보호 | `deploy.sh`가 `DB_NAME=potato_server_v2` 강제, 레거시 DB 거부 | 수동 `alembic` 명령에는 이 보호가 **없음** — DB 이름을 직접 확인 |
| 비밀 | `.env`, `.env.database`는 이미지·컨텍스트에서 제외 (`Dockerfile.dockerignore`) | `.env.example`은 자리표시자만 포함. compose 기본값 `DB_PASSWORD:-mashlab`은 약함 → 호스트 `.env`에 실제 값 필수 |
| 로그 | 앱은 요청 본문·토큰을 로그하지 않음(예외만). uvicorn 접근 로그는 경로를 기록 | 쿼리스트링에 토큰을 쓰지 않음(헤더 사용) |
| HTTPS | Caddy 자동 TLS (`oranganman.site`) | **APK는 평문 HTTP를 차단**(`usesCleartextTraffic=false`) — 유효한 인증서가 반드시 필요 |
| 선택 변수 | `AGENT_WORKER_*`(lease/폴링), `AGENT_CHECKPOINT_DATABASE_URL`(PG 체크포인터) | 기본(메모리 체크포인터)으로도 4인 시연 흐름은 검증됨. PG 체크포인터는 `setup()` 1회 필요 |
| 시간대 | PostgreSQL이 UTC로 반환 | 앱이 서울 시간으로 변환 (테스트 있음) |

## 5. 롤백

| 계층 | 방법 | 근거/주의 |
|---|---|---|
| API | `deploy.sh`가 헬스체크 실패 시 이전 이미지 자동 복원 | 기존 동작 |
| Worker | `compose stop agent-worker && compose rm -f agent-worker` | 중지해도 DB의 Run은 `QUEUED`로 남고 다시 켜면 이어서 처리 |
| Caddy | `infra/Caddyfile.pre-potato.orig`를 복원 후 reload | |
| **DB** | **되돌리지 않는 것을 기본으로** | 0005~0011은 **추가형**(새 테이블·기본값 있는 컬럼). 이전 API 이미지는 새 컬럼을 무시하므로 앱만 되돌려도 v1 동작 가능(빈 DB 기준 검증, 운영 데이터 기준은 §2-4에서 확인) |
| DB 강제 복구 | 백업(`/home/linuxuser/conditional-ok-backups/postgres/*.dump`)을 **새 DB 이름**으로 복원 후 `DB_NAME` 전환 | 사용자 승인 필수. 레거시 `mashpotato-server-db` 덮어쓰기 금지 |
| 마이그레이션 downgrade | `alembic -c alembic.v21.ini downgrade 20261102_0007` | PG 16.2 빈 DB에서 왕복 검증됨. **데이터가 있으면 컬럼 삭제로 정보 손실** — 승인 없이 금지 |

## 6. APK

- 로컬 테스트 빌드: `apps/mobile/android/app/build/outputs/apk/release/app-release.apk`
  — **디버그 키 서명, 배포용 아님**. 표시명·아이콘·스플래시 검증용.
- **정식 서명 APK 얻는 안전한 경로 (배포 없이)**: 변경을 GitHub에 올린 뒤 Actions에서 `Test and signed Android release`를
  **`workflow_dispatch`(수동 실행)** 로 실행. `deploy` 작업은 `main` push 에서만 돌므로 서버는 건드리지 않고,
  `release` 작업이 `ANDROID_KEYSTORE_BASE64` 등 저장된 시크릿으로 서명한 APK를 아티팩트(`conditional-ok-signed-release`)로 만듭니다.
  (단, 같은 워크플로의 `test` 작업이 먼저 통과해야 합니다.)
- 이미 설치된 앱 위에 업데이트하려면 **같은 서명 키**여야 합니다. 로컬 디버그 APK는 정식 키 앱 위에 설치되지 않으므로 먼저 삭제해야 합니다.
- 접속 서버 변경 시: 빌드 때 `CONDITIONAL_OK_API_URL=https://…/v1` (HTTPS만 허용).
- 앱 링크(`oranganman.site/join`)의 자동 검증은 서명 인증서에 묶여 있음(`assetlinks.json`). 코드 직접 입력 참가는 이와 무관하게 동작.

## 7. 4인 실제 휴대폰 시연 체크리스트

사전(시연 하루 전): §2 통과, §3 완료, 폰 4대에 APK 설치(출처 불명 앱 허용 필요, Play Protect 경고 가능), 폰 시간 자동 설정 확인.

| 단계 | 누가 | 확인 |
|---|---|---|
| 1. 가입·로그인 | 4명 각자 | 이메일 형식 아이디 + **12자 이상** 비밀번호. 인증코드 입력란이 **없고** "이메일 인증은 아직 지원하지 않아요" 안내가 보임 |
| 2. 모임 만들기 | 방장 | 이름·활동·소요시간(예 `1시간`)·장소 입력 → 가능한 시간(날짜 포함) 추가 → 완료 후 **방 화면에 8자리 코드** |
| 3. 코드 공유 | 방장 | "코드 공유"로 메신저 전송 (링크 아님) |
| 4. 코드 참가 | 나머지 3명 | 홈 → "초대 코드로 참가" → 코드·이름 입력. **후보 날짜 안에서만** 시간 입력 가능 |
| 5. 시간 제출 | 4명 | 방 화면에서 4명이 "시간 제출 완료"로 보임. 빈 시간은 제출 불가 + 안내 문구 |
| 6. 계산 | 방장 | "일정 계산하기" → 수 초 내 후보 표시. 3명 폰에도 같은 후보 표시 |
| 7. 후보 선택 | 방장 | "이 시간으로 정하기" |
| 8. 동의 | 4명 | 각자 "동의하기" → 모두 동의하면 방장에 "승인하기" |
| 9. 확정 | 방장 | "승인하기" → "최종 확정하기" → 4대 모두 "✅ 모임이 확정됐어요" + 서울 시간으로 표시 |
| 10. 확정 후 | 아무나 | 시간 수정 버튼이 사라짐(확정 이후 변경 불가) |

시연 중 서버 확인(운영자): `docker logs -f backend-agent-worker` 에 `run … finished status=ALL_AVAILABLE` 이 찍혀야 함.

### 장애 대응표

| 증상 | 가장 가능성 높은 원인 | 조치 |
|---|---|---|
| 로그인 직후 모든 화면이 "찾을 수 없어요" | Caddy에 `/v2/*` 미반영, 또는 `/v2` 미배포 서버 | `curl -i https://…/v2/rooms` 가 401 JSON인지 확인 → Caddy reload |
| "서버에 연결하지 못했어요" | 폰 네트워크/HTTPS 인증서 | 폰 브라우저로 `https://oranganman.site/openapi.json` 열림 확인 |
| "계산 중이에요…"가 30초 이상 | **Worker 정지** | `docker ps`/`docker logs backend-agent-worker` → `compose up -d --no-deps agent-worker` |
| "아직 기다리는 사람이 있어요: …" | 응답 대기/시간 미제출 | 해당 사람에게 시간 제출 요청 (자동 불참 처리 없음. 방장 제외 기능은 릴리스에서 비활성) |
| "계산할 수 없는 상태예요" | 참여자 2명 미만 또는 최소 인원 초과 | 참여자 확인 |
| "참여자나 시간이 바뀌어 이전 계산이 무효" | 계산 후 누군가 시간 수정/참가 | 방장이 "다시 계산하기" (이미 한 동의는 새 계산에서 처음부터) |
| 후보가 안 나옴(`NO_FEASIBLE`) | 공통 시간 없음 | 가능한 시간을 늘리고 다시 계산 |
| 코드 참가가 "코드를 다시 확인" | 오타(0/1/O/I 제외 문자 사용) 또는 다른 서버 | 코드 재확인 |
| 한 명만 나가야 함 | 코드 참가자는 "모임 나가기" 가능(되돌릴 수 없음) | 초대 연결 멤버는 나갈 수 없음(409) |
| 앱 설치 거부 | 서명 불일치(기존 앱) | 기존 앱 삭제 후 설치 |
