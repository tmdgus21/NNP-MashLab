param([string]$Architectures = 'arm64-v8a,x86_64', [switch]$CreateSigningKey)
$ErrorActionPreference = 'Stop'
$mobileRoot = Split-Path $PSScriptRoot -Parent
Set-Location $mobileRoot
$secretDir = Join-Path $env:USERPROFILE '.android/conditional-ok-signing'
$secretFile = Join-Path $secretDir 'credentials.xml'
if ($CreateSigningKey -and -not (Test-Path $secretFile)) {
  New-Item -ItemType Directory -Force $secretDir | Out-Null
  $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
  & icacls.exe $secretDir /inheritance:r /grant:r "${identity}:(OI)(CI)F" | Out-Null
  if ($LASTEXITCODE -ne 0) {throw 'Cannot protect signing directory'}
  $keyPath = Join-Path $secretDir 'release.jks'
  if (Test-Path $keyPath) {throw 'Existing key found without credentials; do not overwrite'}
  $bytes = New-Object byte[] 48
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  $password = [Convert]::ToBase64String($bytes)
  $env:CONDITIONAL_OK_STORE_PASSWORD = $password
  & "$env:JAVA_HOME/bin/keytool.exe" -genkeypair -storetype JKS -keystore $keyPath -storepass:env CONDITIONAL_OK_STORE_PASSWORD -keypass:env CONDITIONAL_OK_STORE_PASSWORD -alias conditional-ok -keyalg RSA -keysize 4096 -validity 10000 -dname 'CN=Conditional OK,O=Conditional OK,C=KR'
  if ($LASTEXITCODE -ne 0) {throw 'Signing key generation failed'}
  [pscredential]::new('conditional-ok', (ConvertTo-SecureString $password -AsPlainText -Force)) | Export-Clixml $secretFile
  $password = $null
}
if (-not $env:CONDITIONAL_OK_KEYSTORE_PATH -and (Test-Path $secretFile)) {
  $credentials = Import-Clixml $secretFile
  $env:CONDITIONAL_OK_KEYSTORE_PATH = Join-Path $secretDir 'release.jks'
  $env:CONDITIONAL_OK_KEY_ALIAS = $credentials.UserName
  $env:CONDITIONAL_OK_STORE_PASSWORD = $credentials.GetNetworkCredential().Password
  $env:CONDITIONAL_OK_KEY_PASSWORD = $env:CONDITIONAL_OK_STORE_PASSWORD
}
node scripts/configure.cjs
if ($LASTEXITCODE -ne 0) {throw 'Invalid API configuration'}
& ./android/gradlew.bat -p android assembleRelease "-PreactNativeArchitectures=$Architectures" --max-workers=2 --console=plain --info '-Dorg.gradle.internal.http.connectionTimeout=30000' '-Dorg.gradle.internal.http.socketTimeout=60000'
if ($LASTEXITCODE -ne 0) {throw 'Release build failed'}
& "$env:ANDROID_HOME/build-tools/37.0.0/apksigner.bat" verify --verbose --print-certs android/app/build/outputs/apk/release/app-release.apk
if ($LASTEXITCODE -ne 0) {throw 'APK signature verification failed'}
Write-Output "APK: $mobileRoot/android/app/build/outputs/apk/release/app-release.apk"
