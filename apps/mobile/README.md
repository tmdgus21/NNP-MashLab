# 조건부 OK · React Native Android

다인원의 가능시간·역할·선호·동반조건을 수집하고 **서버가 반환한 담당표**를 함께 검토하는 한국어 모바일 앱입니다. Community CLI + TypeScript + npm, applicationId `com.conditionalok.app`.

## 구현
- 모임 생성 / 초대 코드 참가 → 조건 입력 → 현황 → 계산 → 동의 / 철회 / 검토요청 → 전원 동의 후 방장 확정 → 완료.
- 현황 / 내 조건 / 담당표의 React Navigation 하단 탭.
- 날짜별 30분 타임그리드: 손가락 드래그로 칠하기·지우기, 비연속 복수 구간, 00:00–24:00 지원. 접근성 활성화 동작으로 칸 선택 가능.
- 참가자별 가로 2D 타임라인 + 같은 시간대 가능 인원 수. 인원 수는 역할 충족 여부와 별도입니다.
- 역할, 이른/늦은 시간 선호, 동반자의 같은 시간 참석 가능 조건, 확인 메모.
- 자연어 입력은 독립 컴포넌트. 해석 초안을 사용자가 명시적으로 반영합니다. 메모를 자동으로 충족했다고 주장하지 않습니다.
- 변경 전 기존안/변경안 비교. 적용 시 회차 갱신, 이전 담당표 보존, 전원 동의 초기화. 서버 revision 충돌은 오류로 표시합니다.
- 로딩·빈 조건·배정불가·오류·재시도 UI. Mock 상태는 AsyncStorage에 저장됩니다.

