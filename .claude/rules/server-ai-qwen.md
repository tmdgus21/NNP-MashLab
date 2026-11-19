---
paths:
  - "server-api/schedule/ai_summary.py"
  - "server-api/schedule/coordination.py"
  - "server-api/ai_conditions.py"
---
# AI(Qwen) 규칙

- 모델: 호스트 llama.cpp `Qwen3-1.7B-Q8_0`, `127.0.0.1:8080/v1/chat/completions`. 외부 LLM API·SDK·키 금지.
- 컨테이너에서는 `QWEN_UNIX_SOCKET`(`/run/conditional-ok/qwen.sock`)으로 UDS 연결, 없으면 loopback TCP. 기존 `ai_conditions.model_client()`와 같은 방식(`trust_env=False`).
- timeout 60s(connect 3s, pool 3s) + 전체 65s. 동시 추론 1개(asyncio.Semaphore) — 바쁘면 요약 생략(조율 API는 실패시키지 않음).
- Qwen은 후보 요약 문장만 만든다. 후보·인원·확정은 `coordination.py` 결정적 코드가 정한다.
- 프롬프트에 이메일 등 개인정보 금지. 닉네임·날짜·시간·인원까지만.
- 테스트는 가짜 클라이언트. 실제 Qwen 호출 테스트를 만들지 않는다. systemd·소켓 설정(`infra/systemd/`)은 건드리지 않는다.
