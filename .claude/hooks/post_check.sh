#!/usr/bin/env bash
# PostToolUse (Edit|Write|MultiEdit): 수정된 파일 검사 → 위반 시 exit 2로 Claude에게 즉시 수정 지시
HOOK_NAME=post_check
source "$(dirname "$0")/lib.sh"

command -v jq >/dev/null 2>&1 || block "jq 없음 — 사후 검사 훅 실행 불가"

INPUT="$(cat)"
FILE="$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')"
[ -n "$FILE" ] && [ -f "$FILE" ] || exit 0
REL="$(relpath "$FILE")"
log "$REL"

PROBLEMS=()
# 주석 줄은 제외하고 패턴 검색 (최대 3줄)
has() { grep -nE -- "$1" "$FILE" | grep -vE '^[0-9]+:[[:space:]]*(//|#|\*)' | head -3; }
add() { [ -n "$2" ] && PROBLEMS+=("$1"$'\n'"$2"); }

case "$REL" in
  apps/android/*.kt|apps/android/*.kts)
    add "'!!' 사용 금지 (android-kotlin):" "$(has '!!')"
    add "GlobalScope 금지:" "$(has 'GlobalScope')"
    case "$REL" in */src/test/*|*/src/androidTest/*) ;; *) add "runBlocking 금지(테스트 제외):" "$(has 'runBlocking')" ;; esac
    case "$REL" in */domain/*)
      add "domain에 Android/Retrofit/OkHttp import 금지:" "$(has '^import (android\.|androidx\.|retrofit2\.|okhttp3\.)')" ;;
    esac
    case "$REL" in */ui/*)
      add "화면에서 Retrofit/Repository 구현 직접 사용 금지:" "$(has '^import (retrofit2\.|com\.potatomeet\.app\.data\.)')" ;;
    esac
    add "평문 HTTP 주소 금지 (HTTPS만):" "$(has '"http://')"
    if command -v ktlint >/dev/null 2>&1; then
      add "ktlint:" "$(ktlint "$FILE" 2>&1 | head -10)"
    fi
    ;;
  server-api/*.py)
    add "외부 LLM SDK 금지 — 자체 Qwen만:" "$(has '^(import|from) (openai|anthropic|google\.generativeai|cohere|langchain)')"
    add "비밀값 하드코딩 의심 — 환경 변수로:" "$(has '(postgres(ql)?(\+[a-z0-9]+)?://[^:/ ]+:[^@ ]+@|(password|secret)[[:space:]]*=[[:space:]]*["'"'"'][^"'"'"']{4,})')"
    case "$REL" in server-api/schedule/*)
      add "schedule 패키지는 기존 workflow/optimizer/ai_conditions에 의존 금지:" "$(has '^(import|from) (workflow|workflow_models|optimizer|ai_conditions)([ .]|$)')"
      add "운영 DB 이름 하드코딩 금지:" "$(has 'potato_server_v2|mashpotato-server-db')" ;;
    esac
    case "$REL" in server-api/migrations_v21/versions/*)
      grep -q 'def downgrade' "$FILE" || PROBLEMS+=("리비전에 downgrade()가 없습니다")
      grep -qE '^revision(: str)? = "[0-9]{8}_[0-9]{4}"' "$FILE" || PROBLEMS+=("리비전 ID는 YYYYMMDD_NNNN 형식이어야 합니다") ;;
    esac
    ;;
esac

# 공통: 키·토큰 패턴
add "키/토큰 하드코딩 의심:" "$(has '(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|-----BEGIN [A-Z ]*PRIVATE KEY-----|"private_key_id"[[:space:]]*:)')"

if [ ${#PROBLEMS[@]} -gt 0 ]; then
  { echo "[HOOK] $REL 규칙 위반 — 바로 고치세요:"; printf -- '- %s\n' "${PROBLEMS[@]}"; } >&2
  log "VIOLATION $REL"
  exit 2
fi

ctx() { jq -n --arg c "[HOOK] $1" '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:$c}}'; }
case "$REL" in
  server-api/db_v21/models/*)
    ctx "DB 모델이 바뀌었습니다. schema-change 스킬(리비전 생성·검토·승인·EXPECTED_TABLES·data-model.md 갱신)을 따르세요." ;;
  server-api/migrations_v21/versions/*)
    ctx "새 v21 리비전이 생성되었습니다. sqlite 테스트 통과와 upgrade/downgrade를 검토하고, 로컬 적용 전 승인을 받으세요." ;;
  apps/android/app/src/main/java/*/ui/feature/*)
    ctx "화면 코드가 바뀌었습니다. 새 페이지라면 add-screen 스킬을 따르고 PRD의 R 번호에 연결되는지 확인하세요." ;;
  server-api/schedule/router.py)
    ctx "API가 바뀌었습니다. docs/potato-meet/architecture.md API 표와 앱 DTO가 일치하는지 확인하세요." ;;
esac
exit 0
