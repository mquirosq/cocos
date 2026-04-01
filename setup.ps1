$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (Test-Path $pythonExe) {
    Write-Host "Using virtual environment Python: $pythonExe"
} else {
    $pythonExe = "python"
    Write-Host "Using system Python from PATH"
}

Write-Host "Installing Python dependencies..."
& $pythonExe -m pip install -r requirements.txt

Write-Host "Installing frontend dependencies (Tailwind + daisyUI)..."
Push-Location "app"
npm install

Write-Host "Building frontend CSS bundle..."
npm run build:css
Pop-Location

Write-Host "Setup completed successfully."
