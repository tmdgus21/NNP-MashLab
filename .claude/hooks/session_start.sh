#!/usr/bin/env bash
# SessionStart: 훅 환경 점검 → 통과 시 세션 마커 생성 → 세션 컨텍스트 주입
HOOK_NAME=session_start
source "$(dirname "$0")/lib.sh"

INPUT="$(cat)"

if ! reason="$(healthcheck)"; then
  # 마커를 만들지 않으므로 이후 모든 도구 호출이 pre_guard에서 차단된다
  echo "[HOOK] 훅 환경 점검 실패: $reason — 이 세션에서는 작업을 진행할 수 없습니다. 사용자에게 보고하세요."
  log "HEALTH FAIL $reason"
  exit 0
fi

SESSION_ID="$(printf '%s' "$INPUT" | jq -r '.session_id // empty')"
[ -n "$SESSION_ID" ] || { echo "[HOOK] session_id를 읽지 못함 — 작업 불가. 사용자에게 보고하세요."; exit 0; }

touch "$STATE_DIR/session_${SESSION_ID}.ok"
find "$STATE_DIR" -name 'session_*.ok' -mtime +7 -delete 2>/dev/null || true
log "OK session=$SESSION_ID"

OPEN_Q="$(grep -cE '\| (미정|잠정) \|' "$PROJECT_DIR/docs/potato-meet/open-questions.md" 2>/dev/null || echo 0)"
BRANCH="$(git -C "$PROJECT_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
HEAD_REV="$(grep -lE '^revision' "$PROJECT_DIR"/server-api/migrations_v21/versions/*.py 2>/dev/null | xargs -r basename -a | sort | tail -1)"

BRANCH_WARN=""
[ "$BRANCH" = "main" ] && BRANCH_WARN=" ⚠ main 브랜치입니다. 커밋 전에 작업 브랜치로 옮기세요(main push = 운영 배포)."

cat <<EOF
[HOOK] 훅 정상 작동 확인 (session=$SESSION_ID, branch=$BRANCH).$BRANCH_WARN
- 범위: docs/potato-meet/PRD.md R1~R9 외 기능 금지.
- 미결정/잠정 항목 ${OPEN_Q}개: docs/potato-meet/open-questions.md — 임의 결정 금지.
- Alembic은 -c alembic.v21.ini만. 최신 리비전 파일: ${HEAD_REV:-없음}
- 코드 변경은 feature-workflow 스킬(계획 → 승인 요청 → 구현).
- 훅 차단/오류가 보이면 즉시 중단 후 보고.
EOF
exit 0
