---
paths:
  - "infra/**"
  - "docker-compose*.yml"
  - ".github/**"
  - "server-api/Dockerfile"
  - "server-api/requirements*"
  - "prometheus.yml"
---
# 운영 환경 규칙

- 이 파일들은 운영과 직결된다. 변경은 승인 후에만(훅이 확인 요청을 띄운다).
- Caddyfile에 새 경로를 추가하지 않는다 — 새 API는 `/v1/*` 아래라 필요 없음.
- `docker-compose.ai.yml` 오버레이(Qwen 소켓, `.env.database`)를 빼지 않는다. 배포 명령은 항상 `-f docker-compose.yml -f docker-compose.ai.yml`.
- `deploy.sh`의 DB 이름 가드(`potato_server_v2`만 허용)를 약화시키지 않는다.
- CI에 Android(Kotlin) 빌드 잡을 추가할 때는 기존 RN 잡을 지우지 않고 추가(제거는 컷오버 승인 후). 서명 Secrets 이름은 기존 것 재사용.
- FCM 서비스 계정 키는 호스트 파일 → compose 읽기 전용 마운트 + `FCM_CREDENTIALS_FILE`. 키를 이미지·저장소·로그에 넣지 않는다.
- `requirements.txt`에 외부 LLM SDK 추가 금지. 알림용 `google-auth` 추가는 승인 후. 새 패키지는 `requirements.lock` 갱신 포함.
