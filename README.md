# 조건부 OK 운영 서비스

React Native Community CLI + TypeScript 모바일 앱과 PostgreSQL/FastAPI 서비스입니다. 운영 앱의 Repository는 HTTPS HttpRepository 하나만 사용하며 실패를 Mock 성공으로 바꾸지 않습니다. MockRepository와 fixtures는 단위 테스트용으로만 남아 있고 앱 진입점에서 참조하지 않습니다.

## 데이터와 권한

- `POST /v1/meetings`: 닉네임으로 생성, 8자리 `code`와 서버 발급 bearer 세션 반환. 앱의 `roomCode`는 HttpRepository에서 명시적으로 매핑합니다.
- `POST /v1/meetings/join`: 코드와 닉네임으로 일반 참여. 코드로 방장 권한을 얻을 수 없습니다.
- `GET /v1/session`, `GET /v1/meetings/{id}`: 인증 세션 복원/현황.
- `POST /v1/meetings/{id}/conditions/parse`: 실제 Qwen 초안. 원문/모델 출력/앱 초안을 별도 저장하며 제출하지 않습니다.
- `POST .../conditions/preview`, `PUT .../conditions`: 사용자 확정 조건의 미리보기와 새 버전 저장.
- `POST .../calculations`: 방장만 CP-SAT 계산. OPTIMAL/FEASIBLE/INFEASIBLE/UNKNOWN을 구분합니다.
- `PUT .../consent`: 자기 동의/철회/검토 요청. 현재 round만 허용합니다.
- `POST .../finalize`: 방장, 최신 조건 버전, 전원 현재 회차 동의를 서버가 검증합니다.
- `GET .../proposals`: 회차별 담당표 이력.
- 기존 `/rooms`, `/rooms/join`, `/ai/parse-condition`, `/metrics` 유지.
- `/join?code=...`: QR/카카오 초대 웹 페이지. `/downloads/conditional-ok.apk`: 운영 APK. assetlinks는 서명 인증서와 연결합니다.

세션 토큰은 서버에서 SHA-256 해시로, 앱에서는 Android Keystore를 사용하는 react-native-keychain으로 보관합니다. 생성/참가의 Idempotency-Key를 기기에 보관하여 네트워크 재시도 시 같은 세션을 복원합니다. 다른 변경은 expectedRevision + PostgreSQL 행 잠금으로 충돌을 409 처리합니다. 앱 재설치로 키가 사라진 경우 닉네임만으로 기존 identity를 복구하지 않습니다.

DB: `ok_rooms`, `ok_members`, `ok_ai_drafts`, `ok_condition_submissions`, `ok_proposals`, `ok_consents`, `ok_room_events`, `ok_schema_versions`. `python database.py`는 advisory lock 안에서 버전 1~2의 추가형 마이그레이션을 적용하며 기존 데이터를 삭제하지 않습니다.

CP-SAT은 후보 중 하나의 공통 활동 시간 구간을 선택하고 역할별 인원을 배정합니다. 가능/불가 시간, 역할 capability/unavailable/required, 필요 인원, 필수 동행을 hard constraint로 처리합니다. 선호 시간/역할/동행은 soft objective입니다. 여러 교대 근무가 이어지는 별도 shift 모델은 현재 지원 범위가 아닙니다.

## 모바일 실행/테스트/서명 APK

Node22.13+/24.3+, JDK17, SDK37.0, Build Tools37.0.0, NDK27.1.12297006, CMake3.22.1. 기존 ConditionalOK_API35 AVD를 사용합니다.

```powershell
cd apps/mobile
npm ci
$env:CONDITIONAL_OK_API_URL='https://oranganman.site/v1'
npm run typecheck
npm test -- --runInBand
npm start
# 별도 터미널
npm run android
# 최초 운영 서명키 생성 및 빌드
./scripts/build-release.ps1 -CreateSigningKey
# 이후 같은 키로 빌드
./scripts/build-release.ps1
```

생성된 API 설정 파일은 Git에서 제외하며 configure 스크립트는 HTTPS만 허용합니다. Release는 서명 환경변수가 없으면 실패합니다. 디버그 서명으로 대체하지 않습니다. 로컬 서명키는 사용자 홈 `.android/conditional-ok-signing`에 사용자 전용 ACL로 저장하고 암호는 Windows DPAPI로 보호합니다. 이 디렉터리는 Git에 포함하지 않습니다. 별도 안전한 키 백업은 운영자가 관리해야 합니다.

GitHub Actions는 PR에서 TypeScript/Jest/Python 테스트를 실행하고 main push 또는 수동 실행에서 서명 Release APK를 artifact로 제공합니다. 저장소 Secrets: ANDROID_KEYSTORE_BASE64, ANDROID_STORE_PASSWORD, ANDROID_KEY_ALIAS, ANDROID_KEY_PASSWORD. 비밀값은 코드와 로그에 넣지 않습니다. 서버 배포는 `infra/deploy.sh`를 사용하며 PR에서 자동으로 운영 서버를 변경하지 않습니다.

## 서버 운영

기존 서버의 기본 docker-compose.yml, Caddyfile과 모니터링을 보존합니다. docker-compose.ai.yml만 추가하여 FastAPI에 DB 환경파일과 Qwen Unix socket 및 APK 읽기 전용 마운트를 제공합니다. `.env.database`는 0600이며 DB_USER/DB_PASSWORD/DB_NAME/APP_SESSION_SECRET를 포함합니다. APP_SESSION_SECRET는 재시도 세션 복구에 사용하므로 안정적으로 유지합니다.

```sh
cd /home/linuxuser/projects/NNP-MashLab
bash infra/deploy.sh
python3 infra/backup_database.py --verify-restore
# 실제 테스트 모임을 생성하는 명시적 통합 테스트
docker exec backend-api python tests/live_service.py
```

배포는 백업→이미지 빌드→21개 이상 단위 테스트→추가형 마이그레이션→FastAPI만 교체→상태 확인 순서입니다. 실패 시 이전 이미지로 복구하며 DB schema를 파괴적으로 되돌리지 않습니다. Caddy/DB/Qwen은 재생성하지 않습니다.

Qwen3-1.7B Q8_0은 기존 systemd 서비스를 유지합니다. 127.0.0.1:8080만 수신합니다. socket/proxy는 Docker의 별도 loopback에서 호스트 모델에 접근하도록 하는 로컬 Unix socket 다리이며 Caddy에 모델 포트를 공개하지 않습니다. AI는 조건만 추출하며 스케줄은 OR-Tools가 생성합니다.

매일 systemd timer로 PostgreSQL custom-format dump와 세션 비밀 환경파일을 0600으로 `/home/linuxuser/conditional-ok-backups/postgres`에 저장하고 14일 보관합니다. 복원 검증은 임시 DB를 만들어 실제 restore 후 그 DB만 삭제합니다. 현재 백업은 같은 서버에 있으므로 별도 서버/스토리지의 암호화된 off-site 백업은 추가 운영 작업입니다.

검증 기록: `server-api/reports/production-live.json`. 실제 테스트 결과와 APK 설치 검증은 최종 보고를 기준으로 하며 과거 Mock/Debug 검증과 구분합니다.
