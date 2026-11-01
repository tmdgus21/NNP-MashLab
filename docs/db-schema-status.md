# NNP-MashLab DB 스키마 현황 (정리본)

**갱신:** 2026-11-02  
**브랜치 기준:** `develop` (배포 준비 반영; `main` 미병합)  
**레거시 운영 DB:** `mashpotato-server-db` + `ok_*` (**보관, 삭제 금지**)  
**v2.1 운영 대상 DB:** `potato_server_v2` (PG 18 호스트)

---

## 1. 한눈에

| 구분 | 상태 |
|------|------|
| 앱 ORM / API | `db_v21` 이식 완료 |
| Alembic | `alembic.v21.ini` / head **`20261101_0004`** |
| `infra/deploy.sh` | **v21 마이그레이션 + `DB_NAME=potato_server_v2` 가드** |
| GitHub Actions deploy | **`main` push만** |
| `main` 병합 / 운영 재시작 | **미실행** |

---

## 2. 이중 DB (혼용 금지)

```
레거시 (유지)
  mashpotato-server-db / ok_*
  구 이미지·구 alembic.ini 경로 — 더 이상 deploy하지 않음

v2.1 (신규 운영 대상)
  potato_server_v2
  deploy.sh → alembic -c alembic.v21.ini upgrade head
  Compose DB_NAME / .env.database 필수
```

상세: [infra/alembic-v21-cutover.md](../infra/alembic-v21-cutover.md)

---

## 3. 배포 준비에서 확인한 항목

1. Dockerfile `COPY . .` + build assert (`alembic.v21.ini`, `migrations_v21`, `db_v21`)
2. deploy 마이그레이션 → `alembic.v21.ini`
3. Compose `DB_NAME` 전달 (기본값 `potato_server_v2`)
4. Actions deploy 게이트 = `push` + `refs/heads/main`
5. deploy.sh가 레거시 DB명 거부
6. 헬스 실패 시 이전 이미지 롤백 (DB DROP 없음)

---

## 4. 다음 (승인 후)

1. 호스트에 빈 `potato_server_v2` 생성
2. `.env` / `.env.database`의 `DB_NAME=potato_server_v2`
3. `develop` → `main` 병합 (별도 승인)
4. Actions deploy 또는 수동 `bash infra/deploy.sh`
5. 레거시 DB는 보관; 삭제는 별도 승인
