---
name: deploy-handoff
description: Potato Meet 변경을 운영에 내보내는 인계를 처리합니다. 배포 대상 확인, 배포 전 점검(테스트·v21 리비전·DB 이름 가드·compose 오버레이·Caddy 무변경), 배포 승인 요청 카드, 답신 대기, 승인 시 PR 본문·사용자가 실행할 명령·확인 절차 작성, 보류 시 점검 결과만 정리까지 진행합니다. Claude는 main push·deploy.sh·SSH를 하지 않습니다. "배포", "main에 올려", "운영 반영", "릴리스", "컷오버" 같은 요청이나 「승인:」「보류:」 입력에 사용합니다.
model: sonnet
---
1. 배포 대상 커밋/브랜치와 포함된 변경(R 번호, 새 리비전 ID, 앱 버전)을 정리한다.
2. 점검한다: 전체 서버 단위 테스트(sqlite) 통과, `alembic -c alembic.v21.ini heads`가 하나, 새 리비전이 추가형, `infra/deploy.sh` DB 가드 무변경, compose `-f docker-compose.ai.yml` 유지, Caddyfile 무변경, 비밀값 미포함.
3. 컷오버가 포함되면(main.py 라우터 교체, 기존 앱 제거) 영향(기존 RN 앱 동작 중단, assetlinks·APK 경로, Q12·Q13)을 따로 적는다.
4. 배포 승인 요청 카드를 보낸다: 포함 변경, 점검 결과(통과/실패), 운영 영향, 롤백 방법(이전 이미지 복구, 스키마는 유지). 「승인:」「보류:」로 답해 달라고 한다.
5. 답신을 기다린다. 점검 실패 항목이 있으면 승인을 받아도 먼저 고치자고 제안한다.
6. 「승인:」이면 PR 본문(대상 `main`)과 사용자가 실행할 절차를 작성한다: PR 병합 → Actions `test`·`deploy` 확인 → 서버에서 `alembic -c alembic.v21.ini current` 확인 → `https://oranganman.site/openapi.json` 200 확인.
7. 「보류:」이면 점검 결과와 남은 작업만 정리하고 끝낸다.
8. Claude는 main push, PR 병합, `deploy.sh` 실행, SSH 접속을 하지 않는다(훅 차단).
9. 완료 보고: PR 본문, 사용자 실행 절차, 확인할 지표, 롤백 절차.
