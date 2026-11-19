#!/usr/bin/env bash
# PreToolUse (모든 도구): 훅 작동 확인 + 보호 경로 차단/확인 요청 + 위험 명령 차단
HOOK_NAME=pre_guard
source "$(dirname "$0")/lib.sh"

command -v jq >/dev/null 2>&1 || block "jq 없음 — 훅을 실행할 수 없어 작업 불가"

INPUT="$(cat)"
SESSION_ID="$(printf '%s' "$INPUT" | jq -r '.session_id // empty')"
TOOL="$(printf '%s' "$INPUT" | jq -r '.tool_name // empty')"

# 1) 원칙 2: SessionStart 훅이 통과하지 않은 세션은 어떤 도구도 실행 불가
if [ -z "$SESSION_ID" ] || [ ! -f "$STATE_DIR/session_${SESSION_ID}.ok" ]; then
  block "SessionStart 훅이 작동하지 않았거나 점검에 실패함 (session=${SESSION_ID:-없음}). 훅이 동작하지 않으면 작업을 실행할 수 없습니다."
fi
reason="$(healthcheck)" || block "훅 환경 이상: $reason"
log "$TOOL"

# 사용자 확인 요청 (차단은 아니고 승인 대화상자를 띄움)
ask() {
  log "ASK $1"
  jq -n --arg r "[HOOK] 확인 필요: $1" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$r}}'
  exit 0
}

# 2) 파일 수정 도구
case "$TOOL" in
  Edit|Write|MultiEdit|NotebookEdit)
    FILE="$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')"
    REL="$(relpath "$FILE")"
    case "$REL" in
      .claude/settings.json|.claude/settings.local.json|.claude/hooks/*)
        block "훅/설정 파일($REL)은 Claude가 수정할 수 없습니다. 변경안을 보여주고 사용자가 직접 수정하게 하세요." ;;
      */google-services.json|google-services.json|*firebase-adminsdk*.json|*fcm*credentials*.json|*service-account*.json)
        block "푸시 키 파일($REL)은 사용자가 직접 배치합니다. Claude는 만들거나 수정하지 않습니다." ;;
      .env|.env.*|*/.env|*/.env.*|*.jks|*.keystore|*/secrets/*|.secrets/*)
        case "$REL" in *.example) ;; *) block "비밀값 파일($REL) 수정 금지." ;; esac ;;
      server-api/migrations/*|server-api/alembic.ini|server-api/alembic.local.ini)
        block "v1 레거시 마이그레이션($REL)은 사용하지 않습니다. v21 체인(migrations_v21)만 다룹니다." ;;
      server-api/migrations_v21/versions/*.py)
        if [ "$TOOL" != "Write" ] || [ -e "$FILE" ]; then
          block "이미 존재하는 v21 리비전($REL)은 수정 금지. 새 리비전을 만드세요 (schema-change 스킬)."
        fi ;;
      infra/*|docker-compose*.yml|.github/*|server-api/Dockerfile|server-api/requirements*|prometheus.yml)
        ask "운영 환경 파일($REL) 변경입니다. 승인된 계획에 포함된 변경인가요?" ;;
      apps/mobile/*|server-api/workflow.py|server-api/workflow_models.py|server-api/optimizer.py|server-api/ai_conditions.py|server-api/public_routes.py)
        ask "기존 앱/API 파일($REL) 변경입니다. 컷오버 작업으로 승인되었나요?" ;;
      server-api/main.py|server-api/user_auth.py|server-api/database.py|server-api/models.py)
        ask "공용 서버 파일($REL) 변경입니다. 승인된 계획에 포함되었나요?" ;;
      server-api/db_v21/models/*)
        case "$REL" in
          server-api/db_v21/models/schedule.py|server-api/db_v21/models/__init__.py) ;;
          *) ask "기존 v21 모델($REL) 변경입니다. 재사용 테이블은 구조를 바꾸지 않는 것이 원칙입니다. 승인되었나요?" ;;
        esac ;;
    esac
    ;;
esac

# 3) Bash: 위험 명령
if [ "$TOOL" = "Bash" ]; then
  CMD="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')"
  check() { printf '%s' "$CMD" | grep -Eiq -- "$1" && block "$2"; }
  check '(^|[;&| ])rm[[:space:]]+-[a-z]*r[a-z]*[[:space:]]+(/|~|\$HOME)([[:space:]]|$)' "루트/홈 삭제 명령"
  check 'git[[:space:]]+push.*(--force|-f([[:space:]]|$))' "강제 push 금지"
  check 'git[[:space:]]+push([[:space:]].*)?[[:space:]](origin[[:space:]]+)?(HEAD:)?(refs/heads/)?main([[:space:]]|$)' "main push 금지 — main push는 운영 자동 배포입니다 (deploy-handoff 스킬)"
  check 'git[[:space:]]+(merge|rebase)[^;&|]*[[:space:]]main([[:space:]]|$)' "main 병합/리베이스는 사용자가 합니다"
  check 'git[[:space:]]+reset[[:space:]]+--hard' "git reset --hard 금지"
  check '\.claude/(hooks|settings)' "Bash로 훅/설정 파일을 건드릴 수 없습니다"
  check '(^|[;&| ])(bash|sh|source|\.)[[:space:]]+[^;&|]*deploy\.sh|(^|[;&|][[:space:]]*)(\./)?infra/deploy\.sh' "deploy.sh는 사용자가 운영 서버에서 실행합니다"
  check '(^|[;&| ])(ssh|scp|rsync)[[:space:]]' "운영 서버 원격 접속 금지"
  check 'potato_server_v2|mashpotato-server-db' "운영/레거시 DB 이름이 포함된 명령 금지 — 로컬 mashlab_v21 또는 sqlite://만"
  check 'docker[[:space:]]+compose[^;&|]*docker-compose\.ai\.yml' "운영 compose 오버레이 조작 금지 — 로컬은 docker-compose.local.yml"
  check 'alembic[^;&|]*[[:space:]](downgrade|stamp)([[:space:]]|$)' "alembic downgrade/stamp는 사용자가 직접 실행합니다"
  if printf '%s' "$CMD" | grep -Eq '(^|[;&| ])alembic([[:space:]]|$)' && ! printf '%s' "$CMD" | grep -Eq -- '-c[[:space:]]+alembic\.v21\.ini'; then
    block "alembic은 -c alembic.v21.ini로만 실행합니다 (기본 alembic.ini는 v1 레거시)"
  fi
  check 'migrations(_v21)?/versions/[^[:space:]]+\.py' "마이그레이션 파일을 Bash로 수정/삭제할 수 없습니다"
  check '(^|[;&| ])psql([[:space:]]|$)' "psql 직접 실행 금지 — 스키마는 Alembic, 조회는 사용자에게 요청"
  check '(pip|pip3|uv|poetry)[[:space:]]+(install|add)[^;&|]*(openai|anthropic|google-generativeai|cohere|langchain)' "외부 LLM SDK 설치 금지 — 자체 Qwen만 사용"
  if printf '%s' "$CMD" | sed -E 's/\.env(\.[a-z]+)*\.example//g' | grep -Eq '(cat|less|more|head|tail|bat|grep|sed|awk)[[:space:]][^;&|]*\.env(\.[a-z]+)?([[:space:]]|$)'; then
    block "비밀값 파일(.env*) 출력 금지"
  fi
  check '(cat|less|more|head|tail|bat|grep|sed|awk|jq)[[:space:]][^;&|]*(google-services\.json|firebase-adminsdk[^[:space:]]*\.json|service-account[^[:space:]]*\.json)' "푸시 키 파일 출력 금지"
fi

exit 0
