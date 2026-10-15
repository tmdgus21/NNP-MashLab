param([string]$Architectures = 'arm64-v8a,x86_64')
$ErrorActionPreference = 'Stop'
$mobileRoot = Split-Path $PSScriptRoot -Parent
Set-Location $mobileRoot
if (-not (Test-Path 'android/app/debug.keystore')) {
  & "$env:JAVA_HOME/bin/keytool.exe" -genkeypair -v -storetype JKS -keystore android/app/debug.keystore -storepass android -alias androiddebugkey -keypass android -keyalg RSA -keysize 2048 -validity 10000 -dname 'CN=Android Debug,O=Android,C=US'
  if ($LASTEXITCODE -ne 0) {throw 'Debug keystore generation failed'}
}
& ./android/gradlew.bat -p android assembleDebug -PofflineBundle "-PreactNativeArchitectures=$Architectures" --max-workers=2 --console=plain
if ($LASTEXITCODE -ne 0) {throw 'APK build failed'}
Write-Output "APK: $mobileRoot/android/app/build/outputs/apk/debug/app-debug.apk"
