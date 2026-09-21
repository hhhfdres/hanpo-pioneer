param(
    [Parameter(Mandatory = $true)]
    [string]$Owner,
    [string]$Repository = "hanpo-pioneer",
    [ValidateSet("public", "private")]
    [string]$Visibility = "public"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI is required: https://cli.github.com/"
}

gh auth status
if ($LASTEXITCODE -ne 0) {
    throw "Run 'gh auth login' before publishing."
}

Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    $fullName = "$Owner/$Repository"
    gh repo view $fullName *> $null
    if ($LASTEXITCODE -eq 0) {
        $remote = git remote get-url origin 2>$null
        if (-not $remote) {
            git remote add origin "https://github.com/$fullName.git"
        }
        git push -u origin main
    }
    else {
        gh repo create $fullName "--$Visibility" --source . --remote origin --push
    }
}
finally {
    Pop-Location
}

