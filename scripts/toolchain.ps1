param([string]$ToolchainRoot = 'D:\zys\myself\codex\fitness_project\research\toolchains')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$env:PATH = "$projectRoot\scripts\tool-shims;$env:PATH"
$env:ANDROID_HOME = Join-Path $ToolchainRoot 'android-sdk'
$env:JAVA_HOME = "D:\zys\myself\codex\fitness_project_v2.1\.cache\toolchains\java17\jdk-17.0.13+11"
$env:FLET_CACHE_DIR = "$projectRoot\.cache\flet"
$env:PUB_CACHE = "$projectRoot\.cache\pub"
$env:GRADLE_USER_HOME = "$projectRoot\.cache\gradle"
$env:PYTHONUTF8 = '1'
$env:TEMP = "$projectRoot\.cache\tmp"
$env:TMP = $env:TEMP
if (!(Test-Path "$env:ANDROID_HOME\platform-tools\adb.exe")) { throw 'Android SDK is missing' }
if (!(Test-Path "$env:JAVA_HOME\bin\java.exe")) { throw 'JDK 17 is missing' }

New-Item -ItemType Directory -Force $env:FLET_CACHE_DIR, $env:PUB_CACHE, $env:GRADLE_USER_HOME, $env:TEMP | Out-Null

# Gradle supports a read-only dependency cache alongside this project writable cache.
$env:GRADLE_RO_DEP_CACHE = "D:/zys/myself/codex/fitness_project_v2.1/.cache/gradle/caches"
