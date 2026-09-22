param(
    [string]$Serial = 'emulator-5560',
    [Parameter(Mandatory=$true)][string]$Apk,
    [string]$Sdk = 'D:\zys\myself\codex\fitness_project\research\toolchains\android-sdk'
)
$ErrorActionPreference = 'Stop'
$adb = Join-Path $Sdk 'platform-tools\adb.exe'
$evidence = Join-Path (Split-Path $PSScriptRoot -Parent) 'research\release'
New-Item -ItemType Directory -Force $evidence | Out-Null
$devices = & $adb devices
if (!($devices -match "$Serial\s+device")) { throw 'Isolated emulator is not ready' }
& $adb -s $Serial shell dumpsys package com.presley.flexify.localflow > "$evidence\package-before.txt"
& $adb -s $Serial install -r $Apk > "$evidence\install.txt"
if ($LASTEXITCODE -ne 0) { throw 'Cover installation failed; app was not uninstalled' }
& $adb -s $Serial shell am force-stop com.presley.flexify.localflow
& $adb -s $Serial shell monkey -p com.presley.flexify.localflow -c android.intent.category.LAUNCHER 1
& $adb -s $Serial shell dumpsys package com.presley.flexify.localflow > "$evidence\package-after.txt"
Write-Output 'Cover installation completed. UI/data acceptance remains a separate check.'
