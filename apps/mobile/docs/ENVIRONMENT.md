# Android 환경 기록

2026-10-06 검증 대상: ConditionalOK_API35 (emulator-5554, API35 / x86_64).
기존 apps/mobile의 Community CLI 템플릿 RN0.87.1 / React19.2.3을 재사용한다.
Node24.18.0, JDK17.0.20, Gradle9.4.1, RN 플러그인 AGP9.2.1, Kotlin2.2.0.
compileSdk37 / targetSdk36 / minSdk24 / Build Tools37.0.0 / NDK27.1.12297006 / CMake3.22.1.

SDK Manager latest는 내장 JRE net.dll 오류가 있어 기존 공식 cmdline-tools/22.0/bin/sdkmanager.bat을 사용했다.
공식 저장소의 API37 패키지는 platforms;android-37.0이다. platforms;android-37은 존재하지 않는다.
기존 platforms/android-35, build-tools/36.0.0, API35 system image와 AVD는 유지했다.

설치 명령(PowerShell):
```powershell
& "$env:ANDROID_HOME/cmdline-tools/22.0/bin/sdkmanager.bat" 'platforms;android-37.0' 'build-tools;37.0.0' 'ndk;27.1.12297006' 'cmake;3.22.1'
```

기본 앱 Metro Android 번들 생성 확인: 4,103,683 bytes.
이 문서의 후속 실제 빌드/실행 검증 결과는 README 검증 항목을 참조한다.
