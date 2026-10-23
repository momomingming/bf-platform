# ============================================================
# bf-platform 服务器更新脚本
# 在【服务器】PowerShell（管理员）里整段粘贴运行即可。
# 前提：本机已联网、gh-proxy 可达；服务名 BFPlatform、目录 C:\apps\bf-platform
# 流程：装依赖 -> 拉 codeload zip(gh-proxy) -> robocopy /E 覆盖(保留 logs)
#       -> 设 BF_DB_PATH 持久化 -> nssm restart -> 自测 + 健康检查
# ============================================================
$ErrorActionPreference = 'Stop'

$svc     = 'BFPlatform'
$appDir  = 'C:\apps\bf-platform'
$dataDir = 'C:\apps\bf-platform\data'
$tmp     = 'C:\apps\update'
$zip     = "$tmp\bf.zip"
$url     = 'https://gh-proxy.com/https://codeload.github.com/momomingming/bf-platform/zip/refs/heads/main'

# nssm：优先 PATH 中的 nssm，否则用常见全路径
$nssm = if (Get-Command nssm -ErrorAction SilentlyContinue) { 'nssm' } else { 'C:\tools\nssm\nssm.exe' }

Write-Host '== 0. 准备目录 =='
New-Item -ItemType Directory -Force -Path $tmp, $dataDir | Out-Null

Write-Host '== 1. 安装数据层依赖 openpyxl/xlrd =='
& C:\Python311\python.exe -m pip install --quiet --upgrade openpyxl xlrd
Write-Host '   deps ok'

Write-Host '== 2. 下载 codeload zip (gh-proxy) =='
Invoke-WebRequest -Uri $url -OutFile $zip -TimeoutSec 600
$size = (Get-Item $zip).Length
if ($size -lt 100KB) { throw "下载异常，文件过小 ($size bytes)，可能 gh-proxy 返回了错误页" }
Write-Host "   downloaded $([Math]::Round($size/1KB,1)) KB"

Write-Host '== 3. 解压 =='
Expand-Archive -Path $zip -DestinationPath $tmp -Force
$src = "$tmp\bf-platform-main"
if (-not (Test-Path $src)) {
    $src = (Get-ChildItem $tmp -Directory | Where-Object { $_.Name -like 'bf-platform*' } | Select-Object -First 1).FullName
}
if (-not (Test-Path $src)) { throw '找不到解压后的源码目录' }
Write-Host "   source: $src"

Write-Host '== 4. robocopy /E 覆盖（保留 logs，不用 /MIR）=='
robocopy $src $appDir /E /NFL /NDL /NJH /NJS
$rc = $LASTEXITCODE
if ($rc -ge 8) { throw "robocopy 失败，退出码 $rc" }
Write-Host "   copied (robocopy rc=$rc)"

Write-Host '== 5. 设置 BF_DB_PATH 持久化（避免每次更新丢库，并保留旧库）=='
# 先把可能存在的旧库（默认路径下的）搬到新位置，决不丢数据
$oldDb = "$appDir\lis_battery_platform\data\platform.db"
$newDb = "$dataDir\platform.db"
if (Test-Path $oldDb) {
    if (-not (Test-Path $newDb)) {
        New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
        Copy-Item $oldDb $newDb -Force
        Write-Host "   已保留旧库：$oldDb -> $newDb"
    } else {
        Write-Host "   新位置已有库，跳过复制：$newDb"
    }
}
$envLine = "BF_DB_PATH=$newDb"
& $nssm set $svc AppEnvironmentExtra $envLine
Write-Host "   $envLine"

Write-Host '== 6. 重启服务 =='
& $nssm restart $svc
Write-Host '   restarted'

Write-Host '== 7. 等 8s 后跑自测 =='
Start-Sleep -Seconds 8
& C:\Python311\python.exe "$appDir\lis_battery_platform\tests\selftest_pipeline.py"
& C:\Python311\python.exe "$appDir\lis_battery_platform\tests\selftest_versioning.py"

Write-Host '== 8. 健康检查 http://localhost:8501 =='
try {
    $r = Invoke-WebRequest -Uri http://localhost:8501 -TimeoutSec 20 -UseBasicParsing
    Write-Host "   HTTP $($r.StatusCode) - 服务已起"
} catch {
    Write-Warning "   服务尚未响应（可能仍在启动）：$_"
}

Write-Host '==== 部署完成 ===='
