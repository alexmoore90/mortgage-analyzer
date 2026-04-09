@echo off
title Mortgage Analyzer - Stop

echo.
echo  [*] Stopping Mortgage Analyzer...
docker stop mortgage-analyzer-app >nul 2>&1
docker rm   mortgage-analyzer-app >nul 2>&1
echo  [+] Stopped.
echo.
pause
