@echo off
setlocal enabledelayedexpansion
title Media Server Setup
cd /d "%~dp0"
echo.
echo  Media Server Setup is starting.
where docker >nul 2>nul
if errorlevel 1 (
  echo.
  echo  Docker Desktop is not installed. Opening the page where you can get it.
  start https://www.docker.com/products/docker-desktop/
  echo  Install it, restart your computer, open Docker Desktop, then open this file again.
  pause
  exit /b 1
)
docker info >nul 2>nul
if errorlevel 1 (
  echo  Starting Docker Desktop. This can take a minute.
  start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
  for /l %%i in (1,1,45) do (
    docker info >nul 2>nul && goto ready
    timeout /t 4 /nobreak >nul
  )
  echo  Docker did not start. Open Docker Desktop yourself, wait until it says running, then open this file again.
  pause
  exit /b 1
)
:ready
set "STACK=%USERPROFILE%\ArrStack"
set "MEDIA=%USERPROFILE%\ArrMedia"
if not exist "%STACK%" mkdir "%STACK%"
set "STACKF=%STACK:\=/%"
set "MEDIAF=%MEDIA:\=/%"
set "HOMEF=%USERPROFILE:\=/%"
echo  Getting the setup ready. The first time it downloads about 100 MB.
docker build -q -t arr-wizard -f wizard\Dockerfile . >nul
if errorlevel 1 ( echo  Could not get the setup ready. Check your internet. & pause & exit /b 1 )
docker rm -f arr-wizard >nul 2>nul
docker run -d --name arr-wizard --restart unless-stopped -p 7979:7979 -v /var/run/docker.sock:/var/run/docker.sock -v "%STACK%":/stack -e HOST_STACK_DIR="%STACKF%" -e HOST_OS=win -e HOST_UID=1000 -e HOST_GID=1000 -e HOST_DEFAULT_MEDIA="%MEDIAF%" -e HOST_HOME="%HOMEF%" -e HOST_ADDRESS=localhost arr-wizard >nul
if errorlevel 1 ( echo  Could not start the setup. Is another program using port 7979? & pause & exit /b 1 )
echo  Ready. Opening your browser.
timeout /t 2 /nobreak >nul
start http://localhost:7979
echo  You can close this window now.
timeout /t 5 >nul
