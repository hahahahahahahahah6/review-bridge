@echo off
chcp 65001 >nul
setlocal
title review-bridge 一键启动
echo ============================================
echo   review-bridge 一键启动
echo   面馆英文评论 → 中文简报 + 差评预警 + 代笔回复
echo ============================================
echo.

set "QUERY=%~1"
if "%QUERY%"=="" set "QUERY=Best Noodle House Rosemead"

REM ---- 1. Ollama ----
where ollama >nul 2>nul
if errorlevel 1 (
  echo [x] 没找到 Ollama，你可能还没装。
  echo     请先去 https://ollama.com/download/windows 下载安装，
  echo     装完后重新双击这个脚本。
  echo.
  pause
  exit /b 1
)
echo [ok] Ollama 已安装

REM ---- 2. 模型 ----
ollama list 2>nul | findstr /i "gemma3:4b" >nul
if errorlevel 1 (
  echo [*] 正在下载 gemma3:4b 模型（约 3.3GB，只需一次）...
  ollama pull gemma3:4b
  if errorlevel 1 (
    echo [x] 模型下载失败，检查网络后重试。
    pause
    exit /b 1
  )
) else (
  echo [ok] gemma3:4b 模型已就绪
)

REM ---- 3. SerpApi key ----
if "%SERPAPI_KEY%"=="" (
  echo [!] 没检测到 SERPAPI_KEY，将以粘贴模式运行（手动粘贴评论，不自动抓取）。
  echo     想要自动抓取：去 serpapi.com 注册免费 key，然后运行
  echo     setx SERPAPI_KEY "你的key" 后重新启动脚本。
  echo.
) else (
  echo [ok] SERPAPI_KEY 已配置，可自动抓取评论
)

REM ---- 4. Python ----
where python >nul 2>nul
if errorlevel 1 (
  echo [x] 没找到 Python，请先安装 Python 3.10+：
  echo     https://www.python.org/downloads/
  pause
  exit /b 1
)

REM ---- 5. 安装 review-bridge ----
echo [*] 正在安装/更新 review-bridge ...
python -m pip install --quiet --upgrade review-bridge
if errorlevel 1 (
  echo [x] 安装失败，检查网络后重试。
  pause
  exit /b 1
)
echo [ok] review-bridge 已就绪
echo.

REM ---- 6. 启动 ----
echo ============================================
echo   服务器启动中...
echo   本机打开： http://localhost:8080
echo   手机（同一 Wi-Fi）：把 localhost 换成这台电脑的 IP 即可
echo   查询店铺： %QUERY%
echo   按 Ctrl+C 停止服务
echo ============================================
echo.
review-bridge serve --query "%QUERY%"
pause
