# 서버 계약 v1

Base URL 예: Android AVD `http://10.0.2.2:8000/v1`, 운영은 HTTPS.
인증은 Bearer access token. 사용자 ID를 신뢰하지 말고 서버 인증 주체로 권한을 검사한다.
날짜는 YYYY-MM-DD, 시간은 자정부터 분(minute) 단위의 [start, end), 30분 배수, timezone은 Asia/Seoul.

| Method | Endpoint | 의미 |
| --- | --- | --- |
| POST | /meetings | 모임 생성 |
| POST | /meetings/join | 초대 코드로 참가 |
| GET | /meetings/:id | 최신 회차, 조건, 담당표, 참가자 조회 |
| POST | /meetings/:id/conditions/preview | expectedRevision과 조건을 받아 현재/변경안 및 영향 반환, 저장하지 않음 |
| PUT | /meetings/:id/conditions | 조건 적용. expectedRevision 일치 검사, 회차 증가, 기존 동의 무효화 |
| POST | /meetings/:id/calculations | 해당 회차 계산 요청, 대기 상태도 반환 가능 |
| PUT | /meetings/:id/consent | round와 agreed/pending/review, 검토요청 사유 |
| POST | /meetings/:id/finalize | 방장만, 최신 회차, 배정가능 및 전원 동의 조건을 원자적으로 검증 |
| POST | /conditions/parse | 자연어 → 구조화 조건 초안과 확인질문. 담당표 반환 불가 |

모든 변경 요청은 expectedRevision 기반 낙관적 잠금을 사용한다. 충돌은 HTTP409, 인증 실패401, 권한403, 유효성422를 반환한다.
계산이 비동기이면 GET 조회로 calculating → feasible/infeasible 상태를 갱신한다. 변경된 회차의 오래된 계산 결과는 서버에서 폐기한다.
재시도/중복 클릭에 대비해 생성 및 계산 요청은 서버에서 Idempotency-Key를 지원해야 한다.

## 책임 분리

FastAPI: 인증, 모임, 조건 검증, revision/round, 동의 및 최종확정 트랜잭션.
Qwen: 독립 자연어 조건 파서. 모호한 입력은 questions로 반환하고 사용자가 구조화 필드를 확인한다.
OR-Tools: hard constraints(역할 자격/가능시간/중복배정/동반조건)와 soft preferences를 사용한 최적화. 최종 담당표는 FastAPI가 반환한다.
모바일: 입력/미리보기/조회/동의 UX. 운영 최적화 알고리즘을 모바일에 넣지 않는다.
MockRepository: UX 검증용 작은 결정론적 배정기 및 고정 시나리오. 최적성/운영 동시성 보장 없음.

## JSON 예시

조건 변경 미리보기/적용 body (actor는 인증 토큰에서 판별):
```json
{
  "expectedRevision": 4,
  "conditions": {
    "roles": ["진행", "기록"],
    "availability": [
      {"date": "2026-10-17", "start": 600, "end": 720},
      {"date": "2026-10-17", "start": 780, "end": 900}
    ],
    "preference": "early",
    "companionId": null,
    "note": "장비 반납 시간을 별도로 확인해 주세요."
  }
}
```
서버가 반환하는 `Meeting.plan` 예시:
```json
{
  "round": 2,
  "status": "feasible",
  "assignments": [
    {"id": "2-0", "role": "진행", "participantId": "p1", "interval": {"date": "2026-10-17", "start": 660, "end": 720}, "status": "proposed"}
  ],
  "notices": [{"id": "check-1", "kind": "warning", "title": "메모 확인 필요", "detail": "자연어 메모의 미확인 조건을 검토하세요."}]
}
```
`idle / calculating / feasible / infeasible` 계산상태와 `info / warning / error` 확인카드 타입은 모든 화면에서 동일합니다.
전체 응답 타입과 런타임 스키마의 단일 기준은 `src/domain/model.ts`입니다. 생성/참가는 `{meeting, actorId}`, 조회/변경/계산/동의/확정은 `Meeting`, 미리보기는 `{revision, before, after, changes}`, 파서는 `{draft, questions, source}`를 반환합니다.
