# 기존 1분 코드 vs Potato Meet 30분 정책

## 요약

- **운영/레거시 workflow**: 시간 구간이 **분 단위 정수**(0–1440)로 저장·검증되며, 서버에 **30분 배수 CHECK가 없다**.
- **Potato Meet 정책**: `SLOT_MINUTES=30`, 반열린 `[start,end)`, 경계 아님 → **422**. DB CHECK로 30분을 강제하지 않고 **서비스 검증**.
- 충돌은 “DB가 30분을 막는다”가 아니라 **레거시 API/앱이 1분을 허용**하는 것과 **신규 schedule 경로가 30분을 요구**하는 것의 병행 문제다.

## 코드 쪽 (1분 허용)

| 위치 | 내용 |
|---|---|
| `workflow_models.Interval` | `start`/`end`가 분 단위 int (`ge=0..1439`, `le=1440`). 30 배수 검증 없음 |
| `CreateMeeting.duration` | `ge=1` → 1분 duration 허용 |
| `condition_available_slots` 등 | timestamptz 구간만 저장; 슬롯 크기 CHECK 없음 |
| 과거 30분 가드 | `raise HTTPException(422, "30분 단위…")` 류는 **현재 server-api에 없음**(1분 정책으로 제거된 상태) |

즉 최근 main의 “1분 단위”는 **레거시 조건부 OK/CP-SAT 경로**에 해당한다.

## 정책 쪽 (30분)

| 문서 | 내용 |
|---|---|
| `coordination-algorithm.md` | `SLOT_MINUTES=30`, 격자 하루 48칸, 후보 길이 ≥60분 |
| `data-model.md` | `schedule_response_ranges` / candidates: 30분 경계는 **서비스 검증** |
| `test-plan` T2-2 | 10:05–10:35 → 422 |

0005 초안의 `schedule_*` 테이블도 `ends_at > starts_at`만 CHECK하고, **분 모듈로 30을 강제하지 않는다**(방언·DST·naive 이슈 회피). 정합은 `schedule` 라우터에서 한다.

## 충돌 매트릭스

| 경로 | 허용 단위 | 컷오버 후 |
|---|---|---|
| 기존 `/v1/meetings` + conditions (Q13 방) | 1분 가능(현 코드) | **쓰기 409**, 조회·방장 삭제만 → 1분 입력은 사실상 동결 |
| 신규 Potato Meet `schedule_*` | 30분만 | 정책 강제 |
| 모바일 구 UI(30분 칸 문구 잔존) vs 서버 1분 | 이미 UX/서버 불일치 가능 | schedule UI는 30분 격자로 통일 |

## 권장 정리 (구현 단계)

1. **신규 경로만 30분**: `schedule` 서비스에 `assert_slot_aligned(dt, 30)` / 구간 길이·자정 분리. 레거시 `workflow_models`는 Q13 동결까지 건드리지 않거나, 쓰기를 막아 충돌 노출을 줄인다.
2. **컷오버**: `workflow_router` 제거 시 1분 허용 코드는 dead path. CP-SAT/optimizer 1분 가정은 schedule 알고리즘과 공유하지 말 것.
3. **앱**: Potato Meet 격자는 30분 고정. 레거시 방 UI는 입력 비활성(Q13).
4. **DB**: 30분 CHECK 추가하지 않음(이번 0005와 동일). 필요 시 generated column/표현식은 PostgreSQL 전용으로 후속 검토.

## 이번 2차 범위

- 모델·마이그레이션만. 서비스 검증·라우터 교체는 다음 단계.
- 운영 DB에 0005를 올리기 전에 위 경로 분리를 API 설계 승인에 포함한다.
