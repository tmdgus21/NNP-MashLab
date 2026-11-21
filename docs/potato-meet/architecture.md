# Potato Meet 아키텍처

## 전체 구성 (기존 운영 환경 재사용)
```
[Potato Meet (Kotlin, apps/android)]
        │ HTTPS, Authorization: Bearer <계정 세션 토큰>
        ▼
https://oranganman.site ── Caddy ── server-api:8000 (FastAPI, Docker)
                                        │            │
                                        │            └─ Unix socket /run/conditional-ok/qwen.sock
                                        │                 └─ host 127.0.0.1:8080 llama.cpp Qwen3-1.7B-Q8_0
                                        ▼
                         host PostgreSQL 18 · DB potato_server_v2 (Alembic v21 체인)
```
- 앱은 API만 호출한다. Qwen·DB 주소는 앱에 없다.
- 새 엔드포인트는 모두 `/v1/` 아래 → **Caddyfile 변경 불필요**.

## 서버 (`server-api/`)
```
server-api/
├── main.py                       # 라우터 등록 (컷오버 때 workflow_router → schedule_router 교체)
├── user_auth.py                  # /v1/auth register·login(+OTP verify/resend)·me·logout, account_from_authorization()
├── mail_otp.py                   # 공통 SMTP OTP 발송 (admin·user 공유, 원문 미로그)
├── database.py                   # 재사용: session(), engine
├── db_v21/models/schedule.py     # 신규 테이블 (data-model.md)
├── migrations_v21/versions/      # 신규 리비전 20261108_0005 ~
├── schedule/                     # 신규 패키지 (workflow.py·optimizer.py·ai_conditions.py에 의존 금지)
│   ├── collection.py             # 입력 기간: 범위·제출 검증·힌트 집계·마감 판정 (순수 함수)
│   ├── router.py                 # APIRouter(prefix="/v1")
│   ├── schemas.py                # Pydantic (extra="forbid", camelCase 응답)
│   ├── deps.py                   # require_account, require_member, require_owner
│   ├── service.py                # 트랜잭션·상태 전이
│   ├── coordination.py           # 집계·후보 산출 (순수 함수)
│   ├── ai_summary.py             # Qwen 요약 클라이언트
│   └── notifications.py          # 푸시: 대상 계산·설정 확인·중복 방지·FCM 발송
└── tests/test_schedule_*.py      # unittest, DATABASE_URL=sqlite://
```
기존 관리자 기능 (Q34)
- 운영 서버는 `ADMIN_ENABLED=0`(꺼짐). 그래서 지금은 `admin.lifecycle.sweep()`이 돌지 않는다
- **환경 차이 보고(2026-11-16)**: 하네스 문서·`docker-compose.yml` 기본값·`.env.admin.example`은 `0`이지만, 이 작업 PC의 로컬 `.env`에는 `ADMIN_ENABLED=1`이 있다(값은 변경하지 않았다). 로컬 `.env`가 운영으로 배포·복사되지 않는지 확인하고, **승인 없이 이 값을 바꾸거나 켜지 않는다.** 테스트·`deploy.sh`는 `ADMIN_ENABLED=0`을 강제 지정한다
- 관리자 회차 로직(`admin/lifecycle.py`)은 기존 앱 데이터(`meeting_settings.dates`, `proposals`)를 기준으로 한다 → **Potato Meet 데이터(`rooms.ends_at`, `schedule_results`)와 일관되게 고치고, 명칭을 Potato Meet로 바꾸는 작업**이 필요하다. 관리자 기능을 다시 켜기 전에 반드시 끝낸다(승인 대상)
- 명칭 변경 범위: 사용자에게 보이는 문구·문서·초대 페이지·APK 이름. 운영 리소스 이름(`conditional-ok-*` systemd 유닛, `/run/conditional-ok` 소켓 경로, `/downloads/conditional-ok.apk`)은 운영 영향이 있어 **별도 승인·배포 계획**으로 진행

