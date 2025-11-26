@echo off
REM Enhanced Windows build script for Qdrant Manager
REM Supports both PyInstaller and Nuitka

setlocal enabledelayedexpansion

echo ========================================
echo Building Qdrant Manager for Windows
echo ========================================
echo.

REM Check for build tool argument
set BUILD_TOOL=pyinstaller
if "%1"=="nuitka" set BUILD_TOOL=nuitka
if "%1"=="auto" set BUILD_TOOL=auto

echo Using build tool: %BUILD_TOOL%
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    pause
    exit /b 1
)

REM Clean previous builds
echo Cleaning previous builds...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
if exist "__pycache__" rmdir /s /q "__pycache__"
for /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"

if "%BUILD_TOOL%"=="auto" (
    echo.
    echo Opening auto-py-to-exe GUI...
    echo Please configure and build using the GUI.
    pip install auto-py-to-exe >nul 2>&1
    auto-py-to-exe
    goto :end
)

if "%BUILD_TOOL%"=="nuitka" (
    echo.
    echo Installing/updating Nuitka...
    pip install nuitka >nul 2>&1
    
    echo Building with Nuitka...
    python build_nuitka.py
    if errorlevel 1 (
        echo.
        echo Build failed!
        pause
        exit /b 1
    )
    goto :success
)

REM PyInstaller build
echo Installing/updating PyInstaller...
pip install pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Failed to install PyInstaller
    pause
    exit /b 1
)

echo.
echo Building executable with PyInstaller...
echo Using simple build script (no spec file needed)...
python build_simple.py
if errorlevel 1 goto :fail
goto :success

:fail
echo.
echo Build failed! Trying alternative method with spec file...
if exist "build.spec" (
    pyinstaller build.spec --clean --noconfirm
    if errorlevel 1 goto :error
    goto :success
) else (
    echo ERROR: build.spec not found and simple build failed
    goto :error
)

if errorlevel 1 (
    echo.
    echo Build failed!
    echo.
    echo Troubleshooting:
    echo 1. Make sure all dependencies are installed: pip install -e ".[all-db]"
    echo 2. Check that build.spec exists
    echo 3. Try building with console=True in build.spec for debugging
    pause
    exit /b 1
)

:success
echo.
echo ========================================
echo Build completed successfully!
echo ========================================
echo.
if exist "dist\QdrantManager.exe" (
    echo Executable location: dist\QdrantManager.exe
    echo File size:
    dir dist\QdrantManager.exe | find "QdrantManager.exe"
) else if exist "dist\QdrantManager" (
    echo Executable location: dist\QdrantManager
)
echo.
echo To test: Run the executable from the dist folder
echo.

:end
pause
