@echo off
rem Windows marks files from a downloaded zip as "from the internet" and then refuses to load some of
rem Meridian's libraries. This clears that mark on this folder, then starts the app.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -LiteralPath '%~dp0' -Recurse -File | Unblock-File"
start "" "%~dp0Meridian.exe"
