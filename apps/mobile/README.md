# 조건부 OK 모바일

운영 구조·서버 계약·배포·백업·서명 관리와 검증 범위는 [프로젝트 README](../../README.md)를 참고하세요.

이 디렉터리에서 `npm ci`, `npm run typecheck`, `npm test -- --runInBand`를 실행합니다. 개발은 `npm start`와 `npm run android`, 운영 APK는 `./scripts/build-release.ps1`입니다. 최초 서명키가 없는 개발 기기에서만 `-CreateSigningKey`를 사용합니다.

앱은 `CONDITIONAL_OK_API_URL`의 실제 HTTPS API만 사용합니다. 기본값은 `https://oranganman.site/v1`입니다. 운영 실패 시 Mock 데이터로 전환하지 않습니다. 테스트 전용 MockRepository는 운영 진입점에서 사용하지 않습니다.

Potato Meet 로그인·회원가입 UI는 `src/potato/PotatoAuthFlow.tsx`에서 독립적으로 제공합니다. 현재는 `PotatoAuthService`의 API 연결이 준비되지 않아 기본 서비스가 작업을 거부하며, 인증코드 발송이나 로그인·회원가입 성공으로 표시하지 않습니다. 이번 단계에서는 기존 `App.tsx` 진입 흐름에 연결하지 않습니다.

Potato Meet 홈 UI는 `src/potato/screens/HomeScreen.tsx`에서 제공하며 일정은 `PotatoAppointment` 타입의 `date` (`YYYY-MM-DD`)를 기준으로 로컬 화면 상태에서만 관리합니다. 친구 UI는 `src/potato/screens/FriendsScreen.tsx`에서 제공하며 친구 목록·추가·삭제·선택 상태는 화면 안에서만 유지합니다. 마이페이지 UI는 `src/potato/screens/MyPageScreen.tsx`에서 제공하며 표시용 닉네임·계정 정보는 props로 받습니다. 하단 탭과 화면 이동은 콜백으로 제공하며 기존 앱 진입 흐름에는 연결하지 않습니다.

모임 생성 STEP 1 UI는 `src/potato/screens/CreateAppointmentStep1Screen.tsx`에서 제공하며, 단계 사이에 유지할 수 있는 선택적 입력값은 `AppointmentCreationDraft`로 상위 화면에서 관리합니다. 완성 일정의 `PotatoAppointment`와 달리 생성 draft에는 아직 없는 날짜·시간 정보가 선택 사항이므로 기존 완료 일정 타입은 변경하지 않습니다.

모임 생성 STEP 2 UI는 `src/potato/screens/CreateAppointmentStep2InviteScreen.tsx`에서 제공하며 친구 목록을 props로, 단계 사이 입력값과 선택 친구를 `AppointmentCreationDraft`로 받습니다. STEP 2에서 친구를 선택하지 않아도 다음 단계 이동을 요청할 수 있습니다.

모임 생성 STEP 3 UI는 `src/potato/screens/CreateAppointmentStep3TimeScreen.tsx`에서 제공하며 날짜(로컬 달력 날짜 문자열), 시작·종료 시각(자정 기준 분)을 `AppointmentCreationDraft`로 관리합니다. `mergeAppointmentTimeSlots`는 같은 날짜의 겹치거나 맞닿은 시간대를 결정적으로 병합합니다.
