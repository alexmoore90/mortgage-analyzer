@echo off
title Mortgage Analyzer - Rebuild

echo.
echo  =========================================
echo   Rebuilding Mortgage Analyzer
echo  =========================================
echo.
echo  Use this after pulling updates from GitHub.
echo.

docker info >nul 2>&1
if errorlevel 1 (
    echo  [!] Docker is not running. Start Docker Desktop first.
    pause
    exit /b 1
)

REM Stop and remove old container and image
echo  [*] Removing old version...
docker stop mortgage-analyzer-app >nul 2>&1
docker rm   mortgage-analyzer-app >nul 2>&1
docker rmi  mortgage-analyzer     >nul 2>&1

REM Rebuild
echo  [*] Building new version...
echo.
docker build -t mortgage-analyzer .

if errorlevel 1 (
    echo.
    echo  [!] Build failed.
    pause
    exit /b 1
)

echo.
echo  [+] Rebuild complete! Run start.bat to launch.
echo.
pause
