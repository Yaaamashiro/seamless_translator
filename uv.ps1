# Prefer a project-local uv, otherwise use an installed uv on PATH.
$env:UV_PYTHON_INSTALL_DIR = Join-Path $PSScriptRoot '.tools\python'
$env:UV_CACHE_DIR = Join-Path $PSScriptRoot '.tools\cache'
$env:UV_PYTHON_NO_REGISTRY = '1'
$uvExecutable = Join-Path $PSScriptRoot '.tools\uv\uv.exe'
if (-not (Test-Path -LiteralPath $uvExecutable)) {
    $uvCommand = Get-Command uv -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $uvCommand) {
        throw 'Install uv first: https://docs.astral.sh/uv/getting-started/installation/'
    }
    $uvExecutable = $uvCommand.Source
}
& $uvExecutable @args
exit $LASTEXITCODE
