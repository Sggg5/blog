[CmdletBinding()]
param(
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$PromptPath = Join-Path $PSScriptRoot 'daily-blog-prompt.md'
$LogDirectory = Join-Path $RepositoryRoot 'logs'
$Timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$LogPath = Join-Path $LogDirectory "daily-blog-$Timestamp.log"

New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null

function Write-RunLog {
    param([Parameter(Mandatory)][string]$Message)
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss K'), $Message
    $line | Tee-Object -FilePath $LogPath -Append
}

function Stop-Run {
    param([Parameter(Mandatory)][string]$Message)
    Write-RunLog "FAILED: $Message"
    exit 1
}

try {
    Write-RunLog "Started. DryRun=$DryRun"
    Set-Location -LiteralPath $RepositoryRoot

    if (-not (Test-Path -LiteralPath $PromptPath -PathType Leaf)) {
        Stop-Run "Prompt file is missing: $PromptPath"
    }

    $initialStatus = @(git -c core.quotepath=false status --porcelain)
    if ($initialStatus.Count -ne 0) {
        Stop-Run 'The repository already has uncommitted changes; no files were touched.'
    }

    git pull --ff-only
    if ($LASTEXITCODE -ne 0) {
        Stop-Run 'git pull --ff-only failed.'
    }

    Write-RunLog 'Starting Codex CLI.'
    Get-Content -LiteralPath $PromptPath -Raw |
        & codex exec --sandbox workspace-write -
    if ($LASTEXITCODE -ne 0) {
        Stop-Run "Codex CLI failed with exit code $LASTEXITCODE."
    }
    Write-RunLog 'Codex CLI completed successfully.'

    $trackedChanges = @((@(git diff --name-only) + @(git diff --cached --name-only)) | Where-Object { $_ })
    $status = @(git -c core.quotepath=false status --porcelain)
    if ($trackedChanges.Count -ne 0) {
        Stop-Run ('Codex changed tracked files: ' + ($trackedChanges -join ', '))
    }
    if ($status.Count -eq 0) {
        Write-RunLog 'No article was generated; exiting without commit.'
        exit 0
    }
    if ($status.Count -ne 1 -or $status[0] -notmatch '^\?\? src/content/blog/[^/\\]+\.md$') {
        Stop-Run ('Unexpected changes detected: ' + ($status -join ' | '))
    }

    $ArticlePath = $status[0].Substring(3)
    if (-not (Test-Path -LiteralPath (Join-Path $RepositoryRoot $ArticlePath) -PathType Leaf)) {
        Stop-Run "Expected new article does not exist: $ArticlePath"
    }
    Write-RunLog "Generated article: $ArticlePath"

    Write-RunLog 'Running Astro build.'
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Stop-Run "Astro build failed with exit code $LASTEXITCODE."
    }
    Write-RunLog 'Astro build succeeded.'

    if ($DryRun) {
        Write-RunLog 'Dry run succeeded; no commit or push was performed. Review the untracked article before deleting it or committing it manually.'
        git status --short
        exit 0
    }

    git add -- $ArticlePath
    if ($LASTEXITCODE -ne 0) {
        Stop-Run 'git add failed.'
    }
    $CommitDate = Get-Date -Format 'yyyy-MM-dd'
    git commit -m "blog: add daily post $CommitDate"
    if ($LASTEXITCODE -ne 0) {
        Stop-Run 'git commit failed.'
    }
    $CommitSha = (git rev-parse HEAD).Trim()
    Write-RunLog "Committed: $CommitSha"

    git push origin main
    if ($LASTEXITCODE -ne 0) {
        Stop-Run 'git push origin main failed.'
    }
    Write-RunLog 'Push succeeded.'
    Write-RunLog 'Finished successfully.'
}
catch {
    try {
        Write-RunLog "FAILED: $($_.Exception.Message)"
    }
    catch {
        Write-Error $_.Exception.Message
    }
    exit 1
}
