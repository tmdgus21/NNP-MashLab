# 작업 흐름 규칙 (항상 로드 — paths 없음)

## 훅 (원칙 2)
- 도구 결과에 `[HOOK] 차단`, "hook error", "hook failed", 훅 스크립트 없음/권한 오류가 보이면 **즉시 작업 중단** → 어떤 훅이 어떤 메시지로 실패했는지 보고하고 지시를 기다린다.
- 훅이 "확인 요청(ask)"을 띄우면 사용자의 허락 없이 같은 변경을 다른 방법으로 시도하지 않는다.
- `.claude/settings.json`, `.claude/hooks/` 수정·삭제·chmod 금지. 바꿔야 하면 변경안을 보여주고 사용자가 직접 수정한다.

## 승인 (원칙 3)
- 코드 변경 → `feature-workflow` / 새 화면 → `add-screen` / 테이블 변경 → `schema-change` / 배포·main 병합 → `deploy-handoff`

## 문서 동기화
- 동작이 바뀌면 같은 작업 안에서 `docs/potato-meet/`를 갱신한다. 코드와 문서가 다르면 문서가 기준이며, 차이를 보고한다.
