param(
    [string]$ToolchainRoot = 'D:\zys\myself\codex\fitness_project\research\toolchains',
    [string]$SigningKeyStore = 'D:\zys\myself\codex\fitness_project\.worktrees\local-flow\app\android\app\pr-testing-public.jks',
    [string]$SigningAlias = 'pr',
    [int]$BuildNumber = 40708
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\toolchain.ps1" -ToolchainRoot $ToolchainRoot
$projectRoot = Split-Path $PSScriptRoot -Parent
$signingPassword = $env:FITNESS_SIGNING_PASSWORD
if (!$signingPassword) { $signingPassword = 'pr-testing-public' }
New-Item -ItemType Directory -Force "$projectRoot\research\release", "$projectRoot\deliverables\candidate" | Out-Null
Push-Location "$projectRoot\app"
try {
    & "$projectRoot\.venv\Scripts\flet.exe" build apk --arch arm64-v8a x86_64 --bundle-id com.presley.flexify.localflow --build-number $BuildNumber --build-version 2.2.0 --android-signing-key-store $SigningKeyStore --android-signing-key-alias $SigningAlias --android-signing-key-store-password $signingPassword --android-signing-key-password $signingPassword --yes --no-rich-output *> "$projectRoot\research\release\build.log"
    if ($LASTEXITCODE -ne 0) { throw 'APK build failed; see research/release/build.log' }
    foreach ($abi in @('arm64-v8a','x86_64')) {
        $apk = "$projectRoot\app\build\apk\fitness-python-$abi.apk"
        & "$projectRoot\.venv\Scripts\python.exe" "$PSScriptRoot\verify-release.py" $apk 'D:\zys\myself\codex\fitness_project\.worktrees\local-flow\deliverables\fitness-local-training-arm64.apk' --build-tools "$env:ANDROID_HOME\build-tools\36.0.0" > "$projectRoot\research\release\identity-$abi.json"
        if ($LASTEXITCODE -ne 0) { throw "APK identity verification failed: $abi" }
        Copy-Item -LiteralPath $apk -Destination "$projectRoot\deliverables\candidate\fitness-python-$abi.apk"
    }
} finally { Pop-Location }
