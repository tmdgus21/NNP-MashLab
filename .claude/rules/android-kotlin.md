---
paths:
  - "apps/android/**/*.kt"
  - "apps/android/**/*.kts"
---
# Kotlin 규칙 (Potato Meet)

- 패키지 루트 `com.potatomeet.app`. 레이어: `ui` → `domain` → `data`. domain은 Android·Retrofit·OkHttp import 금지.
- `!!` 금지. `GlobalScope` 금지. `runBlocking`은 테스트에서만. ViewModel은 `viewModelScope`, 그 외는 주입된 Dispatcher.
- 시간은 `java.time`, 시간대는 `ZoneId.of("Asia/Seoul")` 상수 하나(`core/time`). **30분** 단위(`SLOT_MINUTES = 30`) 계산은 그 상수·유틸만 사용. 시간 선택 UI는 30분 칸만 허용.
- 네트워크: Retrofit 인터페이스 `data/remote`, DTO는 kotlinx.serialization(`@SerialName`으로 서버 camelCase와 일치). 호출은 Repository에서만.
- 에러는 `core.Result`로 반환, UI는 UiState.error로 표현. 401은 세션 만료 이벤트로 P1 이동, 409는 새로고침 안내.
- API 주소는 `BuildConfig.API_BASE_URL`(HTTPS만). 토큰은 Keystore 기반 암호화 저장소. 하드코딩된 토큰·키·비밀번호 금지(훅 검사).
- 사용자에게 보이는 문자열은 `strings.xml`(한국어). 앱 이름 `Potato Meet`.
