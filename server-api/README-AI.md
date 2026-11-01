# 조건 파싱 API 운영

`POST https://oranganman.site/ai/parse-condition`은 사용자 자연어를 조건 초안으로 변환한다. Qwen은 일정/담당표를 만들지 않으며, DB에 조건을 저장하거나 기존 방을 변경하지 않는다. 최종 배정은 향후 별도 서버 계산기(예: OR-Tools)가 담당한다. 모델의 의미 추출은 완전하지 않으므로 앱에서 확인·수정 후 제출하는 흐름을 유지한다.

## 요청과 응답

```json
{"text":"기록 역할을 선호해요. 촬영 역할은 못 해요.","meeting_date":"2026-10-17"}
```

```json
{"availability":[],"role_preferences":[{"role":"기록","strength":"preferred"}],"role_unavailable":["촬영"],"companion_requirement":[],"ambiguities":[]}
```

- `text`: 공백 제외 1~1500자. `meeting_date`: 선택적인 ISO 날짜, 상대 날짜를 추측하기 위한 기준일이 아니라 실제 모임 날짜.
- `availability`: `{date: "YYYY-MM-DD" | null, start: "HH:MM", end: "HH:MM", kind: "available" | "unavailable", strength: "required" | "preferred"}`. 시작 포함/종료 제외인 당일 구간. 자정 넘김 또는 불명확한 시작/종료는 확인 필요. 이 API는 30분 단위로 임의 반올림하지 않는다.
- `role_preferences`: `{role, strength}` 배열. `preferred`는 선호, `required`는 필수 역할.
- `role_unavailable`: 명확히 수행 불가능한 역할 이름 배열. 단순 비선호를 불가능으로 바꾸지 않는다.
- `companion_requirement`: `{person, relation: "together" | "apart", strength}` 배열. 이름은 아직 서버 참가자 ID로 연결하지 않는다.
- `ambiguities`: 모호한 시간, 날짜 누락, 충돌 등 확인할 사항. 언급 없는 조건은 빈 배열.
- 확정된 가능/불가능 진술은 `required`, 희망하는 시간대는 `preferred`. 가능은 전체 시간의 여집합이나 배정 확정을 의미하지 않는다.

모델 출력은 llama.cpp JSON schema 생성 제약과 Pydantic 검증을 모두 거친다. 추가 필드/잘못된 enum/시간/역순 구간/미완성 출력/잘못된 JSON을 거부한다. 입력에 없는 역할·사람·날짜 및 시간 표현 없는 구간 생성을 추가 거부한다. 이 검증은 모든 의미 오류를 탐지하는 보장은 아니다.

| HTTP | detail.code | 의미 |
|---|---|---|
| 422 | FastAPI validation errors | 잘못된 요청 |
| 502 | AI_INVALID_RESPONSE | JSON/schema/근거 검증 실패 |
| 503 | AI_UNAVAILABLE | 모델 연결 또는 모델 HTTP 장애 |
| 503 | AI_BUSY | 처리 중, Retry-After: 3 |
| 504 | AI_TIMEOUT | 모델 read 60초 또는 전체 65초 초과 |

## 배포 구조

기존 Caddy HTTPS -> Docker `server-api:8000` 경로는 유지한다. 호스트 Qwen은 **127.0.0.1:8080**만 리슨한다. 컨테이너의 localhost는 호스트와 다르므로 systemd Unix socket proxy를 사용한다:

FastAPI HTTPX(`http://127.0.0.1:8080/v1/chat/completions`) -> `/run/conditional-ok/qwen.sock` -> host `127.0.0.1:8080`.

소켓은 root만 사용 가능한 0600이고 현재 FastAPI 컨테이너는 root로 실행된다. `/run/conditional-ok` 디렉터리를 읽기 전용 마운트하며 socket 재생성도 보인다. 컨테이너를 non-root로 바꾸면 일치하는 전용 그룹과 socket 권한을 함께 설정해야 한다. 추가 TCP 포트, host networking, Caddy의 8080 프록시는 없다. 호스트에서 직접 FastAPI를 실행하면 `QWEN_UNIX_SOCKET`을 생략하여 loopback TCP로 연결한다.

