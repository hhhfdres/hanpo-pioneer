$ErrorActionPreference = "Stop"

Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    $env:PYTHONPATH = "src"
    python -m unittest discover -v
}
finally {
    Pop-Location
}