재사용할 기존 패턴
- 세션 확인: `user_auth.account_from_authorization(db, authorization)`
- DB 세션: `with session() as db, db.begin():` (요청 단위 트랜잭션)
- 동시 수정: `rooms.revision` + `expectedRevision` + `SELECT … FOR UPDATE` → 불일치 409
- 생성/참여 재시도: `Idempotency-Key` 헤더 + `room_members.request_key_hash/request_hash`
- 삭제: 물리 삭제 대신 `progress_status='deleted'`, `deleted_at` (기존 방식). 삭제 요청 30일 뒤 물리 삭제 정책(정리 배치는 미구현일 수 있음)
- Qwen 호출: `httpx.AsyncHTTPTransport(uds=QWEN_UNIX_SOCKET)`, timeout 60s(+전체 65s), 동시 1개. 조율 요청 안에서 기다리지 않고 커밋 후 백그라운드로 요약 저장
- 마감 주기 작업: `main.py` lifespan이 **항상** 60초마다 `schedule.service.sweep()` 실행(입력 유예·24h·투표 마감). `ADMIN_ENABLED=1`일 때만 기존 `admin.lifecycle.sweep`도 병행. 모임당 별도 트랜잭션·멱등(중복 sweep·동시성 안전)
- `main.py` 라우터: `schedule_router`를 workflow보다 먼저 마운트. `POST/GET/DELETE /v1/meetings*`는 본문·방 종류로 Potato Meet vs 레거시 Conditional OK에 디스패치(레거시 코드·경로 삭제 없음)

## API (신규 라우터)
| 메서드 · 경로 | 설명 | 권한 | R | 페이지 |
|---|---|---|---|---|
| `POST /v1/auth/register` | 이메일·비밀번호 → OTP challenge (계정·토큰 없음) | 공개 | R1 | P1 |
| `POST /v1/auth/register/verify` · `resend` | OTP 검증 후 계정 ACTIVE + 토큰 / 재발송 | challenge | R1 | P1 |
| `POST /v1/auth/login` | 비밀번호 검증 → OTP challenge (토큰 없음) | 공개 | R1 | P1 |
| `POST /v1/auth/login/verify` · `resend` | OTP 검증 후 토큰 / 재발송 | challenge | R1 | P1 |
| `GET /v1/auth/me` · `POST /v1/auth/logout` | 세션 조회·폐기 | Bearer | R1 | P1 |
| `GET /v1/meetings` | 내 모임 목록 | 로그인 | R2·R3 | P2 |
| `POST /v1/meetings` | 생성 `{title, nickname, selectedDates[]}` 우선(또는 하위호환 `startDate`+`endDate`). 둘 다 보내면 422. 모임 길이 없음. 날짜: 오늘~오늘+1개월(KST). `meeting_settings.selectedDates` 저장, `starts_at`/`ends_at`=min/max | 로그인 | R2 | P3 |
| `GET /v1/time` | 서버 시각 `{serverTime, timezone:"Asia/Seoul", maxEndDate}` — 앱 날짜 선택기 기준 | – | R2 | P3 |
| `POST /v1/meetings/join` | 참여 `{code, nickname}` → MEMBER. **입력 OPEN 또는 3분 유예 중에만**(Q14). 입력 마감·후보 계산 시작 이후·투표·확정·진행 중·지난 모임·조율 불가·기존 앱 모임·삭제는 **409**. 유예 중 참여는 `grace_until` 취소 | 로그인 | R3 | P4 |
| `GET /v1/meetings/{id}` | 상세 + 멤버 + 상태 | 멤버 | R3 | P4 |
| `DELETE /v1/meetings/{id}` | 삭제 `{expectedRevision}` | **OWNER** | R8 | P4 |
| `GET /v1/meetings/{id}/collection` | 현재 입력 기간: 범위, 마감 시각, 완료 k/N, `mySubmitted`, `myAvailable`(전체 불가능이면 [] + submitted true), **칸별 가능 인원 수(30분 단위, 멤버 식별자 없음)**, `graceUntil`, 재조정이면 **`nearMisses`(조금만 늘리면 되는 구간, 인원 수만)** | 멤버 | R4·R5 | P5 |
| `PUT /v1/meetings/{id}/collections/{collectionId}/response` | 내 입력 제출·수정 `{available:[{start,end}], allUnavailable?}`. `available=[]` + `allUnavailable` 없음/false → 기존처럼 남은 scope 전체 가능. `allUnavailable=true` + `available=[]` → 전체 불가능(빈 ranges 저장). 둘 다 범위 있으면 422. `available` 최대 1000. 30분 경계. **처음** 전원 완료(≥2)로 전이될 때만 `grace_until=now+3분`. 유예 중 재제출은 내용만 저장·**유예 시각 유지**. 유예/`closes_at` 중 먼저 도래한 쪽으로 마감 → 완료자 ≥2면 조율 | 멤버, OPEN(유예 포함)·마감 전. 기존 앱 모임은 409 | R4·R5 | P5 |
| `GET /v1/meetings/{id}/candidates` | 최신 후보(정렬: 인원 DESC→길이 DESC→시작 ASC) + **후보별 가능 멤버 닉네임** + 득표 수 + 마감 시각 + AI 요약 | 멤버 | R6·R7 | P6·P7 |
| `PUT /v1/meetings/{id}/votes/me` | 중복 투표 `{candidateIds}` (빈 배열 = 빈 투표, 완료로 셈). 검증: 완료자만(403), 본인이 가능한 후보만(422), VOTING·마감 전(409) | 멤버(그 조율 완료자), VOTING | R7 | P7 |
| `GET /v1/meetings/{id}/result` | 확정 결과 | 멤버 | R7 | P8 |
| `GET /v1/meetings/{id}/events` | **실시간 이벤트 스트림 (SSE)** | 멤버 | R3~R7 | P4~P8 |
| `PUT /v1/devices/me` · `DELETE /v1/devices/me` | 푸시 토큰 등록·해제 `{token}` | 로그인 | R9 | – |
| `GET` · `PUT /v1/notification-settings` | 알림 on/off `{start, remind, extend}` | 로그인 | R9 | P9 |
| `GET /join?code=` · `/.well-known/assetlinks.json` | **기존 그대로** (패키지·서명 갱신 필요) | – | R3 | 초대 |

