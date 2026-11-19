# Face UI ↔ Potato Meet 매핑 (origin/face @ db93eeb)

원본 보존: `apps/android/upstream/face-db93eeb/`

| 기존 화면 | PRD | 분류 | API 연동 |
|---|---|---|---|
| LoginScreen / SignUpScreen | P1 | UI 유지 · 연동 완료 | `/v1/auth/*` |
| HomeScreen | P2·P4 | UI 유지 · 연동 완료 | 목록·상세 진입·초대코드 참여·삭제(방장) |
| Create step1 | P3 | UI 유지 + 닉네임·날짜 필드 최소 추가 | `POST /meetings` (title, nickname, startDate, endDate). category/duration/location은 참고용(미전송) |
| Create step2 | R3 | UI 유지 + 초대코드 카드 | 코드/링크 표시·복사. 친구 목록 UI는 범위 밖 유지 |
| Create step3 | P5 | UI 유지 · 연동 | 추가한 시간대를 `available` 구간으로 `PUT …/response` |
| Create step4 | P6 진입 | UI 유지 | 멤버·내 시간 미리보기 후 후보 화면으로 |
| AiRecommendationScreen | P6·P7 | UI 유지 · 연동 | candidates + aiSummary + 복수 투표 |
| ResultScreen | P8 | **최소 추가**(기존 디자인 톤) | `GET …/result` |
| FriendsScreen | — | 범위 밖 · 유지 | 연동 없음 |
| MyPageScreen | — | 범위 밖 · 유지 | 닉네임 서버 저장 없음(`accounts.nickname` 없음) |
| SSE | Q10 | 연동 | `okhttp-sse` → `GET …/events`, 재연결 시 REST 재조회 |

닉네임 정책: 모임 생성·참가 시 room_members에만 저장. 계정 nickname 컬럼 추가 없음.
