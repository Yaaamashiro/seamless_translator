param([switch]$SkipModels)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (-not (Test-Path .venv-qwen/Scripts/python.exe)) {
        & .\uv.ps1 venv .venv-qwen --python .venv/Scripts/python.exe
        if ($LASTEXITCODE -ne 0) { throw 'Qwen environment setup failed' }
    }
    & .\uv.ps1 pip sync --python .venv-qwen/Scripts/python.exe requirements-qwen.lock --extra-index-url https://download.pytorch.org/whl/cu126 --index-strategy unsafe-best-match
    if ($LASTEXITCODE -ne 0) { throw 'Qwen dependency setup failed' }
    & .venv-qwen/Scripts/python.exe -c "import torch; from qwen_tts import Qwen3TTSModel; assert torch.cuda.is_available(), 'CUDA is unavailable'; print(torch.cuda.get_device_name(0))"
    if ($LASTEXITCODE -ne 0) { throw 'Qwen GPU check failed' }
    if (-not $SkipModels) {
        & .venv/Scripts/python.exe scripts/prepare_qwen_tts.py
        if ($LASTEXITCODE -ne 0) { throw 'Qwen download failed' }
    }
} finally { Pop-Location }