## 부하 테스트 (Q36) — JMeter
- 모임 인원 상한 `MAX_MEMBERS`는 **부하 테스트 결과로 정하는 설정값**(환경 변수). 결정 전에는 코드에 숫자를 박지 않는다
- 시나리오(예정): 동시 로그인 / 모임 참여 / 입력 제출 동시 폭주(전원 완료 → 유예 → 조율) / SSE 동시 연결 수 / 투표 동시 제출 / 60초 주기 작업 중 요청
- 대상: 로컬 또는 별도 스테이징. **운영 서버 대상 부하 테스트는 사용자 승인·실행**
- JMeter 계획 파일(`tests/load/*.jmx`)은 저장소에 두되 운영 주소·계정을 넣지 않는다

에러 본문은 기존과 같이 `{"detail": ...}`. 401 미로그인 · 403 방장 아님/투표 대상자 아님 · 404 멤버 아님/없음 · 409 상태·revision 충돌(참여 잠금 포함) · 422 경계(30분)·범위·투표 후보 자격 위반 · 503 `AI_BUSY`.

## 조율 순서 (마감 → 계산)
- 제출 → 전원 완료로 **전이**될 때만 `grace_until` 설정 → **3분 유예**(재제출로 연장하지 않음) → `close_collection_if_due`(멱등, 행 잠금) → 조율. `closes_at`이 더 빠르면 데드라인 우선
- 신규 참가로 전원 완료 깨짐 → 유예 취소. 다시 전원 완료 → 새 3분
- 마감 후 완료자 < 2: 1회 24시간 연장(`rooms.ends_at` 상한) → 그래도 < 2면 조율 불가. 수동 시작 API 없음
- 후보: 구간 전체 교집합 인원, 같은 집합의 최대 구간만, 정렬 인원 DESC→길이 DESC→시작 ASC (`coordination-algorithm.md` §4)
- Qwen은 설명(요약)만. 후보 산출·정렬·확정은 `coordination.py`/`service.py`(결정적 코드)

## 기존 조건부 OK 데이터 (Q13)
- 목록·상세 조회 유지. 방장(`OWNER` + 현재 계정으로 식별 가능)만 `DELETE`
- schedule 입력·투표·재조율·join 변경 API는 거부(409). 자동 마이그레이션·일괄 삭제 없음
- **지난 모임(Q39)과 혼동 금지**. 계정 미연결 OWNER 삭제는 구현 전 보고 대상

## DTO 규칙 (30분)
- 시간 필드는 모두 ISO 8601 `+09:00`, **30분 경계**, 반열린 `[start, end)`. 앱 격자도 `SLOT_MINUTES=30`
- 입력 중 응답에는 칸별 `count`만(멤버 식별자 금지). 후보 응답부터 `memberNicknames`
- 투표 요청은 검증 후에만 저장(자격·후보 소속). 확정 후 모든 변경 409

## 실시간 갱신 (Q10) — SSE
- 방식: Server-Sent Events. `GET /v1/meetings/{id}/events`, `Accept: text/event-stream`, `Authorization: Bearer`
  - `/v1/*` 경로라 Caddy 설정 변경 없음 (Caddy reverse_proxy는 event-stream을 버퍼링 없이 흘려보냄)
  - 15초마다 `: ping` 주석으로 연결 유지
- 이벤트 (본문은 최소 정보, 앱은 받으면 해당 API를 다시 조회):
  `member_joined`, `response_submitted`, `collection_closed`, `collection_opened`, `coordinated`, `ai_summary_ready`, `readjust_opened`, `grace_started`, `voting_started`, `vote_updated`, `voting_closed`, `confirmed`, `meeting_deleted`
  - 형식: `event: <이름>\ndata: {"meetingId":"…","revision":N}\n\n`
