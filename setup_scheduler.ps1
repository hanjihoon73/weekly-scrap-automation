# PowerShell script to create Windows Task Scheduler tasks
# 1. Test Run: Every Friday at 12:01 PM (Kevin only)
# 2. Main Run: Every Friday at 12:20 PM (All recipients)

$PythonPath = (Get-Command python).Source
$WorkingDirectory = $PSScriptRoot

$Tasks = @(
    @{
        Name        = "Naver Blog Scraper Test"
        Script      = "execution\scrape_naver_test_email.py"
        Time        = "12:01PM"
        Description = "Pre-release test email to Kevin (Every Friday at 12:01 PM)"
    },
    @{
        Name        = "Naver Blog Scraper Weekly"
        Script      = "execution\scrape_naver_email.py"
        Time        = "12:20PM"
        Description = "Weekly blog scrap report to all recipients (Every Friday at 12:20 PM)"
    }
)

foreach ($Task in $Tasks) {
    $TaskName = $Task.Name
    $ScriptPath = Join-Path $WorkingDirectory $Task.Script
    
    $Action = New-ScheduledTaskAction -Execute $PythonPath `
        -Argument "`"$ScriptPath`"" `
        -WorkingDirectory $WorkingDirectory

    $Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At $Task.Time

    $Settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RunOnlyIfNetworkAvailable

    try {
        $ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if ($ExistingTask) {
            Write-Host "Updating existing task: $TaskName"
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        }
        
        Register-ScheduledTask -TaskName $TaskName `
            -Action $Action `
            -Trigger $Trigger `
            -Settings $Settings `
            -Description $Task.Description `
            -User $env:USERNAME
        
        Write-Host "✓ Task '$TaskName' created successfully! (Scheduled for $($Task.Time))" -ForegroundColor Green
    }
    catch {
        Write-Host "✗ Error creating task '$TaskName': $_" -ForegroundColor Red
    }
}

Write-Host "`nAll tasks updated. Please ensure you have administrator privileges if needed." -ForegroundColor Cyan
