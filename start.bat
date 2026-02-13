@echo off
echo ==========================================
echo 正在启动所有服务...
echo ==========================================

echo [1/3] 正在启动 GPT-SoVITS API...
start "SoVITS API" cmd /k "cd /d GPT-SoVITS-v2pro-20250604-nvidia50 && call conda activate test_ai && python api_v2.py"
timeout /t 3 /nobreak >nul

:: 2. 启动 Backend Server
echo [2/3] 正在启动 Backend Server...
start "Backend Server" cmd /k "call conda activate test_ai && python backend\server.py"

:: 等待 3 秒，防止 conda 临时文件冲突

:: 3. 启动 Frontend
echo [3/3] 正在启动 Frontend...
start "Frontend Vue" cmd /k "cd /d frontend && npm run dev"

echo ==========================================
echo ? 所有服务已启动！
echo ==========================================
pause