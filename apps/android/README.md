# Potato Meet Android (`apps/android`)

Kotlin · Jetpack Compose · Hilt · Retrofit

## Upstream UI

Team lee Compose dump from `origin/face` @ `db93eeb` is preserved under
`upstream/face-db93eeb/` and imported into `ui/face/**` without redesign.

## Configure

```bash
cp potatomeet.properties.example potatomeet.properties
# optional: API_BASE_URL=https://oranganman.site/v1
```

`local.properties` with `sdk.dir=...` is required for Gradle (Android SDK).

## Build

```bash
./gradlew ktlintCheck testDebugUnitTest assembleDebug
```

## Mapping

See `UI_MAPPING.md`.
