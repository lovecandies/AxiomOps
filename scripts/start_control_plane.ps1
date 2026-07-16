$env:DOCKER_BUILDKIT = "0"
$env:COMPOSE_DOCKER_CLI_BUILD = "0"

$root = Join-Path $PSScriptRoot ".."
$envFile = Join-Path $root ".env"
$composeArgs = @("-f", "ops-control-plane/docker-compose.yml")
if (Test-Path $envFile) {
    $composeArgs = @("--env-file", $envFile) + $composeArgs
}

docker compose @composeArgs up -d --build
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

docker compose @composeArgs ps
