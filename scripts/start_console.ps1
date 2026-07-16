$frontend = Join-Path $PSScriptRoot "..\frontend"

Push-Location $frontend
try {
    if (-not (Test-Path "node_modules")) {
        npm install
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    npm run dev -- --host 127.0.0.1
} finally {
    Pop-Location
}
