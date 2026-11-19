---
paths:
  - "apps/android/**/*.gradle.kts"
  - "apps/android/gradle/**"
  - "apps/android/gradle.properties"
---
# Android 빌드 규칙

- 의존성 버전은 `apps/android/gradle/libs.versions.toml`에서만. build.gradle.kts에 버전 문자열 직접 쓰지 않는다.
- 새 라이브러리 추가·SDK 버전 변경은 승인 대상(이름·용도·대안 제시). 예정: `firebase-messaging`(R9), `okhttp-sse`(실시간)
- `google-services.json`은 사용자가 배치. 파일이 없어도 디버그 빌드가 되도록 하는 방법을 승인 요청에 포함.
- JDK 17 (기존 CI와 동일). ktlint 플러그인 유지.
- 릴리스 서명은 환경 변수/CI Secrets(`ANDROID_KEYSTORE_BASE64` 등 기존 이름 재사용)로만. 디버그 서명으로 릴리스를 대체하지 않는다.
- 확인: `cd apps/android && ./gradlew assembleDebug`
