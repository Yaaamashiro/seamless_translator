param([switch]$SkipModels)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (-not (Test-Path .venv-kokoro/Scripts/python.exe)) {
        & .\uv.ps1 venv .venv-kokoro --python .venv/Scripts/python.exe
        if ($LASTEXITCODE -ne 0) { throw 'Kokoro environment setup failed' }
    }
    & .\uv.ps1 pip sync --python .venv-kokoro/Scripts/python.exe requirements-kokoro.lock --extra-index-url https://download.pytorch.org/whl/cu126 --index-strategy unsafe-best-match
    if ($LASTEXITCODE -ne 0) { throw 'Kokoro dependency setup failed' }
    & .venv-kokoro/Scripts/python.exe scripts/prepare_kokoro_frontend.py
    if ($LASTEXITCODE -ne 0) { throw 'Kokoro Japanese frontend setup failed' }
    & .venv-kokoro/Scripts/python.exe -c "import torch; from kokoro import KModel; assert torch.cuda.is_available(), 'CUDA is unavailable'; print(torch.cuda.get_device_name(0))"
    if ($LASTEXITCODE -ne 0) { throw 'Kokoro GPU check failed' }
    if (-not $SkipModels) {
        & .venv/Scripts/python.exe scripts/prepare_kokoro.py
        if ($LASTEXITCODE -ne 0) { throw 'Kokoro download failed' }
    }
} finally { Pop-Location }
