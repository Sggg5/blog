[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$TaskName = 'FRANTA Daily Blog',
    [string]$RunAt = '08:10'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ExpectedTimeZone = 'Singapore Standard Time'
if ([TimeZoneInfo]::Local.Id -ne $ExpectedTimeZone) {
    throw "This task uses the Windows local clock. Set Windows time zone to '$ExpectedTimeZone' before installing; current time zone is '$([TimeZoneInfo]::Local.Id)'."
}

try {
    $time = [DateTime]::ParseExact($RunAt, 'HH:mm', [Globalization.CultureInfo]::InvariantCulture)
}
catch {
    throw 'RunAt must use 24-hour HH:mm format, for example 08:10.'
}

$runScript = Join-Path $PSScriptRoot 'run-daily-blog.ps1'
if (-not (Test-Path -LiteralPath $runScript -PathType Leaf)) {
    throw "Run script is missing: $runScript"
}

$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
if (-not (Test-Path -LiteralPath $powershell -PathType Leaf)) {
    throw "Windows PowerShell executable is missing: $powershell"
}
$arguments = "-NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$runScript`""
$action = New-ScheduledTaskAction -Execute $powershell -Argument $arguments -WorkingDirectory (Split-Path -Parent $PSScriptRoot)
$trigger = New-ScheduledTaskTrigger -Daily -At $time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 30) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$description = 'Runs the local Codex CLI with the daily blog prompt at 08:10 Singapore time. The task uses the cached ChatGPT login and commits only a validated new blog Markdown file.'

if ($PSCmdlet.ShouldProcess($TaskName, 'Register or replace scheduled task')) {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description $description -Force | Out-Null
    Write-Output "Installed '$TaskName'. It runs daily at $RunAt in Windows time zone '$ExpectedTimeZone'."
    Write-Output "The task runs only while $env:USERNAME is signed in, so the local ChatGPT/Codex login can be reused."
}
