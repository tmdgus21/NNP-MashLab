param([string]$Serial = 'emulator-5554', [string]$Name = 'smoke', [switch]$Install)
$ErrorActionPreference = 'Stop'
$mobileRoot = Split-Path $PSScriptRoot -Parent
$artifactRoot = Join-Path $mobileRoot '.artifacts'
New-Item -ItemType Directory -Force $artifactRoot | Out-Null
function Invoke-Adb {
  & "$env:ANDROID_HOME/platform-tools/adb.exe" -s $Serial @args
  if ($LASTEXITCODE -ne 0) { throw "adb failed: $args" }
}
if ($Install) { Invoke-Adb install -r "$mobileRoot/android/app/build/outputs/apk/debug/app-debug.apk" }
Invoke-Adb reverse tcp:8081 tcp:8081
Invoke-Adb logcat -c
Invoke-Adb shell am force-stop com.conditionalok.app
Invoke-Adb shell am start -W -n com.conditionalok.app/.MainActivity
$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
  Start-Sleep -Seconds 2
  $dump = Invoke-Adb shell uiautomator dump /sdcard/conditionalok-window.xml
  if ($dump -notmatch 'dumped') {continue}
  $xml = Invoke-Adb shell cat /sdcard/conditionalok-window.xml
  if ($xml -match 'rn_redbox|development server returned') {throw 'React Native error screen detected'}
  if ($xml -match '조건부 OK') {$ready = $true; break}
}
if (-not $ready) {throw 'The app UI did not become ready'}
Invoke-Adb shell pidof com.conditionalok.app
Invoke-Adb pull /sdcard/conditionalok-window.xml "$artifactRoot/$Name.xml"
Invoke-Adb shell screencap -p /sdcard/conditionalok-screen.png
Invoke-Adb pull /sdcard/conditionalok-screen.png "$artifactRoot/$Name.png"
$log = @(Invoke-Adb logcat -d -s AndroidRuntime:E ReactNativeJS:V ReactNative:W)
Set-Content -Encoding utf8 -Path "$artifactRoot/${Name}-logcat.log" -Value ($log -join "`n")
if ($log -match 'FATAL EXCEPTION|ReactNativeJS:.*(Error:|Invariant Violation)') {throw 'Runtime error: inspect logcat artifact'}
Write-Output "PASS: $artifactRoot/$Name.png and $Name.xml"
