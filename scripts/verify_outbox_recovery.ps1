$compose = "ops-control-plane/docker-compose.yml"
$key = "outage-" + [guid]::NewGuid().ToString()
$body = @{
    title = "RocketMQ outage durability"
    service = "inventory-service"
    severity = "SEV2"
    summary = "incident must survive a temporary RocketMQ outage"
} | ConvertTo-Json

docker compose -f $compose stop proxy
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

try {
    Start-Sleep -Seconds 3
    $response = Invoke-WebRequest `
        -UseBasicParsing `
        -Method Post `
        -Uri "http://127.0.0.1:18000/incidents" `
        -Headers @{"Idempotency-Key" = $key} `
        -ContentType "application/json" `
        -Body $body
    $created = $response.Content | ConvertFrom-Json
    Start-Sleep -Seconds 5
    $pending = Invoke-RestMethod `
        -Uri ("http://127.0.0.1:18000/incidents/" + $created.id)

    if ($response.StatusCode -ne 201 -or $pending.status -ne "RECEIVED") {
        throw "Incident was not durably stored while RocketMQ was unavailable"
    }

    docker compose -f $compose start proxy
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    $deadline = (Get-Date).AddSeconds(75)
    do {
        Start-Sleep -Seconds 2
        $recovered = Invoke-RestMethod `
            -Uri ("http://127.0.0.1:18000/incidents/" + $created.id)
    } while (
        ($recovered.status -ne "INVESTIGATION_QUEUED" -or
         $recovered.outbox[0].status -ne "PUBLISHED") -and
        (Get-Date) -lt $deadline
    )

    if ($recovered.status -ne "INVESTIGATION_QUEUED") {
        throw "Outbox did not recover after RocketMQ restarted"
    }

    [PSCustomObject]@{
        passed = $true
        incident_id = $recovered.id
        status_while_proxy_down = $pending.status
        final_status = $recovered.status
        final_outbox_status = $recovered.outbox[0].status
        delivery_attempts = $recovered.outbox[0].attempts
    } | ConvertTo-Json
} finally {
    docker compose -f $compose start proxy | Out-Null
}
