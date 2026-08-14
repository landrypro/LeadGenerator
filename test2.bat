$currentProcessId = $currentListener.OwningProcess

Get-CimInstance Win32_Process `
    -Filter "ProcessId = $currentProcessId" |
    Select-Object ProcessId, ParentProcessId, Name, CommandLine

Stop-Process -Id $currentProcessId -Force
}

