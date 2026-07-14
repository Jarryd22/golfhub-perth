@echo off
setlocal
cd /d "%~dp0\.."

echo Building GolfHub Perth v4...
py -3 scripts\build_windows_icon.py
if errorlevel 1 exit /b 1
py -3 -m PyInstaller --noconfirm --clean GolfHub_v4.spec
if errorlevel 1 exit /b 1

set "ISCC=%LocalAppData%\Programs\Inno Setup 7\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 7\ISCC.exe"
if not exist "%ISCC%" (
  echo Inno Setup 7 was not found.
  exit /b 1
)

"%ISCC%" build_tools\GolfHub_v4_InnoSetup.iss
if errorlevel 1 exit /b 1
echo Installer created in installer\GolfHub_Perth_Setup_v4.exe
