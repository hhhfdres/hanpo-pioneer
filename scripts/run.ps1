$ErrorActionPreference = "Stop"

Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    $env:PYTHONPATH = "src"
    python -m hanpo --open-browser
}
finally {
    Pop-Location
}

