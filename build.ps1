param(
    [switch]$SkipNative,
    [string]$OutputFolder='dist',
    [string]$Python='python',
    [string]$Zig='zig'
)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$runtime = Join-Path $taskRoot 'runtime'
$destination = [System.IO.Path]::GetFullPath((Join-Path $taskRoot $OutputFolder))
$buildWorkspace = [System.IO.Path]::GetFullPath($taskRoot).TrimEnd('\') + '\'
if (!$destination.StartsWith($buildWorkspace,[System.StringComparison]::OrdinalIgnoreCase)) { throw 'Build destination must stay inside the app workspace.' }
foreach ($userData in @('skins.json','skins','imports','cache','logs','installations')) {
    if (Test-Path -LiteralPath (Join-Path $destination $userData)) { throw 'This output folder contains user data. Choose a fresh OutputFolder.' }
}
$versionMatch = [regex]::Match((Get-Content -LiteralPath (Join-Path $taskRoot 'app/version.py') -Raw), "VERSION\s*=\s*'([^']+)'")
if (!$versionMatch.Success) { throw 'Could not read the app version.' }
$version = $versionMatch.Groups[1].Value
& $Python (Join-Path $taskRoot 'packaging/check_gui.py')
if ($LASTEXITCODE -ne 0) { throw 'Tcl/Tk preflight failed. Repair this Python installation or set TCL_LIBRARY and TK_LIBRARY to matching runtime scripts before building.' }
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
$env:ZIG_GLOBAL_CACHE_DIR = Join-Path $taskRoot '.zig-global-cache'
if (!$SkipNative) {
    $hook = Join-Path $taskRoot 'vendor/minhook'
    & $Zig cc -target x86_64-windows-gnu -shared -O2 -g -Wall -Wextra -DFM_THEME_LAB -I (Join-Path $hook 'include') (Join-Path $taskRoot 'native/reload.c') (Join-Path $hook 'src/buffer.c') (Join-Path $hook 'src/hook.c') (Join-Path $hook 'src/trampoline.c') (Join-Path $hook 'src/hde/hde64.c') -luser32 -o (Join-Path $runtime 'fm_skin_theme_probe_v10.dll')
    if ($LASTEXITCODE -ne 0) { throw 'Native build failed.' }
}
if (!(Test-Path -LiteralPath (Join-Path $runtime 'fm_skin_theme_probe_v10.dll'))) { throw 'Build the native DLL first; SkipNative requires an existing DLL.' }
& $Python (Join-Path $taskRoot 'packaging/collect_notices.py')
if ($LASTEXITCODE -ne 0) { throw 'License collection failed.' }
& $Python -m PyInstaller --clean --noconfirm --distpath $destination --workpath (Join-Path $taskRoot "build-$version") (Join-Path $taskRoot 'packaging/FMGraphicsReload.spec')
if ($LASTEXITCODE -ne 0) { throw 'EXE build failed.' }
& $Python (Join-Path $taskRoot 'packaging/check_gui.py') --archive (Join-Path $destination "FM Graphics Reload $version.exe")
if ($LASTEXITCODE -ne 0) { throw 'The EXE is missing required GUI components. Do not distribute it.' }
Get-Item -LiteralPath (Join-Path $destination "FM Graphics Reload $version.exe") | Select-Object FullName,Length
