@echo off
REM Build Windows Installer (setup.exe) using Inno Setup
REM This script builds the installer with license agreement and post-install launch
REM Can be run from project root or installers directory

setlocal enabledelayedexpansion

echo ========================================
echo Building Windows Installer for Qdrant Manager
echo ========================================
echo.

REM Determine if we're in project root or installers directory
set PROJECT_ROOT=.
set INSTALLERS_DIR=installers
if exist "installers\windows\QdrantManager.iss" (
    set PROJECT_ROOT=.
    set INSTALLERS_DIR=installers
) else if exist "windows\QdrantManager.iss" (
    set PROJECT_ROOT=..
    set INSTALLERS_DIR=.
    cd ..
)

REM Check if executable exists
if not exist "%PROJECT_ROOT%\dist\QdrantManager.exe" (
    echo ERROR: QdrantManager.exe not found in dist folder
    echo Please build the executable first using: build_windows.bat
    pause
    exit /b 1
)

REM Check if Inno Setup is installed
set INNO_SETUP_PATH=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "INNO_SETUP_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "INNO_SETUP_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files (x86)\Inno Setup 5\ISCC.exe" (
    set "INNO_SETUP_PATH=C:\Program Files (x86)\Inno Setup 5\ISCC.exe"
) else if exist "C:\Program Files\Inno Setup 5\ISCC.exe" (
    set "INNO_SETUP_PATH=C:\Program Files\Inno Setup 5\ISCC.exe"
) else (
    REM Try to find it using where command
    for /f "delims=" %%i in ('where ISCC 2^>nul') do (
        set "INNO_SETUP_PATH=%%i"
        goto :found_inno
    )
    :found_inno
    if not defined INNO_SETUP_PATH (
        echo.
        echo ERROR: Inno Setup not found!
        echo.
        echo Please install Inno Setup from: https://jrsoftware.org/isinfo.php
        echo Or download from: https://jrsoftware.org/isdl.php
        echo.
        echo If Inno Setup is installed in a custom location, please set the
        echo INNO_SETUP_PATH environment variable to point to ISCC.exe
        echo.
        echo Example: set INNO_SETUP_PATH=C:\Path\To\Inno Setup\ISCC.exe
        echo.
        pause
        exit /b 1
    )
)

echo Found Inno Setup at: %INNO_SETUP_PATH%
echo.

REM Check if license file exists
if not exist "%PROJECT_ROOT%\LICENSE.txt" (
    echo ERROR: LICENSE.txt not found in project root
    pause
    exit /b 1
)

REM Create output directory
if not exist "%PROJECT_ROOT%\dist\installers" mkdir "%PROJECT_ROOT%\dist\installers"

echo Building installer...
echo.

REM Compile the installer (change to installers/windows directory)
cd %INSTALLERS_DIR%\windows
"%INNO_SETUP_PATH%" "QdrantManager.iss"
set BUILD_RESULT=%ERRORLEVEL%
cd %PROJECT_ROOT%

if %BUILD_RESULT% NEQ 0 (
    echo.
    echo ERROR: Installer build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Installer built successfully!
echo ========================================
echo.
echo Installer location: %PROJECT_ROOT%\dist\installers\QdrantManager-Setup.exe
echo.

REM Check if file exists and show size
if exist "%PROJECT_ROOT%\dist\installers\QdrantManager-Setup.exe" (
    echo File size:
    dir "%PROJECT_ROOT%\dist\installers\QdrantManager-Setup.exe" | find "QdrantManager-Setup.exe"
    echo.
    echo You can now distribute this installer to users.
    echo The installer includes:
    echo   - License agreement (must be accepted)
    echo   - Automatic installation
    echo   - Option to launch Qdrant Manager after installation
    echo.
) else (
    echo WARNING: Installer file not found in expected location
)

pause
