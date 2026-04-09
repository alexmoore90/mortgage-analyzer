@echo off
title Mortgage Analyzer

echo.
echo  =========================================
echo   Mortgage ^& Rental Analyzer
echo  =========================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo  [!] Docker is not running.
    echo      Please start Docker Desktop and try again.
    echo.
    pause
    exit /b 1
)

REM Check if image already exists, build if not
docker image inspect mortgage-analyzer >nul 2>&1
if errorlevel 1 (
    echo  [*] First run: building the app image...
    echo      This takes 2-3 minutes once, then is instant.
    echo.
    docker build -t mortgage-analyzer .
    if errorlevel 1 (
        echo.
        echo  [!] Build failed. Check the output above.
        pause
        exit /b 1
    )
)

REM Stop any existing container
docker stop mortgage-analyzer-app >nul 2>&1
docker rm   mortgage-analyzer-app >nul 2>&1

echo  [*] Starting Mortgage Analyzer...
echo.

REM Start the container
docker run -d ^
    --name mortgage-analyzer-app ^
    -p 8501:8501 ^
    --restart unless-stopped ^
    mortgage-analyzer

if errorlevel 1 (
    echo  [!] Failed to start container.
    pause
    exit /b 1
)

REM Wait a moment for Streamlit to boot
timeout /t 3 /nobreak >nul

echo  [+] App is running!
echo.
echo      Open your browser to:
echo      http://localhost:8501
echo.

REM Open the browser automatically
start http://localhost:8501

echo  [*] The app runs in the background.
echo      Run stop.bat to shut it down.
echo.
pause
