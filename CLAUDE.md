# CLAUDE.md — NNP-MashLab / Potato Meet

> 매 세션 자동으로 읽힌다. 프로젝트가 무엇인지, 어떤 규칙이 있는지, 모르면 어디를 봐야 하는지를 담는다.

## 1. 지금 하는 일
기존 "조건부 OK"(React Native + CP-SAT 역할 배정) 앱을 **완전히 갈아엎고**, 새 Kotlin Android 앱 **Potato Meet**을 만든다.
여러 사람이 모임 날짜 범위 안에서 가능한 시간을 입력하면, 최다 참여 가능 인원 기준으로 요일·시간을 추천하고,
후보가 2개 이상이면 중복 투표, 1개면 자동 확정한다.

서버·DB·AI·배포 **환경은 기존 것을 그대로 쓴다**. 새로 만드는 것은 앱, 새 API 라우터, 새 테이블뿐이다.

### 현재 진행 상태
- R1 로그인: **UI·DB 연결까지 완료**(기존 `/v1/auth` 사용). 남은 일: 앱에서 오는 데이터와 서버를 일관되게 맞추고 명칭을 Potato Meet로 정리
- 운영 관리자 기능: 꺼져 있음(`ADMIN_ENABLED=0`). 켜기 전 Potato Meet 데이터 기준으로 수정 필요(Q34)
- 나머지(R2~R9): 설계 완료, 구현 전
- **정책 동기화 2026-11-16** (문서만 갱신, 서버·마이그레이션 변경 없음): 상세는 `docs/potato-meet/policy-diff-20261116.md`
  - 입력 격자 **30분**(`SLOT_MINUTES=30`, 24시간, 기본 전부 가능), 모임 생성에 길이 입력 없음
  - 전원 완료 → **3분 유예** 후 자동 마감(즉시 조율 아님), 입력 중에만 참여 가능(OPEN·유예), 마감 때 완료자 2명 미만이면 **24시간 연장 1회** 후 실패
  - 후보 정렬 = 가능 인원 DESC → 길이 DESC → 시작 ASC (최다 인원만 남기지 않음), 투표는 완료자·참석 가능 후보만, 빈 투표도 완료
  - 개인정보: 입력 중 칸별 **인원 수만**, 후보 이후 후보별 닉네임. Qwen은 설명만
  - Alembic head는 여전히 `20261101_0004`. 리비전 `0005`(신규 테이블 12개 설계)는 **아직 만들지 않았다**
  - `ADMIN_ENABLED`: 하네스·운영 기준은 `0`이지만 이 PC의 로컬 `.env`는 `1`(값 변경 안 함). **승인 없이 바꾸거나 켜지 않는다**

## 2. 범위 (가장 중요)
허용 기능은 `docs/potato-meet/PRD.md`의 R1~R9뿐이다. **목록에 없는 기능·페이지는 만들지 않는다.** 애매하면 묻는다.

## 3. 저장소 지도
| 경로 | 상태 | 다루는 법 |
|---|---|---|
| `apps/android/` | **새 Kotlin 앱 (Potato Meet)** | 주 작업 대상 |
| `server-api/schedule/` | **새 API 라우터** | 주 작업 대상 |
| `server-api/db_v21/models/schedule.py` | **새 테이블 모델** | schema-change 스킬로만 |
| `server-api/migrations_v21/versions/` | v21 체인 (head `20261101_0004`) | 새 리비전만 추가, 기존 파일 수정 금지 |
| `server-api/db_v21/` 나머지, `user_auth.py`, `database.py` | 재사용 (계정·모임·멤버·가용 시간) | 수정은 승인 후 |
| `server-api/migrations/`, `alembic.ini`, `alembic.local.ini` | v1 레거시 (ok_*) | **건드리지 않음, 실행하지 않음** |
| `apps/mobile/`, `workflow.py`, `optimizer.py`, `ai_conditions.py` | 기존 앱·API | 새 앱 완성 후 제거 예정. 그 전엔 수정하지 않음 |
| `infra/`, `docker-compose*.yml`, `.github/`, `Dockerfile` | 운영 환경 | 변경은 승인 필수 (훅이 확인 요청) |
| `ops-dashboard/`, `server-api/admin/` | 운영 관리 도구 | 범위 밖 |

