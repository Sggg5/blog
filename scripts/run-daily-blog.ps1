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

function Resolve-CodexExecutable {
    $fromPath = Get-Command codex -ErrorAction SilentlyContinue
    if ($fromPath) {
        return $fromPath.Source
    }

    $npmBin = Join-Path ([Environment]::GetFolderPath('ApplicationData')) 'npm\codex.cmd'
    if (Test-Path -LiteralPath $npmBin -PathType Leaf) {
        return $npmBin
    }

    throw 'Codex CLI was not found. Install it for the current Windows user or add its npm bin directory to PATH.'
}

try {
    Write-RunLog "Started. DryRun=$DryRun"
    Set-Location -LiteralPath $RepositoryRoot

    if (-not (Test-Path -LiteralPath $PromptPath -PathType Leaf)) {
        Stop-Run "Prompt file is missing: $PromptPath"
    }
    $CodexExecutable = Resolve-CodexExecutable
    Write-RunLog "Using Codex CLI: $CodexExecutable"

    $initialStatus = @(git -c core.quotepath=false status --porcelain)
    if ($initialStatus.Count -ne 0) {
        Stop-Run 'The repository already has uncommitted changes; no files were touched.'
    }

    $BlogDirectory = Join-Path $RepositoryRoot 'src\content\blog'
    $BlogPostsBefore = @(
        Get-ChildItem -LiteralPath $BlogDirectory -File -Filter '*.md' |
            ForEach-Object { $_.FullName }
    )

    git pull --ff-only
    if ($LASTEXITCODE -ne 0) {
        Stop-Run 'git pull --ff-only failed.'
    }

    Write-RunLog 'Starting Codex CLI.'
    Get-Content -LiteralPath $PromptPath -Raw |
        & $CodexExecutable exec --sandbox workspace-write -
    if ($LASTEXITCODE -ne 0) {
        Stop-Run "Codex CLI failed with exit code $LASTEXITCODE."
    }
    Write-RunLog 'Codex CLI completed successfully.'

    $trackedChanges = @((@(git diff --name-only) + @(git diff --cached --name-only)) | Where-Object { $_ })
    if ($trackedChanges.Count -ne 0) {
        Stop-Run ('Codex changed tracked files: ' + ($trackedChanges -join ', '))
    }
    # Do not parse `git status --porcelain` paths here: legacy Windows console
    # encoding can corrupt Chinese filenames. Count Git's untracked entries, then
    # identify the new Markdown file from the filesystem's native paths.
    $untrackedFiles = @(git ls-files --others --exclude-standard)
    $BlogPostsAfter = @(
        Get-ChildItem -LiteralPath $BlogDirectory -File -Filter '*.md' |
            ForEach-Object { $_.FullName }
    )
    $newBlogPosts = @($BlogPostsAfter | Where-Object { $_ -notin $BlogPostsBefore })
    if ($untrackedFiles.Count -eq 0 -and $newBlogPosts.Count -eq 0) {
        Write-RunLog 'No article was generated; exiting without commit.'
        exit 0
    }
    if ($untrackedFiles.Count -ne 1 -or $newBlogPosts.Count -ne 1) {
        Stop-Run ('Unexpected changes detected. Untracked count={0}; new blog Markdown count={1}.' -f $untrackedFiles.Count, $newBlogPosts.Count)
    }

    $ArticlePath = [IO.Path]::GetRelativePath($RepositoryRoot, $newBlogPosts[0])
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

    # The scheduler runs in its own worktree branch. Push that exact commit to
    # remote main instead of the local `main` ref from another checkout.
    git push origin HEAD:main
    if ($LASTEXITCODE -ne 0) {
        Write-RunLog 'Standard push failed; retrying with HTTP/1.1.'
        git -c http.version=HTTP/1.1 push origin HEAD:main
        if ($LASTEXITCODE -ne 0) {
            Stop-Run 'git push to origin/main failed.'
        }
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
