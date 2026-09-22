param(
    [string]$ToolchainRoot = 'D:\zys\myself\codex\fitness_project\research\toolchains',
    [string]$SigningKeyStore = 'D:\zys\myself\codex\fitness_project\.worktrees\local-flow\app\android\app\pr-testing-public.jks',
    [string]$SigningAlias = 'pr',
    [int]$BuildNumber = 40709
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\toolchain.ps1" -ToolchainRoot $ToolchainRoot
$projectRoot = Split-Path $PSScriptRoot -Parent
$signingPassword = $env:FITNESS_SIGNING_PASSWORD
if (!$signingPassword) { $signingPassword = 'pr-testing-public' }
New-Item -ItemType Directory -Force "$projectRoot\research\release", "$projectRoot\deliverables\candidate" | Out-Null
Push-Location "$projectRoot\app"
try {
    $extraBuildArgs = @()
    $generatedSpec = "$projectRoot\app\build\flutter\pubspec.yaml"
    if ((Test-Path -LiteralPath $generatedSpec) -and !(Test-Path -LiteralPath "$projectRoot\app\build\flutter-packages\flet_charts\pubspec.yaml")) {
        $generatedRoot = [IO.Path]::GetFullPath("$projectRoot\app\build")
        $expectedRoot = [IO.Path]::GetFullPath("$projectRoot\app") + [IO.Path]::DirectorySeparatorChar
        if (!$generatedRoot.StartsWith($expectedRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe generated build path' }
        & "$projectRoot\.venv\Scripts\flet.exe" clean "$projectRoot\app"
        if ($LASTEXITCODE -ne 0) { throw 'Cannot reset generated Flet shell' }
    }
    & "$projectRoot\.venv\Scripts\flet.exe" build apk @extraBuildArgs --arch arm64-v8a x86_64 --bundle-id com.presley.flexify.localflow --build-number $BuildNumber --build-version 2.2.0 --android-signing-key-store $SigningKeyStore --android-signing-key-alias $SigningAlias --android-signing-key-store-password $signingPassword --android-signing-key-password $signingPassword --yes --no-rich-output -vv *> "$projectRoot\research\release\build.log"
    if ($LASTEXITCODE -ne 0) { throw 'APK build failed; see research/release/build.log' }
    foreach ($abi in @('arm64-v8a','x86_64')) {
        $apk = "$projectRoot\app\build\apk\fitness-python-$abi.apk"
        & "$projectRoot\.venv\Scripts\python.exe" "$PSScriptRoot\verify-release.py" $apk 'D:\zys\myself\codex\fitness_project\.worktrees\local-flow\deliverables\fitness-local-training-arm64.apk' --build-tools "$env:ANDROID_HOME\build-tools\36.0.0" > "$projectRoot\research\release\identity-$abi.json"
        if ($LASTEXITCODE -ne 0) { throw "APK identity verification failed: $abi" }
        $previous = "D:\zys\myself\codex\fitness_project_v2.1\app\build\apk\fitness-python-$abi.apk"
        if (Test-Path -LiteralPath $previous) {
            & "$projectRoot\.venv\Scripts\python.exe" "$PSScriptRoot\verify-release.py" $apk $previous --build-tools "$env:ANDROID_HOME\build-tools\36.0.0" > "$projectRoot\research\release\upgrade-$abi.json"
            if ($LASTEXITCODE -ne 0) { throw "Python upgrade identity check failed: $abi" }
        } else { throw "Previous Python APK unavailable: $abi" }
        Copy-Item -LiteralPath $apk -Destination "$projectRoot\deliverables\candidate\fitness-python-$abi.apk"
    }
} finally { Pop-Location }
