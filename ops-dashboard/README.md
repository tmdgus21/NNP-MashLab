# 조건부 OK Super Admin

기존 `server-api/main.py`에 라우터를 추가합니다. 별도 FastAPI 서버/DB나 운영 Mock은 없습니다. 기존 `ops-dashboard/test3.txt`, 모바일 작업, 기본 Caddy/Compose 설정은 보존했습니다. 운영 배포·운영 마이그레이션·Git push는 수행하지 않았습니다.

## 로컬 실행

1. **운영과 분리된 로컬 PostgreSQL**을 준비하고 `server-api/.env.admin.example`의 값을 프로세스 환경변수로 설정합니다. 앱은 이 파일을 자동 로드하지 않습니다. 기존 `DATABASE_URL`, `APP_SESSION_SECRET`도 로컬 값으로 설정합니다. SMTP는 STARTTLS를 지원하는 실제 SMTP 계정이 필요합니다. `ADMIN_SECRET`은 최소 32자의 암호학적 난수입니다. 저장소에 비밀값을 넣지 마세요.
2. `server-api`에서 `python -m pip install -r requirements.txt`, `python -m database`, `python migrations/003_admin.py --apply`. **선택한 로컬 DB에만** 실행합니다. 관리자 마이그레이션은 앱 시작 시 자동 실행하지 않습니다.
3. `python -m admin.cli create 관리자이메일 --role SUPER_ADMIN --reason "최초 관리자 수동 등록"`. 비밀번호는 숨김 입력으로만 받습니다. 공개 등록 API는 없습니다. 다른 관리자는 기본 `VIEWER`로 등록합니다.
4. `ADMIN_ENABLED=1`, `ADMIN_ORIGIN=https://localhost:8443`을 설정하고 기존 서버를 `uvicorn main:app --host 127.0.0.1 --port 8000`으로 실행합니다.
5. 이 디렉터리에서 `npm ci`, `npm run dev -- --port 5179`. 저장소 루트에서 설치된 Caddy로 `caddy run --config infra/Caddyfile.admin.local`. 로컬 CA 신뢰 설정 후 `https://localhost:8443` 접속. 쿠키의 Secure 설정을 낮추는 개발 우회는 없습니다.
6. `npm run build` 결과는 `ops-dashboard/dist`. 기존 운영 구성에 적용하려면 향후 검토 후에만 `docker-compose.admin.yml` 오버레이를 사용합니다. 이번 작업에서는 실행하지 않았습니다.

## 인증·권한

- `/admin-api/auth/csrf → login → verify → me/logout`. 이메일/비밀번호(Argon2id), 매번 SMTP OTP, 5분 만료·1회 사용·60초 재발송 제한. 올바른 비밀번호만으로 실패 횟수를 초기화하지 않습니다.
- 비밀번호/OTP 실패 합계 5회면 영구 동결. 다른 승인된 최고 관리자나 `python -m admin.cli unfreeze 이메일 --reason "본인 확인 후 해제"`만 해제합니다. 실패 횟수는 정상 2FA 때만 0이 됩니다. 권한 변경/동결/해제는 기존 세션과 OTP를 무효화합니다.
- 8시간 고정 만료, 세션 쿠키 `HttpOnly; Secure; SameSite=Strict; Path=/`, Max-Age/Expires 없음. 토큰은 DB에 해시 저장, 브라우저 localStorage/Refresh Token/Remember Me 없음. 새로고침은 기존 세션을 조회합니다. 브라우저의 세션 복원 기능은 종료 후 쿠키를 복원할 수 있으므로 공용 기기에서는 반드시 로그아웃해야 합니다.
- Origin+CSRF, IP 및 계정 Rate Limit, DB 서버 측 권한 검사. 기본값은 소켓 IP만 신뢰합니다. Caddy가 덮어쓰는 `X-Admin-Client-IP`를 사용하려면 **실제 Caddy 프록시의 최소 IP/CIDR**만 `ADMIN_TRUSTED_PROXY_CIDRS`에 지정합니다. 임의 전달 헤더나 모든 주소를 신뢰하지 마세요. 미설정 시 프록시 전체가 하나의 IP 한도를 공유합니다.
- SUPER_ADMIN: 계정·감사·모임 관리. OPERATOR: 모임 관리. VIEWER: 모임 조회. 모바일 토큰·API 인증은 그대로 사용하며 방장 이전 후 매 요청 DB의 현재 방장을 재검사합니다.

