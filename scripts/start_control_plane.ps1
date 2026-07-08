$env:DOCKER_BUILDKIT = "0"
$env:COMPOSE_DOCKER_CLI_BUILD = "0"

docker compose -f ops-control-plane/docker-compose.yml up -d --build
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

docker compose -f ops-control-plane/docker-compose.yml ps
