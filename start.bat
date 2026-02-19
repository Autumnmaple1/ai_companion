@echo off
echo ==========================================
echo 正在启动所有服务...
echo ==========================================

:: 2. 启动 Backend Server
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