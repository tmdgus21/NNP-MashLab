# Qwen 연결 구성 최종 검토 — 2026-10-07

| 구성 | 필요한 이유 | 중복 여부 |
|---|---|---|
| `conditional-ok-qwen.service` | 기존 호스트 llama.cpp 바이너리로 모델 1개를 실행한다. 부팅 자동 실행, 비정상 종료 재시작, 실행 사용자, 모델 경로, loopback 주소를 관리한다. | Qwen 실행 주체는 이것 하나다. Docker 안에서 별도 Qwen을 실행하지 않는다. |
| `conditional-ok-qwen-proxy.socket` | 호스트 `/run/conditional-ok/qwen.sock`을 만들고 대기한다. 접근 권한 0600(root 전용)이며 첫 연결 때 proxy service를 활성화한다. 재부팅으로 `/run`이 비워져도 다시 생성된다. | 모델을 실행하는 두 번째 서비스가 아니다. 소켓 수명과 접근 권한을 관리한다. |
| `conditional-ok-qwen-proxy.service` | systemd 기본 `systemd-socket-proxyd`가 Unix socket의 HTTP 바이트를 호스트 `127.0.0.1:8080`으로 전달한다. Docker 컨테이너의 localhost와 호스트 localhost가 서로 다르기 때문에 필요하다. | 별도 모델·API 서버가 아니다. 작은 전송 중계 프로세스이며 최초 관측 메모리는 약 1.1MiB였다. |
| `docker-compose.ai.yml` | 기존 FastAPI에 socket 경로 환경변수와 읽기 전용 디렉터리 마운트만 추가한다. 기존 Caddy/네트워크/Postgres 설정을 바꾸지 않고 Linux 운영 설정을 분리한다. | 기본 Compose를 재정의하는 전체 복사본이 아니라 작은 overlay다. 추가 공개 TCP 포트가 없다. |
| Docker `restart: unless-stopped` | 호스트 Docker가 부팅하면 기존 FastAPI/Caddy/Postgres 컨테이너가 자동 재시작한다. | 같은 컨테이너를 또 시작하는 별도 systemd 서비스를 만들지 않았다. |

경로: HTTPS:443 → Caddy → FastAPI:8000(Docker 내부) → Unix socket → host 127.0.0.1:8080 → Qwen.

**판정:** 현재 제약(기존 호스트 systemd 모델, Docker FastAPI, host 8080 loopback 전용, Caddy 유지) 안에서 기능 중복은 없다. 3개 unit은 모델 실행/소켓 관리/전송 중계라는 서로 다른 역할이다. 전체를 host network로 바꾸거나 Qwen까지 Docker로 옮기면 중계 단계를 줄일 수 있지만, 기존 격리와 배포 구조를 바꾸게 되므로 이번에는 유지한다. 임의의 Python/socat daemon을 추가하지 않고 systemd 기본 중계기를 사용한다.

운영 주의점:

- 재배포 시 기본 Compose와 AI overlay를 함께 지정한다. GitHub Actions에도 반영돼 있다.
- FastAPI가 root이므로 0600 socket을 사용할 수 있다. non-root 전환 시 전용 그룹 권한을 함께 설계한다.
- socket/proxy가 준비됐다는 것은 모델 로드 완료와 같은 뜻이 아니다. 짧은 초기 준비 구간에는 AI API가 503을 반환할 수 있다. 실제 재부팅 후 모델 목록 및 AI 추론 성공으로 복구를 판정했다.
- `unless-stopped`는 운영자가 명시적으로 중지한 컨테이너를 부팅 때 다시 켜는 정책은 아니다. 이번 검증은 실행 중인 정상 운영 상태에서 OS 재부팅했다.
- `/rooms`는 기존의 메모리 저장 방식이다. API 계약은 유지하지만 OS/API 재시작 시 방 데이터는 초기화된다.

발견 및 수정: 잘못된 모델 응답 `{"choices":[null]}` 또는 `{"choices":[[]]}`가 Pydantic 이전 단계에서 AttributeError를 일으켰다. choice가 객체인지 검증한 뒤 처리하도록 변경하여 502 `AI_INVALID_RESPONSE`를 반환한다. 오류 재현 후 수정하고 13개 단위·계약 테스트를 모두 재실행했다. 한국어 10개는 프롬프트 변경 없이 통과했으며, 최종 이미지 재부팅 뒤 반복 측정한 결과는 `final-audit.md`에 기록한다.

실제 재부팅 증거:

| 단계 | Linux boot ID | 결과 |
|---|---|---|
| 최초 검사 | `f161837c-a965-495a-92cb-c2404d8143e9` | 이전 부팅에서 운영 중 |
| 1차 OS 재부팅 | `7e67d8ff-2a19-433e-b1b2-8b91468276b2` | 모델/소켓/Docker active, Q8_0 모델 목록 200, HTTPS 200, 한국어 10/10 |
| 검증 오류 수정 후 최종 OS 재부팅 | `eaa24c2b-c22a-4d06-ba13-08ea5b691e2d` | 수동 start 없이 모델/소켓/Docker active, FastAPI/Caddy/Postgres 자동 복구, HTTPS 200 |

각 재부팅 후 `systemctl start`나 `docker compose up`을 호출하지 않고 먼저 복구 상태를 확인했다. 최종 Qwen 프로세스 PID는 972이며 socket proxy는 첫 API 요청으로 자동 활성화됐다. PostgreSQL도 healthy였다.

네트워크 및 회귀 결과:

- 서버 `ss -ltnp`: Qwen은 `127.0.0.1:8080` 단일 리스너. `0.0.0.0:8080`, `[::]:8080` 없음.
- 외부 Windows PC → DNS A 주소 `141.164.35.228:8080`: 4초 연결 timeout, 접속 불가. DNS에 AAAA 주소는 반환되지 않음. timeout 단독으로 바인딩을 단정하지 않고 서버 리스너와 함께 확인했다.
- 호스트 loopback `/v1/models`: HTTP 200, 모델 메타데이터 Q8_0 확인.
- FastAPI Docker 공개 PortBindings `{}`. Caddy는 기존 80/443만 publish. 공개 HTTPS `/v1/models`는 404.
- 최종 `/rooms`: 실제 생성 201, 응답 `code` 8자리·members·roles 계약 유지, 잘못된 요청 422. `/` 200 및 OpenAPI 양쪽 API 존재.

검증 도구 `server-api/tests/final_audit.py`는 요청 전에 정의한 전체 기대 JSON과 실제 JSON을 비교한다. 필드 누락/추가, 부정확한 강도, 환각 시간, 확인사항 내용까지 포함하므로 일부 필드만 확인하던 기존 live 검사보다 엄격하다. RAM은 프로세스 RSS를 250ms마다 측정하고 API 시간은 공개 HTTPS 전체 요청 시간으로 측정한다.

참고: [Docker restart policy 공식 문서](https://docs.docker.com/engine/containers/start-containers-automatically/).
