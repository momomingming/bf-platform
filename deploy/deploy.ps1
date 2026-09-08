<#
Li-S Battery Platform · Windows Deployment Script
适用于：Windows Server 2019/2022 + 宝塔面板 + 2GB 内存
执行：powershell -ExecutionPolicy Bypass -File deploy.ps1
#>

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# ===== Configuration =====
$AppRoot         = "C:\apps\bf-platform"
$PythonVersion   = "3.11.9"
$PythonExe       = "C:\Python311\python.exe"
$NssmDir         = "C:\tools\nssm"
$LogDir          = "$AppRoot\logs"
$ServiceName     = "BFPlatform"
$ServicePort     = 8501
$GithubRepo      = "https://github.com/momomingming/bf-platform.git"

# ===== [1/7] Directories =====
Write-Host "=== [1/7] Preparing directories ===" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path "C:\temp", $AppRoot, $LogDir, $NssmDir | Out-Null

# ===== [2/7] Python =====
Write-Host "=== [2/7] Checking Python ===" -ForegroundColor Cyan
if (-not (Test-Path $PythonExe)) {
    Write-Host "  Installing Python $PythonVersion..." -ForegroundColor Yellow
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $installer = "C:\temp\python-installer.exe"
    Invoke-WebRequest -Uri "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe" `
        -OutFile $installer -UseBasicParsing
    Start-Process -Wait -FilePath $installer -ArgumentList @(
        "/quiet","InstallAllUsers=1","PrependPath=1",
        "Include_test=0","Include_doc=0","Include_launcher=0",
        "TargetDir=C:\Python311"
    )
    Remove-Item $installer -Force
}
Write-Host "  Python: $PythonExe" -ForegroundColor Green
& $PythonExe --version
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path","User")

# ===== [3/7] Git =====
Write-Host "=== [3/7] Checking Git ===" -ForegroundColor Cyan
$gitExe = $null
try { $gitExe = (Get-Command git -ErrorAction Stop).Source } catch {}
if (-not $gitExe) {
    Write-Host "  Git not found. Install from https://git-scm.com/download/win first." -ForegroundColor Red
    exit 1
}
Write-Host "  Git: $gitExe" -ForegroundColor Green

# ===== [4/7] Repository =====
Write-Host "=== [4/7] Syncing repository ===" -ForegroundColor Cyan
if (Test-Path "$AppRoot\.git") {
    Write-Host "  Repo exists, pulling latest..." -ForegroundColor Yellow
    Push-Location $AppRoot; git pull origin main; Pop-Location
} else {
    if (Test-Path $AppRoot) { Remove-Item $AppRoot -Recurse -Force }
    git clone $GithubRepo $AppRoot
}
Write-Host "  Repo at: $AppRoot" -ForegroundColor Green

# ===== [5/7] Python dependencies =====
Write-Host "=== [5/7] Installing Python dependencies ===" -ForegroundColor Cyan
Push-Location "$AppRoot\lis_battery_platform"
& $PythonExe -m pip install --upgrade pip --disable-pip-version-check 2>&1 | Out-Null
& $PythonExe -m pip install -r requirements.txt --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
Pop-Location
Write-Host "  Dependencies installed" -ForegroundColor Green

# ===== [6/7] nssm =====
Write-Host "=== [6/7] Installing nssm ===" -ForegroundColor Cyan
if (-not (Test-Path "$NssmDir\nssm.exe")) {
    $nssmZip = "C:\temp\nssm.zip"
    Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile $nssmZip -UseBasicParsing
    Expand-Archive -Path $nssmZip -DestinationPath "C:\temp\nssm-extract" -Force
    Copy-Item -Path "C:\temp\nssm-extract\nssm-2.24\win64\*" -Destination $NssmDir -Recurse -Force
    Remove-Item $nssmZip -Force
    Remove-Item "C:\temp\nssm-extract" -Recurse -Force
}
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";$NssmDir", "Machine")
Write-Host "  nssm: $NssmDir\nssm.exe" -ForegroundColor Green

# ===== [7/7] Register & start service =====
Write-Host "=== [7/7] Registering Windows service ===" -ForegroundColor Cyan
$nssm       = "$NssmDir\nssm.exe"
$appDir     = "$AppRoot\lis_battery_platform"
$appArgs    = "run app.py --server.port=$ServicePort --server.address=0.0.0.0 --server.headless=true"

# 清理旧服务
& $nssm stop $ServiceName 2>&1 | Out-Null
& $nssm remove $ServiceName confirm 2>&1 | Out-Null

# 注册
& $nssm install $ServiceName $PythonExe "-m streamlit $appArgs"
& $nssm set $ServiceName AppDirectory $appDir
& $nssm set $ServiceName AppStdout "$LogDir\streamlit.log"
& $nssm set $ServiceName AppStderr "$LogDir\streamlit.err.log"
& $nssm set $ServiceName AppRotateFiles 1
& $nssm set $ServiceName AppRotateBytes 10485760
& $nssm set $ServiceName Start SERVICE_AUTO_START
& $nssm set $ServiceName AppRestartDelay 5000

# 启动
& $nssm start $ServiceName
Start-Sleep -Seconds 6

# 健康检查
$healthy = $false
for ($i = 1; $i -le 6; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$ServicePort/_stcore/health" -UseBasicParsing -TimeoutSec 5
        if ($r.StatusCode -eq 200) { $healthy = $true; break }
    } catch {}
    Start-Sleep -Seconds 3
}

if ($healthy) {
    Write-Host ""
    Write-Host "=== ✅ DEPLOYMENT SUCCESSFUL ===" -ForegroundColor Green
    Write-Host "  Service: $ServiceName" -ForegroundColor Green
    Write-Host "  Local:   http://127.0.0.1:$ServicePort" -ForegroundColor Green
    Write-Host "  Public:  http://82.156.43.223:$ServicePort" -ForegroundColor Green
    Write-Host "  Logs:    $LogDir\streamlit.log" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "=== ❌ Service did not respond to health check ===" -ForegroundColor Red
    Write-Host "Last 40 lines of error log:" -ForegroundColor Yellow
    if (Test-Path "$LogDir\streamlit.err.log") {
        Get-Content "$LogDir\streamlit.err.log" -Tail 40
    }
    exit 1
}
