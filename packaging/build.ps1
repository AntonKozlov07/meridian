# Builds the Windows app. Run from the project root in PowerShell:  .\packaging\build.ps1
$ErrorActionPreference = "Stop"
python -m pip install -r requirements.txt pyinstaller
python -m pytest -q
python -m PyInstaller packaging/meridian.spec --noconfirm
Copy-Item packaging\Start-Meridian.bat dist\Meridian\
& .\dist\Meridian\Meridian.exe --selfcheck
if ($LASTEXITCODE -ne 0) { throw "The built app failed its self-check" }
Compress-Archive -Path .\dist\Meridian -DestinationPath .\dist\Meridian-windows.zip -Force
Write-Host "Done: dist\Meridian\Meridian.exe and dist\Meridian-windows.zip"