모델은 공식 `Qwen/Qwen3-1.7B-GGUF`의 `Qwen3-1.7B-Q8_0.gguf`, revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`을 사용한다. 설치 경로는 `/home/linuxuser/models/Qwen3-1.7B-Q8_0.gguf`. 바이너리는 기존 `/home/linuxuser/.local/bin/llama` (0.6.0-dev build 11429). 최초 SSH 확인 시 기존 실행 프로세스·8080 리스너·GGUF가 없어 공식 모델을 내려받았다. 기존 수동 실행 인자는 확인하지 못했다.

```sh
sudo install -m 644 infra/systemd/conditional-ok-qwen* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now conditional-ok-qwen.service conditional-ok-qwen-proxy.socket
docker compose -f docker-compose.yml -f docker-compose.ai.yml up -d --build --no-deps server-api
systemctl status conditional-ok-qwen.service conditional-ok-qwen-proxy.socket
curl http://127.0.0.1:8080/v1/models
sudo journalctl -u conditional-ok-qwen.service -n 30 --no-pager
```

systemd 서비스는 실패 시 5초 뒤 재시작하고 부팅 시 자동 시작한다. CPU threads=4, context=8192, parallel=1, thinking off. FastAPI도 동시 추론 1개로 제한하여 대기열 누적을 피한다. 2026-10-07 최종 검증에서 실제 OS 재부팅 후 자동 복구를 확인했다. 구성 검토는 `reports/architecture-review.md`, 전체 기대/실제 JSON 및 성능 측정은 `reports/final-audit.md`를 참고한다.

모든 이후 Compose 배포에도 `-f docker-compose.ai.yml`을 포함해야 한다. GitHub Actions 배포 명령에도 반영했다. 운영 서버의 Caddyfile 및 기본 Compose(Postgres loopback 포트 포함)는 변경하지 않았다. 로컬의 기본 Compose/Caddy 설정과 운영 설정 차이는 기존 상태대로 남아 있다.

## 테스트

```sh
docker compose -f docker-compose.yml -f docker-compose.ai.yml run --rm --no-deps server-api python -m unittest discover -s tests -p test_api.py -v
python3 server-api/tests/live_korean.py https://oranganman.site
python3 server-api/tests/live_rooms.py
```

첫 명령은 모델 응답을 모킹한 계약/오류/기존 `/rooms` 회귀 검증이다. 두 번째는 실제 Qwen을 사용하는 한국어 10개 의미 검증이며 응답 본문과 시간을 출력한다. 세 번째는 실제 HTTPS 경로로 테스트용 방 1개를 만들고 기존 응답 `code`와 유효성 검사를 확인한다. 배포 직후 `/` 200으로 기동 준비를 확인한 후 실행한다.

## 변경 파일

- `server-api/ai_conditions.py`: Pydantic 모델, 한국어 prompt/examples, HTTPX 모델 호출, 검증 및 오류 처리.
- `server-api/main.py`: 원격 기존 `/rooms` 그대로 + AI router 등록. 로컬의 오래된 main.py는 원격 버전을 기준으로 동기화.
- `server-api/requirements.txt`: HTTPX 추가.
- `server-api/tests/test_api.py`, `live_korean.py`, `live_rooms.py`, `live_recovery.py`: 계약/장애/실제 추론/회귀 테스트. `live_recovery.py`는 운영 Qwen만 잠시 중단하므로 유지보수 시 명시적으로 실행한다.
- `infra/systemd/conditional-ok-qwen.service`, `conditional-ok-qwen-proxy.socket`, `conditional-ok-qwen-proxy.service`: 모델 및 로컬 연결 서비스.
- `docker-compose.ai.yml`: FastAPI에만 Unix socket 마운트/환경변수.
- `.github/workflows/gitmain.yml`: 이후 배포에서 overlay 사용.
- `server-api/.dockerignore`, `.gitignore`: 불필요한 빌드/환경/모델 파일 제외.
- `server-api/README-AI.md`: 계약, 운영, 테스트 및 제한 사항.

## 2026-10-07 검증 결과

- 단위/계약 테스트 13개 통과(한국어 출력 fixture 6개 subcase 및 timeout/JSON/모델 장애 포함).
- 실제 HTTPS -> FastAPI -> Qwen 한국어 추론 **10/10 통과**: 가능, 불가능, 역할 선호/불가, 필수 역할, 필수 동반, 선호 동반, 저녁의 모호함, 시간 선호, 3시쯤의 모호함, 복수 구간. 응답 시간 약 6~19초.
- 실제 `/rooms` 생성 201 (`code` 유지), 잘못된 입력 422, `/` 200, `/v1/models` 공개 경로 404, OpenAPI 양쪽 API 확인.
- 실제 Qwen 중단 시 AI API 503 `AI_UNAVAILABLE` 및 기존 HTTPS 200. 재시작 후 모델 목록 200 및 실제 AI 응답 200 복구. FastAPI/Caddy는 장애 테스트 중 재시작하지 않음.
- `conditional-ok-qwen.service`, `conditional-ok-qwen-proxy.socket` enabled/active, proxy service active. `ss`에서 Qwen은 `127.0.0.1:8080`만 리슨.
- 최초 배포에서는 서비스 재시작으로 확인했으며, 후속 최종 검증에서 실제 OS 재부팅 2회로 자동 복구를 확인함. 초기 프롬프트의 의미 오류는 예시를 보강한 후 위 10개 전체를 다시 실행하여 확인함.

`/rooms` 구현은 기존 메모리 저장소를 유지한다. 서버 재시작 시 방이 사라지는 기존 특성도 동일하며 Postgres 영속화는 이번 변경에 포함되지 않는다. 배포 전 원격 main.py/requirements.txt는 `/home/linuxuser/conditional-ok-backups/pre-ai/`에 보관했다. 모델 파일은 Git과 Docker 빌드에 포함하지 않는다.

참고: [공식 Qwen 모델](https://huggingface.co/Qwen/Qwen3-1.7B-GGUF/blob/90862c4b9d2787eaed51d12237eafdfe7c5f6077/Qwen3-1.7B-Q8_0.gguf), [llama.cpp Pydantic JSON schema 예제](https://github.com/ggml-org/llama.cpp/blob/master/examples/json_schema_pydantic_example.py), [HTTPX timeout](https://www.python-httpx.org/advanced/timeouts/).

## Meeting deletion (local change; requires server deployment)

`DELETE /v1/meetings/{room_id}` requires the host's Bearer session and
`{"expectedRevision": <latest revision>}`. Success returns `{"deleted": true}`.
Missing authentication returns 401; guests/other rooms return 403; stale revisions
return 409. Retrying by the same host after deletion returns the same success.
Deletion is logical: `ok_rooms.status = deleted`; historical records remain for
recovery/audit. No schema migration is required. All session/read/write/proposal
access returns 410 after deletion, and joining with its code returns 404.
This is not a personal-data erasure endpoint. The mobile app removes the saved
room session only after confirmed deletion, and handles 410 for other members.
The currently deployed server must be updated separately; do not deploy this
change without the project owner's approval.
