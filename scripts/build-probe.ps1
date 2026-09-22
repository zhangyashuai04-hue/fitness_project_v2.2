param([ValidateSet("x86_64", "arm64-v8a")][string[]]$Architecture = @("arm64-v8a", "x86_64"))
$ErrorActionPreference = "Stop"
if ("arm64-v8a" -notin $Architecture) { throw "The current packaging plugin requires arm64-v8a as the primary Python dependency ABI." }
$root = Split-Path $PSScriptRoot -Parent
$env:PATH = "$root\scripts\tool-shims;$env:PATH"
$env:ANDROID_HOME = 'D:\zys\myself\codex\fitness_project\research\toolchains\android-sdk'
$env:JAVA_HOME = "$root\.cache\toolchains\java17\jdk-17.0.13+11"
$env:FLET_CACHE_DIR = "$root\.cache\flet"
$env:PUB_CACHE = "$root\.cache\pub"
$env:GRADLE_USER_HOME = "$root\.cache\gradle"
$env:PYTHONUTF8 = "1"
$env:TEMP = "$root\.cache\tmp"
$env:TMP = $env:TEMP
Push-Location "$root\spike\android_probe"
try {
    & "$root\.venv\Scripts\flet.exe" build apk --arch $Architecture --bundle-id com.localflow.pythonprobe --yes --no-rich-output -vv *> "$root\research\android-build.log"
    $result = $LASTEXITCODE
    if ($result -eq 0) { foreach ($abi in $Architecture) {
        & "$root\.venv\Scripts\python.exe" "$root\scripts\verify-apk.py" "build\apk\fitness-python-probe-$abi.apk"
        if ($LASTEXITCODE -ne 0) { $result = $LASTEXITCODE }
    }}
} finally { Pop-Location }
Get-Content "$root\research\android-build.log" -Tail 18
exit $result






