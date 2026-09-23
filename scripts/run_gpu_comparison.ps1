param(
    [ValidateSet('gemma4-e2b','gemma4-e4b','hy-mt2','qwen3.5')]
    [string[]]$Models = @('gemma4-e2b','gemma4-e4b','hy-mt2','qwen3.5'),
    [string]$Device = 'Vulkan1'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Push-Location $projectRoot
try {
    $runtimeRoot = Join-Path $projectRoot '.tools/ollama-v0.34.2-vulkan'
    $runtimeExe = Join-Path $runtimeRoot 'lib/ollama/llama-server.exe'
    if (-not (Test-Path -LiteralPath $runtimeExe)) { throw 'Run scripts/prepare_ollama_vulkan.py first.' }
    $binaries = @(Get-ChildItem -LiteralPath $runtimeRoot -Recurse -File -Include *.exe,*.dll)
    if ($binaries.Count -eq 0) { throw 'No runtime binaries found.' }
    $invalid = @($binaries | Get-AuthenticodeSignature | Where-Object Status -ne Valid)
    if ($invalid.Count -gt 0) { throw ('Invalid runtime signatures: ' + ($invalid.Path -join ', ')) }
    foreach ($model in $Models) {
        & .venv/Scripts/python.exe scripts/compare_gemma.py --model $model --backend vulkan --runtime $runtimeExe --device $Device
        if ($LASTEXITCODE -ne 0) { throw "GPU comparison failed: $model" }
        $result = Get-Content -LiteralPath "artifacts/gemma-comparison/$model-vulkan.json" -Raw | ConvertFrom-Json
        if ($result.request_failures -ne 0 -or $result.rows.Count -ne 48) { throw "Incomplete GPU result: $model" }
    }
    & .venv/Scripts/python.exe scripts/report_gemma.py
    if ($LASTEXITCODE -ne 0) { throw 'Report validation failed.' }
}
finally { Pop-Location }
