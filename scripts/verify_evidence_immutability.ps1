$compose = "ops-control-plane/docker-compose.yml"
$rawResult = & .\.venv\Scripts\python.exe scripts\verify_evidence.py
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
$result = ($rawResult -join "`n") | ConvertFrom-Json
$target = $result.evidence[0]

docker compose -f $compose exec -T mysql `
    mysql -uaxiomops -paxiomops axiomops `
    -e "UPDATE evidence SET source='tampered' WHERE id='$($target.id)';" `
    2>$null
$updateRejected = $LASTEXITCODE -ne 0

docker compose -f $compose exec -T mysql `
    mysql -uaxiomops -paxiomops axiomops `
    -e "DELETE FROM evidence WHERE id='$($target.id)';" `
    2>$null
$deleteRejected = $LASTEXITCODE -ne 0

if (-not $updateRejected -or -not $deleteRejected) {
    throw "Evidence database immutability trigger did not reject a write"
}

$artifactPath = "/var/lib/axiomops/evidence/" + $target.artifact_path
docker compose -f $compose exec -T control-plane `
    sh -c 'printf tampered > "$1"' _ $artifactPath
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$statusCode = curl.exe `
    -s `
    -o NUL `
    -w "%{http_code}" `
    ("http://127.0.0.1:18000/evidence/" + $target.id + "/content")
$integrityRejected = $statusCode -eq "409"

if (-not $integrityRejected) {
    throw "Tampered Evidence content was not rejected"
}

[PSCustomObject]@{
    passed = $true
    incident_id = $result.incident_id
    evidence_count = $result.evidence_count
    update_rejected = $updateRejected
    delete_rejected = $deleteRejected
    tamper_read_status = 409
    tampered_evidence_id = $target.id
} | ConvertTo-Json
