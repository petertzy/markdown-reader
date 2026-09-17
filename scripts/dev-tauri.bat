@echo off
setlocal
set "BASH_EXE=C:\Program Files\Git\bin\bash.exe"

if not exist "%BASH_EXE%" (
    echo [ERROR] Git Bash not found at %BASH_EXE%.
    echo Please install Git for Windows or run the script manually.
    exit /b 1
)

"%BASH_EXE%" "%~dp0dev-tauri.sh" %*
