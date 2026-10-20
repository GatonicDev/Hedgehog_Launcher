@echo off
cd /d "%~dp0"
if exist "HedgehodLauncher-Keyframes.exe" (
  start "" "HedgehodLauncher-Keyframes.exe"
) else (
  where py >nul 2>nul
  if %errorlevel%==0 (
    py -3 hedgehod_launcher.py
  ) else (
    python hedgehod_launcher.py
  )
)
