$ErrorActionPreference = 'Stop'
$base = 'http://127.0.0.1:8000'

function Invoke-Api([string]$method, [string]$path, $body = $null) {
    if ($null -eq $body) { return Invoke-RestMethod -Method $method -Uri "$base$path" -TimeoutSec 30 }
    $json = ConvertTo-Json -InputObject $body -Depth 100 -Compress
    return Invoke-RestMethod -Method $method -Uri "$base$path" -ContentType 'application/json' -Body $json -TimeoutSec 30
}

function Assert-That([bool]$condition, [string]$message) {
    if (-not $condition) { throw "QA assertion failed: $message" }
}

$health = Invoke-Api 'Get' '/api/health'
Assert-That ($health.status -eq 'ok') 'API health check'
$session = Invoke-Api 'Post' '/api/game/new' @{ seed = 2026 }
$id = $session.session_id
Assert-That ($id -and $session.cells.Count -eq 768 -and $session.budget_credits -eq 100) 'new session, map size and starting budget'
$station = 'weather-central'
$records = @($session.historical_observations | Where-Object station_id -eq $station | Sort-Object timestamp)
$six = @($records | Select-Object -First 6)
Assert-That ($six.Count -eq 6) 'historical station observations returned'
$rain = @($six | ForEach-Object { [double]$_.rainfall_mm_hr })
$stats = Invoke-Api 'Post' '/api/analytics/statistics' @{ values = $rain; session_id = $id }
$smooth = Invoke-Api 'Post' '/api/analytics/moving-average' @{ data = $rain; timestamps = @($six | ForEach-Object timestamp); window_size = 3; session_id = $id }
Assert-That ($smooth.values.Count -eq 4 -and $stats.count -eq 6) 'statistics and moving-average observations'

$lab = Invoke-Api 'Get' '/api/analytics/lab?station_id=weather-central&window_size=6&seed=2026'
$observations = @($lab.training_observations) + @($lab.heldout_observations)
$regression = Invoke-Api 'Post' '/api/analytics/regression' @{
    x = @($observations | ForEach-Object { [double]$_.rainfall_mm_hr })
    y = @($observations | ForEach-Object { [double]$_.water_depth_mm })
    test_fraction = 0.2
    manual_line_x = @(0.0, 50.0)
    manual_line_y = @(0.0, 100.0)
    session_id = $id
}
$correlation = Invoke-Api 'Post' '/api/analytics/correlation' @{
    x = @($observations | ForEach-Object { [double]$_.rainfall_mm_hr })
    y = @($observations | ForEach-Object { [double]$_.water_depth_mm })
    x_label = 'Rainfall'; y_label = 'Water depth'; session_id = $id
}
$evaluation = Invoke-Api 'Post' '/api/analytics/evaluate' @{
    actual = @($lab.evaluation.actual_water_depth_mm)
    timestamps = @($lab.evaluation.timestamps)
    moving_average_predictions = @($lab.evaluation.moving_average.predictions_mm)
    regression_predictions = @($lab.evaluation.linear_regression.predictions_mm)
    session_id = $id
}
$futureRain = @($lab.eastbank_scenario | Select-Object -First 6 | ForEach-Object { [double]$_.rainfall_mm_hr })
$forecast = Invoke-Api 'Post' '/api/analytics/forecast' @{
    station_id = $station; rainfall_observations = $futureRain; seed = 2026; interval_minutes = 10; window_size = 6; session_id = $id
}
Assert-That ($regression.split_method -eq 'chronological' -and $correlation.coefficient -ne $null) 'regression and correlation'
Assert-That ($evaluation.sample_count -eq $lab.evaluation.sample_count -and $forecast.predictions.Count -eq 6) 'same-holdout evaluation and future forecast'

$state = Invoke-Api 'Get' "/api/game/$id/state"
$pumpCell = $state.cells | Where-Object { $_.terrain_type -in @('grass','park','road') -and $_.can_water_flow -and -not $_.building_id } | Select-Object -First 1
$boatCell = $state.cells | Where-Object { $_.is_road -and -not $_.building_id } | Select-Object -First 1
Assert-That ($null -ne $pumpCell -and $null -ne $boatCell) 'valid resource candidates exist'
$afterPump = Invoke-Api 'Post' "/api/game/$id/place-resource" @{ resource_type = 'pump'; x = $pumpCell.x; y = $pumpCell.y }
$afterBarrier = Invoke-Api 'Post' "/api/game/$id/place-resource" @{ resource_type = 'barrier'; x = $pumpCell.x; y = $pumpCell.y; direction = 'E' }
$afterBoat = Invoke-Api 'Post' "/api/game/$id/place-resource" @{ resource_type = 'rescue-boat'; x = $boatCell.x; y = $boatCell.y }
Assert-That ($afterBoat.budget_credits -eq 0) 'pump, barrier and boat costs total 100 credits'
$invalidRejected = $false
try { $null = Invoke-Api 'Post' "/api/game/$id/place-resource" @{ resource_type = 'pump'; x = 13; y = 13 } }
catch { $invalidRejected = $true }
Assert-That $invalidRejected 'invalid pump placement is rejected'

$riskCell = $state.cells | Sort-Object flood_risk_index -Descending | Select-Object -First 1
$null = Invoke-Api 'Post' "/api/game/$id/identify-risk" @{ x = $riskCell.x; y = $riskCell.y }
$null = Invoke-Api 'Post' "/api/game/$id/scenario/start"
$steps = 0
$final = $null
for ($batch = 0; $batch -lt 30; $batch++) {
    $final = Invoke-Api 'Post' "/api/game/$id/advance" @{ steps = 6 }
    $steps += 6
    if ($final.scenario_progress.complete) { break }
}
Assert-That ($final.scenario_progress.complete -and $final.response_outcome.finalized) 'full Eastbank storm completes and final report is finalized'
$outcome = $final.response_outcome
$reset = Invoke-Api 'Post' "/api/game/$id/reset" @{ seed = 2026 }
Assert-That ($reset.budget_credits -eq 100 -and $reset.resources.pumps.Count -eq 0) 'reset restores the budget and clears equipment'

Write-Host 'Integration walkthrough: PASS'
Write-Host "Session: $id"
Write-Host "Data: $($records.Count) station records; MA window returned $($smooth.values.Count) values; regression slope $([math]::Round($regression.slope,4)); holdout n=$($evaluation.sample_count); forecast n=$($forecast.predictions.Count)."
Write-Host "Response: pump/barrier/boat spent 100 credits; invalid pump rejected; storm advanced in $steps requested steps."
Write-Host "Final report: $($outcome.ending), score $($outcome.score)/1000, flooded cells $($outcome.total_flooded_cells), road cells $($outcome.flooded_road_count), hospital $($outcome.hospital_access), evacuated $($outcome.residents_evacuated)."
Write-Host 'Reset: PASS (100 credits, no deployed pumps).'
