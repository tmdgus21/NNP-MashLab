# 조건부 OK 모바일

운영 구조·서버 계약·배포·백업·서명 관리와 검증 범위는 [프로젝트 README](../../README.md)를 참고하세요.

이 디렉터리에서 `npm ci`, `npm run typecheck`, `npm test -- --runInBand`를 실행합니다. 개발은 `npm start`와 `npm run android`, 운영 APK는 `./scripts/build-release.ps1`입니다. 최초 서명키가 없는 개발 기기에서만 `-CreateSigningKey`를 사용합니다.

앱은 `CONDITIONAL_OK_API_URL`의 실제 HTTPS API만 사용합니다. 기본값은 `https://oranganman.site/v1`입니다. 운영 실패 시 Mock 데이터로 전환하지 않습니다. 테스트 전용 MockRepository는 운영 진입점에서 사용하지 않습니다.

Potato Meet 로그인·회원가입 UI는 `src/potato/PotatoAuthFlow.tsx`에서 독립적으로 제공합니다. 현재는 `PotatoAuthService`의 API 연결이 준비되지 않아 기본 서비스가 작업을 거부하며, 인증코드 발송이나 로그인·회원가입 성공으로 표시하지 않습니다. 앱 진입 연결은 개발 빌드 전용 프리뷰에 한정됩니다.

개발 빌드(`__DEV__`)에서는 앱 시작 화면이 `src/potato/PotatoMeetDevPreview.tsx`로 연결되어 로그인·회원가입, 홈·친구·마이페이지, 모임 생성 STEP 1~4 및 AI 추천 화면을 확인할 수 있습니다. 이 프리뷰는 개발 전용 샘플 데이터임을 표시하며 `AppointmentCreationDraft`를 상위 상태에서 유지합니다. AI 화면의 프리뷰 상태 선택기는 `src/potato/dev/appointmentRecommendationFixtures.ts`에 정의된 예시 상태만 표시하고 실제 추천을 계산하거나 API를 호출하지 않습니다. STEP 4에서 이동한 경우 입력 준비 결과와 draft를 유지하며, 서버 미연결 안내를 표시합니다. 릴리스에서는 기존 앱 `Content` 진입 흐름을 유지합니다.

Potato Meet 홈 UI는 `src/potato/screens/HomeScreen.tsx`에서 제공하며 일정은 `PotatoAppointment` 타입의 `date` (`YYYY-MM-DD`)를 기준으로 로컬 화면 상태에서만 관리합니다. 친구 UI는 `src/potato/screens/FriendsScreen.tsx`에서 제공하며 친구 목록·추가·삭제·선택 상태는 화면 안에서만 유지합니다. 마이페이지 UI는 `src/potato/screens/MyPageScreen.tsx`에서 제공하며 표시용 닉네임·계정 정보는 props로 받습니다. 하단 탭과 화면 이동은 콜백으로 제공하며 기존 앱 진입 흐름에는 연결하지 않습니다.

모임 생성 STEP 1 UI는 `src/potato/screens/CreateAppointmentStep1Screen.tsx`에서 제공하며, 단계 사이에 유지할 수 있는 선택적 입력값은 `AppointmentCreationDraft`로 상위 화면에서 관리합니다. 완성 일정의 `PotatoAppointment`와 달리 생성 draft에는 아직 없는 날짜·시간 정보가 선택 사항이므로 기존 완료 일정 타입은 변경하지 않습니다.

모임 생성 STEP 2 UI는 `src/potato/screens/CreateAppointmentStep2InviteScreen.tsx`에서 제공하며 친구 목록을 props로, 단계 사이 입력값과 선택 친구를 `AppointmentCreationDraft`로 받습니다. 선택의 기준은 `invitedFriendIds`이며 기존 화면 호환을 위해 `invitedFriends` 이름 목록도 함께 유지합니다. 기존 이름에서 ID를 찾을 때는 정확히 한 명만 일치하는 경우에만 변환하고, 동명이인·알 수 없는 이름은 `unresolvedInvitedFriendNames`에 남겨 추측하지 않습니다. 선택된 친구는 발송 전(`not_sent`), 응답 대기(`pending`), 시간 미제출 상태로 저장되며 실제 초대 발송이나 응답을 가장하지 않습니다. STEP 2에서 친구를 선택하지 않아도 다음 단계 이동을 요청할 수 있습니다.

모임 생성 STEP 3 UI는 `src/potato/screens/CreateAppointmentStep3TimeScreen.tsx`에서 제공하며 날짜(로컬 달력 날짜 문자열), 시작·종료 시각(자정 기준 분)을 `AppointmentCreationDraft`로 관리합니다. `mergeAppointmentTimeSlots`는 같은 날짜의 겹치거나 맞닿은 시간대를 결정적으로 병합합니다.

모임 생성 STEP 4 UI는 `src/potato/screens/CreateAppointmentStep4AdjustScreen.tsx`에서 제공하며 STEP 3의 유효 슬롯이 있는 날짜를 선택해 24시간 그래프와 정확한 시작·종료 시각을 확인합니다. 그래프 구간은 분 단위로 비례 표시하며 친구는 실제 제출 데이터에 따라 발송 전·응답 대기·시간 미제출·제출 완료로 구분합니다. 친구별 슬롯이 없는 경우 가용 시간으로 추정하지 않습니다. `appointmentParticipants.ts`는 생성자·초대 대상, 초대 발송 상태, 참여 응답, 참여자별 제출 상태를 분리하고, 제출 슬롯은 `appointmentTime.ts`의 날짜·분 단위 검증 및 병합 규칙을 사용합니다.

향후 추천 입력은 `prepareAppointmentAiRecommendation`으로 준비합니다. 소요시간은 검증된 정수 분으로 변환하고, 생성자 ID·시간대·유효 시간·수락한 참여자의 제출 시간이 부족하거나 잘못되면 `needs_information`과 누락·오류 필드를 반환합니다. 준비 완료일 때만 ID 기반 참여자, 상태, 참여자별 슬롯, 시간대, 사용자 추가 요청이 포함된 `AppointmentAiRecommendationRequest`를 반환합니다. `AiRecommendationScreen`은 에이전트 상태, 참여자 제출 상태, 검증된 후보(최대 3개), 재조율 입력 및 승인 요청을 표시합니다. 전체 참석 후보를 우선하고, `allAvailableExhausted`가 확인된 뒤에만 부분 참석 대안을 노출합니다. 후보 검증 상태·시간·필수 참석자·현재 입력 revision 중 하나라도 맞지 않으면 후보 선택과 승인 요청을 허용하지 않습니다. 승인 요청은 최종 일정 확정과 구분됩니다. `AppointmentRecommendationAgentApi`는 최초 요청, 상태 조회, 재조율, 후보 선택, 승인 요청, 재시도 및 취소의 타입 계약만 정의하며 실제 API/AI 호출은 구현하지 않았습니다.
