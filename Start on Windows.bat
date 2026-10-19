@echo off
setlocal enabledelayedexpansion
title Media Server Setup
cd /d "%~dp0"
cls
echo.
echo   Media Server Setup
echo   Movies, shows, anime, comics and manga, set up for you.
echo.

rem ---- 1. Docker ----
<nul set /p "=  [1/4] Checking Docker ... "
where docker >nul 2>nul
if errorlevel 1 (
  echo not found
  echo.
  echo   Docker Desktop is not installed. The download page is opening now.
  echo   Install it, restart your computer, open Docker Desktop, then open this file again.
  start https://www.docker.com/products/docker-desktop/
  echo.
  pause
  exit /b 1
)
docker info >nul 2>nul
if errorlevel 1 (
  echo starting Docker Desktop, this can take a minute
  start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
  for /l %%i in (1,1,45) do (
    docker info >nul 2>nul && goto ready
    timeout /t 4 /nobreak >nul
  )
  echo.
  echo   Docker did not start. Open Docker Desktop yourself, wait until it says running,
  echo   then open this file again.
  echo.
  pause
  exit /b 1
)
:ready
echo OK

rem ---- 2. Folders ----
set "STACK=%USERPROFILE%\ArrStack"
set "MEDIA=%USERPROFILE%\ArrMedia"
if not exist "%STACK%" mkdir "%STACK%"
set "STACKF=%STACK:\=/%"
set "MEDIAF=%MEDIA:\=/%"
set "HOMEF=%USERPROFILE:\=/%"
<nul set /p "=  [2/4] Getting the setup ready (first time: about 100 MB) ... "
docker build -q -t arr-wizard -f wizard\Dockerfile . >nul
if errorlevel 1 (
  echo failed
  echo.
  echo   Could not get the setup ready. Check your internet connection, then open this file again.
  echo.
  pause
  exit /b 1
)
echo OK

rem ---- 3. Start ----
<nul set /p "=  [3/4] Starting the setup ... "
docker rm -f arr-wizard >nul 2>nul
docker run -d --name arr-wizard --restart unless-stopped -p 7979:7979 -v /var/run/docker.sock:/var/run/docker.sock -v "%STACK%":/stack -e HOST_STACK_DIR="%STACKF%" -e HOST_OS=win -e HOST_UID=1000 -e HOST_GID=1000 -e HOST_DEFAULT_MEDIA="%MEDIAF%" -e HOST_HOME="%HOMEF%" -e HOST_ADDRESS=localhost arr-wizard >nul
if errorlevel 1 (
  echo failed
  echo.
  echo   Could not start the setup. Another program may be using port 7979. Close it and try again.
  echo.
  pause
  exit /b 1
)
echo OK

rem ---- 4. Open ----
<nul set /p "=  [4/4] Opening your browser ... "
timeout /t 2 /nobreak >nul
start http://localhost:7979
echo OK
echo.
echo   Your setup page is ready.
echo.
echo       http://localhost:7979
echo.
echo   If your browser did not open, type that address into it yourself.
echo   You can close this window. The setup keeps running, and stopping it never touches your media.
echo.
timeout /t 8 >nul
