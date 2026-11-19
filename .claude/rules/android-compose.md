---
paths:
  - "apps/android/app/src/main/java/**/ui/**/*.kt"
---
# Compose UI 규칙

- 화면 = `XxxRoute`(ViewModel 연결) + `XxxScreen`(stateless, @Preview). ViewModel은 `StateFlow<XxxUiState>` 1개 + 일회성 이벤트 Channel.
- 화면에서 Repository·Retrofit 직접 호출 금지. UseCase만.
- 방장 전용 UI(모임 삭제)는 `role == Role.OWNER`일 때만 컴포지션에 포함. `enabled=false`로 숨기지 않는다. 표시 문구는 "방장"/"팀원".
- 입력 화면(P5)은 24시간 × 30분 Etta 격자 한 화면, 기본값 '전부 가능' + 불가능만 표시. 중간 상태는 기기에 임시 저장, "완료" 때만 제출. 입력 마감 후·VOTING/CONFIRMED이면 읽기 전용. 입력 중 칸 상세에 타인 닉네임을 넣지 않는다(인원 수만).
- 다른 사람 정보는 닉네임으로 표시(Q37). 이메일 표시 금지.
- 날짜 선택기는 `GET /v1/time`의 서버 시각 기준(오늘 ~ 오늘+1개월). 기기 시각으로 판단하지 않는다.
- 모임 화면은 SSE 이벤트를 받으면 해당 데이터를 다시 조회한다. 연결은 화면이 보일 때만(`repeatOnLifecycle(STARTED)`).
- 로딩·빈 상태·에러 상태를 모두 그린다. 색·타이포는 `MaterialTheme`.
- 새 페이지는 `add-screen` 스킬 필수. PRD에 없는 화면 금지.
