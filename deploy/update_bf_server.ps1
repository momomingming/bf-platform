# ============================================================
# bf-platform server update script (ASCII-only, multi-mirror download)
# Run inside server PowerShell (admin).
# ============================================================
$ErrorActionPreference = 'Stop'

$svc     = 'BFPlatform'
$appDir  = 'C:\apps\bf-platform'
$dataDir = 'C:\apps\bf-platform\data'
$tmp     = 'C:\apps\update'
$zip     = "$tmp\bf.zip"

$nssm = if (Get-Command nssm -ErrorAction SilentlyContinue) { 'nssm' } else { 'C:\tools\nssm\nssm.exe' }

# try multiple mirrors in order; use the first that returns a real zip
$zipUrls = @(
  'https://codeload.github.com/momomingming/bf-platform/zip/refs/heads/main',
  'https://ghproxy.net/https://codeload.github.com/momomingming/bf-platform/zip/refs/heads/main',
  'https://gh-proxy.com/https://codeload.github.com/momomingming/bf-platform/zip/refs/heads/main'
)

Write-Host '== 0. prepare dirs =='
New-Item -ItemType Directory -Force -Path $tmp, $dataDir | Out-Null

Write-Host '== 1. install deps openpyxl/xlrd =='
& C:\Python311\python.exe -m pip install --quiet --upgrade openpyxl xlrd
Write-Host '   deps ok'

Write-Host '== 2. download codeload zip (try multiple mirrors) =='
$ok = $false
foreach ($u in $zipUrls) {
  Write-Host "   trying $u"
  try {
    Invoke-WebRequest -Uri $u -OutFile $zip -TimeoutSec 120 -ErrorAction Stop
    $sz = (Get-Item $zip).Length
    if ($sz -ge 100KB) { $ok = $true; Write-Host "   downloaded $([Math]::Round($sz/1KB,1)) KB from $u"; break }
    else { Write-Host "   too small ($sz), try next" }
  } catch { Write-Host "   failed: $_" }
}
if (-not $ok) { throw 'all mirrors failed to download zip' }

Write-Host '== 3. extract =='
Expand-Archive -Path $zip -DestinationPath $tmp -Force
$src = "$tmp\bf-platform-main"
if (-not (Test-Path $src)) {
    $src = (Get-ChildItem $tmp -Directory | Where-Object { $_.Name -like 'bf-platform*' } | Select-Object -First 1).FullName
}
if (-not (Test-Path $src)) { throw 'cannot find extracted source dir' }
Write-Host "   source: $src"

Write-Host '== 4. robocopy /E overwrite (keep logs, no /MIR) =='
robocopy $src $appDir /E /NFL /NDL /NJH /NJS
$rc = $LASTEXITCODE
if ($rc -ge 8) { throw "robocopy failed rc=$rc" }
Write-Host "   copied (robocopy rc=$rc)"

Write-Host '== 5. set BF_DB_PATH persistent (keep old db) =='
$oldDb = "$appDir\lis_battery_platform\data\platform.db"
$newDb = "$dataDir\platform.db"
if (Test-Path $oldDb) {
    if (-not (Test-Path $newDb)) {
        New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
        Copy-Item $oldDb $newDb -Force
        Write-Host "   kept old db: $oldDb -> $newDb"
    } else {
        Write-Host "   new db already exists, skip: $newDb"
    }
}
$envLine = "BF_DB_PATH=$newDb"
& $nssm set $svc AppEnvironmentExtra $envLine
Write-Host "   $envLine"

Write-Host '== 6. restart service =='
& $nssm restart $svc
Write-Host '   restarted'

Write-Host '== 7. wait 8s then selftest =='
Start-Sleep -Seconds 8
& C:\Python311\python.exe "$appDir\lis_battery_platform\tests\selftest_pipeline.py"
& C:\Python311\python.exe "$appDir\lis_battery_platform\tests\selftest_versioning.py"

Write-Host '== 8. health check http://localhost:8501 =='
try {
    $r = Invoke-WebRequest -Uri http://localhost:8501 -TimeoutSec 20 -UseBasicParsing
    Write-Host "   HTTP $($r.StatusCode) - service up"
} catch {
    Write-Warning "   service not responding yet (maybe still starting): $_"
}

Write-Host '==== DEPLOY DONE ===='