## 환경
RN **0.87.1**, React19.2.3, Node24.18.0, JDK17, Gradle9.4.1 / AGP9.2.1.
compileSdk37 / targetSdk36 / minSdk24 / Build Tools37.0.0 / NDK27.1.12297006 / CMake3.22.1.
기존 API35, 시스템 이미지와 `ConditionalOK_API35` AVD를 유지하고 필요한 SDK만 추가했습니다.
자세한 설치 경위는 [환경 기록](docs/ENVIRONMENT.md), 근거는 [RN0.87 공식 릴리스](https://reactnative.dev/blog/2026/08/11/react-native-0.87)입니다.

## 설치와 개발 실행 (PowerShell)
```powershell
cd C:\mashlab\NNP-MashLab\apps\mobile
npm ci
npm run setup:android
& "$env:ANDROID_HOME/emulator/emulator.exe" -avd ConditionalOK_API35
npm start -- --max-workers 2
# 다른 터미널
adb -s emulator-5554 reverse tcp:8081 tcp:8081
npm run android -- --device emulator-5554
```
`JAVA_HOME`은 JDK17, `ANDROID_HOME`은 기존 Android SDK 경로입니다. 새 환경의 SDK 설치:
```powershell
& "$env:ANDROID_HOME/cmdline-tools/22.0/bin/sdkmanager.bat" 'platforms;android-37.0' 'build-tools;37.0.0' 'ndk;27.1.12297006' 'cmake;3.22.1'
```
이 환경의 `latest` SDK CLI는 내장 JRE `net.dll` 오류가 있어 기존 공식 22.0 SDK Manager를 사용했습니다.
AVD의 `10.0.2.2` 네트워크가 끊기면 개발자 메뉴 → Dev Settings → Debug server host를 `localhost:8081`로 지정하고 위 `adb reverse`를 사용하세요. API35를 다운그레이드/재생성할 필요가 없습니다.

## 테스트 및 APK
```powershell
npm run typecheck
npm test -- --runInBand
npm run lint
npm run apk:debug
adb -s emulator-5554 install -r android/app/build/outputs/apk/debug/app-debug.apk
adb -s emulator-5554 shell am start -n com.conditionalok.app/.MainActivity
npm run test:android
```
`apk:debug`는 `arm64-v8a,x86_64` 두 ABI, JS/Hermes 번들 포함, 개발 서버 연결을 끈 **독립 실행 Debug APK**를 생성합니다. 디버그 서명으로 배포용 서명이 아닙니다.
출력: `android/app/build/outputs/apk/debug/app-debug.apk`.
에뮬레이터 전용 빠른 빌드: `./scripts/build-apk.ps1 -Architectures x86_64`.
일반 `npm run android`는 `offlineBundle` 옵션 없이 빌드하므로 다시 Metro 개발 모드가 됩니다.
스크린샷·UI 계층·로그 등 로컬 검증 증거는 `.artifacts/`에 있으며 Git에서 제외합니다.

## 구조
```text
App.tsx                   앱 경계, 안전영역, 하단 탐색
src/screens/              생성/참가, 현황, 내 조건, 담당표
src/ui/                   타임그리드, 타임라인, 담당표, 자연어 입력, 공통 카드
src/domain/               구조화 JSON 스키마/타입, 시간 변환, 확정 규칙
src/data/RepositoryPort.ts 서버 계약 인터페이스
src/data/MockRepository.ts 로컬 상태/회차/합의와 데모 시나리오
src/data/mockSolver.ts     소규모 데모용 결정론적 배정 탐색
src/data/HttpRepository.ts 인증 토큰, 타임아웃, HTTP 오류, Zod 응답 검증
src/data/repositoryInstance.ts Repository 교체 지점
src/state/                Zustand 비동기 작업·로딩·오류 상태
__tests__/                시간 구간, 상태 전이, HTTP 계약, 담당표 렌더링
```

## Mock 시나리오
첫 화면의 **데모 모임 체험하기** 또는 코드 `OK2026`으로 시작합니다. 현황 하단의 **데모 시나리오 · 참가자 전환**에서 배정가능 / 시간충돌 / 역할부족 / 조건변경·재동의 / 최종확정 / 빈 조건 / 다음 조회 오류를 재현합니다.
참가자를 하나씩 전환해 담당표에 동의한 후 방장 민지로 돌아와 확정하세요. 이것은 Mock 전용이며 HTTP 모드에서는 인증된 사용자만 응답합니다.
모임은 후보 날짜 중 한 날, 지정한 시간 범위 안의 연속 활동시간을 선택하고 필요한 역할마다 1명을 배정합니다. 역할 간 동시 중복배정은 금지합니다. 동반조건은 상대방이 해당 시간에 참석 가능한지 검사하며 상대의 담당 역할까지 강제하지 않습니다.
Mock은 한 기기용입니다. 다른 기기 사이의 초대·동기화는 실제 서버 연결 후 가능합니다. 앱을 종료해도 마지막 모임은 복구됩니다. 데모 시나리오 초기화는 데모 모임만 교체합니다.

## FastAPI / Qwen / OR-Tools 연결
[API 계약](docs/API.md)을 참고해 `repositoryInstance.ts`를 `new HttpRepository(baseUrl, secureTokenProvider)`로 바꾸세요.
1. FastAPI: `/v1/meetings` 등 계약 엔드포인트, 인증·참가 권한, revision 검증, 동의/확정 트랜잭션, 세션 복원 API.
2. Qwen: `/v1/conditions/parse`에서 조건 초안과 확인질문만 반환. 모바일에서 확인 후 적용하며 최종 담당표를 생성하지 않습니다.
3. OR-Tools: 역할 자격·가능시간·중복배정·동반조건은 hard constraint, 선호는 soft objective. 최종 결과는 FastAPI가 `Plan`으로 반환합니다.
4. 비동기 계산은 `calculating`을 반환하고 조회/폴링 또는 이벤트 구독을 연결하세요. UI는 조회로 계산 상태를 갱신할 수 있습니다.
5. 운영 전 Secure Storage 기반 토큰/세션 복원, 요청 멱등성, 서버 부하 테스트와 통합 테스트, 운영 서명이 필요합니다.
현재 저장소의 `server-api/main.py`는 상태 확인 엔드포인트만 있으며 이번 작업은 그 서버를 임의 변경하지 않습니다.

## 저장소 관리와 제한
빌드 산출물, APK, `.gradle`, `.cxx`, `node_modules`, `.artifacts`, `.env`, keystore는 Git 제외. `package-lock.json`은 포함합니다. Debug 키는 `setup:android` 또는 APK 빌드 시 로컬 생성됩니다.
RN 템플릿의 AGP9 호환 플래그는 공식 권고대로 유지합니다. Zod의 ES export namespace 처리를 위해 Babel7 호환 `@babel/plugin-transform-export-namespace-from`만 추가했습니다([공식 문서](https://babeljs.io/docs/babel-plugin-transform-export-namespace-from)).
`npm audit`는 현재 RN/Metro/CLI 등 도구 체인의 전이 의존성 경고를 보고합니다. 자동 권고가 RN0.72로 다운그레이드하는 경우가 있어 `audit fix --force`는 적용하지 않았습니다. RN0.87.1을 유지하며 향후 호환 패치 릴리스를 검토해야 합니다.

## 검증 기록 (2026-10-06)
- 기존 기본 템플릿을 먼저 빌드(87 tasks)하고 ConditionalOK_API35에서 `Welcome to React Native / 0.87.1 / Hermes` 화면을 확인한 다음 기능을 구현했습니다.
- 라이브러리 추가 후 네이티브 Gradle 빌드 성공(195 tasks), 독립 실행 APK 빌드 성공(202 tasks).
- `npm run typecheck` 통과. Jest 4 suites / 23 tests 통과. ESLint 오류 0; 인라인 스타일/명시적 void 등 스타일 경고는 남아 있습니다.
- 실제 AVD: 생성/참가 진입 화면, 데모 현황, 30분 드래그 추가, 중간 칸 삭제로 구간 분리, 기존 구간 보존, 변경안 미리보기, 2차 조율, 재계산, 동의·철회·재동의, 참가자 4명 동의 후 방장 확정 확인.
- 실행 로그 `Running "ConditionalOK" ... fabric:true` 확인. 위 UI 흐름 중 AndroidRuntime / ReactNativeJS 치명 오류 없음.
- `.artifacts/baseline.png`, `overview.png`, `grid-drag-erase.png`, `preview.png`, `schedule.png`, `finalized.png`에 로컬 검증 캡처를 남겼습니다.
- APK Manifest: com.conditionalok.app, label 조건부 OK, compileSdk37, minSdk24, targetSdk36. ARM64/x86_64 및 assets/index.android.bundle 포함 확인.
