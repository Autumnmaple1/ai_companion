@echo off
setlocal

:: 检查 Docker 是否安装运行中
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker not found. Please install Docker first.
    pause
    exit /b
)

echo [INFO] Starting base services with Docker Compose...

:: 启动容器
:: -d 后台运行
:: --build 强制重新构建 (如果修改过 Dockerfile)
docker-compose up -d

if %errorlevel% neq 0 (
    echo [ERROR] Failed to start Docker containers.
    pause
    exit /b
)

echo.
echo [SUCCESS] Docker services are running:
docker-compose ps

echo.
echo [INFO] You can now initialize the character memory by running:
echo python scripts/init_letta.py
echo.

pause
endlocal