## 4. 환경 요약
- 도메인 `https://oranganman.site` → Caddy → `server-api:8000`(FastAPI). Caddy는 `/v1/*`, `/join*`, `/.well-known/*` 등만 API로 보낸다.
- DB: 호스트 PostgreSQL 18. 운영 DB `potato_server_v2`(v21). 레거시 `mashpotato-server-db`(보관, 손대지 않음).
- 스키마: `alembic -c alembic.v21.ini` **만** 사용.
- AI: 호스트의 Qwen3-1.7B-Q8_0 (llama.cpp, `127.0.0.1:8080`, OpenAI 호환 `/v1/chat/completions`).
  컨테이너는 Unix 소켓 `QWEN_UNIX_SOCKET=/run/conditional-ok/qwen.sock`으로 접근. 외부 LLM API·키 없음.
- 로그인: 기존 `/v1/auth` (이메일 + 비밀번호, argon2, Bearer 세션 토큰 30일).
- 푸시: FCM(Firebase Cloud Messaging). 앱 `google-services.json`과 서버 서비스 계정 키는 사용자가 직접 배치, Claude는 만들거나 읽지 않는다.
- 배포: `main` push → GitHub Actions → `infra/deploy.sh`(백업 → 테스트 → v21 마이그레이션 → API 교체). **Claude는 main에 push하지 않는다.**

## 5. 모르면 어디를 보나
| 궁금한 것 | 볼 곳 |
|---|---|
| 페이지별 화면·동작 | `docs/potato-meet/PRD.md` |
| 앱·서버 구조, API 목록 | `docs/potato-meet/architecture.md` |
| 테이블 (재사용 + 신규) | `docs/potato-meet/data-model.md` |
| 조율·추천·투표 계산 | `docs/potato-meet/coordination-algorithm.md` |
| 아직 정하지 않은 것 | `docs/potato-meet/open-questions.md` (임의 결정 금지) |
| 설치할 것·버전·환경 변수·경로 | `docs/potato-meet/environment.yaml` |
| 기존 v21 스키마 | `server-api/db_v21/README.md`, `docs/db-schema-status.md` |
| Qwen 운영 | `server-api/README-AI.md` |
| 배포·컷오버 | `infra/alembic-v21-cutover.md`, `infra/deploy.sh` |
| 코딩 규칙 | `.claude/rules/` (주제별, 해당 파일 작업 시 자동 로드) |
| 순서가 정해진 작업 | `.claude/skills/` |

## 6. 3대 원칙 (영구)
1. **Rules** — `.claude/rules/`에 주제별로. `paths:` 없으면 세션 시작 시, 있으면 일치하는 파일을 다룰 때 읽힌다.
2. **Hooks** — `.claude/settings.json`의 훅이 도구 호출 앞뒤에서 자동 실행된다.
   **훅이 동작하지 않거나 훅 오류가 보이면 즉시 모든 작업을 멈추고 보고한다.** 우회 금지.
3. **Skills** — 순서가 정해진 작업(승인 요청 → 답신 → 후처리)은 `.claude/skills/` 매뉴얼을 따른다. 명세는 `docs/potato-meet/`.

## 7. 명령
- 서버 테스트: `cd server-api && DATABASE_URL=sqlite:// ADMIN_ENABLED=0 python -m unittest discover -s tests -v`
- 로컬 DB: `docker compose -f docker-compose.local.yml up -d` (127.0.0.1:5432, mashlab/mashlab)
- 로컬 마이그레이션: `cd server-api && DATABASE_URL=postgresql+psycopg://mashlab:mashlab@127.0.0.1:5432/mashlab_v21 alembic -c alembic.v21.ini upgrade head`
- 앱: `cd apps/android && ./gradlew ktlintCheck testDebugUnitTest assembleDebug`
