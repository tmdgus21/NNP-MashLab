#!/usr/bin/env bash
# 공통 함수. 모든 훅이 source 한다.
set -u

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
STATE_DIR="$PROJECT_DIR/.claude/state"
LOG_FILE="$STATE_DIR/hook.log"
mkdir -p "$STATE_DIR"

# 차단: exit 2 → Claude Code가 도구 실행을 막고 stderr를 Claude에게 전달
block() {
  echo "[HOOK] 차단: $1" >&2
  echo "[HOOK] 규칙(.claude/rules/01-workflow.md)에 따라 작업을 멈추고 사용자에게 보고하세요." >&2
  log "BLOCK $1"
  exit 2
}

log() {
  printf '%s\t%s\t%s\n' "$(date '+%F %T')" "${HOOK_NAME:-?}" "$1" >> "$LOG_FILE" 2>/dev/null || true
}

# 훅 실행 환경 점검. 실패하면 이유를 출력하고 1 반환
healthcheck() {
  command -v jq >/dev/null 2>&1 || { echo "jq가 설치되어 있지 않음"; return 1; }
  local f
  for f in session_start.sh pre_guard.sh post_check.sh lib.sh; do
    [ -f "$PROJECT_DIR/.claude/hooks/$f" ] || { echo "훅 파일 없음: $f"; return 1; }
  done
  for f in session_start.sh pre_guard.sh post_check.sh; do
    [ -x "$PROJECT_DIR/.claude/hooks/$f" ] || { echo "실행 권한 없음: $f (chmod +x 필요)"; return 1; }
  done
  [ -w "$STATE_DIR" ] || { echo "상태 폴더에 쓸 수 없음: $STATE_DIR"; return 1; }
  return 0
}

# 프로젝트 기준 상대 경로
relpath() {
  local p="$1"
  case "$p" in
    "$PROJECT_DIR"/*) echo "${p#"$PROJECT_DIR"/}" ;;
    *) echo "$p" ;;
  esac
}