## API와 데이터

- `GET /admin-api/rooms`: q/state/management/start/end/sort/direction/page/size, 서버 SQL 필터·정렬·페이지네이션.
- `GET /admin-api/rooms/{id}`: 참여자, 현재 조건, 모든 제출 버전·배정·동의·확정·회차 스냅샷, 최근 100건 조치 이력.
- `POST /admin-api/rooms/{id}/actions`: disable/enable/transfer/extend/actual_end, 사유·expectedRevision 필수. 연장은 Idempotency-Key 필수. actual_end는 진행 회차의 시간대 포함 시각만 허용하며 과거 회차를 다시 열지 않습니다.
- `GET /admin-api/accounts`, `POST /admin-api/accounts/{id}/actions`: role/freeze/unfreeze. 자기 권한/동결 변경 금지. `GET /admin-api/audit?page=1`: 30건씩 조회.
- `POST /v1/meetings/{id}/extensions`: 현재 방장, 기존 revision·Bearer 인증, 새 dates/reason/Idempotency-Key. 날짜 경과 후에는 관리자 승인만 허용합니다. 기존 모바일의 주요 화면과 JSON 계약을 바꾸지 않았으므로 **모바일 연장 버튼은 별도 연결이 필요**합니다.
- 기존 `ok_rooms/members/condition_submissions/proposals/consents/room_events` 보존. 추가 테이블: `ok_admin_accounts/otps/sessions/audit/rate_limits`, `ok_room_lifecycle`, `ok_room_cycles`.
- 진행(status), 종료(state), 관리(management)를 분리. Asia/Seoul 예정일 다음 날 00:00 또는 더 늦은 실제 종료 시각. 확정 후 종료=CLOSED_CONFIRMED, 미확정=EXPIRED, 취소=CANCELLED. 개최 여부는 단정하지 않습니다.
- 60초 정기 검사와 API 만료 검사. room row lock, revision, 고유 회차·요청 키로 중복/경합 방어. 연장 시 코드·참여자·옛 기록 유지, 현재 조건·배정·동의 초기화. 기존 조건 재제출을 참석·조건 재확인으로 처리하며 **별도 참석/불참 선택 UI/API는 아직 없습니다**.
- 배포 전 기존 백업 정책으로 `pg_dump -Fc` 백업 및 별도 DB 복구 리허설을 해야 합니다. 003은 additive/idempotent이며 기존 테이블 삭제·데이터 덮어쓰기 없이 기록을 추가합니다. 되돌릴 때 ADMIN_ENABLED=0 및 기본 Caddy로 복원하고 추가 테이블을 삭제하지 않습니다.

## 검증

`server-api`에서 격리 테스트 DB를 지정하고 `python -m unittest discover -s tests -v`. 기본 SQLite 테스트에서는 SMTP/Qwen 전송 경계만 test double로 대체합니다. 실제 서비스 경로에는 대체 성공 응답이 없습니다. `ADMIN_PG_TESTS=1`은 반드시 폐기 가능한 로컬 PostgreSQL에서만 사용합니다.

웹: `npm test`, `npm run build`. 로그인 화면을 390/768/1280px에서 확인하며 label, 키보드 포커스, native dialog, 오류·빈 상태, reduced-motion을 적용했습니다. 로그인 이후 전체 브라우저 E2E·스크린리더 검증은 아직 미완료입니다.

실측 결과와 미검증 항목은 작업 최종 보고를 기준으로 확인하세요. 실제 SMTP 수신/재부팅/운영 DB 성능·동시성은 SQLite 통과로 대체할 수 없습니다.
