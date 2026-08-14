$currentListener = Get-NetTCPConnection `
    -LocalPort 8000 `
    -State Listen `
    -ErrorAction SilentlyContinue |
    Select-Object -First 1

if ($null -eq $currentListener) {
    Write-Host "Le port 8000 est libre."
}
else {
    Write-Host "Le port 8000 est occupé par le PID $($currentListener.OwningProcess)."
}

