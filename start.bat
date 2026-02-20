@echo off
echo ==========================================
echo 正在启动所有服务...
echo ==========================================

:: 1. 检查 Node.js 环境
echo [0/2] 正在检查开发环境...
node -v >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 Node.js，请先安装 Node.js！
    pause
    exit /b
)

:: 2. 检查 Python Conda 环境
call conda --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 Conda，请确保已安装并添加到环境变量！
    pause
    exit /b
)

:: 3. 启动 Backend Server
echo [1/2] 正在启动 Backend Server...
start "Backend Server" cmd /k "call conda activate test_ai && python backend\server.py"

:: 等待 3 秒，防止 conda 临时文件冲突

:: 3. 启动 Frontend
echo [2/2] 正在启动 Frontend...
:: 这里会先自动执行 npm install 确保依赖最新，然后再运行启动命令
start "Frontend Web" cmd /k "cd /d frontend && echo 正在检查/安装前端依赖... && npm install && echo 正在开启前端服务... && npm run dev"

echo ==========================================
echo ? 所有服务已启动！
echo ==========================================
pause