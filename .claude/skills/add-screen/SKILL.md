---
name: add-screen
description: Potato Meet Android 앱(apps/android) 화면 P1~P8 구현을 처리합니다. PRD 페이지·요구사항 확인, 서버 API 존재 확인, 화면 구성 승인 요청, 답신 대기, 승인 시 UseCase→API·DTO→UiState→ViewModel→Screen→Route→내비게이션→문자열 순서로 생성, 방장/팀원·상태별 노출 확인, 검증과 완료 보고까지 진행합니다. "화면 만들어줘", "페이지 추가", "P3 구현", "UI" 같은 요청이나 「승인:」「수정:」「취소:」 입력에 사용합니다.
model: sonnet
---
1. `docs/potato-meet/PRD.md`에서 P 번호와 R 번호를 찾는다. PRD에 없는 페이지면 만들지 않고 묻는다.
2. `architecture.md` API 표에서 필요한 엔드포인트를 확인하고, `server-api/schedule/router.py`에 실제로 있는지 본다. 없으면 서버 작업(feature-workflow)을 먼저 계획에 넣는다.
3. 승인 요청 카드를 보낸다: 화면 구성(PRD 그대로), UiState 필드, 이벤트, 호출 UseCase·API, 생성할 파일.
4. 답신을 기다린다. 「수정:」이면 3번으로, 「취소:」이면 무변경 종료.
5. 「승인:」이면 `apps/android/app/src/main/java/com/potatomeet/app/` 아래에 이 순서로 만든다: `domain/usecase`(+테스트) → `data/remote` API·DTO(서버 camelCase와 일치) → `ui/feature/<이름>/XxxUiState` → `XxxViewModel` → `XxxScreen`(stateless, @Preview) → `XxxRoute` → `ui/navigation` 등록 → `res/values/strings.xml`.
6. 확인한다: 방장 전용 UI는 OWNER일 때만 표시, VOTING/CONFIRMED에서 스케줄 입력 읽기 전용, 로딩·빈 상태·에러, 401→P1·409→새로고침 처리, 뒤로 가기가 PRD 흐름과 일치.
7. `cd apps/android && ./gradlew ktlintCheck testDebugUnitTest assembleDebug`로 검증한다.
8. 완료 보고: P/R 번호, 생성 파일, 내비게이션 경로, 사용한 API, 남은 미정 항목.
