# 저장소·운영 안전 규칙 (항상 로드 — paths 없음)

- **main 브랜치에 push·merge하지 않는다.** main push = 운영 자동 배포(`.github/workflows/gitmain.yml`). 작업은 `develop` 또는 기능 브랜치.
- `infra/deploy.sh` 실행, 운영 서버 SSH 접속, 운영 docker compose 조작은 하지 않는다. 필요하면 사용자가 실행할 명령만 안내.
- DB 이름: 운영 `potato_server_v2`, 레거시 `mashpotato-server-db`. Claude는 둘 다에 접속·마이그레이션하지 않는다. 로컬 `mashlab_v21` 또는 `sqlite://`만.
- Alembic은 `-c alembic.v21.ini`만. `alembic.ini`/`alembic.local.ini`(v1, ok_*)는 실행하지 않는다.
- v1 레거시 `server-api/migrations/`는 읽지도 고치지도 않아도 된다. 참고 대상 아님.
- 기존 앱·API(`apps/mobile/`, `workflow.py`, `optimizer.py`, `ai_conditions.py`)는 컷오버 전까지 수정하지 않는다. 제거는 별도 승인.
- 비밀값(`.env*`, `.env.database`, 키스토어, `APP_SESSION_SECRET`, `ADMIN_*`)은 읽거나 출력하거나 커밋하지 않는다.
