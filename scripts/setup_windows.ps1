$ErrorActionPreference = "Stop"

Write-Host "Setting up ClauseGuard..." -ForegroundColor Cyan

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example. Mock mode is enabled by default."
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Run tests: python -m unittest discover -s tests -p `"test_*.py`""
Write-Host "Run demo:  python run_demo.py"
Write-Host "Run API:   python src/dashboard.py"
