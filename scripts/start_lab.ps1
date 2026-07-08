$ErrorActionPreference = "Stop"
$env:DOCKER_BUILDKIT = "0"
$env:COMPOSE_DOCKER_CLI_BUILD = "0"

docker compose -f ops-lab/docker-compose.yml up -d --build
docker compose -f ops-lab/docker-compose.yml ps