- 서버 구현: `schedule/events.py`에 프로세스 내 브로드캐스터(room별 asyncio.Queue 구독자). **DB 커밋 이후에만** 발행
  - 현재 컨테이너는 uvicorn 단일 프로세스(Dockerfile CMD에 --workers 없음)라 프로세스 내 방식으로 충분
  - 워커를 늘리면 PostgreSQL LISTEN/NOTIFY로 바꿔야 함 → 그때 승인 받아 변경
- 이벤트를 놓쳐도 되는 구조: 재연결·앱 복귀 시 전체 재조회, `revision`으로 오래된 응답 무시
- 앱: OkHttp SSE(`okhttp-sse`, 새 라이브러리 → 승인 대상), 화면이 보일 때만 연결(`repeatOnLifecycle(STARTED)`), 끊기면 1s→2s→…최대 30s 재연결

## 푸시 알림 (R9) — FCM
- 앱: Firebase Cloud Messaging(`firebase-messaging`). 로그인 후 토큰을 `PUT /v1/devices/me`로 등록, 토큰 갱신 시 재등록, 로그아웃 시 `DELETE`
  - `apps/android/app/google-services.json`은 **사용자가 직접 넣는다**(Claude 작성·출력 금지, 훅 차단)
- 서버: FCM HTTP v1 API를 `httpx`로 직접 호출(firebase-admin SDK 없이), OAuth 토큰은 `google-auth`로 서비스 계정에서 발급
  - 서비스 계정 키 JSON은 호스트 파일 → `docker-compose.ai.yml`에서 읽기 전용 마운트, 경로는 `FCM_CREDENTIALS_FILE` (compose·requirements 변경은 승인 필요)
  - 키가 없으면 알림만 비활성(경고 로그), 나머지 기능은 정상
- 발송은 커밋 이후 백그라운드. 임박 알림은 60초 주기 작업(`schedule.service.sweep()`)이 `notification_log`로 중복 없이 처리
- 본문에 이메일 등 개인정보 금지. 모임명·시간·인원만. 탭하면 `potatomeet://meetings/{id}` 딥링크

## 앱 (`apps/android/`)
```
apps/android/
├── settings.gradle.kts  build.gradle.kts  gradle/libs.versions.toml
└── app/src/main/java/com/potatomeet/app/
    ├── PotatoMeetApp.kt  MainActivity.kt         # Hilt, NavHost, App Links(/join)
    ├── core/                                      # Result, 날짜(Asia/Seoul), 토큰 저장소
    ├── domain/{model,usecase,repository}
    ├── data/{remote,repository,di}                # Retrofit + OkHttp + kotlinx.serialization
    └── ui/{navigation,theme,feature/...}
```
- Kotlin, Jetpack Compose(Material3), Navigation Compose, Hilt, Coroutines/Flow
- 앱 이름 `Potato Meet`, applicationId `com.potatomeet.app` (Q11)
- API 주소는 `BuildConfig.API_BASE_URL` (기본 `https://oranganman.site/v1`, HTTPS만)
- 토큰은 Android Keystore 기반 암호화 저장 (기존 앱과 같은 원칙)
- 릴리스 서명은 CI Secrets/로컬 환경 변수로만. 저장소에 키 파일 금지

| 페이지 | 패키지 `ui/feature/` | R |
|---|---|---|
| P1 | auth | R1 |
| P2 | meetinglist | R2·R3 |
| P3 | createmeeting | R2 |
| P4 | meetingdetail | R3·R8 |
| P5 | availability (24시간 × 30분 격자, Etta 스타일 한 화면) | R4 |
| P6 | coordination | R5·R6 |
| P7 | vote | R7 |
| P8 | result | R7 |
| P9 | notificationsettings (P2의 하단 시트) | R9 |

## 컷오버 (기존 앱 → Potato Meet)
1. `schedule` 라우터·테이블·앱을 `develop`에서 완성 (기존 `/v1/meetings` 경로와 겹치므로 main.py 등록은 마지막에)
2. 한 번의 승인된 변경으로 main.py에서 `workflow_router` 제거 + `schedule_router` 등록. **기존 방 행은 유지**(Q13: 조회+방장 삭제만)
3. 이후 `apps/mobile`, `workflow.py`, `optimizer.py`, `ai_conditions.py` 제거는 별도 승인(데이터 DROP 아님)
4. 배포는 `deploy-handoff` 스킬 → 사용자가 main 병합
