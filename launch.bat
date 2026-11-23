@echo off
setlocal

rem ---------------------------------------------------------------------------
rem  Shared Drive Policy Manager — Windows batch launcher
rem  Launches the GUI using the ArcGIS Pro 3.3.1 Python interpreter.
rem  No installation or admin rights required.
rem ---------------------------------------------------------------------------

rem Check system-wide install first, then per-user install (ArcGIS Pro 3.x supports both).
set "ARCPY=%ProgramFiles%\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe"
if not exist "%ARCPY%" set "ARCPY=%LOCALAPPDATA%\Programs\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe"

if not exist "%ARCPY%" (
    echo ERROR: ArcGIS Pro Python interpreter not found.
    echo Searched:
    echo   %ProgramFiles%\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe
    echo   %LOCALAPPDATA%\Programs\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe
    echo.
    echo Please verify that ArcGIS Pro 3.3.1 is installed, then try again.
    pause
    exit /b 1
)

rem Change to the directory that contains this batch file so relative imports work.
cd /d "%~dp0"

"%ARCPY%" run_app.py %*

if errorlevel 1 (
    echo.
    echo Application exited with an error. Check the log at:
    echo   %LOCALAPPDATA%\SharedDrivePolicyManager\logs\app.log
    pause
)

endlocal
