# review-bridge Windows 一键安装脚本
# 用法: 在 PowerShell 里运行 .\setup-windows.ps1 (Ollama 安装后可能需要重开一个 PowerShell 窗口)

$ErrorActionPreference = "Stop"

Write-Host "[1/5] 选择模型存放位置..."
$modelDir = $null
if (Test-Path "D:\") {
    $modelDir = "D:\ollama-models"
    if (-not (Test-Path $modelDir)) { New-Item -ItemType Directory -Path $modelDir | Out-Null }
    Write-Host "检测到 D 盘, 模型将存到 $modelDir (不占 C 盘)."
    # 当前会话 + 永久生效
    $env:OLLAMA_MODELS = $modelDir
    setx OLLAMA_MODELS $modelDir | Out-Null
    # Ollama 如果已经在跑, 必须重启, 新路径才会生效
    $procs = Get-Process ollama -ErrorAction SilentlyContinue
    if ($procs) {
        Write-Host "正在重启已运行的 Ollama, 使新路径生效..."
        $procs | Stop-Process -Force
        Start-Sleep -Seconds 2
    }
    # 清掉 C 盘之前下载失败的残留 (没下完的模型分片, 留着没用)
    $stale = Join-Path $env:USERPROFILE ".ollama\models"
    if (Test-Path $stale) {
        Write-Host "清理 C 盘旧的失败下载残留: $stale"
        Remove-Item -Recurse -Force $stale
    }
} else {
    Write-Host "没检测到 D 盘, 模型放默认位置 (C 盘用户目录, 请确保 C 盘有 5GB 以上空闲)."
}

Write-Host "[2/5] 检查 Ollama..."
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "正在用 winget 安装 Ollama..."
    winget install -e --id Ollama.Ollama --accept-source-agreements --accept-package-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
} else {
    Write-Host "Ollama 已安装."
}

Write-Host "[3/5] 拉取 gemma3:4b 模型 (约 3GB, 需要几分钟)..."
ollama pull gemma3:4b

Write-Host "[4/5] 设置 SERPAPI_KEY..."
setx SERPAPI_KEY "1c1910d5657d9b4c19b4822647d43c0fdea644e1b99e3fd3e1a13716bae3ddbd"

Write-Host "[5/5] 安装 review-bridge..."
pip install -U review-bridge

Write-Host ""
Write-Host "完成! 先冒烟测试:  review-bridge serve --mock"
Write-Host "真机测试 (把店名换成你家的):  review-bridge serve --query `"店名`""
Write-Host "手机连同一个 Wi-Fi, 打开 http://<这台电脑IP>:8080"
